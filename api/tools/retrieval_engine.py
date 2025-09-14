"""Milvus-based retrieval system for RightLine.

This module implements hybrid retrieval using Milvus Cloud for vector search
and keyword matching for legal document chunks. Optimized for serverless
deployment with per-request connections.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set

import boto3
import httpx
import structlog
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

# Import reranker for quality improvement
from api.tools.reranker import get_reranker, RerankerConfig
from api.models import ChunkV3 as Chunk, ParentDocumentV3 as ParentDocument

# LangChain imports
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

logger = structlog.get_logger(__name__)

# Milvus configuration from environment
MILVUS_ENDPOINT = os.environ.get("MILVUS_ENDPOINT")
MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN")
MILVUS_COLLECTION_NAME = os.environ.get("MILVUS_COLLECTION_NAME", "legal_chunks_v2")  # Updated for v2.0

# R2 configuration from environment
R2_ENDPOINT = os.environ.get("R2_ENDPOINT") or os.environ.get("CLOUDFLARE_R2_S3_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")  
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")

# R2 performance configuration
R2_CONCURRENT_REQUESTS = int(os.environ.get("R2_CONCURRENT_REQUESTS", "20"))  # Max concurrent R2 requests
R2_REQUEST_TIMEOUT = int(os.environ.get("R2_REQUEST_TIMEOUT", "30"))  # R2 request timeout in seconds

# OpenAI configuration for embeddings (must match index dim=3072)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour

# Data paths (for alias map and preconditions)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
DOCS_JSONL_PATH = os.path.join(DATA_PROCESSED_DIR, "docs.jsonl")
CHUNKS_WITH_EMB_PATH = os.path.join(DATA_PROCESSED_DIR, "chunks_with_embeddings.jsonl")
CHUNKS_JSONL_PATH = os.path.join(DATA_PROCESSED_DIR, "chunks.jsonl")

# Feature flags
ENABLE_SPARSE = os.environ.get("ENABLE_SPARSE", "1") == "1"
ENABLE_RERANK = os.environ.get("ENABLE_RERANK", "0") == "1"
OPENAI_RERANK_MODEL = os.environ.get("OPENAI_RERANK_MODEL", "")


class RetrievalResult(BaseModel):
    """Result from document retrieval (V3) - Enhanced for LangChain compatibility."""
    
    chunk: "ChunkV3"
    parent_doc: Optional["ParentDocumentV3"] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Legacy compatibility fields
    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id
    
    @property
    def chunk_text(self) -> str:
        return self.chunk.chunk_text
    
    @property
    def doc_id(self) -> str:
        return self.chunk.doc_id
    
    @property
    def score(self) -> float:
        return self.confidence
    
    @property
    def source(self) -> str:
        return self.metadata.get("source", "hybrid")


class RetrievalConfig(BaseModel):
    """Configuration for retrieval parameters."""
    
    top_k: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=0.1, ge=0.0, le=1.0)
    enable_reranking: bool = Field(default=False)
    date_filter: Optional[str] = Field(default=None, description="ISO date for temporal filtering")
    # Multi-query expansion and fusion
    expansions_count: int = Field(default=4, ge=1, le=8)
    top_k_per_variant: int = Field(default=24, ge=1, le=100)
    rrf_k: int = Field(default=60, ge=1, le=200)
    max_per_doc: int = Field(default=3, ge=1, le=10)


class QueryProcessor:
    """Process and normalize user queries."""
    
    _alias_cache: Dict[str, Set[str]] = {}
    _alias_cache_loaded_at: Optional[float] = None

    STATUTE_SECTION_PATTERNS = [
        # e.g., "section 12C of the Labour Act"
        re.compile(r"\bsection\s+([0-9]+[A-Za-z]?)\b", re.IGNORECASE),
        re.compile(r"\bs\.?\s*([0-9]+[A-Za-z]?)\b", re.IGNORECASE),
        re.compile(r"\bsec\.?\s*([0-9]+[A-Za-z]?)\b", re.IGNORECASE),
    ]

    CHAPTER_PATTERN = re.compile(r"\bchapter\s*([0-9]{1,3}:[0-9]{2})\b", re.IGNORECASE)

    @staticmethod
    def normalize_query(text: str) -> str:
        """Normalize query text for consistent processing."""
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep legal terms
        text = re.sub(r'[^\w\s\-\.]', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def extract_date_context(text: str) -> Tuple[str, Optional[str]]:
        """Extract date context from query (e.g., 'as at 2023-01-01')."""
        # Pattern for "as at DATE" or "as of DATE"
        date_pattern = r'\b(?:as\s+(?:at|of)|on|before|after)\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
        match = re.search(date_pattern, text, re.IGNORECASE)
        
        if match:
            date_str = match.group(1).replace('/', '-')
            # Remove the date context from the query
            clean_text = re.sub(date_pattern, '', text, flags=re.IGNORECASE).strip()
            clean_text = re.sub(r'\s+', ' ', clean_text)  # Clean up extra spaces
            return clean_text, date_str
        
        return text, None
    
    @classmethod
    def _load_alias_map(cls) -> Dict[str, Set[str]]:
        """Load or rebuild a statute alias map from docs.jsonl.

        Keys are normalized canonical titles; values include short titles, common names,
        and chapter references (if present).
        """
        now = time.time()
        if cls._alias_cache and cls._alias_cache_loaded_at and (now - cls._alias_cache_loaded_at) < CACHE_TTL_SECONDS:
            return cls._alias_cache

        alias_map: Dict[str, Set[str]] = {}
        try:
            with open(DOCS_JSONL_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    title = (obj.get('title') or '').strip()
                    if not title:
                        continue
                    extra = obj.get('extra', {}) or {}
                    chapter = (extra.get('chapter') or '').strip()
                    # Build aliases
                    aliases: Set[str] = set()
                    canon = QueryProcessor.normalize_query(title)
                    aliases.add(canon)
                    # Remove bracketed and parenthesized segments
                    no_brackets = re.sub(r"\[.*?\]", " ", title)
                    no_paren = re.sub(r"\(.*?\)", " ", no_brackets)
                    # Remove trailing years
                    no_year = re.sub(r"\b(19|20)\d{2}\b", " ", no_paren)
                    base = QueryProcessor.normalize_query(no_year)
                    if base:
                        aliases.add(base)
                    # Preserve legal type tokens; ensure 'act' kept
                    m = re.search(r"\b(act|ordinance|statutory instrument|constitution)\b", base, re.IGNORECASE)
                    if m:
                        legal_type = m.group(1)
                        # Keep '[Name] legal_type' form if present
                        name_part = base.split(legal_type)[0].strip()
                        if name_part:
                            aliases.add(f"{name_part} {legal_type}".strip())
                    # Constitution special aliases
                    if 'constitution' in base:
                        aliases.add('constitution')
                        if 'zimbabwe' in base:
                            aliases.add('constitution of zimbabwe')
                    # Chapter alias
                    if chapter:
                        aliases.add(f"chapter {chapter.lower()}")
                    # Record under canonical key
                    alias_map[canon] = alias_map.get(canon, set()) | aliases
        except FileNotFoundError:
            logger.warning("docs.jsonl not found for alias map", path=DOCS_JSONL_PATH)
        except Exception as e:
            logger.warning("alias map load error", error=str(e))

        cls._alias_cache = alias_map
        cls._alias_cache_loaded_at = now
        return alias_map

    @classmethod
    def find_statute_candidates(cls, text: str) -> List[str]:
        """Return possible statute titles/aliases matched in the query."""
        norm = cls.normalize_query(text)
        alias_map = cls._load_alias_map()
        hits: Set[str] = set()
        # Exact alias containment scan (efficient set membership over small map)
        for canon, aliases in alias_map.items():
            for a in aliases:
                if a and a in norm:
                    hits.add(canon)
                    break
        return list(hits)[:5]

    @classmethod
    def extract_section_and_chapter(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract first section number (e.g., 12C) and chapter (e.g., 28:01) if present."""
        section = None
        for pat in cls.STATUTE_SECTION_PATTERNS:
            m = pat.search(text)
            if m:
                section = m.group(1).upper()
                break
        chap = None
        m2 = cls.CHAPTER_PATTERN.search(text)
        if m2:
            chap = m2.group(1)
        return section, chap

    @classmethod
    def detect_intent(cls, text: str) -> Dict[str, Any]:
        """Detect intent flags and extracted targets from a user query."""
        norm = cls.normalize_query(text)
        section, chapter = cls.extract_section_and_chapter(norm)
        statutes = cls.find_statute_candidates(norm)
        intent = {
            "section_lookup": bool(section and (statutes or chapter)),
            "statute_lookup": bool(statutes and not section),
            "general_question": not (statutes or section),
            "section": section,
            "chapter": chapter,
            "statutes": statutes,
        }
        return intent

    @classmethod
    def generate_reformulations(cls, text: str, intent: Dict[str, Any], max_variants: int = 4) -> List[str]:
        """Generate lightweight reformulations for multi-query retrieval.
        Returns a list beginning with the normalized original.
        """
        base = cls.normalize_query(text)
        variants: List[str] = [base]
        # Expand SI abbreviation
        if ' si ' in f" {base} ":
            variants.append(base.replace(' si ', ' statutory instrument '))
        # Section synonyms
        if intent.get('section'):
            v = re.sub(r"\bs\.?\s*(\d+[A-Za-z]?)", r"section \1", base)
            if v != base:
                variants.append(v)
        # Add statute canonical title if recognized
        statutes = intent.get('statutes') or []
        if statutes:
            for s in statutes[:2]:
                if s not in base:
                    variants.append(f"{base} in {s}")
        # Chapter addition
        if intent.get('chapter') and intent['chapter'] not in base:
            variants.append(f"{base} chapter {intent['chapter']}")
        # Dedup and cap
        out = []
        seen = set()
        for v in variants:
            if v and v not in seen:
                out.append(v)
                seen.add(v)
            if len(out) >= max_variants:
                break
        return out

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Neutral keyword extraction (kept for compatibility; not labor-specific)."""
        words = re.sub(r"[^\w\s]", " ", text.lower())
        words = re.sub(r"\s+", " ", words).strip().split()
        return [w for w in words if len(w) > 2][:20]


class MilvusClient:
    """Milvus client for vector operations."""
    
    def __init__(self):
        self.base_url = None
        self.headers = {}
        self.connected = False
    
    async def connect(self) -> bool:
        """Setup HTTP client for Milvus Cloud API."""
        if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
            logger.warning("Milvus credentials not configured")
            return False
        
        try:
            # Parse endpoint to get base URL for HTTP API
            if MILVUS_ENDPOINT.startswith("https://"):
                # Milvus Cloud format: https://in03-xxx.api.gcp-us-west1.zillizcloud.com:443
                self.base_url = MILVUS_ENDPOINT.replace(":443", "").replace(":19530", "")
                # Milvus Cloud uses /v2/vectordb for API endpoints
                if not self.base_url.endswith("/v2/vectordb"):
                    self.base_url += "/v2/vectordb"
            else:
                logger.error("Unsupported Milvus endpoint format", endpoint=MILVUS_ENDPOINT)
                return False
            
            self.headers = {
                "Authorization": f"Bearer {MILVUS_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Test connection with collections list endpoint
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}/collections/list", headers=self.headers)
                if response.status_code == 200:
                    self.connected = True
                    logger.info("Milvus HTTP API connected", endpoint=self.base_url, collection=MILVUS_COLLECTION_NAME)
                    return True
                else:
                    logger.error("Milvus HTTP API connection failed", status=response.status_code, response=response.text)
                    return False
            
        except Exception as e:
            logger.error("Failed to connect to Milvus HTTP API", error=str(e))
            self.connected = False
            return False
    
    async def disconnect(self):
        """No persistent connection to close in HTTP mode."""
        self.connected = False
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def search_similar(
        self, 
        query_vector: List[float], 
        top_k: int = 20,
        date_filter: Optional[str] = None,
        doc_type_filter: Optional[List[str]] = None,
    ) -> List[RetrievalResult]:
        """Search for similar chunks using HTTP API (single query)."""
        if not self.connected:
            logger.warning("Milvus HTTP API not connected")
            return []
        
        try:
            # Build search request payload for Milvus Cloud HTTP API v2
            search_payload = {
                "collectionName": MILVUS_COLLECTION_NAME,
                "data": [query_vector],
                "limit": top_k,
                "outputFields": [
                    "chunk_id",           # v3.0 primary key
                    "parent_doc_id",      # For small-to-big expansion
                    "tree_node_id",       # PageIndex tree node reference
                    "chunk_object_key",   # For R2 content fetching
                    "source_document_key", # For document serving
                    "doc_type",           # Document type filtering
                    "num_tokens",         # Token count metadata
                    "nature",             # Legal document nature
                    "year",               # Publication year
                    "chapter",            # Chapter reference
                    "date_context"        # Date context
                ]
            }
            
            # Add filter expression if specified
            if doc_type_filter:
                types = ",".join([f'"{t}"' for t in doc_type_filter])
                search_payload["filter"] = f"doc_type in [{types}]"
            
            # Perform HTTP search
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/entities/search",
                    headers=self.headers,
                    json=search_payload
                )
                
                if response.status_code != 200:
                    logger.error("Milvus search failed", status=response.status_code, response=response.text)
                    return []
                
                data = response.json()
                
                # Convert to RetrievalResult objects
                retrieval_results = []
                results = data.get("data", [])
                if results:
                    for hit in results:
                        # Parse metadata if it's a JSON string
                        metadata = hit.get("metadata", {})
                        if isinstance(metadata, str):
                            try:
                                metadata = json.loads(metadata)
                            except:
                                metadata = {}
                        
                        # For v3.0 schema with enhanced metadata
                        # Create ChunkV3 object for RetrievalResult
                        from api.models import ChunkV3
                        chunk = ChunkV3(
                            chunk_id=str(hit.get("chunk_id", "")),
                            chunk_text="",  # Will be populated from R2 or parent expansion
                            doc_id=hit.get("parent_doc_id", ""),
                            chunk_object_key=metadata.get("chunk_object_key", ""),
                            parent_doc_id=hit.get("parent_doc_id", ""),
                            doc_type=metadata.get("doc_type", "unknown"),
                            metadata=metadata,
                            entities={}
                        )
                        
                        retrieval_results.append(RetrievalResult(
                            chunk=chunk,
                            confidence=min(1.0, float(hit.get("distance", 0.5))),
                            metadata={
                                "source": "vector",
                                **metadata,
                                "tree_node_id": hit.get("tree_node_id", ""),
                                "chapter": hit.get("chapter", ""),
                                "nature": hit.get("nature", ""),
                                "year": hit.get("year", ""),
                                "chunk_object_key": hit.get("chunk_object_key", ""),  # Store R2 key
                                "parent_doc_id": hit.get("parent_doc_id", ""),        # 🔧 FIX: Explicitly store parent_doc_id
                                "source_document_key": hit.get("source_document_key", ""),
                                "doc_type": hit.get("doc_type", ""),
                                "num_tokens": hit.get("num_tokens", 0),
                                "nature": hit.get("nature", ""),
                                "year": hit.get("year", 0),
                                "chapter": hit.get("chapter", ""),
                                "date_context": hit.get("date_context", "")
                            }
                        ))
                
                logger.info(
                    "Vector search completed", 
                    results_count=len(retrieval_results),
                    top_score=retrieval_results[0].score if retrieval_results else 0
                )
                
                return retrieval_results
            
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            return []

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def search_similar_multi(
        self,
        query_vectors: List[List[float]],
        top_k: int = 20,
        doc_type_filter: Optional[List[str]] = None,
    ) -> List[List[RetrievalResult]]:
        """Search with multiple query vectors using HTTP API (sequential calls)."""
        if not self.connected:
            logger.warning("Milvus HTTP API not connected")
            return []
        
        # For HTTP API, we'll make sequential calls for each vector
        # This is less efficient than the SDK's batch mode, but keeps us under size limits
        results = []
        for query_vector in query_vectors:
            single_result = await self.search_similar(
                query_vector=query_vector,
                top_k=top_k,
                doc_type_filter=doc_type_filter
            )
            results.append(single_result)
        
        return results


class EmbeddingClient:
    """OpenAI client for generating embeddings."""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using OpenAI API."""
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured!")
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Batch embeddings for multiple inputs in one request."""
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
            return None

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={"input": texts, "model": OPENAI_EMBEDDING_MODEL}
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.error(f"OpenAI embedding error: {str(e)}")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_EMBEDDING_MODEL,
                        "input": text[:8000],  # Truncate to avoid token limits
                        "encoding_format": "float"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    embedding = data["data"][0]["embedding"]
                    
                    logger.info(
                        "Embedding generated",
                        model=OPENAI_EMBEDDING_MODEL,
                        input_length=len(text),
                        embedding_dim=len(embedding)
                    )
                    
                    return embedding
                else:
                    logger.error(
                        "OpenAI embedding failed",
                        status=response.status_code,
                        response=response.text[:200]
                    )
                    return None
                    
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None


class SparseProvider:
    """Abstract sparse search provider interface."""
    async def search(self, query: str, top_k: int = 50) -> List[RetrievalResult]:  # pragma: no cover
        raise NotImplementedError


class SimpleSparseProvider(SparseProvider):
    """Fallback sparse search scanning titles/section titles quickly.

    Loads a lightweight in-memory view of chunks.jsonl on first use.
    Scoring: title match (x3), section_title (x2), chunk_text prefix (x1),
    with small bonuses for exact token matches.
    """
    _loaded = False
    _rows: List[Dict[str, Any]] = []

    def _ensure_loaded(self):
        if self._loaded:
            return
        rows = []
        try:
            with open(CHUNKS_JSONL_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    rows.append({
                        "chunk_id": o.get("chunk_id"),
                        "doc_id": o.get("doc_id"),
                        "chunk_text": (o.get("chunk_text") or "")[:400].lower(),
                        "metadata": o.get("metadata") or {},
                    })
        except FileNotFoundError:
            logger.warning("chunks.jsonl not found for sparse provider", path=CHUNKS_JSONL_PATH)
        self._rows = rows
        self._loaded = True

    @staticmethod
    def _tokens(text: str) -> List[str]:
        t = re.sub(r"[^\w\s]", " ", text.lower())
        t = re.sub(r"\s+", " ", t).strip()
        return [w for w in t.split() if len(w) > 2]

    async def search(self, query: str, top_k: int = 50) -> List[RetrievalResult]:
        self._ensure_loaded()
        if not self._rows:
            return []
        qtokens = set(self._tokens(query))
        if not qtokens:
            return []
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for row in self._rows:
            md = row.get("metadata") or {}
            title = (md.get("title") or "").lower()
            sect = (md.get("section_title") or "").lower()
            text = row.get("chunk_text") or ""
            score = 0.0
            for t in qtokens:
                if t in title:
                    score += 3.0
                if t in sect:
                    score += 2.0
                if t in text:
                    score += 1.0
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[RetrievalResult] = []
        for s, row in scored[:top_k]:
            # Create ChunkV3 object for RetrievalResult
            from api.models import ChunkV3
            chunk = ChunkV3(
                chunk_id=str(row.get("chunk_id")),
                chunk_text=row.get("chunk_text") or "",
                doc_id=str(row.get("doc_id")),
                chunk_object_key=row.get("chunk_object_key", ""),
                parent_doc_id=str(row.get("doc_id")),
                doc_type=row.get("doc_type", "unknown"),
                metadata=row.get("metadata") or {},
                entities={}
            )
            
            out.append(RetrievalResult(
                chunk=chunk,
                confidence=float(min(1.0, s / 10.0)),
                metadata={
                    "source": "sparse_fallback",
                    **row.get("metadata", {})
                }
            ))
        return out


class OpenAIReranker:
    """Optional reranker using OpenAI (lightweight prompt-based scoring)."""
    model: str

    def __init__(self, model: str):
        self.model = model

    async def rerank(self, query: str, candidates: List[RetrievalResult], max_items: int = 40) -> List[RetrievalResult]:
        # For efficiency and stability, apply deterministic boosts locally; skip remote call by default.
        # Placeholder for real OpenAI rerank integration.
        return candidates
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_EMBEDDING_MODEL,
                        "input": [t[:8000] for t in texts],
                        "encoding_format": "float",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    embs = [row["embedding"] for row in data.get("data", [])]
                    return embs
                logger.error("OpenAI batch embedding failed", status=response.status_code, response=response.text[:200])
                return None
        except Exception as e:
            logger.error("Batch embedding generation failed", error=str(e))
            return None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_EMBEDDING_MODEL,
                        "input": text[:8000],  # Truncate to avoid token limits
                        "encoding_format": "float"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    embedding = data["data"][0]["embedding"]
                    
                    logger.info(
                        "Embedding generated",
                        model=OPENAI_EMBEDDING_MODEL,
                        input_length=len(text),
                        embedding_dim=len(embedding)
                    )
                    
                    return embedding
                else:
                    logger.error(
                        "OpenAI embedding failed",
                        status=response.status_code,
                        response=response.text[:200]
                    )
                    return None
                    
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None


class MilvusRetriever(BaseRetriever):
    """LangChain BaseRetriever wrapper for Milvus vector search."""
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, milvus_client, embedding_client, query_processor, top_k=20):
        super().__init__()
        object.__setattr__(self, 'milvus_client', milvus_client)
        object.__setattr__(self, 'embedding_client', embedding_client)
        object.__setattr__(self, 'query_processor', query_processor)
        object.__setattr__(self, 'top_k', top_k)
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Synchronous wrapper - not used in async context."""
        raise NotImplementedError("Use aget_relevant_documents for async retrieval")
    
    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Async retrieval from Milvus with LangSmith tracing."""
        
        # Handle both string and dict input from LCEL chain
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        # Connect to Milvus if needed
        if not self.milvus_client.connected:
            await self.milvus_client.connect()
        
        # Process query and generate embeddings
        normalized_query = self.query_processor.normalize_query(query)
        clean_query, _ = self.query_processor.extract_date_context(normalized_query)
        intent = self.query_processor.detect_intent(clean_query)
        
        # Generate query variants for better recall
        variants = self.query_processor.generate_reformulations(
            clean_query, intent, max_variants=4
        )
        
        # Get embeddings for all variants
        embeddings = await self.embedding_client.get_embeddings(variants)
        if not embeddings:
            logger.warning("No embeddings generated for Milvus retrieval")
            return []
        
        # Perform multi-query vector search
        doc_types = ["act", "ordinance", "si", "constitution"]
        dense_hits_by_variant = await self.milvus_client.search_similar_multi(
            query_vectors=embeddings,
            top_k=self.top_k,
            doc_type_filter=doc_types,
        )
        
        # Convert to LangChain Documents
        documents = []
        for variant_idx, hits in enumerate(dense_hits_by_variant):
            for hit in hits:
                # Create Document with metadata
                doc = Document(
                    page_content=str(hit.chunk_text or ""),
                    metadata={
                        **hit.metadata,
                        "chunk_id": hit.chunk_id,
                        "doc_id": hit.doc_id,
                        "score": hit.score,
                        "source": "milvus",
                        "variant_idx": variant_idx,
                        "retrieval_result": hit  # Store original for later use
                    }
                )
                documents.append(doc)
        
        logger.info(
            "Milvus retrieval completed",
            query_variants=len(variants),
            total_documents=len(documents),
            top_score=documents[0].metadata["score"] if documents else 0
        )
        
        return documents


class BM25Retriever(BaseRetriever):
    """LangChain BaseRetriever wrapper for BM25 sparse search."""
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, bm25_provider, top_k=50):
        super().__init__()
        object.__setattr__(self, 'bm25_provider', bm25_provider)
        object.__setattr__(self, 'top_k', top_k)
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Synchronous wrapper - not used in async context."""
        raise NotImplementedError("Use aget_relevant_documents for async retrieval")
    
    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """Async retrieval from BM25 with LangSmith tracing."""
        
        # Handle both string and dict input from LCEL chain
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        # Perform BM25 search
        bm25_results = await self.bm25_provider.search(query, top_k=self.top_k)
        
        # Convert to LangChain Documents
        documents = []
        for result in bm25_results:
            doc = Document(
                page_content=str(result.chunk_text or ""),
                metadata={
                    **result.metadata,
                    "chunk_id": result.chunk_id,
                    "doc_id": result.doc_id,
                    "score": result.score,
                    "source": "bm25",
                    "retrieval_result": result  # Store original for later use
                }
            )
            documents.append(doc)
        
        logger.info(
            "BM25 retrieval completed",
            total_documents=len(documents),
            top_score=documents[0].metadata["score"] if documents else 0
        )
        
        return documents


class RetrievalEngine:
    """
    LangChain-based retrieval engine implementing Task 4.3.
    
    This class uses LangChain components for composable, traceable retrieval:
    - EnsembleRetriever for parallel dense + sparse search with RRF
    - ContextualCompressionRetriever with CrossEncoderReranker
    - RunnableLambda for Small-to-Big parent document expansion
    - Full LangSmith tracing and observability
    """
    
    def __init__(self):
        # Initialize core components
        self.milvus_client = MilvusClient()
        self.embedding_client = EmbeddingClient()
        self.query_processor = QueryProcessor()
        self._r2_client = None  # Initialize R2 client attribute
        self._r2_semaphore = asyncio.Semaphore(5)  # Limit concurrent R2 requests
        
        # Initialize BM25 provider
        from api.bm25_provider import ProductionBM25Provider
        self.bm25_provider = ProductionBM25Provider()
        
        # Initialize LangChain retrievers
        self.milvus_retriever = MilvusRetriever(
            milvus_client=self.milvus_client,
            embedding_client=self.embedding_client,
            query_processor=self.query_processor,
            top_k=20
        )
        
        self.bm25_retriever = BM25Retriever(
            bm25_provider=self.bm25_provider,
            top_k=50
        )
        
        # Create EnsembleRetriever for parallel execution with RRF
        from langchain.retrievers import EnsembleRetriever
        self._ensemble_retriever = EnsembleRetriever(
            retrievers=[self.milvus_retriever, self.bm25_retriever],
            weights=[0.6, 0.4],  # Favor vector search slightly
            search_type="rrf",   # Use Reciprocal Rank Fusion
            c=60  # RRF constant (same as original config.rrf_k)
        )
        
        # Create CrossEncoder reranker
        from langchain_community.cross_encoders import HuggingFaceCrossEncoder
        from langchain.retrievers.document_compressors import CrossEncoderReranker
        cross_encoder = HuggingFaceCrossEncoder(
            model_name="cross-encoder/ms-marco-TinyBERT-L-2-v2"
        )
        self.reranker = CrossEncoderReranker(
            model=cross_encoder
        )
        
        # Create ContextualCompressionRetriever with reranking
        from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
        self._compression_retriever = ContextualCompressionRetriever(
            base_retriever=self._ensemble_retriever,
            base_compressor=self.reranker
        )
        
        # Create parent document fetcher as RunnableLambda
        from langchain_core.runnables import RunnableLambda, RunnablePassthrough
        self._parent_fetcher = RunnableLambda(self._fetch_parent_documents)
        
        # Build the complete LCEL chain (temporarily disable reranker)
        self.retrieval_chain = (
            RunnablePassthrough.assign(
                # Step 1: Get documents (skip reranker for now)
                documents=self._ensemble_retriever
            )
            | RunnablePassthrough.assign(
                # Step 2: Expand to parent documents (Small-to-Big)
                results=self._parent_fetcher
            )
            | RunnableLambda(self._format_final_results)
        )
    
    def _get_r2_client(self):
        """Get or create R2 client for content fetching."""
        if self._r2_client is None:
            if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
                logger.warning("R2 configuration incomplete, content fetching will be disabled")
                return None
            
            self._r2_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY,
                aws_secret_access_key=R2_SECRET_KEY,
                region_name='auto'  # R2 uses 'auto' region
            )
        return self._r2_client
    
    async def _fetch_chunk_content_from_r2(self, chunk_object_key: str) -> Optional[Chunk]:
        """Fetch single chunk content from R2.
        
        Args:
            chunk_object_key: R2 object key for the chunk (e.g., 'corpus/chunks/act/chunk_001.json')
            
        Returns:
            Dict containing chunk data including chunk_text, or None if fetch fails
        """
        r2_client = self._get_r2_client()
        if not r2_client:
            return None
            
        async with self._r2_semaphore:  # Limit concurrent requests
            try:
                # Use asyncio to make the sync boto3 call non-blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: r2_client.get_object(
                        Bucket=R2_BUCKET_NAME,
                        Key=chunk_object_key
                    )
                )
                
                content = response['Body'].read().decode('utf-8')
                chunk_dict = json.loads(content)
                return Chunk(**chunk_dict)
                
            except Exception as e:
                logger.warning(
                    "Failed to fetch chunk content from R2",
                    chunk_key=chunk_object_key,
                    error=str(e)
                )
                return None
    
    async def _fetch_chunk_contents_batch(self, chunk_object_keys: List[str]) -> List[Optional[Chunk]]:
        """Fetch multiple chunk contents from R2 in parallel.
        
        Args:
            chunk_object_keys: List of R2 object keys for chunks
            
        Returns:
            List of chunk data dicts (same order as input), None for failed fetches
        """
        if not chunk_object_keys:
            return []
        
        start_time = time.time()
        logger.info(
            "Starting R2 batch fetch",
            chunk_count=len(chunk_object_keys),
            concurrent_limit=R2_CONCURRENT_REQUESTS
        )
        
        # Create tasks for parallel fetching
        tasks = [
            self._fetch_chunk_content_from_r2(key) 
            for key in chunk_object_keys
        ]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "R2 fetch task failed",
                    chunk_key=chunk_object_keys[i],
                    error=str(result)
                )
                processed_results.append(None)
            else:
                if result is not None:
                    success_count += 1
                processed_results.append(result)
        
        fetch_time = time.time() - start_time
        logger.info(
            "R2 batch fetch completed",
            total_chunks=len(chunk_object_keys),
            successful=success_count,
            failed=len(chunk_object_keys) - success_count,
            duration_ms=round(fetch_time * 1000, 2)
        )
        
        return processed_results

    async def _fetch_parent_document_from_r2(self, parent_doc_id: str, doc_type: str = "") -> Optional[ParentDocument]:
        """Fetch full parent document from R2 for small-to-big retrieval."""
        r2_client = self._get_r2_client()
        if not r2_client:
            return None
        # Construct parent document object key.
        # Note: In V3, parent_doc_id is the canonical doc_id, so we can look it up directly.
        # The doc_type helps narrow the path for efficiency but is not strictly required if IDs are unique.
        possible_prefixes = [f"corpus/docs/{doc_type}/", "corpus/docs/"] if doc_type else ["corpus/docs/"]
        
        for prefix in possible_prefixes:
            # Attempt to find the document in primary and fallback locations
            # This is robust to cases where doc_type might be missing from metadata
            # but the doc_id is globally unique.
            for dt in ["act", "si", "judgment", "constitution", "ordinance", ""]:
                key = f"{prefix}{dt}/{parent_doc_id}.json" if dt else f"{prefix}{parent_doc_id}.json"
                result = await self._fetch_parent_document_from_r2_key(key)
                if result:
                    return result
        
        logger.warning("Parent document not found in any known R2 path", doc_id=parent_doc_id)
        return None
    
    async def _fetch_parent_document_from_r2_key(self, parent_object_key: str) -> Optional[ParentDocument]:
        """Fetch parent document by exact R2 key."""
        async with self._r2_semaphore:
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._get_r2_client().get_object(
                        Bucket=R2_BUCKET_NAME,
                        Key=parent_object_key
                    )
                )
                
                content = response['Body'].read().decode('utf-8')
                parent_dict = json.loads(content)
                return ParentDocument(**parent_dict)
                
            except Exception as e:
                logger.debug(
                    "Parent document not found at key",
                    key=parent_object_key,
                    error=str(e)
                )
                return None
    
    async def _fetch_parent_documents_batch(self, parent_doc_requests: List[tuple]) -> List[Optional[ParentDocument]]:
        """Fetch multiple parent documents in parallel.
        
        Args:
            parent_doc_requests: List of (parent_doc_id, doc_type) tuples
            
        Returns:
            List of parent document data (same order as input), None for failed fetches
        """
        if not parent_doc_requests:
            return []
        
        start_time = time.time()
        logger.info(
            "Starting parent document batch fetch",
            parent_count=len(parent_doc_requests)
        )
        
        # Create tasks for parallel fetching with ID mapping
        tasks = [self._fetch_parent_document_from_r2(parent_id, doc_type) for parent_id, doc_type in parent_doc_requests]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Parent document fetch failed",
                    parent_doc_id=parent_doc_requests[i][0],
                    error=str(result)
                )
                processed_results.append(None)
            else:
                if result is not None:
                    success_count += 1
                processed_results.append(result)
        
        fetch_time = time.time() - start_time
        logger.info(
            "Parent document batch fetch completed",
            total_requests=len(parent_doc_requests),
            successful=success_count,
            failed=len(parent_doc_requests) - success_count,
            duration_ms=round(fetch_time * 1000, 2)
        )
        
        return processed_results
    
    async def _expand_to_parent_documents(self, chunk_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Expand small chunks to full parent documents for synthesis (small-to-big).
        
        This is the CORE of Task 3.1: after identifying top-k small chunks,
        fetch their corresponding parent documents for rich context.
        
        Args:
            chunk_results: Small chunk results from hybrid search
            
        Returns:
            Results with full parent document content for synthesis
        """
        if not chunk_results:
            return []
        
        logger.info(
            "Expanding chunks to parent documents (small-to-big)",
            chunk_count=len(chunk_results)
        )
        
        # Extract unique parent document requests
        parent_requests = []
        chunk_to_parent_map = {}  # Map chunk index to parent doc index
        
        for i, result in enumerate(chunk_results):
            # FIX: Use doc_id as the parent document identifier (it's the same thing!)
            parent_doc_id = result.doc_id  # This is the original document ID
            doc_type = result.metadata.get("doc_type", "")
            
            # Check if we already requested this parent doc
            parent_key = (parent_doc_id, doc_type)
            existing_idx = None
            for j, existing in enumerate(parent_requests):
                if existing == parent_key:
                    existing_idx = j
                    break
            
            if existing_idx is not None:
                chunk_to_parent_map[i] = existing_idx
            else:
                parent_requests.append(parent_key)
                chunk_to_parent_map[i] = len(parent_requests) - 1
        
        # Fetch parent documents in parallel
        parent_docs = await self._fetch_parent_documents_batch(parent_requests)
        
        # Create expanded results with parent document content
        expanded_results = []
        for i, chunk_result in enumerate(chunk_results):
            parent_idx = chunk_to_parent_map[i]
            parent_doc = parent_docs[parent_idx] if parent_idx < len(parent_docs) else None
            
            if parent_doc:
                # Replace chunk with full parent document for synthesis
                # Get parent document content (PageIndex markdown)
                parent_content = parent_doc.pageindex_markdown if parent_doc else ""
                
                # Create expanded ChunkV3 with parent content
                expanded_chunk = ChunkV3(
                    chunk_id=chunk_result.chunk_id,
                    chunk_text=parent_content,  # Use PageIndex markdown content
                    doc_id=chunk_result.doc_id,
                    chunk_object_key=chunk_result.chunk.chunk_object_key,
                    parent_doc_id=chunk_result.chunk.parent_doc_id,
                    doc_type=chunk_result.chunk.doc_type,
                    metadata=chunk_result.chunk.metadata,
                    entities=chunk_result.chunk.entities
                )
                
                expanded_result = RetrievalResult(
                    chunk=expanded_chunk,
                    parent_doc=parent_doc,
                    confidence=chunk_result.confidence,
                    metadata={
                        **chunk_result.metadata,
                        "expanded_to_parent": True,
                        "parent_doc_length": len(parent_content) if parent_doc else 0,
                        "original_chunk_text": chunk_result.chunk_text,  # Keep original for citation
                        "title": parent_doc.title if parent_doc else "",
                        "chapter": parent_doc.chapter if parent_doc else "",
                        "canonical_citation": parent_doc.canonical_citation if parent_doc else "",
                    }
                )
                expanded_results.append(expanded_result)
            else:
                # Keep original chunk if parent not found
                logger.warning(
                    "Parent document not found, keeping original chunk",
                    chunk_id=chunk_result.chunk_id,
                    doc_id=chunk_result.doc_id
                )
                expanded_results.append(chunk_result)
        
        success_count = sum(1 for r in expanded_results if r.metadata.get("expanded_to_parent"))
        logger.info(
            "Small-to-big expansion completed",
            total_chunks=len(chunk_results),
            expanded_to_parents=success_count,
            kept_as_chunks=len(chunk_results) - success_count
        )
        
        return expanded_results

    def _check_preconditions(self) -> None:
        """Validate Milvus and data availability once per engine instance."""
        if self._preconditions_checked:
            return
        problems = []
        if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
            problems.append("MILVUS env not configured")
        if not os.path.exists(DOCS_JSONL_PATH):
            problems.append(f"missing {DOCS_JSONL_PATH}")
        if not os.path.exists(CHUNKS_WITH_EMB_PATH):
            problems.append(f"missing {CHUNKS_WITH_EMB_PATH}")
        if problems:
            logger.warning("retrieval preconditions", problems=problems)
        else:
            logger.info("retrieval preconditions ok")
        # Always mark to avoid repeated checks per request
        self._preconditions_checked = True

    def _shortcut_section_lookup(self, intent: Dict[str, Any]) -> List[RetrievalResult]:
        """Direct lookup path when query names a statute and a specific section.
        Scans chunks.jsonl for matching doc aliases and section number, returns pseudo-results.
        """
        section = (intent.get("section") or "").upper()
        statutes = intent.get("statutes") or []
        if not section or not statutes:
            return []
        aliases = set()
        alias_map = self.query_processor._load_alias_map()
        for canon in statutes:
            # Merge all aliases for candidate canon keys
            aliases |= alias_map.get(canon, set())
            aliases.add(canon)
        matches: List[RetrievalResult] = []
        try:
            with open(CHUNKS_JSONL_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    md = o.get("metadata") or {}
                    title = (md.get("title") or "").lower()
                    # Determine section number: prefer explicit number; else parse from md['section'] prefix like "12C. ..."
                    sect_num = (md.get("section_number") or "").strip().upper()
                    if not sect_num:
                        sec_field = (md.get("section") or md.get("section_title") or "").strip()
                        m = re.match(r"^(\d+[A-Za-z]?)\.", sec_field)
                        if not m:
                            m = re.search(r"\b(\d+[A-Za-z]?)\b", sec_field)
                        if m:
                            sect_num = m.group(1).upper()
                    if sect_num != section:
                        continue
                    norm_title = self.query_processor.normalize_query(title)
                    if not any(a in norm_title for a in aliases):
                        continue
                    # Create ChunkV3 object for RetrievalResult
                    from api.models import ChunkV3
                    chunk = ChunkV3(
                        chunk_id=str(o.get("chunk_id")),
                        chunk_text=o.get("chunk_text") or "",
                        doc_id=str(o.get("doc_id")),
                        chunk_object_key=o.get("chunk_object_key", ""),
                        parent_doc_id=str(o.get("doc_id")),
                        doc_type=o.get("doc_type", "unknown"),
                        metadata=md,
                        entities={}
                    )
                    
                    matches.append(RetrievalResult(
                        chunk=chunk,
                        confidence=0.99,
                        metadata={
                            "source": "shortcut_section",
                            **md
                        }
                    ))
                    if len(matches) >= 6:
                        break
        except FileNotFoundError:
            return []
        return matches

    def _shortcut_statute_toc(self, intent: Dict[str, Any]) -> List[RetrievalResult]:
        """If statute-only: return representative sections from the statute to guide narrowing."""
        statutes = intent.get("statutes") or []
        if not statutes:
            return []
        aliases = set()
        alias_map = self.query_processor._load_alias_map()
        for canon in statutes:
            aliases |= alias_map.get(canon, set())
            aliases.add(canon)
        out: List[RetrievalResult] = []
        seen_sections = set()
        try:
            with open(CHUNKS_JSONL_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    md = o.get("metadata") or {}
                    title = (md.get("title") or "").lower()
                    norm_title = self.query_processor.normalize_query(title)
                    if not any(a in norm_title for a in aliases):
                        continue
                    # Prefer sections; if missing, take first chunks per doc as overview
                    sect_title = md.get("section_title") or md.get("section") or ""
                    sect_num = (md.get("section_number") or "").upper()
                    if not sect_num and sect_title:
                        m = re.match(r"^(\d+[A-Za-z]?)\.", sect_title)
                        if m:
                            sect_num = m.group(1).upper()
                    key = (o.get("doc_id"), sect_num or sect_title or md.get("chunk_index", 0))
                    if key in seen_sections:
                        continue
                    seen_sections.add(key)
                    # Create ChunkV3 object for RetrievalResult
                    from api.models import ChunkV3
                    chunk = ChunkV3(
                        chunk_id=str(o.get("chunk_id")),
                        chunk_text=o.get("chunk_text") or "",
                        doc_id=str(o.get("doc_id")),
                        chunk_object_key=o.get("chunk_object_key", ""),
                        parent_doc_id=str(o.get("doc_id")),
                        doc_type=o.get("doc_type", "unknown"),
                        metadata=md,
                        entities={}
                    )
                    
                    out.append(RetrievalResult(
                        chunk=chunk,
                        confidence=0.7,
                        metadata={
                            "source": "shortcut_toc",
                            **md
                        }
                    ))
                    if len(out) >= 8:
                        break
        except FileNotFoundError:
            return []
        return out
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.milvus_client.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.milvus_client.disconnect()
    
    async def _fetch_parent_documents(self, input_data: Dict[str, Any]) -> List[RetrievalResult]:
        """
        RunnableLambda function for Small-to-Big parent document fetching.
        
        This implements the core Small-to-Big retrieval pattern where we:
        1. Use small chunks for precise retrieval
        2. Fetch their parent documents for rich context
        """
        documents = input_data.get("documents", [])
        if not documents:
            return []
        
        logger.info("Starting Small-to-Big parent document expansion", 
                   chunk_count=len(documents))
        
        # Extract unique parent document requests
        parent_requests = []
        doc_to_parent_map = {}
        
        for i, doc in enumerate(documents):
            retrieval_result = doc.metadata.get("retrieval_result")
            if not retrieval_result:
                continue
                
            parent_doc_id = retrieval_result.doc_id
            doc_type = retrieval_result.metadata.get("doc_type", "")
            
            parent_key = (parent_doc_id, doc_type)
            if parent_key not in doc_to_parent_map:
                parent_requests.append(parent_key)
                doc_to_parent_map[parent_key] = []
            doc_to_parent_map[parent_key].append(i)
        
        # Fetch parent documents in parallel (reuse existing logic)
        parent_docs = await self._fetch_parent_documents_batch(parent_requests)
        
        # Create RetrievalResult objects with parent documents
        results = []
        for i, doc in enumerate(documents):
            retrieval_result = doc.metadata.get("retrieval_result")
            if not retrieval_result:
                continue
            
            # Find corresponding parent document
            parent_doc_id = retrieval_result.doc_id
            doc_type = retrieval_result.metadata.get("doc_type", "")
            parent_key = (parent_doc_id, doc_type)
            
            parent_doc = None
            if parent_key in doc_to_parent_map:
                parent_idx = parent_requests.index(parent_key)
                if parent_idx < len(parent_docs):
                    parent_doc = parent_docs[parent_idx]
            
            # Create enhanced chunk from retrieval result
            chunk = Chunk(
                doc_id=retrieval_result.doc_id,
                chunk_id=retrieval_result.chunk_id,
                chunk_text=retrieval_result.chunk_text or doc.page_content,
                tree_node_id=retrieval_result.metadata.get("tree_node_id", "0000")
            )
            
            # Calculate confidence based on score and source
            confidence = min(1.0, max(0.7, retrieval_result.score))
            
            result = RetrievalResult(
                chunk=chunk,
                parent_doc=parent_doc,
                confidence=confidence,
                metadata={
                    **retrieval_result.metadata,
                    "expanded_to_parent": parent_doc is not None,
                    "source": retrieval_result.source,
                    "langchain_processed": True
                }
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r.parent_doc is not None)
        logger.info(
            "Small-to-Big expansion completed",
            total_chunks=len(documents),
            parent_docs_fetched=success_count,
            expansion_rate=round(success_count / len(documents), 2) if documents else 0
        )
        
        return results
    
    async def _format_final_results(self, input_data: Dict[str, Any]) -> List[RetrievalResult]:
        """Format the final results for return."""
        return input_data.get("results", [])
    
    async def retrieve(
        self,
        query: str,
        config: Optional[RetrievalConfig] = None
    ) -> List[RetrievalResult]:
        """
        Main retrieval method using the LangChain LCEL chain.
        
        This method orchestrates the entire retrieval pipeline:
        1. Parallel dense + sparse retrieval (EnsembleRetriever)
        2. Reranking (ContextualCompressionRetriever)
        3. Parent document expansion (RunnableLambda)
        """
        if config is None:
            config = RetrievalConfig()
        
        start_time = time.time()
        
        logger.info(
            "Starting LangChain retrieval pipeline",
            query=query[:100],
            top_k=config.top_k
        )
        
        try:
            # Execute the complete LCEL chain
            results = await self.retrieval_chain.ainvoke({"query": query})
            
            # Apply top_k limit
            if len(results) > config.top_k:
                results = results[:config.top_k]
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "LangChain retrieval pipeline completed",
                results_count=len(results),
                elapsed_ms=round(elapsed_ms, 2),
                top_confidence=results[0].confidence if results else 0,
                parent_expansion_rate=sum(1 for r in results if r.parent_doc) / len(results) if results else 0
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "LangChain retrieval pipeline failed",
                error=str(e),
                query=query[:50]
            )
            raise
    
    def calculate_confidence(self, results: List[RetrievalResult]) -> float:
        """Calculate overall confidence score for the retrieval results."""
        if not results:
            return 0.0
        
        # Use confidence scores from individual results
        confidences = [r.confidence for r in results]
        
        # Weighted average: top result gets more weight
        if len(confidences) == 1:
            return confidences[0]
        
        weights = [0.5, 0.3, 0.2] + [0.1] * (len(confidences) - 3)
        weights = weights[:len(confidences)]
        
        weighted_confidence = sum(c * w for c, w in zip(confidences, weights)) / sum(weights)
        return round(weighted_confidence, 3)


# Convenience functions for direct use

async def search_legal_documents(
    query: str,
    top_k: int = 20,
    date_filter: Optional[str] = None,
    min_score: float = 0.1
) -> Tuple[List[RetrievalResult], float]:
    """
    LangChain-based legal document search with compatibility wrapper.
    
    This function provides the same API as the original while using
    the new LangChain-based implementation underneath.
    """
    config = RetrievalConfig(
        top_k=top_k,
        date_filter=date_filter,
        min_score=min_score
    )
    
    engine = RetrievalEngine()
    results = await engine.retrieve(query, config)
    confidence = engine.calculate_confidence(results)
    
    return results, confidence


# Debug/utility endpoints helpers
async def direct_section_lookup(title_or_alias: str, section: str, top_k: int = 6) -> List[RetrievalResult]:
    """Convenience wrapper for fast-path direct section lookup."""
    engine = RetrievalEngine()
    # Build intent-like payload
    intent = {
        "section": section.upper().strip(),
        "statutes": [QueryProcessor.normalize_query(title_or_alias)],
    }
    return engine._shortcut_section_lookup(intent)[:top_k]


# Rebuild Pydantic models to resolve forward references
try:
    from api.models import ChunkV3, ParentDocumentV3
    RetrievalResult.model_rebuild()
    logger.info("RetrievalResult model rebuilt successfully")
except Exception as e:
    logger.warning("RetrievalResult model rebuild failed", error=str(e))

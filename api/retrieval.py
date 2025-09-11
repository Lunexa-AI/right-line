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


@dataclass
class RetrievalResult:
    """Result from document retrieval."""
    
    chunk_id: str
    chunk_text: str
    doc_id: str
    metadata: Dict[str, Any]
    score: float
    source: str  # "vector", "keyword", "hybrid"


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
                    "chunk_id",           # v2.0 primary key
                    "parent_doc_id",      # For small-to-big expansion
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
                        
                        # For v2.0 schema, we'll fetch chunk_text from R2 later
                        retrieval_results.append(RetrievalResult(
                            chunk_id=str(hit.get("chunk_id", "")),  # v2.0 uses chunk_id field
                            chunk_text="",  # Will be populated from R2
                            doc_id=hit.get("parent_doc_id", ""),   # v2.0 uses parent_doc_id
                            metadata={
                                **metadata,
                                "chunk_object_key": hit.get("chunk_object_key", ""),  # Store R2 key
                                "parent_doc_id": hit.get("parent_doc_id", ""),        # 🔧 FIX: Explicitly store parent_doc_id
                                "source_document_key": hit.get("source_document_key", ""),
                                "doc_type": hit.get("doc_type", ""),
                                "num_tokens": hit.get("num_tokens", 0),
                                "nature": hit.get("nature", ""),
                                "year": hit.get("year", 0),
                                "chapter": hit.get("chapter", ""),
                                "date_context": hit.get("date_context", "")
                            },
                            score=float(hit.get("distance", 0.0)),
                            source="vector"
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
            out.append(RetrievalResult(
                chunk_id=str(row.get("chunk_id")),
                chunk_text=row.get("chunk_text") or "",
                doc_id=str(row.get("doc_id")),
                metadata=row.get("metadata") or {},
                score=float(min(1.0, s / 10.0)),
                source="sparse",
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


class RetrievalEngine:
    """Main retrieval engine combining vector and keyword search with R2 content fetching."""
    
    def __init__(self):
        self.milvus_client = MilvusClient()
        self.embedding_client = EmbeddingClient()
        self.query_processor = QueryProcessor()
        self._preconditions_checked = False
        self._r2_client = None
        self._r2_semaphore = asyncio.Semaphore(R2_CONCURRENT_REQUESTS)
    
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
    
    async def _fetch_chunk_content_from_r2(self, chunk_object_key: str) -> Optional[Dict[str, Any]]:
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
                chunk_data = json.loads(content)
                return chunk_data
                
            except Exception as e:
                logger.warning(
                    "Failed to fetch chunk content from R2",
                    chunk_key=chunk_object_key,
                    error=str(e)
                )
                return None
    
    async def _fetch_chunk_contents_batch(self, chunk_object_keys: List[str]) -> List[Optional[Dict[str, Any]]]:
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
                processed_results.append(result)
                if result is not None:
                    success_count += 1
        
        fetch_time = time.time() - start_time
        logger.info(
            "R2 batch fetch completed",
            total_chunks=len(chunk_object_keys),
            successful=success_count,
            failed=len(chunk_object_keys) - success_count,
            duration_ms=round(fetch_time * 1000, 2)
        )
        
        return processed_results

    async def _fetch_parent_document_from_r2(self, parent_doc_id: str, doc_type: str = "", chunk_doc_id: str = "") -> Optional[Dict[str, Any]]:
        """Fetch full parent document from R2 for small-to-big retrieval.
        
        Args:
            parent_doc_id: Parent document ID from chunk metadata
            doc_type: Document type for path construction (e.g., 'act')
            chunk_doc_id: Chunk's doc_id for ID mapping resolution
            
        Returns:
            Dict containing full parent document or None if fetch fails
        """
        r2_client = self._get_r2_client()
        if not r2_client:
            return None
        
        # TEMPORARY FIX: Use ID mapping to resolve parent_doc_id mismatch
        try:
            from api.parent_doc_mapping import parent_doc_mapper
            resolved_parent_id = await parent_doc_mapper.resolve_parent_doc_id(parent_doc_id, chunk_doc_id)
            
            if resolved_parent_id and resolved_parent_id != parent_doc_id:
                logger.debug(
                    "Resolved parent doc ID via mapping",
                    original_parent_id=parent_doc_id,
                    resolved_parent_id=resolved_parent_id,
                    chunk_doc_id=chunk_doc_id
                )
                parent_doc_id = resolved_parent_id
                
        except ImportError:
            logger.warning("Parent doc mapping not available, using original ID")
        
        # Construct parent document object key
        if doc_type:
            parent_object_key = f"corpus/docs/{doc_type}/{parent_doc_id}.json"
        else:
            # Try common patterns if doc_type not provided
            possible_keys = [
                f"corpus/docs/act/{parent_doc_id}.json",
                f"corpus/docs/judgment/{parent_doc_id}.json", 
                f"corpus/docs/constitution/{parent_doc_id}.json",
                f"corpus/docs/si/{parent_doc_id}.json"
            ]
            
            # Try each possible key
            for key in possible_keys:
                result = await self._fetch_parent_document_from_r2_key(key)
                if result:
                    return result
            return None
        
        return await self._fetch_parent_document_from_r2_key(parent_object_key)
    
    async def _fetch_parent_document_from_r2_key(self, parent_object_key: str) -> Optional[Dict[str, Any]]:
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
                parent_doc_data = json.loads(content)
                return parent_doc_data
                
            except Exception as e:
                logger.debug(
                    "Parent document not found at key",
                    key=parent_object_key,
                    error=str(e)
                )
                return None
    
    async def _fetch_parent_documents_batch(self, parent_doc_requests: List[tuple]) -> List[Optional[Dict[str, Any]]]:
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
        tasks = [
            self._fetch_parent_document_from_r2(parent_id, doc_type, chunk_doc_id="") 
            for parent_id, doc_type in parent_doc_requests
        ]
        
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
                processed_results.append(result)
                if result is not None:
                    success_count += 1
        
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
            parent_doc_id = result.metadata.get("parent_doc_id") or result.doc_id
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
                expanded_result = RetrievalResult(
                    chunk_id=chunk_result.chunk_id,
                    chunk_text=parent_doc.get("doc_text", chunk_result.chunk_text),  # Full parent text
                    doc_id=chunk_result.doc_id,
                    metadata={
                        **chunk_result.metadata,
                        "expanded_to_parent": True,
                        "parent_doc_length": len(parent_doc.get("doc_text", "")),
                        "original_chunk_text": chunk_result.chunk_text,  # Keep original for citation
                        "parent_doc_object_key": parent_doc.get("doc_object_key", ""),
                    },
                    score=chunk_result.score,
                    source=f"{chunk_result.source}_expanded"
                )
                expanded_results.append(expanded_result)
            else:
                # Keep original chunk if parent not found
                logger.warning(
                    "Parent document not found, keeping original chunk",
                    chunk_id=chunk_result.chunk_id,
                    parent_doc_id=chunk_result.metadata.get("parent_doc_id")
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
                    matches.append(RetrievalResult(
                        chunk_id=str(o.get("chunk_id")),
                        chunk_text=o.get("chunk_text") or "",
                        doc_id=str(o.get("doc_id")),
                        metadata=md,
                        score=0.99,
                        source="shortcut",
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
                    out.append(RetrievalResult(
                        chunk_id=str(o.get("chunk_id")),
                        chunk_text=o.get("chunk_text") or "",
                        doc_id=str(o.get("doc_id")),
                        metadata=md,
                        score=0.7,
                        source="shortcut",
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
    
    async def retrieve(
        self,
        query: str,
        config: Optional[RetrievalConfig] = None
    ) -> List[RetrievalResult]:
        """Retrieve relevant chunks for a query using hybrid search."""
        if config is None:
            config = RetrievalConfig()
        
        start_time = time.time()
        
        # Preconditions (one-time per engine lifetime)
        self._check_preconditions()

        # Process query: normalize, detect date, intent
        normalized_query = self.query_processor.normalize_query(query)
        clean_query, date_context = self.query_processor.extract_date_context(normalized_query)
        intent = self.query_processor.detect_intent(clean_query)

        # Fast paths
        if intent.get("section_lookup"):
            fp = self._shortcut_section_lookup(intent)
            if fp:
                logger.info("Using direct section lookup fast-path", count=len(fp))
                return fp[:config.top_k]
        if intent.get("statute_lookup"):
            toc = self._shortcut_statute_toc(intent)
            if toc:
                logger.info("Using statute TOC fast-path", count=len(toc))
                return toc[:config.top_k]
        
        # Use date from config or extracted date
        effective_date = config.date_filter or date_context
        
        logger.info(
            "Starting retrieval",
            original_query=query[:100],
            normalized_query=clean_query[:100],
            date_filter=effective_date,
            top_k=config.top_k,
            intent=intent
        )
        
        # Multi-query expansion
        intent = intent  # already computed
        variants = self.query_processor.generate_reformulations(clean_query, intent, max_variants=config.expansions_count)
        # Batch embed variants
        embeddings = await self.embedding_client.get_embeddings(variants)
        results: List[RetrievalResult] = []
        if embeddings:
            # Dense retrieval
            doc_types = ["act", "ordinance", "si", "constitution"]
            dense_hits_by_variant = await self.milvus_client.search_similar_multi(
                query_vectors=embeddings,
                top_k=config.top_k_per_variant,
                doc_type_filter=doc_types,
            )
            # Sparse retrieval using production BM25 (optional)
            sparse_hits_by_variant: List[List[RetrievalResult]] = []
            if ENABLE_SPARSE:
                try:
                    from api.bm25_provider import production_bm25_provider
                    sparse_start = time.time()
                    
                    # Use production BM25 for all variants
                    for v in variants:
                        bm25_results = await production_bm25_provider.search(v, top_k=50)
                        sparse_hits_by_variant.append(bm25_results)
                    
                    sparse_time = time.time() - sparse_start
                    logger.info(
                        "BM25 sparse search completed",
                        variants_count=len(variants),
                        total_results=sum(len(hits) for hits in sparse_hits_by_variant),
                        elapsed_ms=round(sparse_time * 1000, 2)
                    )
                    
                except ImportError:
                    logger.warning("Production BM25 provider not available, falling back to SimpleSparseProvider")
                    sparse = SimpleSparseProvider()
                    for v in variants:
                        sh = await sparse.search(v, top_k=50)
                        sparse_hits_by_variant.append(sh)

            # ========================================================================
            # TASK 3.1: Optimized RRF (Reciprocal Rank Fusion) for production performance
            # ========================================================================
            rrf_start = time.time()
            logger.info("Starting optimized RRF fusion", 
                       dense_variants=len(dense_hits_by_variant),
                       sparse_variants=len(sparse_hits_by_variant))
            
            rrf_scores: Dict[str, float] = {}
            rrf_details: Dict[str, Dict[str, Any]] = {}
            K = config.rrf_k
            
            # Dense contributions (vector search results)
            dense_contribution_count = 0
            for variant_idx, hits in enumerate(dense_hits_by_variant):
                for rank, hit in enumerate(hits, start=1):
                    key = hit.chunk_id
                    rrf_contribution = 1.0 / (K + rank)
                    rrf_scores[key] = rrf_scores.get(key, 0.0) + rrf_contribution
                    dense_contribution_count += 1
                    
                    # Keep track of best hit for this chunk_id
                    existing = rrf_details.get(key)
                    if not existing or hit.score > existing["hit"].score:
                        rrf_details[key] = {
                            "hit": hit, 
                            "variant": variant_idx, 
                            "source": "dense",
                            "rrf_contribution": rrf_contribution
                        }
            
            # Sparse contributions (BM25 results)  
            sparse_contribution_count = 0
            for variant_idx, hits in enumerate(sparse_hits_by_variant, start=len(dense_hits_by_variant)):
                for rank, hit in enumerate(hits, start=1):
                    key = hit.chunk_id
                    rrf_contribution = 1.0 / (K + rank)
                    rrf_scores[key] = rrf_scores.get(key, 0.0) + rrf_contribution
                    sparse_contribution_count += 1
                    
                    # Prefer dense hits for ties, but allow sparse-only results
                    existing = rrf_details.get(key)
                    if not existing or (hit.score > existing["hit"].score and existing["source"] != "dense"):
                        rrf_details[key] = {
                            "hit": hit,
                            "variant": variant_idx,
                            "source": "sparse", 
                            "rrf_contribution": rrf_contribution
                        }

            # Build optimized fused results with performance optimizations
            fused: List[Tuple[str, float]] = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Apply diversity and quality filters
            seen_per_doc: Dict[str, int] = {}
            final: List[RetrievalResult] = []
            quality_filtered = 0
            diversity_filtered = 0
            
            for chunk_id, rrf_score in fused:
                detail = rrf_details[chunk_id]
                hit = detail["hit"]
                
                # Quality gate: apply minimum score filter only to vector results
                if hit.source == "vector" and hit.score < config.min_score:
                    quality_filtered += 1
                    continue
                
                # Diversity control: limit chunks per document
                doc_id = hit.doc_id
                cnt = seen_per_doc.get(doc_id, 0)
                if cnt >= config.max_per_doc:
                    diversity_filtered += 1
                    continue
                
                seen_per_doc[doc_id] = cnt + 1
                
                # Enrich metadata with RRF information
                hit.metadata.update({
                    "rrf_score": round(rrf_score, 4),
                    "rrf_rank": len(final) + 1,
                    "fusion_source": detail["source"]
                })
                
                final.append(hit)
                
                if len(final) >= config.top_k:
                    break
            
            rrf_time = time.time() - rrf_start
            
            # Log RRF performance metrics 
            logger.info(
                "Optimized RRF fusion completed",
                dense_contributions=dense_contribution_count,
                sparse_contributions=sparse_contribution_count,
                unique_chunks=len(rrf_scores),
                quality_filtered=quality_filtered,
                diversity_filtered=diversity_filtered,
                final_results=len(final),
                rrf_time_ms=round(rrf_time * 1000, 2),
                top_rrf_score=final[0].metadata.get("rrf_score") if final else 0
            )
            # Optional rerank
            if ENABLE_RERANK and OPENAI_RERANK_MODEL:
                reranker = OpenAIReranker(OPENAI_RERANK_MODEL)
                final = await reranker.rerank(clean_query, final, max_items=40)
            results = final
        else:
            logger.warning("No embeddings generated for variants; skipping search")
        
        # ========================================================================
        # TASK 3.1: Small-to-Big Retrieval - Expand chunks to parent documents
        # ========================================================================
        if results:
            # Step 1: Expand small chunks to parent documents for rich synthesis context
            logger.info("Expanding to parent documents (small-to-big)", chunk_count=len(results))
            results = await self._expand_to_parent_documents(results)
            
            # Step 2: For chunks without parent docs, fetch original chunk content from R2
            chunks_needing_content = [
                (i, r) for i, r in enumerate(results) 
                if not r.chunk_text and not r.metadata.get("expanded_to_parent")
            ]
            
            if chunks_needing_content:
                logger.info("Fetching chunk content from R2 for non-expanded results", 
                           count=len(chunks_needing_content))
                
                chunk_keys = []
                chunk_indices = []
                for i, result in chunks_needing_content:
                    chunk_key = result.metadata.get("chunk_object_key", "")
                    if chunk_key:
                        chunk_keys.append(chunk_key)
                        chunk_indices.append(i)
                
                if chunk_keys:
                    # Batch fetch chunk content from R2
                    chunk_contents = await self._fetch_chunk_contents_batch(chunk_keys)
                    
                    # Update results with fetched content
                    for content_idx, result_idx in enumerate(chunk_indices):
                        if content_idx < len(chunk_contents) and chunk_contents[content_idx] is not None:
                            chunk_data = chunk_contents[content_idx]
                            results[result_idx].chunk_text = chunk_data.get("chunk_text", "")
                            results[result_idx].metadata.update({
                                "section_path": chunk_data.get("section_path", ""),
                                "start_char": chunk_data.get("start_char", 0),
                                "end_char": chunk_data.get("end_char", 0),
                            })
            
            # Log final content status
            expanded_count = sum(1 for r in results if r.metadata.get("expanded_to_parent"))
            content_count = sum(1 for r in results if r.chunk_text)
            
            logger.info(
                "Small-to-big content retrieval completed",
                total_results=len(results),
                expanded_to_parents=expanded_count,
                chunk_content_fetched=content_count - expanded_count,
                ready_for_synthesis=content_count
            )
        
        # ========================================================================
        # TASK 3.1: Comprehensive Performance Monitoring & Observability  
        # ========================================================================
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Calculate detailed performance metrics
        performance_metrics = {
            "total_latency_ms": elapsed_ms,
            "results_count": len(results),
            "top_score": results[0].score if results else 0,
            "query_variants": len(variants) if 'variants' in locals() else 1,
            "dense_search_enabled": bool(embeddings),
            "sparse_search_enabled": ENABLE_SPARSE and len(sparse_hits_by_variant) > 0,
            "small_to_big_enabled": bool(results and any(r.metadata.get("expanded_to_parent") for r in results)),
            "r2_content_fetched": bool(results and any(r.chunk_text for r in results)),
        }
        
        # Add fusion metrics if available
        if 'rrf_scores' in locals():
            performance_metrics.update({
                "rrf_candidates": len(rrf_scores),
                "rrf_fusion_time_ms": round(rrf_time * 1000, 2),
                "dense_contributions": dense_contribution_count,
                "sparse_contributions": sparse_contribution_count,
            })
        
        # Add parent document metrics if available  
        if results:
            parent_expanded_count = sum(1 for r in results if r.metadata.get("expanded_to_parent"))
            performance_metrics.update({
                "parent_docs_expanded": parent_expanded_count,
                "parent_expansion_rate": round(parent_expanded_count / len(results), 2),
                "avg_content_length": round(sum(len(r.chunk_text) for r in results if r.chunk_text) / max(1, len([r for r in results if r.chunk_text])), 0)
            })
        
        # Log comprehensive performance metrics
        logger.info(
            "Production hybrid retrieval completed",
            **performance_metrics
        )
        
        # Performance alerting - warn if exceeding production thresholds
        if elapsed_ms > 2500:  # > 2.5s P95 target
            logger.warning(
                "Retrieval latency exceeded target",
                latency_ms=elapsed_ms,
                target_ms=2500,
                query_preview=query[:50]
            )
        
        # Quality alerting - warn if low relevance
        if results and results[0].score < 0.3:
            logger.warning(
                "Low relevance results detected", 
                top_score=results[0].score,
                results_count=len(results),
                query_preview=query[:50]
            )
        
        return results
    
    def calculate_confidence(self, results: List[RetrievalResult]) -> float:
        """Calculate confidence score based on retrieval results."""
        if not results:
            return 0.0
        # Use a blend of top score and average of top 5, with diversity bonus
        top_score = results[0].score
        top5 = results[:5]
        avg5 = sum(r.score for r in top5) / max(1, len(top5))
        confidence = 0.7 * top_score + 0.3 * avg5
        doc_diversity = len({r.doc_id for r in top5})
        if doc_diversity >= 3:
            confidence = min(1.0, confidence + 0.05)
        return round(confidence, 3)


# Convenience functions for direct use

async def search_legal_documents(
    query: str,
    top_k: int = 20,
    date_filter: Optional[str] = None,
    min_score: float = 0.1
) -> Tuple[List[RetrievalResult], float]:
    """
    Search legal documents and return results with confidence.
    
    Args:
        query: User query text
        top_k: Maximum number of results
        date_filter: ISO date for temporal filtering
        min_score: Minimum similarity score threshold
    
    Returns:
        Tuple of (results, confidence_score)
    """
    config = RetrievalConfig(
        top_k=top_k,
        date_filter=date_filter,
        min_score=min_score
    )
    
    async with RetrievalEngine() as engine:
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

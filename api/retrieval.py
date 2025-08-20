"""Milvus-based retrieval system for RightLine.

This module implements hybrid retrieval using Milvus Cloud for vector search
and keyword matching for legal document chunks. Optimized for serverless
deployment with per-request connections.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from pydantic import BaseModel, Field
from pymilvus import Collection, connections
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# Milvus configuration from environment
MILVUS_ENDPOINT = os.environ.get("MILVUS_ENDPOINT")
MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN")
MILVUS_COLLECTION_NAME = os.environ.get("MILVUS_COLLECTION_NAME", "legal_chunks")

# OpenAI configuration for embeddings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# Cache configuration
CACHE_TTL_SECONDS = 3600  # 1 hour


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


class QueryProcessor:
    """Process and normalize user queries."""
    
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
    
    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract important keywords for hybrid search."""
        # Common legal terms that should be preserved
        legal_terms = {
            'employment', 'labour', 'labor', 'wage', 'salary', 'termination', 
            'notice', 'dismissal', 'contract', 'overtime', 'leave', 'maternity',
            'paternity', 'retrenchment', 'discrimination', 'harassment'
        }
        
        words = text.lower().split()
        keywords = []
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            if len(clean_word) > 2:  # Skip very short words
                keywords.append(clean_word)
        
        # Prioritize legal terms
        priority_keywords = [kw for kw in keywords if kw in legal_terms]
        other_keywords = [kw for kw in keywords if kw not in legal_terms]
        
        return priority_keywords + other_keywords[:10]  # Limit total keywords


class MilvusClient:
    """Milvus client for vector operations."""
    
    def __init__(self):
        self.collection: Optional[Collection] = None
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to Milvus Cloud."""
        if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
            logger.warning("Milvus credentials not configured")
            return False
        
        try:
            # Create connection
            connections.connect(
                alias="default",
                uri=MILVUS_ENDPOINT,
                token=MILVUS_TOKEN,
                timeout=10,
            )
            
            # Get collection
            self.collection = Collection(MILVUS_COLLECTION_NAME)
            self.collection.load()  # Load collection into memory
            
            self.connected = True
            logger.info("Connected to Milvus", collection=MILVUS_COLLECTION_NAME)
            return True
            
        except Exception as e:
            logger.error("Failed to connect to Milvus", error=str(e))
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Milvus."""
        try:
            if self.connected:
                connections.disconnect("default")
                self.connected = False
        except Exception as e:
            logger.warning("Error disconnecting from Milvus", error=str(e))
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def search_similar(
        self, 
        query_vector: List[float], 
        top_k: int = 20,
        date_filter: Optional[str] = None
    ) -> List[RetrievalResult]:
        """Search for similar chunks using vector similarity."""
        if not self.connected or not self.collection:
            logger.warning("Milvus not connected")
            return []
        
        try:
            # Build search parameters
            search_params = {
                "metric_type": "COSINE",
                "params": {"ef": 64}  # HNSW search parameter
            }
            
            # Build filter expression if date provided
            filter_expr = None
            if date_filter:
                # Filter by effective date in metadata
                filter_expr = f'metadata["effective_date"] <= "{date_filter}"'
            
            # Perform search
            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["doc_id", "chunk_text", "metadata"]
            )
            
            # Convert to RetrievalResult objects
            retrieval_results = []
            for hit in results[0]:  # results[0] because we only sent one query
                retrieval_results.append(RetrievalResult(
                    chunk_id=str(hit.id),
                    chunk_text=hit.entity.get("chunk_text", ""),
                    doc_id=hit.entity.get("doc_id", ""),
                    metadata=hit.entity.get("metadata", {}),
                    score=float(hit.score),
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


class EmbeddingClient:
    """OpenAI client for generating embeddings."""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using OpenAI API."""
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not configured")
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
    """Main retrieval engine combining vector and keyword search."""
    
    def __init__(self):
        self.milvus_client = MilvusClient()
        self.embedding_client = EmbeddingClient()
        self.query_processor = QueryProcessor()
    
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
        
        # Process query
        normalized_query = self.query_processor.normalize_query(query)
        clean_query, date_context = self.query_processor.extract_date_context(normalized_query)
        
        # Use date from config or extracted date
        effective_date = config.date_filter or date_context
        
        logger.info(
            "Starting retrieval",
            original_query=query[:100],
            normalized_query=clean_query[:100],
            date_filter=effective_date,
            top_k=config.top_k
        )
        
        # Generate embedding for vector search
        embedding = await self.embedding_client.get_embedding(clean_query)
        
        results = []
        
        if embedding:
            # Vector search
            vector_results = await self.milvus_client.search_similar(
                query_vector=embedding,
                top_k=config.top_k,
                date_filter=effective_date
            )
            results.extend(vector_results)
        else:
            logger.warning("No embedding generated, skipping vector search")
        
        # Filter by minimum score
        results = [r for r in results if r.score >= config.min_score]
        
        # Sort by score (descending)
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Limit results
        results = results[:config.top_k]
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Retrieval completed",
            results_count=len(results),
            elapsed_ms=elapsed_ms,
            top_score=results[0].score if results else 0
        )
        
        return results
    
    def calculate_confidence(self, results: List[RetrievalResult]) -> float:
        """Calculate confidence score based on retrieval results."""
        if not results:
            return 0.0
        
        # Base confidence on top score
        top_score = results[0].score
        
        # Boost confidence if multiple good results
        good_results = [r for r in results if r.score > 0.7]
        score_diversity = len(set(round(r.score, 1) for r in results[:5]))
        
        confidence = top_score
        
        # Boost for multiple good results
        if len(good_results) > 1:
            confidence = min(1.0, confidence + 0.1)
        
        # Slight boost for score diversity (indicates robust matching)
        if score_diversity > 2:
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

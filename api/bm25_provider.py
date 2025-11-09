#!/usr/bin/env python3
"""
Production-grade BM25 provider for lightning-fast sparse search.

This module implements Task 3.1: replacing SimpleSparseProvider with a robust
BM25 implementation using the rank-bm25 library. Optimized for production
performance with < 50ms search latency for 50K+ document corpus.

Key features:
- Lightning-fast BM25 search using pre-built index
- Legal document tokenization optimization
- Async-compatible with semaphore-controlled loading
- Comprehensive error handling and fallback mechanisms
- Performance monitoring and structured logging
- Memory-efficient index caching

Author: RightLine Team
"""

from __future__ import annotations

import asyncio
import os
import pickle
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import structlog
from rank_bm25 import BM25Okapi

from api.tools.retrieval_engine import RetrievalResult, SparseProvider
from api.models import ChunkV3

logger = structlog.get_logger(__name__)

# Configuration - Cloud-Native R2 Storage
BM25_INDEX_R2_KEY = os.environ.get("BM25_INDEX_R2_KEY", "corpus/indexes/bm25_index.pkl")
BM25_INDEX_LOCAL_PATH = os.environ.get("BM25_INDEX_LOCAL_PATH", "data/processed/bm25_index.pkl")  # Development fallback
BM25_LOAD_TIMEOUT = int(os.environ.get("BM25_LOAD_TIMEOUT", "10"))  # seconds
BM25_SEARCH_TIMEOUT = int(os.environ.get("BM25_SEARCH_TIMEOUT", "5"))   # seconds

# R2 configuration from environment  
R2_ENDPOINT = os.environ.get("R2_ENDPOINT") or os.environ.get("CLOUDFLARE_R2_S3_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")


class ProductionBM25Provider(SparseProvider):
    """
    Production-grade BM25 sparse search provider with cloud-native R2 storage.
    
    Replaces SimpleSparseProvider with lightning-fast BM25 search using
    pre-built index stored in R2 for truly serverless deployment.
    
    Performance targets:
    - Index loading: < 2s (cold start from R2)
    - Search latency: < 50ms (50K corpus)  
    - Memory usage: < 500MB (index + metadata)
    - Concurrent safety: Thread-safe operations
    """
    
    def __init__(self, r2_index_key: str = BM25_INDEX_R2_KEY, local_fallback: str = BM25_INDEX_LOCAL_PATH):
        self.r2_index_key = r2_index_key
        self.local_fallback_path = local_fallback
        self._index_data: Optional[Dict[str, Any]] = None
        self._bm25_index: Optional[BM25Okapi] = None
        self._chunk_metadata: List[Dict[str, Any]] = []
        self._load_lock = asyncio.Lock()
        self._loaded = False
        self._r2_client = None
    
    def _get_r2_client(self):
        """Get or create R2 client for index loading."""
        if self._r2_client is None:
            if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
                logger.warning("R2 configuration incomplete, using local fallback")
                return None
            
            import boto3
            self._r2_client = boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY,
                aws_secret_access_key=R2_SECRET_KEY,
                region_name='auto'  # R2 uses 'auto' region
            )
        return self._r2_client
    
    async def _ensure_index_loaded(self) -> bool:
        """Ensure BM25 index is loaded into memory.
        
        Returns:
            True if index loaded successfully, False otherwise
        """
        if self._loaded:
            return True
        
        async with self._load_lock:
            # Double-check pattern for async safety
            if self._loaded:
                return True
            
            try:
                return await self._load_index()
            except Exception as e:
                logger.error("Failed to load BM25 index", error=str(e), path=self.index_path)
                return False
    
    async def _load_index(self) -> bool:
        """Load BM25 index from R2 (cloud-native) with local fallback."""
        start_time = time.time()
        
        # Try R2 first (cloud-native)
        if await self._load_index_from_r2():
            return True
        
        # Fallback to local file for development
        logger.info("Falling back to local BM25 index for development")
        return await self._load_index_from_local()
    
    async def _load_index_from_r2(self) -> bool:
        """Load BM25 index from R2 storage (production)."""
        r2_client = self._get_r2_client()
        if not r2_client:
            return False
        
        start_time = time.time()
        logger.info("Loading BM25 index from R2 (cloud-native)", key=self.r2_index_key)
        
        try:
            # Load index from R2 in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            def load_from_r2():
                response = r2_client.get_object(Bucket=R2_BUCKET_NAME, Key=self.r2_index_key)
                return pickle.loads(response['Body'].read())
            
            # Load with timeout
            self._index_data = await asyncio.wait_for(
                loop.run_in_executor(None, load_from_r2),
                timeout=BM25_LOAD_TIMEOUT
            )
            
            # Extract components
            self._bm25_index = self._index_data["bm25_index"]
            self._chunk_metadata = self._index_data["chunk_metadata"]
            
            # Log performance metrics
            load_time = time.time() - start_time
            corpus_size = self._index_data.get("corpus_size", 0)
            
            logger.info(
                "BM25 index loaded from R2 successfully",
                corpus_size=corpus_size,
                load_time_ms=round(load_time * 1000, 2),
                r2_key=self.r2_index_key,
                build_timestamp=self._index_data.get("build_timestamp", 0),
                cloud_native=True
            )
            
            self._loaded = True
            return True
            
        except Exception as e:
            logger.warning("Failed to load BM25 index from R2", error=str(e), key=self.r2_index_key)
            return False
    
    async def _load_index_from_local(self) -> bool:
        """Load BM25 index from local file (development fallback)."""
        if not os.path.exists(self.local_fallback_path):
            logger.warning("Local BM25 index file not found", path=self.local_fallback_path)
            return False
        
        start_time = time.time()
        logger.info("Loading BM25 index from local file (development)", path=self.local_fallback_path)
        
        try:
            # Load index in executor
            loop = asyncio.get_event_loop()
            
            def load_pickle():
                with open(self.local_fallback_path, 'rb') as f:
                    return pickle.load(f)
            
            self._index_data = await asyncio.wait_for(
                loop.run_in_executor(None, load_pickle),
                timeout=BM25_LOAD_TIMEOUT
            )
            
            # Extract components
            self._bm25_index = self._index_data["bm25_index"]
            self._chunk_metadata = self._index_data["chunk_metadata"]
            
            load_time = time.time() - start_time
            corpus_size = self._index_data.get("corpus_size", 0)
            
            logger.info(
                "BM25 index loaded from local file successfully",
                corpus_size=corpus_size,
                load_time_ms=round(load_time * 1000, 2),
                local_path=self.local_fallback_path,
                cloud_native=False
            )
            
            self._loaded = True
            return True
            
        except Exception as e:
            logger.error("Error loading local BM25 index", error=str(e))
            return False
    
    def _tokenize_query(self, query: str) -> List[str]:
        """Tokenize query using same optimization as corpus."""
        from scripts.build_bm25_index import optimize_tokenize_legal_text
        return optimize_tokenize_legal_text(query)
    
    async def search(self, query: str, top_k: int = 50) -> List[RetrievalResult]:
        """
        Search using BM25 algorithm for lightning-fast sparse retrieval.
        
        Args:
            query: Search query
            top_k: Maximum number of results to return
            
        Returns:
            List of RetrievalResult objects ranked by BM25 relevance
        """
        # Ensure index is loaded
        if not await self._ensure_index_loaded():
            logger.warning("BM25 index not available, returning empty results")
            return []
        
        if not query.strip():
            return []
        
        start_time = time.time()
        
        try:
            # Tokenize query
            query_tokens = self._tokenize_query(query)
            if not query_tokens:
                return []
            
            logger.info(
                "Starting BM25 search",
                query_length=len(query),
                query_tokens=len(query_tokens),
                corpus_size=len(self._chunk_metadata),
                top_k=top_k
            )
            
            # Perform BM25 search
            search_start = time.time()
            bm25_scores = self._bm25_index.get_scores(query_tokens)
            search_time = time.time() - search_start
            
            # Get top-k results with scores
            top_indices = bm25_scores.argsort()[-top_k:][::-1]  # Reverse for descending order
            
            # Build results
            results = []
            for idx in top_indices:
                score = float(bm25_scores[idx])
                if score <= 0:
                    continue  # Skip irrelevant results
                
                metadata = self._chunk_metadata[idx]
                
                # Create ChunkV3 object for RetrievalResult
                chunk = ChunkV3(
                    chunk_id=metadata["chunk_id"],
                    chunk_text="",  # Will be fetched from R2 by RetrievalEngine
                    doc_id=metadata["parent_doc_id"],  # Use parent_doc_id as doc_id for consistency
                    doc_type=metadata["doc_type"],
                    metadata=metadata.get("metadata", {}),
                    entities={}
                )
                
                results.append(RetrievalResult(
                    chunk=chunk,
                    confidence=min(score, 1.0),  # Ensure confidence is <= 1.0
                    metadata={
                        "source": "bm25",
                        "bm25_score": score,
                        **metadata.get("metadata", {})
                    }
                ))
            
            # Log performance metrics
            total_time = time.time() - start_time
            logger.info(
                "BM25 search completed",
                results_count=len(results),
                search_time_ms=round(search_time * 1000, 2),
                total_time_ms=round(total_time * 1000, 2),
                top_score=results[0].score if results else 0,
                tokens_per_ms=round(len(query_tokens) / (search_time * 1000), 2) if search_time > 0 else 0
            )
            
            return results
            
        except Exception as e:
            logger.error("BM25 search failed", error=str(e), query=query[:100])
            return []  # Graceful fallback


class BM25IndexManager:
    """Manager for BM25 index lifecycle and maintenance (cloud-native)."""
    
    @staticmethod
    def get_r2_client():
        """Get R2 client for index operations."""
        if not all([R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY]):
            return None
        
        import boto3
        return boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name='auto'
        )
    
    @staticmethod
    def get_index_info_from_r2(r2_key: str = BM25_INDEX_R2_KEY) -> Optional[Dict[str, Any]]:
        """Get information about the BM25 index from R2 without loading it."""
        r2_client = BM25IndexManager.get_r2_client()
        if not r2_client:
            return BM25IndexManager.get_local_index_info()  # Fallback
        
        try:
            response = r2_client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            metadata = response.get('Metadata', {})
            
            return {
                "r2_key": r2_key,
                "size_mb": round(response['ContentLength'] / 1024 / 1024, 2),
                "last_modified": response['LastModified'].timestamp(),
                "corpus_size": int(metadata.get("corpus_size", 0)),
                "build_timestamp": float(metadata.get("build_timestamp", 0)),
                "cloud_native": True,
                "exists": True
            }
        except Exception as e:
            logger.warning("Error getting BM25 index info from R2", error=str(e))
            return BM25IndexManager.get_local_index_info()  # Fallback
    
    @staticmethod  
    def get_local_index_info(index_path: str = BM25_INDEX_LOCAL_PATH) -> Optional[Dict[str, Any]]:
        """Get information about local BM25 index (development fallback)."""
        if not os.path.exists(index_path):
            return None
        
        try:
            file_stats = os.stat(index_path)
            return {
                "path": index_path,
                "size_mb": round(file_stats.st_size / 1024 / 1024, 2),
                "last_modified": file_stats.st_mtime,
                "cloud_native": False,
                "exists": True
            }
        except Exception as e:
            logger.error("Error getting local BM25 index info", error=str(e))
            return None
    
    @staticmethod
    def get_index_info() -> Optional[Dict[str, Any]]:
        """Get BM25 index info, trying R2 first then local fallback."""
        # Try R2 first (production)
        r2_info = BM25IndexManager.get_index_info_from_r2()
        if r2_info:
            return r2_info
        
        # Fallback to local (development)
        return BM25IndexManager.get_local_index_info()
    
    @staticmethod
    def validate_index_freshness(max_age_hours: int = 24) -> bool:
        """Validate that BM25 index is fresh enough for production use."""
        info = BM25IndexManager.get_index_info()
        if not info:
            return False
        
        last_modified = info.get("last_modified", 0)
        age_hours = (time.time() - last_modified) / 3600
        is_fresh = age_hours <= max_age_hours
        
        logger.info(
            "BM25 index freshness check",
            age_hours=round(age_hours, 2),
            max_age_hours=max_age_hours,
            is_fresh=is_fresh,
            cloud_native=info.get("cloud_native", False)
        )
        
        return is_fresh


# Singleton instance for production use
production_bm25_provider = ProductionBM25Provider()

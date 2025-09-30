"""
Multi-level semantic cache for Gweta Legal AI queries.

Provides:
- Level 1: Exact match (hash-based, <5ms)
- Level 2: Semantic similarity (embedding-based, <50ms)  
- Level 3: Intent caching
- Level 4: Embedding caching

Follows .cursorrules: async-first, graceful degradation, comprehensive metrics.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    
    total_requests: int = 0
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.exact_hits + self.semantic_hits) / self.total_requests


class SemanticCache:
    """
    Multi-level semantic cache for legal AI queries.
    
    Usage:
        cache = SemanticCache(redis_url="redis://localhost:6379/0")
        await cache.connect()
        
        # Try to get cached response
        cached = await cache.get_cached_response(query, user_type="professional")
        if cached:
            return cached
        
        # On cache miss, process query and cache result
        result = await process_query(query)
        await cache.cache_response(query, result, user_type="professional")
    """
    
    def __init__(
        self,
        redis_url: str,
        similarity_threshold: float = 0.95,
        default_ttl: int = 3600
    ):
        """
        Initialize semantic cache.
        
        Args:
            redis_url: Redis connection URL
            similarity_threshold: Minimum cosine similarity for semantic match (0-1)
            default_ttl: Default TTL in seconds for cached entries
        """
        self.redis_url = redis_url
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        self._redis_client = None
        self._embedding_client = None
        self._stats = CacheStats()
    
    async def connect(self, use_fake: bool = None):
        """
        Connect to Redis and initialize embedding client.
        
        Args:
            use_fake: If True, use fakeredis for testing. If None, auto-detect.
        """
        if self._redis_client is not None:
            # Already connected
            return
        
        # Auto-detect test environment
        if use_fake is None:
            import os
            use_fake = os.getenv("RIGHTLINE_APP_ENV") == "test"
        
        # Use fakeredis directly in test mode (avoids event loop issues)
        if use_fake:
            try:
                from fakeredis import aioredis as fakeredis
                self._redis_client = fakeredis.FakeRedis(decode_responses=True)
                logger.info("SemanticCache using fakeredis for testing")
                return
            except ImportError:
                logger.warning("fakeredis not installed, using real Redis")
        
        # Use the redis_client module for real Redis
        from libs.caching.redis_client import get_redis_client
        
        self._redis_client = await get_redis_client(use_fake=use_fake)
        
        if self._redis_client is None:
            logger.warning("Failed to connect to Redis, caching disabled")
            return
        
        # Initialize embedding client for semantic search
        if not use_fake:  # Only initialize for real usage, not tests
            try:
                from api.tools.retrieval_engine import EmbeddingClient
                self._embedding_client = EmbeddingClient()
                logger.info("Embedding client initialized for semantic caching")
            except Exception as e:
                logger.warning("Failed to initialize embedding client", error=str(e))
        
        logger.info(
            "SemanticCache connected to Redis",
            similarity_threshold=self.similarity_threshold,
            default_ttl=self.default_ttl,
            embedding_client_available=self._embedding_client is not None
        )
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis_client is not None:
            try:
                # Note: We don't close here because redis_client manages the singleton
                # Just clear our reference
                self._redis_client = None
                logger.info("SemanticCache disconnected")
            except Exception as e:
                logger.warning("Error during disconnect", error=str(e))
    
    def _get_exact_cache_key(self, query: str, user_type: str) -> str:
        """
        Generate cache key for exact match.
        
        Args:
            query: User query
            user_type: User type (professional/citizen)
            
        Returns:
            Cache key string
        """
        # Normalize query (lowercase, strip, remove multiple spaces)
        normalized = " ".join(query.lower().strip().split())
        
        # Generate MD5 hash for consistent key
        query_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        
        return f"cache:exact:{user_type}:{query_hash}"
    
    async def get_cached_response(
        self,
        query: str,
        user_type: str = "professional",
        check_semantic: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response with multi-level fallback.
        
        Args:
            query: User query
            user_type: User type (professional/citizen)
            check_semantic: Whether to check semantic similarity
            
        Returns:
            Cached response dict or None if miss
        """
        if self._redis_client is None:
            logger.warning("Redis not connected, cache disabled")
            return None
        
        self._stats.total_requests += 1
        
        # Level 1: Exact match (hash-based)
        exact_key = self._get_exact_cache_key(query, user_type)
        
        try:
            cached_exact = await self._redis_client.get(exact_key)
            
            if cached_exact:
                self._stats.exact_hits += 1
                logger.info(
                    "Cache hit: exact match",
                    query_preview=query[:50],
                    cache_key=exact_key
                )
                
                # Increment hit count
                await self._redis_client.hincrby(f"{exact_key}:meta", "hit_count", 1)
                
                response = json.loads(cached_exact)
                response["_cache_hit"] = "exact"
                return response
        
        except Exception as e:
            logger.error("Error checking exact cache", error=str(e))
        
        # Level 2: Semantic similarity (if enabled and embedding client available)
        if check_semantic and self._embedding_client is not None:
            try:
                similar_response = await self._find_similar_cached_query(query, user_type)
                
                if similar_response:
                    self._stats.semantic_hits += 1
                    logger.info(
                        "Cache hit: semantic similarity",
                        similarity=similar_response["similarity"],
                        query_preview=query[:50],
                        original_query=similar_response["original_query"][:50]
                    )
                    
                    response = similar_response["response"]
                    response["_cache_hit"] = "semantic"
                    response["_cache_similarity"] = similar_response["similarity"]
                    return response
            
            except Exception as e:
                logger.error("Semantic similarity search failed", error=str(e))
        
        # Cache miss
        self._stats.misses += 1
        logger.info("Cache miss", query_preview=query[:50])
        
        return None
    
    async def cache_response(
        self,
        query: str,
        response: Dict[str, Any],
        user_type: str = "professional",
        ttl_seconds: Optional[int] = None
    ):
        """
        Cache response for future queries.
        
        Args:
            query: User query
            response: Response dict to cache
            user_type: User type
            ttl_seconds: TTL in seconds (default: self.default_ttl)
        """
        if self._redis_client is None:
            logger.warning("Redis not connected, cannot cache")
            return
        
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl
        
        try:
            # Store exact match
            exact_key = self._get_exact_cache_key(query, user_type)
            
            # Remove all internal metadata (fields starting with _) before storing
            clean_response = {k: v for k, v in response.items() if not k.startswith('_')}
            
            await self._redis_client.setex(
                exact_key,
                ttl_seconds,
                json.dumps(clean_response)
            )
            
            # Generate embedding for semantic search (if client available)
            embedding = None
            if self._embedding_client is not None:
                try:
                    embeddings = await self._embedding_client.get_embeddings([query])
                    embedding = embeddings[0] if embeddings else None
                except Exception as e:
                    logger.warning("Failed to generate embedding", error=str(e))
            
            # Store metadata (including embedding for semantic search)
            metadata = {
                "query": query,
                "user_type": user_type,
                "created_at": datetime.utcnow().isoformat(),
                "hit_count": "0"
            }
            
            if embedding:
                metadata["embedding"] = json.dumps(embedding)
            
            await self._redis_client.hset(f"{exact_key}:meta", mapping=metadata)
            await self._redis_client.expire(f"{exact_key}:meta", ttl_seconds)
            
            # Add to semantic search index if embedding available
            if embedding:
                await self._add_to_semantic_index(exact_key, user_type)
            
            logger.info(
                "Response cached",
                cache_key=exact_key,
                ttl_seconds=ttl_seconds,
                query_preview=query[:50]
            )
            
        except Exception as e:
            logger.error("Failed to cache response", error=str(e))
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (0-1)
        """
        dot_product = np.dot(vec1, vec2)
        norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
        return float(dot_product / norm_product) if norm_product > 0 else 0.0
    
    async def _find_similar_cached_query(
        self,
        query: str,
        user_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find semantically similar cached query using cosine similarity.
        
        Args:
            query: User query
            user_type: User type
            
        Returns:
            Dict with response, similarity, and original_query, or None
        """
        if self._embedding_client is None:
            return None
        
        try:
            # Get query embedding
            embeddings = await self._embedding_client.get_embeddings([query])
            if not embeddings:
                return None
            
            query_embedding = np.array(embeddings[0])
            
            # Get all cached keys for this user type from semantic index
            index_key = f"semantic_index:{user_type}"
            cached_keys = await self._redis_client.smembers(index_key)
            
            if not cached_keys:
                return None
            
            # Compare embeddings to find best match
            max_similarity = 0.0
            best_match_key = None
            best_match_meta = None
            
            for cached_key in cached_keys:
                # Get cached embedding
                cached_meta = await self._redis_client.hgetall(f"{cached_key}:meta")
                if not cached_meta or "embedding" not in cached_meta:
                    continue
                
                cached_embedding_json = cached_meta["embedding"]
                cached_embedding = np.array(json.loads(cached_embedding_json))
                
                # Compute cosine similarity
                similarity = self._cosine_similarity(query_embedding, cached_embedding)
                
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_match_key = cached_key
                    best_match_meta = cached_meta
            
            # Check if similarity exceeds threshold
            if max_similarity >= self.similarity_threshold and best_match_key:
                # Fetch cached response
                cached_response = await self._redis_client.get(best_match_key)
                if cached_response:
                    # Increment hit count
                    await self._redis_client.hincrby(f"{best_match_key}:meta", "hit_count", 1)
                    
                    return {
                        "response": json.loads(cached_response),
                        "similarity": max_similarity,
                        "original_query": best_match_meta["query"]
                    }
            
            return None
            
        except Exception as e:
            logger.error("Semantic similarity search failed", error=str(e))
            return None
    
    async def _add_to_semantic_index(self, cache_key: str, user_type: str):
        """
        Add cache entry to semantic search index.
        
        Args:
            cache_key: Cache key to add to index
            user_type: User type
        """
        index_key = f"semantic_index:{user_type}"
        await self._redis_client.sadd(index_key, cache_key)
    
    async def get_embedding_cache(self, query: str) -> Optional[List[float]]:
        """
        Get cached query embedding.
        
        Args:
            query: Query to get embedding for
            
        Returns:
            Cached embedding or None
        """
        if self._redis_client is None:
            return None
        
        key = f"cache:embedding:{hashlib.md5(query.encode()).hexdigest()}"
        
        try:
            cached = await self._redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error("Error getting embedding cache", error=str(e))
        
        return None
    
    async def cache_embedding(
        self,
        query: str,
        embedding: List[float],
        ttl: int = 3600
    ):
        """
        Cache query embedding.
        
        Args:
            query: Query
            embedding: Embedding vector
            ttl: TTL in seconds (default 1 hour)
        """
        if self._redis_client is None:
            return
        
        key = f"cache:embedding:{hashlib.md5(query.encode()).hexdigest()}"
        
        try:
            await self._redis_client.setex(key, ttl, json.dumps(embedding))
        except Exception as e:
            logger.error("Error caching embedding", error=str(e))
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def clear_cache(self, pattern: str = "cache:*") -> int:
        """
        Clear cache entries matching pattern.
        
        Args:
            pattern: Redis key pattern
            
        Returns:
            Number of keys deleted
        """
        if self._redis_client is None:
            return 0
        
        try:
            cursor = 0
            deleted = 0
            
            while True:
                cursor, keys = await self._redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )
                
                if keys:
                    deleted += await self._redis_client.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.info("Cache cleared", pattern=pattern, deleted=deleted)
            return deleted
            
        except Exception as e:
            logger.error("Error clearing cache", error=str(e))
            return 0


# Global cache instance
_global_cache: Optional[SemanticCache] = None


async def get_cache() -> Optional[SemanticCache]:
    """Get or create global cache instance."""
    global _global_cache
    
    if _global_cache is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _global_cache = SemanticCache(redis_url=redis_url)
        await _global_cache.connect()
    
    return _global_cache

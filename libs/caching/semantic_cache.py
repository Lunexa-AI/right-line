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
        
        logger.info(
            "SemanticCache connected to Redis",
            similarity_threshold=self.similarity_threshold,
            default_ttl=self.default_ttl
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
        
        # Level 2: Semantic similarity
        # (Will be implemented in ARCH-015)
        if check_semantic:
            # Placeholder for now
            pass
        
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
            
            # Remove cache metadata before storing
            clean_response = {k: v for k, v in response.items() if not k.startswith('_cache')}
            
            await self._redis_client.setex(
                exact_key,
                ttl_seconds,
                json.dumps(clean_response)
            )
            
            # Store metadata
            await self._redis_client.hset(
                f"{exact_key}:meta",
                mapping={
                    "query": query,
                    "user_type": user_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "hit_count": "0"
                }
            )
            await self._redis_client.expire(f"{exact_key}:meta", ttl_seconds)
            
            logger.info(
                "Response cached",
                cache_key=exact_key,
                ttl_seconds=ttl_seconds,
                query_preview=query[:50]
            )
            
        except Exception as e:
            logger.error("Failed to cache response", error=str(e))
    
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

"""
Redis client manager for Gweta caching infrastructure.

Provides:
- Async Redis client with connection pooling
- Singleton pattern for resource efficiency
- Graceful error handling and fallbacks
- Environment-based configuration

Follows .cursorrules: async-first, connection pooling, observability, error handling.
"""

import os
from typing import Optional
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)

# Global Redis client instance (singleton)
_redis_client: Optional[redis.Redis] = None
_connection_failed = False  # Circuit breaker for repeated failures


async def get_redis_client(use_fake: bool = None) -> Optional[redis.Redis]:
    """
    Get or create async Redis client with connection pooling.
    
    Singleton pattern - returns same client instance for efficiency.
    Graceful degradation - returns None if Redis unavailable.
    
    Args:
        use_fake: If True, use fakeredis for testing. If None, auto-detect from env.
    
    Returns:
        Redis client instance or None if connection fails
        
    Raises:
        No exceptions - returns None on failure for graceful degradation
    """
    global _redis_client, _connection_failed
    
    # Auto-detect test environment
    if use_fake is None:
        use_fake = os.getenv("RIGHTLINE_APP_ENV") == "test"
    
    # Use fakeredis in test environment
    if use_fake:
        try:
            from fakeredis import aioredis as fakeredis
            if _redis_client is None:
                _redis_client = fakeredis.FakeRedis(decode_responses=True)
                logger.info("Using fakeredis for testing")
            return _redis_client
        except ImportError:
            logger.warning("fakeredis not installed, falling back to real Redis")
            use_fake = False
    
    # If previous connection attempt failed, don't retry immediately
    if _connection_failed:
        logger.warning("Redis connection previously failed, skipping reconnect attempt")
        return None
    
    # Return existing client if available
    if _redis_client is not None:
        try:
            # Verify connection is still alive
            await _redis_client.ping()
            return _redis_client
        except Exception as e:
            logger.warning("Existing Redis connection failed, reconnecting", error=str(e))
            _redis_client = None
    
    # Get Redis URL from environment
    redis_url = os.getenv("REDIS_URL")
    
    if not redis_url:
        logger.warning(
            "REDIS_URL not configured, caching will be disabled",
            hint="Set REDIS_URL environment variable to enable caching"
        )
        _connection_failed = True
        return None
    
    try:
        # Create new Redis client with connection pooling
        _redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,  # Auto-decode bytes to strings
            max_connections=20,  # Connection pool size
            socket_timeout=5,  # 5 second timeout
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        
        # Test connection
        await _redis_client.ping()
        
        logger.info(
            "Redis client initialized successfully",
            url=redis_url.split("@")[-1] if "@" in redis_url else redis_url.split("//")[-1],  # Hide credentials
            max_connections=20
        )
        
        return _redis_client
        
    except redis.ConnectionError as e:
        logger.error(
            "Redis connection failed",
            error=str(e),
            redis_url=redis_url.split("@")[-1] if "@" in redis_url else "unknown",
            hint="Check REDIS_URL and ensure Redis server is running"
        )
        _connection_failed = True
        return None
        
    except Exception as e:
        logger.error(
            "Unexpected error initializing Redis",
            error=str(e),
            error_type=type(e).__name__
        )
        _connection_failed = True
        return None


async def close_redis_client():
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client is not None:
        try:
            await _redis_client.close()
            logger.info("Redis client closed")
        except Exception as e:
            logger.warning("Error closing Redis client", error=str(e))
        finally:
            _redis_client = None


async def reset_redis_client():
    """Reset Redis client (for testing or after connection failures)."""
    global _redis_client, _connection_failed
    
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:
            pass  # Ignore errors on close
    
    _redis_client = None
    _connection_failed = False
    
    logger.info("Redis client reset")


async def health_check() -> bool:
    """
    Check Redis health.
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    try:
        redis_client = await get_redis_client()
        if redis_client is None:
            return False
        
        response = await redis_client.ping()
        return response is True
        
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False

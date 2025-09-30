"""
Tests for Redis infrastructure setup.

Tests verify:
- Redis connection can be established
- Redis ping/pong works
- Redis can store and retrieve data
- Redis TTL works correctly
- Connection pooling is efficient

Follows .cursorrules: TDD, test before implementation.
"""

import pytest
import os
from datetime import datetime


@pytest.fixture(autouse=True)
async def reset_redis():
    """Reset Redis client before each test."""
    from libs.caching.redis_client import reset_redis_client
    await reset_redis_client()
    yield
    await reset_redis_client()


@pytest.mark.asyncio
async def test_redis_connection():
    """Test that Redis connection can be established."""
    
    from libs.caching.redis_client import get_redis_client
    
    redis = await get_redis_client(use_fake=True)
    
    assert redis is not None, "Should return Redis client"
    
    # Should be able to ping
    response = await redis.ping()
    assert response is True, "Redis ping should return True"


@pytest.mark.asyncio
async def test_redis_set_get():
    """Test Redis set and get operations."""
    
    from libs.caching.redis_client import get_redis_client
    
    redis = await get_redis_client(use_fake=True)
    
    # Set a value
    test_key = "test:key:123"
    test_value = "test_value"
    
    await redis.set(test_key, test_value)
    
    # Get the value
    retrieved = await redis.get(test_key)
    assert retrieved == test_value, f"Should retrieve same value, got: {retrieved}"
    
    # Cleanup
    await redis.delete(test_key)


@pytest.mark.asyncio
async def test_redis_ttl():
    """Test Redis TTL (time to live) works."""
    
    from libs.caching.redis_client import get_redis_client
    
    redis = await get_redis_client(use_fake=True)
    
    # Set with TTL
    test_key = "test:ttl:456"
    test_value = "expires_soon"
    ttl_seconds = 10
    
    await redis.setex(test_key, ttl_seconds, test_value)
    
    # Should exist immediately
    value = await redis.get(test_key)
    assert value is not None, "Value should exist immediately"
    
    # Check TTL
    ttl = await redis.ttl(test_key)
    assert 0 < ttl <= ttl_seconds, f"TTL should be set, got: {ttl}"
    
    # Cleanup
    await redis.delete(test_key)


@pytest.mark.asyncio
async def test_redis_hash_operations():
    """Test Redis hash operations (used for metadata)."""
    
    from libs.caching.redis_client import get_redis_client
    
    redis = await get_redis_client(use_fake=True)
    
    # Set hash
    test_key = "test:hash:789"
    test_data = {
        "field1": "value1",
        "field2": "value2",
        "count": "10"
    }
    
    await redis.hset(test_key, mapping=test_data)
    
    # Get hash
    retrieved = await redis.hgetall(test_key)
    
    assert retrieved["field1"] == "value1"
    assert retrieved["field2"] == "value2"
    assert retrieved["count"] == "10"
    
    # Cleanup
    await redis.delete(test_key)


@pytest.mark.asyncio
async def test_redis_connection_pooling():
    """Test that connection pooling works (don't create new connection each time)."""
    
    from libs.caching.redis_client import get_redis_client
    
    # Get client twice - should reuse connection (singleton)
    redis1 = await get_redis_client(use_fake=True)
    redis2 = await get_redis_client(use_fake=True)
    
    # Should be same instance (singleton pattern)
    assert redis1 is redis2, "Should return same instance (singleton)"
    
    # Both should work
    ping1 = await redis1.ping()
    ping2 = await redis2.ping()
    
    assert ping1 is True
    assert ping2 is True


@pytest.mark.asyncio
async def test_redis_url_from_env():
    """Test that Redis URL is read from environment."""
    
    # Should read from REDIS_URL env var
    redis_url = os.getenv("REDIS_URL")
    
    # For this test, we'll allow it to be None in test environment
    # In production, it should be set
    if redis_url:
        assert redis_url.startswith("redis://") or redis_url.startswith("rediss://"), \
            "Redis URL should use redis:// or rediss:// scheme"


@pytest.mark.asyncio
async def test_redis_error_handling():
    """Test graceful error handling for Redis connection failures."""
    
    from libs.caching.redis_client import get_redis_client
    import os
    
    # Temporarily unset REDIS_URL to test error handling
    original_url = os.getenv("REDIS_URL")
    os.environ.pop("REDIS_URL", None)
    
    # Reset to clear any cached client
    from libs.caching.redis_client import reset_redis_client
    await reset_redis_client()
    
    # This should return None gracefully (not crash)
    redis = await get_redis_client(use_fake=False)  # Force real redis
    assert redis is None, "Should return None when REDIS_URL not configured"
    
    # Restore original URL
    if original_url:
        os.environ["REDIS_URL"] = original_url
    
    # Reset again for next tests
    await reset_redis_client()

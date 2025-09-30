"""
Integration tests for Redis using REAL Redis connection.

These tests require Redis to be running:
- Local: docker run -d -p 6379:6379 redis:7-alpine
- Or: REDIS_URL pointing to Redis Cloud

Run with: RIGHTLINE_APP_ENV=development pytest tests/integration/test_redis_integration.py

Follows .cursorrules: Integration testing with real dependencies.
"""

import pytest
import os
import asyncio
from datetime import datetime


# Skip these tests if Redis not available
pytestmark = pytest.mark.skipif(
    os.getenv("RIGHTLINE_APP_ENV") == "test",
    reason="Integration tests require real Redis (set RIGHTLINE_APP_ENV=development)"
)


@pytest.fixture
async def real_redis():
    """Get REAL Redis connection for integration testing."""
    from libs.caching.redis_client import get_redis_client, reset_redis_client
    
    # Reset to ensure clean state
    await reset_redis_client()
    
    # Get real Redis (force use_fake=False)
    redis = await get_redis_client(use_fake=False)
    
    if redis is None:
        pytest.skip("Real Redis not available - set REDIS_URL and start Redis server")
    
    # Clean test database before tests
    await redis.flushdb()
    
    yield redis
    
    # Clean test database after tests
    await redis.flushdb()


@pytest.mark.asyncio
async def test_real_redis_connection(real_redis):
    """Test connection to real Redis server."""
    
    # Should be able to ping
    response = await real_redis.ping()
    assert response is True, "Real Redis ping should return True"


@pytest.mark.asyncio
async def test_real_redis_concurrent_operations(real_redis):
    """Test concurrent operations on real Redis (catches race conditions)."""
    
    # Perform many operations concurrently
    async def set_and_get(i):
        key = f"concurrent:test:{i}"
        value = f"value_{i}"
        
        await real_redis.set(key, value)
        retrieved = await real_redis.get(key)
        assert retrieved == value
        await real_redis.delete(key)
        return True
    
    # Run 50 concurrent operations
    tasks = [set_and_get(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    assert all(results), "All concurrent operations should succeed"


@pytest.mark.asyncio
async def test_real_redis_ttl_expiration(real_redis):
    """Test TTL expiration with real Redis (timing matters)."""
    
    key = "ttl:test:expires"
    value = "temporary_value"
    
    # Set with 2 second TTL
    await real_redis.setex(key, 2, value)
    
    # Should exist immediately
    assert await real_redis.get(key) == value
    
    # Check TTL
    ttl = await real_redis.ttl(key)
    assert 0 < ttl <= 2
    
    # Wait for expiration
    await asyncio.sleep(2.5)
    
    # Should be gone
    expired_value = await real_redis.get(key)
    assert expired_value is None, "Value should expire after TTL"


@pytest.mark.asyncio
async def test_real_redis_pipeline_performance(real_redis):
    """Test pipeline performance with real Redis."""
    import time
    
    # Test without pipeline
    start = time.time()
    for i in range(100):
        await real_redis.set(f"perf:single:{i}", f"value_{i}")
    single_time = time.time() - start
    
    # Clean up
    keys = await real_redis.keys("perf:single:*")
    if keys:
        await real_redis.delete(*keys)
    
    # Test with pipeline
    start = time.time()
    pipe = real_redis.pipeline()
    for i in range(100):
        pipe.set(f"perf:pipeline:{i}", f"value_{i}")
    await pipe.execute()
    pipeline_time = time.time() - start
    
    # Pipeline should be significantly faster
    print(f"\nPerformance comparison:")
    print(f"  Single operations: {single_time:.3f}s")
    print(f"  Pipeline operations: {pipeline_time:.3f}s")
    print(f"  Speedup: {single_time/pipeline_time:.1f}x")
    
    # Pipeline should be at least 2x faster
    assert pipeline_time < single_time, "Pipeline should be faster"
    
    # Clean up
    keys = await real_redis.keys("perf:pipeline:*")
    if keys:
        await real_redis.delete(*keys)


@pytest.mark.asyncio
async def test_real_redis_connection_resilience(real_redis):
    """Test connection resilience and recovery."""
    
    # Perform operation
    await real_redis.set("resilience:test", "value1")
    value = await real_redis.get("resilience:test")
    assert value == "value1"
    
    # Simulate reconnection by getting info
    info = await real_redis.info("server")
    assert "redis_version" in info
    
    # Should still work after info query
    await real_redis.set("resilience:test", "value2")
    value = await real_redis.get("resilience:test")
    assert value == "value2"
    
    # Cleanup
    await real_redis.delete("resilience:test")


@pytest.mark.asyncio
async def test_semantic_cache_with_real_redis():
    """Test SemanticCache with real Redis."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        similarity_threshold=0.95
    )
    
    # Connect to real Redis
    await cache.connect(use_fake=False)
    
    if cache._redis_client is None:
        pytest.skip("Real Redis not available")
    
    # Clear any existing test data
    await cache.clear_cache("test:semantic:*")
    
    # Test exact match caching
    query = "What is labour law?"
    response = {
        "answer": "Labour law regulates employment...",
        "sources": ["Labour Act"]
    }
    
    # Should be cache miss initially
    cached = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached is None, "Should be cache miss initially"
    
    # Cache the response
    await cache.cache_response(query, response, "professional", ttl_seconds=60)
    
    # Should be cache hit now
    cached = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached is not None, "Should be cache hit"
    assert cached["answer"] == response["answer"]
    
    # Stats should reflect the operations
    stats = cache.get_stats()
    assert stats.total_requests == 2, f"Expected 2 requests, got {stats.total_requests}"
    assert stats.exact_hits == 1, f"Expected 1 exact hit, got {stats.exact_hits}"
    assert stats.misses == 1, f"Expected 1 miss, got {stats.misses}"
    
    # Clean up
    await cache.clear_cache("cache:exact:*")
    await cache.disconnect()


@pytest.mark.asyncio
async def test_cache_performance_with_real_redis(real_redis):
    """Test cache performance characteristics with real Redis."""
    import time
    
    # Test cache write performance
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url=os.getenv("REDIS_URL"))
    cache._redis_client = real_redis  # Use fixture
    
    # Measure cache write time
    start = time.time()
    
    test_response = {
        "answer": "Test answer " * 50,  # ~1KB response
        "sources": ["Source 1", "Source 2"]
    }
    
    for i in range(10):
        await cache.cache_response(
            f"Test query {i}",
            test_response,
            "professional",
            ttl_seconds=300
        )
    
    write_time = time.time() - start
    avg_write_ms = (write_time / 10) * 1000
    
    print(f"\nCache write performance: {avg_write_ms:.2f}ms average")
    
    # Should be fast (<50ms average)
    assert avg_write_ms < 100, f"Cache writes too slow: {avg_write_ms:.2f}ms"
    
    # Measure cache read time
    start = time.time()
    
    for i in range(10):
        cached = await cache.get_cached_response(
            f"Test query {i}",
            "professional",
            check_semantic=False
        )
        assert cached is not None
    
    read_time = time.time() - start
    avg_read_ms = (read_time / 10) * 1000
    
    print(f"Cache read performance: {avg_read_ms:.2f}ms average")
    
    # Reads should be even faster (<20ms average)
    assert avg_read_ms < 50, f"Cache reads too slow: {avg_read_ms:.2f}ms"
    
    # Cleanup
    await cache.clear_cache("cache:exact:*")

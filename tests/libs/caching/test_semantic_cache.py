"""
Tests for SemanticCache implementation.

Tests verify:
- Cache initialization and connection
- Exact match caching (hash-based)
- Statistics tracking
- Error handling

Follows .cursorrules: TDD, comprehensive coverage, async testing.
"""

import pytest
from datetime import datetime


@pytest.fixture
async def semantic_cache():
    """Create SemanticCache instance for testing."""
    from libs.caching.semantic_cache import SemanticCache
    
    # Use test Redis URL
    cache = SemanticCache(
        redis_url="redis://localhost:6379/9",  # Test DB
        similarity_threshold=0.95,
        default_ttl=3600
    )
    
    # Connect with fakeredis
    await cache.connect(use_fake=True)
    
    yield cache
    
    # Cleanup
    await cache.disconnect()


@pytest.mark.asyncio
async def test_semantic_cache_initialization():
    """Test SemanticCache can be initialized."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(
        redis_url="redis://localhost:6379/9",
        similarity_threshold=0.95
    )
    
    assert cache.redis_url == "redis://localhost:6379/9"
    assert cache.similarity_threshold == 0.95
    assert cache._redis_client is None  # Not connected yet


@pytest.mark.asyncio
async def test_semantic_cache_connect(semantic_cache):
    """Test SemanticCache connection."""
    
    assert semantic_cache._redis_client is not None, "Should be connected"
    
    # Should be able to ping
    response = await semantic_cache._redis_client.ping()
    assert response is True


@pytest.mark.asyncio
async def test_semantic_cache_disconnect(semantic_cache):
    """Test SemanticCache disconnect."""
    
    # Should be connected initially
    assert semantic_cache._redis_client is not None
    
    # Disconnect
    await semantic_cache.disconnect()
    
    # Should be None after disconnect
    assert semantic_cache._redis_client is None


@pytest.mark.asyncio
async def test_get_exact_cache_key():
    """Test exact cache key generation."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    
    # Test query normalization
    query1 = "What is labour law?"
    query2 = "what is labour law?"  # Different case
    query3 = "  What   is  labour law?  "  # Extra whitespace
    
    key1 = cache._get_exact_cache_key(query1, "professional")
    key2 = cache._get_exact_cache_key(query2, "professional")
    key3 = cache._get_exact_cache_key(query3, "professional")
    
    # Should normalize to same key
    assert key1 == key2 == key3, "Should normalize queries to same key"
    
    # Different user types should have different keys
    key_professional = cache._get_exact_cache_key(query1, "professional")
    key_citizen = cache._get_exact_cache_key(query1, "citizen")
    
    assert key_professional != key_citizen, "Different user types should have different keys"


@pytest.mark.asyncio
async def test_cache_stats_initialization():
    """Test cache statistics initialization."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    
    stats = cache.get_stats()
    
    assert stats.total_requests == 0
    assert stats.exact_hits == 0
    assert stats.semantic_hits == 0
    assert stats.misses == 0
    assert stats.hit_rate == 0.0


@pytest.mark.asyncio
async def test_cache_stats_tracking(semantic_cache):
    """Test that cache statistics are tracked correctly."""
    
    # Initial stats
    stats = semantic_cache.get_stats()
    assert stats.total_requests == 0
    
    # This will be a cache miss
    result = await semantic_cache.get_cached_response(
        query="Test query",
        user_type="professional",
        check_semantic=False  # Skip semantic for speed
    )
    
    assert result is None, "Should be cache miss"
    
    # Check stats updated
    stats = semantic_cache.get_stats()
    assert stats.total_requests == 1, "Should increment total_requests"
    assert stats.misses == 1, "Should track miss"
    assert stats.hit_rate == 0.0, "Hit rate should be 0 with no hits"


@pytest.mark.asyncio
async def test_connect_multiple_times():
    """Test that connecting multiple times doesn't create issues."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    
    # Connect multiple times
    await cache.connect()
    await cache.connect()  # Should not error
    await cache.connect()
    
    # Should still be connected
    assert cache._redis_client is not None
    
    await cache.disconnect()


@pytest.mark.asyncio
async def test_disconnect_without_connect():
    """Test that disconnecting without connecting doesn't crash."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    
    # Disconnect without connecting - should not crash
    await cache.disconnect()
    
    # Should be fine
    assert cache._redis_client is None

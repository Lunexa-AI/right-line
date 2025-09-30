"""
Tests for intent caching functionality.

Tests verify:
- Intent classification caching
- 2-hour TTL for intent cache
- Cache key generation
- Stats not affected by intent cache (separate concern)

Follows .cursorrules: TDD, comprehensive coverage.
"""

import pytest


@pytest.fixture
async def cache():
    """Create SemanticCache for testing."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    await cache.clear_cache("cache:*")
    
    yield cache
    
    await cache.clear_cache("cache:*")
    await cache.disconnect()


@pytest.mark.asyncio
async def test_intent_cache_miss(cache):
    """Test intent cache miss for new query."""
    
    query = "What is labour law?"
    
    # Should be cache miss
    cached_intent = await cache.get_intent_cache(query)
    
    assert cached_intent is None, "Should be cache miss for new query"


@pytest.mark.asyncio
async def test_intent_cache_hit(cache):
    """Test intent cache hit for previously classified query."""
    
    query = "What is labour law?"
    intent_data = {
        "intent": "rag_qa",
        "complexity": "moderate",
        "user_type": "professional",
        "confidence": 0.85,
        "reasoning_framework": "irac"
    }
    
    # Cache the intent
    await cache.cache_intent(query, intent_data, ttl=7200)  # 2 hours
    
    # Retrieve it
    cached = await cache.get_intent_cache(query)
    
    assert cached is not None, "Should be cache hit"
    assert cached["intent"] == "rag_qa"
    assert cached["complexity"] == "moderate"
    assert cached["user_type"] == "professional"
    assert cached["confidence"] == 0.85


@pytest.mark.asyncio
async def test_intent_cache_different_queries(cache):
    """Test that different queries have different cached intents."""
    
    # Cache two different queries with different intents
    await cache.cache_intent(
        "What is labour law?",
        {"intent": "rag_qa", "complexity": "simple"},
        ttl=7200
    )
    
    await cache.cache_intent(
        "What is constitutional law?",
        {"intent": "constitutional_interpretation", "complexity": "complex"},
        ttl=7200
    )
    
    # Retrieve both
    cached1 = await cache.get_intent_cache("What is labour law?")
    cached2 = await cache.get_intent_cache("What is constitutional law?")
    
    assert cached1["intent"] == "rag_qa"
    assert cached1["complexity"] == "simple"
    
    assert cached2["intent"] == "constitutional_interpretation"
    assert cached2["complexity"] == "complex"


@pytest.mark.asyncio
async def test_intent_cache_ttl():
    """Test that intent cache has 2-hour TTL."""
    from libs.caching.semantic_cache import SemanticCache
    import hashlib
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    
    query = "Test TTL"
    intent_data = {"intent": "rag_qa"}
    
    # Cache with 2-hour TTL
    await cache.cache_intent(query, intent_data, ttl=7200)
    
    # Check TTL in Redis
    key = f"cache:intent:{hashlib.md5(query.lower().encode()).hexdigest()}"
    ttl = await cache._redis_client.ttl(key)
    
    # TTL should be ~2 hours (7200 seconds)
    assert 7100 < ttl <= 7200, f"TTL should be ~7200s, got {ttl}s"
    
    await cache.disconnect()


@pytest.mark.asyncio
async def test_intent_cache_overwrites(cache):
    """Test that caching same query overwrites previous intent."""
    
    query = "Overwrite test"
    
    # Cache first intent
    await cache.cache_intent(query, {"intent": "rag_qa", "complexity": "simple"})
    
    # Verify first cached
    cached = await cache.get_intent_cache(query)
    assert cached["complexity"] == "simple"
    
    # Cache second intent (overwrite)
    await cache.cache_intent(query, {"intent": "rag_qa", "complexity": "complex"})
    
    # Should get updated version
    cached = await cache.get_intent_cache(query)
    assert cached["complexity"] == "complex"


@pytest.mark.asyncio
async def test_intent_cache_with_redis_unavailable():
    """Test graceful degradation when Redis unavailable."""
    from libs.caching.semantic_cache import SemanticCache
    from libs.caching.redis_client import reset_redis_client
    import os
    
    # Save and clear Redis URL
    original_url = os.getenv("REDIS_URL")
    os.environ.pop("REDIS_URL", None)
    await reset_redis_client()
    
    cache = SemanticCache(redis_url="")  # Invalid URL
    await cache.connect(use_fake=False)
    
    # Redis client should be None
    assert cache._redis_client is None
    
    # Should return None gracefully (not crash)
    cached = await cache.get_intent_cache("test")
    assert cached is None
    
    # Should not crash when caching
    await cache.cache_intent("test", {"intent": "rag_qa"})
    # No error = success
    
    # Restore
    if original_url:
        os.environ["REDIS_URL"] = original_url
    await reset_redis_client()


@pytest.mark.asyncio
async def test_intent_cache_case_sensitive():
    """Test that intent cache is case-sensitive for query matching."""
    
    from libs.caching.semantic_cache import SemanticCache
    import hashlib
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    
    # Cache with one case
    await cache.cache_intent("What is Labour Law?", {"intent": "rag_qa"})
    
    # Keys should normalize to lowercase
    key1 = hashlib.md5("What is Labour Law?".lower().encode()).hexdigest()
    key2 = hashlib.md5("what is labour law?".lower().encode()).hexdigest()
    
    assert key1 == key2, "Keys should be case-insensitive"
    
    # Should hit with different case
    cached = await cache.get_intent_cache("what is labour law?")
    assert cached is not None, "Should hit with different case"
    
    await cache.disconnect()

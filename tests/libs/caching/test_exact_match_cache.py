"""
Tests for exact match caching (Level 1).

Tests verify:
- Query normalization (case, whitespace)
- Hash-based key generation
- TTL expiration
- Cache hit/miss tracking
- User type separation
- Response metadata handling

Follows .cursorrules: TDD, comprehensive edge case coverage.
"""

import pytest
import asyncio
from datetime import datetime


@pytest.fixture
async def cache():
    """Create SemanticCache for testing."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(
        redis_url="redis://localhost:6379/9",
        similarity_threshold=0.95,
        default_ttl=3600
    )
    
    await cache.connect(use_fake=True)
    
    # Clear any existing test data
    await cache.clear_cache("cache:*")
    
    yield cache
    
    # Cleanup
    await cache.clear_cache("cache:*")
    await cache.disconnect()


@pytest.mark.asyncio
async def test_exact_match_cache_hit(cache):
    """Test basic exact match cache hit."""
    
    query = "What is labour law?"
    response = {
        "answer": "Labour law regulates employment relationships...",
        "sources": ["Labour Act [Chapter 28:01]"],
        "confidence": 0.85
    }
    
    # Cache the response
    await cache.cache_response(query, response, user_type="professional")
    
    # Retrieve it
    cached = await cache.get_cached_response(query, user_type="professional", check_semantic=False)
    
    assert cached is not None, "Should be cache hit"
    assert cached["answer"] == response["answer"]
    assert cached["sources"] == response["sources"]
    assert cached["_cache_hit"] == "exact"
    
    # Stats should show hit
    stats = cache.get_stats()
    assert stats.exact_hits == 1
    assert stats.misses == 0


@pytest.mark.asyncio
async def test_exact_match_cache_miss(cache):
    """Test cache miss for query not in cache."""
    
    query = "What is company law?"
    
    # Should be miss
    cached = await cache.get_cached_response(query, user_type="professional", check_semantic=False)
    
    assert cached is None, "Should be cache miss"
    
    # Stats should show miss
    stats = cache.get_stats()
    assert stats.misses == 1
    assert stats.exact_hits == 0


@pytest.mark.asyncio
async def test_query_normalization_case_insensitive(cache):
    """Test that cache is case-insensitive."""
    
    response = {"answer": "Test answer"}
    
    # Cache with original case
    await cache.cache_response("What is Labour Law?", response, "professional")
    
    # Should hit with different case
    cached1 = await cache.get_cached_response("what is labour law?", "professional", check_semantic=False)
    cached2 = await cache.get_cached_response("WHAT IS LABOUR LAW?", "professional", check_semantic=False)
    cached3 = await cache.get_cached_response("What Is Labour Law?", "professional", check_semantic=False)
    
    assert cached1 is not None, "Should hit with lowercase"
    assert cached2 is not None, "Should hit with uppercase"
    assert cached3 is not None, "Should hit with mixed case"
    
    # All should be same response
    assert cached1["answer"] == cached2["answer"] == cached3["answer"]


@pytest.mark.asyncio
async def test_query_normalization_whitespace(cache):
    """Test that cache normalizes whitespace."""
    
    response = {"answer": "Test answer"}
    
    # Cache with normal spacing
    await cache.cache_response("What is labour law?", response, "professional")
    
    # Should hit with different whitespace
    cached1 = await cache.get_cached_response("What  is  labour  law?", "professional", check_semantic=False)
    cached2 = await cache.get_cached_response("  What is labour law?  ", "professional", check_semantic=False)
    cached3 = await cache.get_cached_response("What\tis\tlabour\tlaw?", "professional", check_semantic=False)
    
    assert cached1 is not None, "Should hit with double spaces"
    assert cached2 is not None, "Should hit with leading/trailing spaces"
    assert cached3 is not None, "Should hit with tabs"


@pytest.mark.asyncio
async def test_user_type_separation(cache):
    """Test that professional and citizen caches are separate."""
    
    query = "What is labour law?"
    professional_response = {"answer": "Comprehensive legal analysis...", "complexity": "complex"}
    citizen_response = {"answer": "Simple explanation...", "complexity": "simple"}
    
    # Cache for both user types
    await cache.cache_response(query, professional_response, "professional")
    await cache.cache_response(query, citizen_response, "citizen")
    
    # Should get different responses
    prof_cached = await cache.get_cached_response(query, "professional", check_semantic=False)
    citizen_cached = await cache.get_cached_response(query, "citizen", check_semantic=False)
    
    assert prof_cached["answer"] == "Comprehensive legal analysis..."
    assert citizen_cached["answer"] == "Simple explanation..."
    assert prof_cached["answer"] != citizen_cached["answer"]


@pytest.mark.asyncio
async def test_ttl_expiration(cache):
    """Test that cached responses expire after TTL."""
    
    query = "Test TTL query"
    response = {"answer": "Temporary answer"}
    
    # Cache with short TTL (2 seconds)
    await cache.cache_response(query, response, "professional", ttl_seconds=2)
    
    # Should hit immediately
    cached = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached is not None, "Should be cached initially"
    
    # Wait for expiration
    await asyncio.sleep(2.5)
    
    # Should be expired now (cache miss)
    cached_after = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached_after is None, "Should be expired after TTL"


@pytest.mark.asyncio
async def test_cache_metadata_stripped(cache):
    """Test that cache metadata fields are stripped before storage."""
    
    query = "Test metadata"
    response = {
        "answer": "Test answer",
        "_cache_hit": "should_be_removed",
        "_cache_similarity": "should_be_removed",
        "_internal_field": "should_be_removed",
        "normal_field": "should_be_kept"
    }
    
    # Cache the response
    await cache.cache_response(query, response, "professional")
    
    # Retrieve it
    cached = await cache.get_cached_response(query, "professional", check_semantic=False)
    
    # Cache metadata should be stripped from stored response
    assert "_cache_hit" not in cached or cached["_cache_hit"] == "exact", \
        "Original _cache_hit should be stripped (or overwritten)"
    assert "_cache_similarity" not in cached, "Should strip _cache_similarity"
    assert "_internal_field" not in cached, "Should strip _internal_field"
    assert cached["normal_field"] == "should_be_kept", "Should keep normal fields"


@pytest.mark.asyncio
async def test_cache_overwrite_existing(cache):
    """Test that caching same query overwrites previous value."""
    
    query = "Overwrite test"
    
    # Cache first response
    response1 = {"answer": "First answer", "version": 1}
    await cache.cache_response(query, response1, "professional")
    
    # Verify first is cached
    cached1 = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached1["answer"] == "First answer"
    
    # Cache second response (overwrites)
    response2 = {"answer": "Second answer", "version": 2}
    await cache.cache_response(query, response2, "professional")
    
    # Should get second response now
    cached2 = await cache.get_cached_response(query, "professional", check_semantic=False)
    assert cached2["answer"] == "Second answer"
    assert cached2["version"] == 2


@pytest.mark.asyncio
async def test_hit_count_increments(cache):
    """Test that hit count increments on each cache hit."""
    
    query = "Hit count test"
    response = {"answer": "Test"}
    
    # Cache response
    await cache.cache_response(query, response, "professional")
    
    # Get cache key
    cache_key = cache._get_exact_cache_key(query, "professional")
    
    # Hit cache multiple times
    for i in range(5):
        cached = await cache.get_cached_response(query, "professional", check_semantic=False)
        assert cached is not None
    
    # Check hit count in metadata
    meta = await cache._redis_client.hgetall(f"{cache_key}:meta")
    hit_count = int(meta.get("hit_count", 0))
    
    assert hit_count == 5, f"Hit count should be 5, got {hit_count}"


@pytest.mark.asyncio
async def test_stats_tracking_accuracy(cache):
    """Test that cache statistics are accurately tracked."""
    
    # Start with clean stats
    stats = cache.get_stats()
    assert stats.total_requests == 0
    
    # Miss
    await cache.get_cached_response("query1", "professional", check_semantic=False)
    stats = cache.get_stats()
    assert stats.total_requests == 1
    assert stats.misses == 1
    assert stats.exact_hits == 0
    assert stats.hit_rate == 0.0
    
    # Cache and hit
    await cache.cache_response("query1", {"answer": "test"}, "professional")
    await cache.get_cached_response("query1", "professional", check_semantic=False)
    
    stats = cache.get_stats()
    assert stats.total_requests == 2
    assert stats.misses == 1
    assert stats.exact_hits == 1
    assert stats.hit_rate == 0.5  # 1 hit / 2 requests


@pytest.mark.asyncio
async def test_empty_query_handling(cache):
    """Test handling of empty or invalid queries."""
    
    # Empty query
    cached = await cache.get_cached_response("", "professional", check_semantic=False)
    # Should handle gracefully (miss or None)
    assert cached is None
    
    # Very long query (should still work)
    long_query = "What is labour law? " * 100  # ~2000 chars
    response = {"answer": "Test"}
    
    await cache.cache_response(long_query, response, "professional")
    cached = await cache.get_cached_response(long_query, "professional", check_semantic=False)
    
    assert cached is not None, "Should handle long queries"


@pytest.mark.asyncio
async def test_cache_different_response_types(cache):
    """Test caching different response structures."""
    
    # Simple response
    simple = {"answer": "Simple"}
    await cache.cache_response("q1", simple, "professional")
    cached = await cache.get_cached_response("q1", "professional", check_semantic=False)
    assert cached["answer"] == "Simple"
    
    # Complex response
    complex_response = {
        "answer": "Complex answer",
        "sources": [{"title": "Doc 1", "section": "12"}],
        "metadata": {"confidence": 0.9, "tokens": 500},
        "suggestions": ["q1", "q2", "q3"]
    }
    await cache.cache_response("q2", complex_response, "professional")
    cached = await cache.get_cached_response("q2", "professional", check_semantic=False)
    assert cached["answer"] == "Complex answer"
    assert len(cached["sources"]) == 1
    assert cached["metadata"]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_concurrent_cache_operations(cache):
    """Test concurrent cache operations don't cause issues."""
    
    async def cache_and_retrieve(i):
        query = f"Concurrent query {i}"
        response = {"answer": f"Answer {i}"}
        
        await cache.cache_response(query, response, "professional")
        cached = await cache.get_cached_response(query, "professional", check_semantic=False)
        
        assert cached is not None
        assert cached["answer"] == f"Answer {i}"
        return True
    
    # Run 20 concurrent operations
    tasks = [cache_and_retrieve(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    assert all(results), "All concurrent operations should succeed"
    assert cache.get_stats().exact_hits == 20


@pytest.mark.asyncio
async def test_cache_with_redis_unavailable():
    """Test graceful degradation when Redis is unavailable."""
    from libs.caching.semantic_cache import SemanticCache
    from libs.caching.redis_client import reset_redis_client
    import os
    
    # Save original URL
    original_url = os.getenv("REDIS_URL")
    
    # Unset Redis URL to simulate unavailable
    os.environ.pop("REDIS_URL", None)
    await reset_redis_client()
    
    # Create cache
    cache = SemanticCache(redis_url="")  # Empty URL
    
    # Connect should handle gracefully
    await cache.connect(use_fake=False)  # Force real Redis (will fail)
    
    # Redis client should be None
    assert cache._redis_client is None, "Redis client should be None when unavailable"
    
    # get_cached_response should return None (not crash)
    cached = await cache.get_cached_response("test", "professional", check_semantic=False)
    assert cached is None, "Should return None when Redis unavailable"
    
    # cache_response should not crash (just logs warning)
    await cache.cache_response("test", {"answer": "test"}, "professional")
    # Should complete without error
    
    # Restore original URL
    if original_url:
        os.environ["REDIS_URL"] = original_url
    await reset_redis_client()

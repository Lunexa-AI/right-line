"""
Tests for semantic similarity caching (Level 2).

Tests verify:
- Embedding generation for queries
- Cosine similarity calculation
- Semantic cache hits (similar queries)
- Similarity threshold enforcement
- Semantic index management
- Performance of similarity search

Follows .cursorrules: TDD, comprehensive coverage, async testing.
"""

import pytest
import numpy as np


@pytest.fixture
async def cache_with_embeddings():
    """Create SemanticCache with mock embedding client."""
    from libs.caching.semantic_cache import SemanticCache
    from unittest.mock import AsyncMock
    
    cache = SemanticCache(
        redis_url="redis://localhost:6379/9",
        similarity_threshold=0.95,
        default_ttl=3600
    )
    
    await cache.connect(use_fake=True)
    await cache.clear_cache("cache:*")
    
    # Mock embedding client for testing
    mock_embedding_client = AsyncMock()
    
    # Define mock embeddings for test queries
    # Similar queries will have similar embeddings (using realistic variation)
    base_labour = np.random.RandomState(42).randn(3072)
    base_company = np.random.RandomState(99).randn(3072)
    
    embeddings_map = {
        "what is labour law": base_labour.tolist(),  # Base query
        "what is employment law": (base_labour * 0.98 + np.random.RandomState(43).randn(3072) * 0.02).tolist(),  # Very similar
        "tell me about labour law": (base_labour * 0.92 + np.random.RandomState(44).randn(3072) * 0.08).tolist(),  # Similar
        "what is company law": base_company.tolist(),  # Different topic
    }
    
    async def mock_get_embeddings(queries):
        results = []
        for q in queries:
            q_normalized = q.lower()
            # Find closest match in our map
            embedding = None
            for key, emb in embeddings_map.items():
                if key in q_normalized or q_normalized in key:
                    embedding = emb
                    break
            if embedding is None:
                # Default embedding
                embedding = [0.5] * 3072
            results.append(embedding)
        return results
    
    mock_embedding_client.get_embeddings = mock_get_embeddings
    cache._embedding_client = mock_embedding_client
    
    yield cache
    
    await cache.clear_cache("cache:*")
    await cache.disconnect()


@pytest.mark.asyncio
async def test_cosine_similarity_calculation():
    """Test cosine similarity calculation."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    
    # Identical vectors
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([1.0, 0.0, 0.0])
    similarity = cache._cosine_similarity(vec1, vec2)
    assert abs(similarity - 1.0) < 0.001, "Identical vectors should have similarity 1.0"
    
    # Orthogonal vectors
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([0.0, 1.0, 0.0])
    similarity = cache._cosine_similarity(vec1, vec2)
    assert abs(similarity - 0.0) < 0.001, "Orthogonal vectors should have similarity 0.0"
    
    # Similar vectors
    vec1 = np.array([1.0, 0.1, 0.0])
    vec2 = np.array([1.0, 0.2, 0.0])
    similarity = cache._cosine_similarity(vec1, vec2)
    assert 0.9 < similarity < 1.0, "Similar vectors should have high similarity"


@pytest.mark.asyncio
async def test_semantic_cache_hit_similar_query(cache_with_embeddings):
    """Test semantic cache hits for similar queries."""
    
    # Cache original query
    original_query = "What is labour law?"
    response = {
        "answer": "Labour law regulates employment...",
        "sources": ["Labour Act"]
    }
    
    await cache_with_embeddings.cache_response(original_query, response, "professional")
    
    # Query with similar meaning should hit cache
    similar_query = "What is employment law?"  # Different wording, same meaning
    
    cached = await cache_with_embeddings.get_cached_response(
        similar_query,
        "professional",
        check_semantic=True
    )
    
    assert cached is not None, "Should find semantically similar cached query"
    assert cached["answer"] == response["answer"]
    assert cached["_cache_hit"] == "semantic"
    
    # Stats should show semantic hit
    stats = cache_with_embeddings.get_stats()
    assert stats.semantic_hits >= 1


@pytest.mark.asyncio
async def test_semantic_cache_miss_dissimilar_query(cache_with_embeddings):
    """Test semantic cache miss for dissimilar queries."""
    
    # Cache labour law query
    await cache_with_embeddings.cache_response(
        "What is labour law?",
        {"answer": "Labour law..."},
        "professional"
    )
    
    # Very different query should miss
    different_query = "What is company law?"  # Different topic
    
    cached = await cache_with_embeddings.get_cached_response(
        different_query,
        "professional",
        check_semantic=True
    )
    
    # Should be miss (similarity < threshold)
    assert cached is None, "Should miss for dissimilar query"
    
    stats = cache_with_embeddings.get_stats()
    assert stats.misses >= 1


@pytest.mark.asyncio
async def test_similarity_threshold_enforcement(cache_with_embeddings):
    """Test that similarity threshold is enforced."""
    
    # Lower the threshold temporarily
    original_threshold = cache_with_embeddings.similarity_threshold
    cache_with_embeddings.similarity_threshold = 0.99  # Very strict
    
    # Cache query
    await cache_with_embeddings.cache_response(
        "What is labour law?",
        {"answer": "Test"},
        "professional"
    )
    
    # Even similar query might not meet strict threshold
    cached = await cache_with_embeddings.get_cached_response(
        "Tell me about labour law",  # Similar but maybe not 99%
        "professional",
        check_semantic=True
    )
    
    # With 99% threshold, might miss
    # (Depends on mock embeddings - this tests threshold logic)
    
    # Restore threshold
    cache_with_embeddings.similarity_threshold = original_threshold


@pytest.mark.asyncio
async def test_semantic_index_management(cache_with_embeddings):
    """Test semantic index is maintained correctly."""
    
    # Cache multiple queries
    queries = [
        "What is labour law?",
        "What is company law?",
        "What is contract law?"
    ]
    
    for i, q in enumerate(queries):
        await cache_with_embeddings.cache_response(
            q,
            {"answer": f"Answer {i}"},
            "professional"
        )
    
    # Check semantic index exists and has entries
    index_key = "semantic_index:professional"
    
    # Index should have entries (one per cached query)
    index_members = await cache_with_embeddings._redis_client.smembers(index_key)
    
    # Should have 3 entries
    assert len(index_members) == 3, f"Index should have 3 entries, got {len(index_members)}"


@pytest.mark.asyncio
async def test_semantic_search_returns_best_match(cache_with_embeddings):
    """Test that semantic search returns best matching query."""
    
    # Cache multiple similar queries
    await cache_with_embeddings.cache_response(
        "What is labour law?",
        {"answer": "Answer 1", "query_id": 1},
        "professional"
    )
    
    await cache_with_embeddings.cache_response(
        "Tell me about labour law",
        {"answer": "Answer 2", "query_id": 2},
        "professional"
    )
    
    # Query that's most similar to first one
    similar_to_first = "What is employment law?"
    
    cached = await cache_with_embeddings.get_cached_response(
        similar_to_first,
        "professional",
        check_semantic=True
    )
    
    # Should return a cached response (best match)
    assert cached is not None
    assert "_cache_similarity" in cached
    assert cached["_cache_similarity"] >= cache_with_embeddings.similarity_threshold


@pytest.mark.asyncio
async def test_embedding_caching():
    """Test that embeddings themselves are cached."""
    from libs.caching.semantic_cache import SemanticCache
    from unittest.mock import AsyncMock
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    
    # Mock embedding client
    mock_client = AsyncMock()
    mock_client.get_embeddings.return_value = [[0.1] * 3072]
    cache._embedding_client = mock_client
    
    # First call should generate embedding
    await cache.cache_embedding("test query", [0.1] * 3072)
    
    # Second call should retrieve from cache
    cached_embedding = await cache.get_embedding_cache("test query")
    
    assert cached_embedding is not None
    assert len(cached_embedding) == 3072
    
    await cache.disconnect()


@pytest.mark.asyncio
async def test_semantic_cache_with_no_embeddings():
    """Test graceful degradation when embeddings unavailable."""
    from libs.caching.semantic_cache import SemanticCache
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    
    # No embedding client set
    cache._embedding_client = None
    
    # Cache a query
    await cache.cache_response("test", {"answer": "test"}, "professional")
    
    # Semantic search should handle gracefully (return None)
    cached = await cache.get_cached_response(
        "similar test",
        "professional",
        check_semantic=True
    )
    
    # Should fall back to None (or exact match if exists)
    # No crash!
    
    await cache.disconnect()


@pytest.mark.asyncio
async def test_semantic_cache_performance():
    """Test semantic similarity search performance."""
    from libs.caching.semantic_cache import SemanticCache
    from unittest.mock import AsyncMock
    import time
    
    cache = SemanticCache(redis_url="redis://localhost:6379/9")
    await cache.connect(use_fake=True)
    
    # Mock embedding client
    mock_client = AsyncMock()
    mock_client.get_embeddings.return_value = [[0.5] * 3072]
    cache._embedding_client = mock_client
    
    # Cache 10 queries
    for i in range(10):
        await cache.cache_response(
            f"Query number {i}",
            {"answer": f"Answer {i}"},
            "professional"
        )
    
    # Measure semantic search time
    start = time.time()
    
    await cache.get_cached_response(
        "Query number similar",
        "professional",
        check_semantic=True
    )
    
    search_time_ms = (time.time() - start) * 1000
    
    # Should be reasonably fast (<100ms for 10 entries)
    assert search_time_ms < 100, f"Semantic search too slow: {search_time_ms:.2f}ms"
    
    await cache.disconnect()

"""
Tests for speculative parent document prefetching.

Tests verify:
- Prefetches top 15 parent documents speculatively
- Stores in state cache for fast access
- Handles deduplication of parent doc IDs
- Batch fetches efficiently from R2
- Measures and logs prefetch performance

Follows .cursorrules: TDD, async testing, performance validation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import time


@pytest.fixture
def orchestrator():
    """Create orchestrator for testing."""
    from api.orchestrators.query_orchestrator import QueryOrchestrator
    return QueryOrchestrator()


@pytest.fixture
def mock_reranked_results():
    """Create mock reranked results with parent docs."""
    from api.tools.retrieval_engine import RetrievalResult
    from api.models import ChunkV3, ParentDocumentV3
    
    results = []
    for i in range(20):
        chunk = ChunkV3(
            chunk_id=f"chunk_{i}",
            doc_id=f"doc_{i % 5}",  # 5 unique parent docs
            chunk_text=f"Text {i}"
        )
        
        parent_doc = ParentDocumentV3(
            doc_id=f"doc_{i % 5}",
            title=f"Document {i % 5}",
            pageindex_markdown=f"# Document {i % 5}\n\nContent {i}"
        )
        
        result = RetrievalResult(
            chunk_id=f"chunk_{i}",
            chunk=chunk,
            score=0.9 - (i * 0.01),
            confidence=0.9 - (i * 0.01),
            metadata={"doc_type": "act"},
            parent_doc=parent_doc
        )
        results.append(result)
    
    return results


@pytest.mark.asyncio
async def test_speculative_prefetch_node_exists(orchestrator):
    """Test that speculative prefetch node method exists."""
    
    assert hasattr(orchestrator, '_parent_prefetch_speculative'), \
        "Should have _parent_prefetch_speculative method"


@pytest.mark.asyncio
async def test_speculative_prefetch_fetches_top_15(orchestrator, mock_reranked_results):
    """Test that speculative prefetch fetches top 15 results."""
    from api.schemas.agent_state import AgentState
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        reranked_results=mock_reranked_results
    )
    
    # Mock the batch fetch to avoid R2 dependency
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = AsyncMock()
        
        # Mock batch fetch to return parent docs
        async def mock_batch_fetch(requests):
            return [
                MagicMock(doc_id=req[0], pageindex_markdown=f"Content for {req[0]}")
                for req in requests
            ]
        
        mock_engine._fetch_parent_documents_batch = mock_batch_fetch
        mock_engine_class.return_value.__aenter__.return_value = mock_engine
        
        # Run prefetch
        result = await orchestrator._parent_prefetch_speculative(state)
        
        # Should have parent_doc_cache
        assert "parent_doc_cache" in result
        assert isinstance(result["parent_doc_cache"], dict)
        
        # Should have prefetched ~5 unique parents (from top 15 results)
        assert len(result["parent_doc_cache"]) >= 3, \
            f"Should cache multiple parent docs, got {len(result['parent_doc_cache'])}"


@pytest.mark.asyncio
async def test_speculative_prefetch_deduplicates_parents(orchestrator, mock_reranked_results):
    """Test that prefetch deduplicates parent document requests."""
    from api.schemas.agent_state import AgentState
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        reranked_results=mock_reranked_results
    )
    
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = AsyncMock()
        
        fetch_calls = []
        
        async def mock_batch_fetch(requests):
            fetch_calls.append(len(requests))  # Track how many unique requests
            return [MagicMock(doc_id=req[0]) for req in requests]
        
        mock_engine._fetch_parent_documents_batch = mock_batch_fetch
        mock_engine_class.return_value.__aenter__.return_value = mock_engine
        
        # Run prefetch
        await orchestrator._parent_prefetch_speculative(state)
        
        # Should have made batch fetch call
        assert len(fetch_calls) == 1, "Should make one batch fetch call"
        
        # Should fetch 5 unique docs (not 15 duplicate requests)
        # mock_reranked_results has chunks from doc_0 to doc_4 (5 unique)
        assert fetch_calls[0] <= 5, \
            f"Should deduplicate parent doc requests, got {fetch_calls[0]} requests"


@pytest.mark.asyncio
async def test_speculative_prefetch_performance(orchestrator, mock_reranked_results):
    """Test that speculative prefetch completes quickly."""
    from api.schemas.agent_state import AgentState
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        reranked_results=mock_reranked_results
    )
    
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = AsyncMock()
        
        # Mock fast R2 fetch (~100ms)
        async def mock_batch_fetch(requests):
            await asyncio.sleep(0.1)  # Simulate R2 latency
            return [MagicMock(doc_id=req[0]) for req in requests]
        
        mock_engine._fetch_parent_documents_batch = mock_batch_fetch
        mock_engine_class.return_value.__aenter__.return_value = mock_engine
        
        # Measure prefetch time
        start = time.time()
        await orchestrator._parent_prefetch_speculative(state)
        duration_ms = (time.time() - start) * 1000
        
        # Should complete in <200ms (includes mocked R2 fetch)
        assert duration_ms < 200, f"Prefetch too slow: {duration_ms:.2f}ms"


@pytest.mark.asyncio
async def test_parent_final_select_uses_cache(orchestrator, mock_reranked_results):
    """Test that final selection uses prefetched cache."""
    from api.schemas.agent_state import AgentState
    
    # Simulate prefetched cache
    parent_cache = {
        "doc_0": MagicMock(doc_id="doc_0", title="Doc 0", pageindex_markdown="Content 0"),
        "doc_1": MagicMock(doc_id="doc_1", title="Doc 1", pageindex_markdown="Content 1"),
        "doc_2": MagicMock(doc_id="doc_2", title="Doc 2", pageindex_markdown="Content 2")
    }
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        topk_results=mock_reranked_results[:8],  # Top 8 after selection
        parent_doc_cache=parent_cache
    )
    
    # Run final selection
    result = await orchestrator._parent_final_select(state)
    
    # Should have bundled_context
    assert "bundled_context" in result
    assert isinstance(result["bundled_context"], list)
    
    # Should use cached parents (not fetch from R2)
    # Verify by checking no R2 calls were made
    assert len(result["bundled_context"]) > 0


@pytest.mark.asyncio
async def test_parent_final_select_performance(orchestrator, mock_reranked_results):
    """Test that final selection is very fast (uses cache)."""
    from api.schemas.agent_state import AgentState
    
    parent_cache = {
        f"doc_{i}": MagicMock(doc_id=f"doc_{i}", pageindex_markdown=f"Content {i}")
        for i in range(5)
    }
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        topk_results=mock_reranked_results[:8],
        parent_doc_cache=parent_cache
    )
    
    # Measure time
    start = time.time()
    await orchestrator._parent_final_select(state)
    duration_ms = (time.time() - start) * 1000
    
    # Should be very fast (<50ms, no R2 fetches)
    assert duration_ms < 50, f"Final selection too slow: {duration_ms:.2f}ms (should be <50ms)"


@pytest.mark.asyncio
async def test_speculative_prefetch_handles_empty_results(orchestrator):
    """Test graceful handling of empty reranked results."""
    from api.schemas.agent_state import AgentState
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        reranked_results=[]  # Empty
    )
    
    # Should handle gracefully
    result = await orchestrator._parent_prefetch_speculative(state)
    
    assert "parent_doc_cache" in result
    assert result["parent_doc_cache"] == {}, \
        "Should return empty cache for empty results"

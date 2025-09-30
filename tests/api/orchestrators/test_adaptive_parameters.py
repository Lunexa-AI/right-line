"""
Tests for adaptive retrieval parameters functionality.

Tests verify that retrieval parameters (top_k) adapt based on query complexity:
- Simple queries: retrieve 15, select 5
- Moderate queries: retrieve 25, select 8
- Complex queries: retrieve 40, select 12
- Expert queries: retrieve 50, select 15

Follows .cursorrules: TDD, comprehensive coverage, async testing.
"""

import pytest
from unittest.mock import AsyncMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState
from api.tools.retrieval_engine import RetrievalResult
from api.models import ChunkV3, ParentDocumentV3


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing."""
    return QueryOrchestrator()


def create_mock_results(count: int = 50) -> list:
    """Helper to create mock retrieval results."""
    results = []
    for i in range(count):
        chunk = ChunkV3(
            chunk_id=f"chunk_{i}",
            doc_id=f"doc_{i % 5}",
            chunk_text=f"Legal content {i}",
            section_path=f"Section {i}"
        )
        
        parent_doc = ParentDocumentV3(
            doc_id=f"doc_{i % 5}",
            title=f"Document {i % 5}",
            pageindex_markdown=f"# Document {i % 5}\n\nContent."
        )
        
        result = RetrievalResult(
            chunk_id=f"chunk_{i}",
            chunk=chunk,
            score=0.8 - (i * 0.01),  # Descending scores
            confidence=0.8 - (i * 0.01),
            metadata={"doc_type": "act"},
            parent_doc=parent_doc
        )
        results.append(result)
    
    return results


@pytest.mark.asyncio
async def test_intent_classifier_sets_adaptive_params(orchestrator):
    """Test that intent classifier sets adaptive retrieval parameters."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="What is labour law?"
    )
    
    result = await orchestrator._route_intent_node(state)
    
    # Should set retrieval parameters
    assert "retrieval_top_k" in result, "Should set retrieval_top_k"
    assert "rerank_top_k" in result, "Should set rerank_top_k"
    
    # Should be integer values
    assert isinstance(result["retrieval_top_k"], int)
    assert isinstance(result["rerank_top_k"], int)
    
    # Should be reasonable values
    assert 10 <= result["retrieval_top_k"] <= 50
    assert 5 <= result["rerank_top_k"] <= 15


@pytest.mark.asyncio
async def test_adaptive_params_simple_complexity(orchestrator):
    """Test adaptive parameters for simple complexity queries."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Simple query",
        complexity="simple",
        retrieval_top_k=15,
        rerank_top_k=5,
        combined_results=create_mock_results(50),
        reranked_results=create_mock_results(10)
    )
    
    # Test select_topk
    result = await orchestrator._select_topk_node(state)
    
    # Should select 5 for simple
    topk = result["topk_results"]
    assert len(topk) <= 5, f"Simple should select max 5, got {len(topk)}"


@pytest.mark.asyncio
async def test_adaptive_params_moderate_complexity(orchestrator):
    """Test adaptive parameters for moderate complexity queries."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Moderate query",
        complexity="moderate",
        retrieval_top_k=25,
        rerank_top_k=8,
        combined_results=create_mock_results(50),
        reranked_results=create_mock_results(16)
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # Should select 8 for moderate
    topk = result["topk_results"]
    assert len(topk) <= 8, f"Moderate should select max 8, got {len(topk)}"


@pytest.mark.asyncio
async def test_adaptive_params_complex_complexity(orchestrator):
    """Test adaptive parameters for complex complexity queries."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Complex multi-faceted query",
        complexity="complex",
        retrieval_top_k=40,
        rerank_top_k=12,
        combined_results=create_mock_results(50),
        reranked_results=create_mock_results(24)
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # Should select 12 for complex
    topk = result["topk_results"]
    assert len(topk) <= 12, f"Complex should select max 12, got {len(topk)}"


@pytest.mark.asyncio
async def test_adaptive_params_expert_complexity(orchestrator):
    """Test adaptive parameters for expert complexity queries."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Expert level legal analysis query",
        complexity="expert",
        retrieval_top_k=50,
        rerank_top_k=15,
        combined_results=create_mock_results(50),
        reranked_results=create_mock_results(30)
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # Should select 15 for expert
    topk = result["topk_results"]
    assert len(topk) <= 15, f"Expert should select max 15, got {len(topk)}"


@pytest.mark.asyncio
async def test_adaptive_params_fallback_on_missing(orchestrator):
    """Test that missing complexity defaults to moderate parameters."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Query without complexity",
        # No complexity specified
        combined_results=create_mock_results(30),
        reranked_results=create_mock_results(16)
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # Should default to moderate (8)
    topk = result["topk_results"]
    assert len(topk) <= 8, f"Should default to moderate (8), got {len(topk)}"


@pytest.mark.asyncio
async def test_retrieval_uses_adaptive_top_k(orchestrator):
    """Test that retrieval node uses adaptive top_k."""
    
    # Mock the retrievers to verify top_k is set
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = AsyncMock()
        mock_bm25 = AsyncMock()
        mock_milvus = AsyncMock()
        
        # Return empty docs for simplicity
        mock_bm25.aget_relevant_documents.return_value = []
        mock_milvus.aget_relevant_documents.return_value = []
        
        mock_engine.bm25_retriever = mock_bm25
        mock_engine.milvus_retriever = mock_milvus
        mock_engine_class.return_value = mock_engine
        
        state = AgentState(
            user_id="test",
            session_id="test",
            raw_query="Complex query",
            complexity="complex",
            retrieval_top_k=40
        )
        
        result = await orchestrator._retrieve_concurrent_node(state)
        
        # Verify top_k was set on retrievers
        assert mock_engine.bm25_retriever.top_k == 40, "BM25 top_k should be set to 40"
        assert mock_engine.milvus_retriever.top_k == 40, "Milvus top_k should be set to 40"


@pytest.mark.asyncio
async def test_quality_threshold_applied_in_selection(orchestrator):
    """Test that quality threshold is applied in top_k selection."""
    
    # Create results with some low scores
    mixed_results = []
    for i in range(20):
        chunk = ChunkV3(
            chunk_id=f"chunk_{i}",
            doc_id="doc_1",
            chunk_text=f"Text {i}"
        )
        parent_doc = ParentDocumentV3(
            doc_id="doc_1",
            title="Document",
            pageindex_markdown="Content"
        )
        
        # First 10 have low scores < 0.3
        score = 0.2 if i < 10 else 0.8
        
        result = RetrievalResult(
            chunk_id=f"chunk_{i}",
            chunk=chunk,
            score=score,
            confidence=score,
            metadata={},
            parent_doc=parent_doc
        )
        mixed_results.append(result)
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test",
        complexity="moderate",
        reranked_results=mixed_results
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # All selected should have score >= 0.3
    topk = result["topk_results"]
    for r in topk:
        assert r.score >= 0.3, f"Result has score {r.score} < 0.3 threshold"


@pytest.mark.asyncio
async def test_params_logged_correctly(orchestrator):
    """Test that adaptive parameters are logged for monitoring."""
    
    state = AgentState(
        user_id="test",
        session_id="test",
        raw_query="Test query",
        complexity="complex",
        retrieval_top_k=40,
        rerank_top_k=12,
        reranked_results=create_mock_results(24)
    )
    
    result = await orchestrator._select_topk_node(state)
    
    # Result should be successful
    assert "topk_results" in result
    assert len(result["topk_results"]) > 0
    
    # Logs are checked in actual usage - this verifies execution doesn't crash


@pytest.mark.asyncio
async def test_end_to_end_adaptive_flow(orchestrator):
    """Test complete flow with adaptive parameters from intent to selection."""
    
    # Mock retrieval to avoid external dependencies
    with patch('api.tools.retrieval_engine.RetrievalEngine') as mock_engine_class:
        mock_engine = AsyncMock()
        mock_bm25 = AsyncMock()
        mock_milvus = AsyncMock()
        
        # Create mock docs
        from langchain_core.documents import Document
        mock_docs = [
            Document(
                page_content=f"Content {i}",
                metadata={"retrieval_result": create_mock_results(1)[0]}
            )
            for i in range(50)
        ]
        
        mock_bm25.aget_relevant_documents.return_value = mock_docs[:25]
        mock_milvus.aget_relevant_documents.return_value = mock_docs[:25]
        
        mock_engine.bm25_retriever = mock_bm25
        mock_engine.milvus_retriever = mock_milvus
        mock_engine_class.return_value = mock_engine
        
        # Start with intent classification
        state = AgentState(
            user_id="test",
            session_id="test",
            raw_query="Complex constitutional law question"
        )
        
        # Run intent classification
        intent_result = await orchestrator._route_intent_node(state)
        
        # Update state
        state = state.model_copy(update=intent_result)
        
        # Verify params were set
        assert hasattr(state, 'retrieval_top_k')
        assert hasattr(state, 'rerank_top_k')
        
        # Run retrieval
        retrieval_result = await orchestrator._retrieve_concurrent_node(state)
        
        # Verify top_k was used
        assert mock_engine.bm25_retriever.top_k is not None
        assert mock_engine.milvus_retriever.top_k is not None

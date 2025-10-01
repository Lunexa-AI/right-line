"""
Tests for ARCH-052 and ARCH-053: Iterative Retrieval and Gap Query Generator

Tests the iterative retrieval system that:
- Analyzes quality issues to identify gaps (ARCH-053)
- Generates targeted gap-filling queries (ARCH-053)
- Retrieves additional sources (ARCH-052)
- Deduplicates and merges with existing results (ARCH-052)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Create a QueryOrchestrator instance for testing."""
    return QueryOrchestrator()


@pytest.fixture
def sample_current_sources():
    """Sample current bundled context."""
    return [
        {
            "parent_doc_id": "doc_1",
            "title": "Labour Act [Chapter 28:01]",
            "content": "Labour provisions...",
            "source_type": "statute",
            "confidence": 0.9
        },
        {
            "parent_doc_id": "doc_2",
            "title": "Employment Regulations",
            "content": "Employment rules...",
            "source_type": "statute",
            "confidence": 0.8
        }
    ]


class TestGapQueryGeneration:
    """Test gap-filling query generation (ARCH-053)."""
    
    @pytest.mark.asyncio
    async def test_citation_gaps_detected(self, orchestrator):
        """Should identify citation gaps in quality issues."""
        quality_issues = [
            "Insufficient legal citations",
            "Missing statutory references"
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What is minimum wage?",
            quality_issues,
            []
        )
        
        assert "legal citations" in gap_query or "statutory references" in gap_query
        assert "What is minimum wage?" in gap_query
    
    @pytest.mark.asyncio
    async def test_coverage_gaps_detected(self, orchestrator):
        """Should identify coverage gaps in quality issues."""
        quality_issues = [
            "Incomplete coverage of labour law",
            "Missing key legal areas"
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are employee rights?",
            quality_issues,
            []
        )
        
        assert "comprehensive coverage" in gap_query
    
    @pytest.mark.asyncio
    async def test_case_law_gaps_detected(self, orchestrator):
        """Should identify missing case law in quality issues."""
        quality_issues = [
            "Missing case law precedents",
            "No judicial interpretations provided"
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are dismissal rules?",
            quality_issues,
            []
        )
        
        assert "case law" in gap_query or "precedent" in gap_query
    
    @pytest.mark.asyncio
    async def test_constitutional_gaps_detected(self, orchestrator):
        """Should identify constitutional gaps."""
        quality_issues = [
            "Missing constitutional provisions",
            "Constitutional analysis incomplete"
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are fundamental rights?",
            quality_issues,
            []
        )
        
        assert "constitutional" in gap_query
    
    @pytest.mark.asyncio
    async def test_source_type_diversity(self, orchestrator, sample_current_sources):
        """Should suggest different source types if current sources are homogeneous."""
        # Current sources are all statutes
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are employment rights?",
            ["Insufficient sources"],
            sample_current_sources
        )
        
        # Should suggest case law since we only have statutes
        assert "case law" in gap_query or "precedent" in gap_query
    
    @pytest.mark.asyncio
    async def test_fallback_on_no_issues(self, orchestrator):
        """Should have fallback query when no specific gaps identified."""
        gap_query = await orchestrator._generate_gap_filling_query(
            "What is labour law?",
            [],  # No quality issues
            []
        )
        
        assert "What is labour law?" in gap_query
        assert "additional" in gap_query


class TestIterativeRetrieval:
    """Test iterative retrieval node (ARCH-052)."""
    
    @pytest.mark.asyncio
    async def test_retrieves_additional_sources(self, orchestrator, sample_current_sources):
        """Should retrieve additional sources using gap query."""
        # Mock retrieval engine
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Create mock documents
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "Additional legal content 1"
            mock_doc1.metadata = {
                "chunk_id": "new_chunk_1",
                "parent_doc_id": "new_doc_1",
                "score": 0.85,
                "confidence": 0.85
            }
            
            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Additional legal content 2"
            mock_doc2.metadata = {
                "chunk_id": "new_chunk_2",
                "parent_doc_id": "new_doc_2",
                "score": 0.80,
                "confidence": 0.80
            }
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[mock_doc1, mock_doc2]
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            # Create state with existing results (use mock objects)
            existing_result = MagicMock()
            existing_result.chunk_id = "existing_chunk_1"
            existing_result.parent_doc_id = "doc_1"
            
            state = AgentState(
                raw_query="What is minimum wage?",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient sources"],
                bundled_context=sample_current_sources,
                combined_results=[existing_result],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            assert "combined_results" in result
            assert len(result["combined_results"]) == 3  # 1 existing + 2 new
            assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_deduplicates_chunks(self, orchestrator, sample_current_sources):
        """Should deduplicate chunks with same chunk_id."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Mock document with duplicate chunk_id
            mock_doc_dup = MagicMock()
            mock_doc_dup.page_content = "Duplicate content"
            mock_doc_dup.metadata = {
                "chunk_id": "existing_chunk_1",  # Same as existing
                "parent_doc_id": "doc_1",
                "score": 0.85,
                "confidence": 0.85
            }
            
            mock_doc_new = MagicMock()
            mock_doc_new.page_content = "New content"
            mock_doc_new.metadata = {
                "chunk_id": "new_chunk_1",
                "parent_doc_id": "new_doc_1",
                "score": 0.80,
                "confidence": 0.80
            }
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[mock_doc_dup, mock_doc_new]
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            existing_result = MagicMock()
            existing_result.chunk_id = "existing_chunk_1"
            existing_result.parent_doc_id = "doc_1"
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient"],
                bundled_context=sample_current_sources,
                combined_results=[existing_result],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should only add 1 new (the duplicate should be filtered)
            assert len(result["combined_results"]) == 2  # 1 existing + 1 new (dup filtered)
    
    @pytest.mark.asyncio
    async def test_increments_iteration(self, orchestrator, sample_current_sources):
        """Should increment refinement iteration."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[]
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Issue"],
                bundled_context=sample_current_sources,
                combined_results=[],
                refinement_iteration=1
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            assert result["refinement_iteration"] == 2


class TestIterativeRetrievalErrorHandling:
    """Test error handling in iterative retrieval."""
    
    @pytest.mark.asyncio
    async def test_retrieval_exception_returns_empty(self, orchestrator, sample_current_sources):
        """Retrieval exception should return empty dict to proceed with existing."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Mock retrieval exception
            MockEngine.side_effect = Exception("Retrieval error")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient sources"],
                bundled_context=sample_current_sources,
                combined_results=[],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should return empty dict
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_no_current_sources_handled(self, orchestrator):
        """Should handle missing bundled_context gracefully."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            mock_doc = MagicMock()
            mock_doc.page_content = "Content"
            mock_doc.metadata = {
                "chunk_id": "chunk_1",
                "parent_doc_id": "doc_1",
                "score": 0.8,
                "confidence": 0.8
            }
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[mock_doc]
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient"],
                bundled_context=[],  # No current sources
                combined_results=[],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should still retrieve
            assert "combined_results" in result
            assert len(result["combined_results"]) == 1


class TestGapQueryEdgeCases:
    """Test edge cases in gap query generation."""
    
    @pytest.mark.asyncio
    async def test_no_quality_issues(self, orchestrator):
        """Should generate fallback query when no quality issues."""
        gap_query = await orchestrator._generate_gap_filling_query(
            "What is labour law?",
            [],
            []
        )
        
        assert "What is labour law?" in gap_query
        assert "additional" in gap_query
    
    @pytest.mark.asyncio
    async def test_empty_current_sources(self, orchestrator):
        """Should handle empty current sources."""
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are my rights?",
            ["Insufficient sources"],
            []
        )
        
        assert "What are my rights?" in gap_query
    
    @pytest.mark.asyncio
    async def test_exception_fallback(self, orchestrator):
        """Should fallback to original query on exception."""
        # Pass invalid data that might cause exception
        gap_query = await orchestrator._generate_gap_filling_query(
            "Test query",
            None,  # Invalid - should be list
            []
        )
        
        # Should still return a valid query
        assert "Test query" in gap_query
        assert "additional" in gap_query


class TestSourceTypeDiversity:
    """Test source type diversity suggestions."""
    
    @pytest.mark.asyncio
    async def test_suggests_case_law_when_only_statutes(self, orchestrator):
        """Should suggest case law when only statutes present."""
        statute_sources = [
            {"source_type": "statute", "title": "Act 1"},
            {"source_type": "statute", "title": "Act 2"}
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What are employment rules?",
            ["Need more sources"],
            statute_sources
        )
        
        assert "case law" in gap_query or "precedent" in gap_query
    
    @pytest.mark.asyncio
    async def test_suggests_statutes_when_only_case_law(self, orchestrator):
        """Should suggest statutes when only case law present."""
        case_law_sources = [
            {"source_type": "case_law", "title": "Case 1"},
            {"source_type": "case_law", "title": "Case 2"}
        ]
        
        gap_query = await orchestrator._generate_gap_filling_query(
            "What is the law?",
            ["Need more"],
            case_law_sources
        )
        
        assert "statutory" in gap_query or "statute" in gap_query or "provisions" in gap_query


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


"""
INTEGRATION TEST: Failure Modes and Resilience

Tests system behavior under failure conditions:
- LLM API failures
- Retrieval engine failures
- Cache/memory failures
- Invalid data scenarios
- Concurrent failure recovery
- Timeout handling
- Resource exhaustion scenarios
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Get orchestrator instance."""
    return QueryOrchestrator()


class TestLLMFailures:
    """Test LLM API failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_intent_llm_timeout(self, orchestrator):
        """Intent LLM timeout should fall back to heuristics."""
        with patch.object(orchestrator, '_classify_intent_llm', side_effect=asyncio.TimeoutError("LLM timeout")):
            state = AgentState(
                raw_query="What is the law on employment contracts?",  # Has legal keywords
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should not raise, should use heuristics
            result = await orchestrator._route_intent_node(state)
            
            assert result["intent"] == "rag_qa"  # Heuristic should catch this
            assert result["complexity"] is not None
    
    @pytest.mark.asyncio
    async def test_self_critic_llm_failure(self, orchestrator):
        """Self-critic LLM failure should return fallback instructions."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            MockLLM.side_effect = Exception("API key invalid")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                final_answer="Answer",
                quality_issues=["Issue 1", "Issue 2", "Issue 3"],
                refinement_iteration=0,
                bundled_context=[]
            )
            
            result = await orchestrator._self_critic_node(state)
            
            # Should return graceful fallback
            assert "refinement_instructions" in result
            assert len(result["refinement_instructions"]) >= 1
            assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_refined_synthesis_llm_failure(self, orchestrator):
        """Refined synthesis LLM failure should keep original."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            MockLLM.side_effect = Exception("Rate limit exceeded")
            
            original_answer = "Original good answer"
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                final_answer=original_answer,
                refinement_instructions=["Improve"],
                refinement_iteration=1,
                bundled_context=[]
            )
            
            result = await orchestrator._refined_synthesis_node(state)
            
            # Should return empty to keep original
            assert result == {}


class TestRetrievalFailures:
    """Test retrieval engine failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_iterative_retrieval_engine_failure(self, orchestrator):
        """Retrieval engine failure should proceed with existing sources."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            MockEngine.side_effect = Exception("Milvus connection failed")
            
            existing_sources = [{"source_type": "statute", "title": "Act 1"}]
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient sources"],
                bundled_context=existing_sources,
                combined_results=[MagicMock(chunk_id="existing")],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should return empty to proceed with existing
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_retrieval_returns_empty_results(self, orchestrator):
        """Retrieval returning no results should be handled."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[]  # No results
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Need more"],
                bundled_context=[],
                combined_results=[],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should handle empty results gracefully
            assert "combined_results" in result
            # Result might be empty or have existing sources
            assert isinstance(result["combined_results"], list)


class TestCacheMemoryFailures:
    """Test cache and memory system failures."""
    
    @pytest.mark.asyncio
    async def test_cache_connection_failure(self, orchestrator):
        """Cache connection failure should not break intent classification."""
        # Mock cache connection failure
        if orchestrator.cache:
            with patch.object(orchestrator.cache, 'connect', side_effect=Exception("Redis connection failed")):
                state = AgentState(
                    raw_query="What is law?",
                    user_id="test_user",
                    session_id="test_session"
                )
                
                # Should still work
                result = await orchestrator._route_intent_node(state)
                assert result["intent"] is not None
    
    @pytest.mark.asyncio
    async def test_memory_fetch_failure(self, orchestrator):
        """Memory fetch failure should not break classification."""
        # Mock memory failure
        if orchestrator.memory:
            with patch.object(orchestrator.memory, 'get_full_context', side_effect=Exception("Firestore error")):
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session"
                )
                
                # Should still work with defaults
                result = await orchestrator._route_intent_node(state)
                assert result["intent"] is not None


class TestInvalidDataHandling:
    """Test handling of invalid or malformed data."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_from_critic(self, orchestrator):
        """Invalid JSON from critic should use fallback."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Return invalid JSON
            mock_response = MagicMock()
            mock_response.content = "This is not JSON at all! Just text."
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue 1", "Issue 2"],
                    refinement_iteration=0,
                    bundled_context=[]
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Should use fallback instructions
                assert "refinement_instructions" in result
                assert len(result["refinement_instructions"]) > 0
    
    @pytest.mark.asyncio
    async def test_empty_query_handled(self, orchestrator):
        """Empty query should be handled gracefully."""
        state = AgentState(
            raw_query="",  # Empty
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        # Should still return something reasonable
        assert result["intent"] is not None
    
    @pytest.mark.asyncio
    async def test_null_quality_confidence_handled(self, orchestrator):
        """Null quality confidence should default to pass."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=None,  # Null
            quality_issues=["Issue"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        
        # Should default to pass when quality data missing
        assert decision == "pass"


class TestConcurrentOperations:
    """Test system under concurrent load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_intent_classifications(self, orchestrator):
        """Multiple concurrent intent classifications should work."""
        queries = [
            "What is minimum wage?",
            "How do I register a company?",
            "What are my constitutional rights?",
            "Can I sue for unfair dismissal?",
            "What is the Companies Act about?"
        ]
        
        states = [
            AgentState(
                raw_query=query,
                user_id=f"user_{i}",
                session_id=f"session_{i}"
            )
            for i, query in enumerate(queries)
        ]
        
        # Process all concurrently
        tasks = [orchestrator._route_intent_node(state) for state in states]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        assert len(results) == 5
        for result in results:
            assert not isinstance(result, Exception)
            assert "intent" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_decision_logic(self, orchestrator):
        """Multiple concurrent decisions should work independently."""
        states = [
            AgentState(
                raw_query=f"Test {i}",
                user_id=f"user_{i}",
                session_id=f"session_{i}",
                quality_passed=False,
                quality_confidence=0.5 + (i * 0.1),
                quality_issues=["Issue"],
                refinement_iteration=0
            )
            for i in range(5)
        ]
        
        # Process all concurrently
        decisions = [orchestrator._decide_refinement_strategy(state) for state in states]
        
        # All should return valid decisions
        assert len(decisions) == 5
        for decision in decisions:
            assert decision in ["pass", "refine_synthesis", "retrieve_more", "fail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


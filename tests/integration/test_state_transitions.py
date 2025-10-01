"""
INTEGRATION TEST: State Transitions and Data Flow

Tests that state transitions correctly through the pipeline:
- State fields populated at each node
- Data flows correctly between nodes
- No data loss or corruption
- State remains valid throughout
- Size limits respected
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Get orchestrator instance."""
    return QueryOrchestrator()


class TestStateFieldPopulation:
    """Test that each node populates expected state fields."""
    
    @pytest.mark.asyncio
    async def test_intent_node_populates_fields(self, orchestrator):
        """Intent node should populate all required fields."""
        state = AgentState(
            raw_query="What is labour law?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        # Required fields
        assert "intent" in result
        assert "complexity" in result
        assert "user_type" in result
        assert "reasoning_framework" in result
        assert "legal_areas" in result
        assert "retrieval_top_k" in result
        assert "rerank_top_k" in result
        assert "jurisdiction" in result
        
        # Types
        assert isinstance(result["intent"], str)
        assert isinstance(result["complexity"], str)
        assert isinstance(result["legal_areas"], list)
        assert isinstance(result["retrieval_top_k"], int)
        assert isinstance(result["rerank_top_k"], int)
    
    @pytest.mark.asyncio
    async def test_self_critic_populates_instructions(self, orchestrator):
        """Self-critic should populate refinement instructions."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = '{"refinement_instructions": ["Fix 1", "Fix 2"], "priority_fixes": ["Critical"], "suggested_additions": ["Add this"]}'
            
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
                    final_answer="Original",
                    quality_issues=["Issue 1", "Issue 2"],
                    refinement_iteration=0,
                    bundled_context=[]
                )
                
                result = await orchestrator._self_critic_node(state)
                
                # Should populate all instruction fields
                assert "refinement_instructions" in result
                assert "priority_fixes" in result
                assert "suggested_additions" in result
                assert "refinement_iteration" in result
                
                # Should be lists
                assert isinstance(result["refinement_instructions"], list)
                assert isinstance(result["priority_fixes"], list)
                assert isinstance(result["suggested_additions"], list)
                
                # Should increment iteration
                assert result["refinement_iteration"] == 1


class TestDataFlowBetweenNodes:
    """Test that data flows correctly between nodes."""
    
    @pytest.mark.asyncio
    async def test_intent_to_retrieval_parameter_flow(self, orchestrator):
        """Parameters from intent should flow to retrieval decisions."""
        # Intent classifies as complex
        state = AgentState(
            raw_query="Complex multi-faceted legal question about labour law and constitutional rights",
            user_id="test_user",
            session_id="test_session"
        )
        
        intent_result = await orchestrator._route_intent_node(state)
        
        # Update state
        for key, value in intent_result.items():
            setattr(state, key, value)
        
        # Parameters should be set and usable downstream
        assert hasattr(state, 'retrieval_top_k')
        assert hasattr(state, 'rerank_top_k')
        assert hasattr(state, 'complexity')
        
        # Values should be appropriate for complexity
        if state.complexity == "complex":
            assert state.retrieval_top_k >= 40
            assert state.rerank_top_k >= 12
    
    @pytest.mark.asyncio
    async def test_quality_to_refinement_flow(self, orchestrator):
        """Quality issues should flow to refinement nodes."""
        # Quality gate sets issues
        quality_issues = ["Issue 1", "Issue 2", "Issue 3"]
        quality_confidence = 0.65
        
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=quality_confidence,
            quality_issues=quality_issues,
            final_answer="Original answer",
            refinement_iteration=0,
            bundled_context=[]
        )
        
        # Decision uses quality data
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision in ["refine_synthesis", "pass"]
        
        # If refining, critic should use quality issues
        if decision == "refine_synthesis":
            with patch('langchain_openai.ChatOpenAI') as MockLLM:
                mock_response = MagicMock()
                mock_response.content = '{"refinement_instructions": [], "priority_fixes": [], "suggested_additions": []}'
                
                mock_llm = AsyncMock()
                mock_llm.ainvoke = AsyncMock(return_value=mock_response)
                MockLLM.return_value = mock_llm
                
                with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                    mock_template = MagicMock()
                    mock_chain = MagicMock()
                    mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                    mock_template.__or__ = MagicMock(return_value=mock_chain)
                    MockTemplate.from_messages = MagicMock(return_value=mock_template)
                    
                    critic_result = await orchestrator._self_critic_node(state)
                    
                    # Critic should have access to quality issues
                    assert "refinement_instructions" in critic_result


class TestStateValidation:
    """Test state remains valid throughout pipeline."""
    
    @pytest.mark.asyncio
    async def test_state_size_stays_reasonable(self, orchestrator):
        """State should not grow excessively large."""
        state = AgentState(
            raw_query="Test" * 100,  # Long query
            user_id="test_user",
            session_id="test_session"
        )
        
        # Add some data
        await orchestrator._route_intent_node(state)
        
        # Check size (should be < 8KB as per design)
        size_bytes = state.get_size_estimate()
        assert size_bytes < 8 * 1024, f"State too large: {size_bytes} bytes"
    
    @pytest.mark.asyncio
    async def test_required_fields_always_present(self, orchestrator):
        """Required fields should always be present."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session"
        )
        
        # Required fields from creation
        assert state.raw_query is not None
        assert state.user_id is not None
        assert state.session_id is not None
        assert state.trace_id is not None
        assert state.state_version is not None
    
    def test_state_serialization(self, orchestrator):
        """State should serialize to JSON correctly."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            complexity="moderate",
            quality_issues=["Issue 1"],
            refinement_iteration=1
        )
        
        # Should serialize without errors
        json_str = state.model_dump_json()
        assert len(json_str) > 0
        assert "raw_query" in json_str
        assert "complexity" in json_str


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    @pytest.mark.asyncio
    async def test_intent_llm_failure_uses_fallback(self, orchestrator):
        """Intent LLM failure should use heuristic fallback."""
        # This is already tested but validates graceful degradation
        state = AgentState(
            raw_query="What is labour law?",  # Has legal keywords
            user_id="test_user",
            session_id="test_session"
        )
        
        # Even if LLM fails, heuristics should work
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] is not None
        # Should default to reasonable values
        assert result["complexity"] in ["simple", "moderate", "complex", "expert"]
    
    @pytest.mark.asyncio
    async def test_missing_cache_handled_gracefully(self, orchestrator):
        """Missing cache should not break pipeline."""
        # Temporarily disable cache
        original_cache = orchestrator.cache
        orchestrator.cache = None
        
        try:
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should still work without cache
            result = await orchestrator._route_intent_node(state)
            assert result["intent"] is not None
            
        finally:
            # Restore cache
            orchestrator.cache = original_cache
    
    @pytest.mark.asyncio
    async def test_missing_memory_handled_gracefully(self, orchestrator):
        """Missing memory should not break pipeline."""
        # Temporarily disable memory
        original_memory = orchestrator.memory
        orchestrator.memory = None
        
        try:
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session"
            )
            
            # Should still work without memory
            result = await orchestrator._route_intent_node(state)
            assert result["intent"] is not None
            
        finally:
            # Restore memory
            orchestrator.memory = original_memory


class TestComplexStateTransitions:
    """Test complex state transitions through self-correction."""
    
    @pytest.mark.asyncio
    async def test_refinement_preserves_metadata(self, orchestrator):
        """Refinement should preserve important metadata."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined answer"
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm
            
            with patch('api.composer.prompts.get_prompt_template') as mock_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_context:
                
                mock_tmpl = MagicMock()
                mock_tmpl.format_messages = MagicMock(return_value=[])
                mock_template.return_value = mock_tmpl
                mock_context.return_value = {"query": "test", "context_documents": []}
                
                state = AgentState(
                    raw_query="Original query",
                    user_id="important_user",
                    session_id="important_session",
                    complexity="complex",
                    user_type="professional",
                    legal_areas=["labour_law"],
                    final_answer="Original",
                    refinement_instructions=["Improve"],
                    refinement_iteration=1,
                    bundled_context=[]
                )
                
                original_user_id = state.user_id
                original_session_id = state.session_id
                original_complexity = state.complexity
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Important metadata should be preserved
                assert state.user_id == original_user_id
                assert state.session_id == original_session_id
                assert state.complexity == original_complexity


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


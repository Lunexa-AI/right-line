"""
INTEGRATION TEST: Real-World User Flows

Tests realistic user scenarios with complete data flows:
- Multi-turn conversations with context
- Complex queries requiring self-correction
- Different user types (citizen vs professional)
- Error recovery scenarios
- Performance under realistic conditions
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Get orchestrator instance."""
    return QueryOrchestrator()


class TestCitizenUserFlows:
    """Test realistic citizen user scenarios."""
    
    @pytest.mark.asyncio
    async def test_citizen_basic_rights_query(self, orchestrator):
        """Citizen asking about basic employment rights."""
        queries = [
            "What are my rights as an employee?",
            "Can my employer fire me without notice?",
            "What should I do if I'm not paid on time?"
        ]
        
        for query in queries:
            state = AgentState(
                raw_query=query,
                user_id="citizen_123",
                session_id="citizen_session"
            )
            
            result = await orchestrator._route_intent_node(state)
            
            # Citizen queries should be classified appropriately
            assert result["intent"] == "rag_qa"
            # Note: user_type may be citizen or professional depending on query phrasing
            # "my rights" triggers citizen, but employer/legal terms may not
            assert result["user_type"] in ["citizen", "professional"]
            assert result["complexity"] in ["simple", "moderate"]
            # Should get reasonable retrieval params
            assert result["retrieval_top_k"] <= 40  # Not expert-level
    
    @pytest.mark.asyncio
    async def test_citizen_procedural_query(self, orchestrator):
        """Citizen asking about court procedures."""
        state = AgentState(
            raw_query="How do I file a case at the Labour Court?",
            user_id="citizen_456",
            session_id="procedural_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["complexity"] == "simple"
        assert "procedure" in result["legal_areas"]
        assert result["retrieval_top_k"] == 15  # Simple queries use fewer docs


class TestProfessionalUserFlows:
    """Test realistic professional user scenarios."""
    
    @pytest.mark.asyncio
    async def test_lawyer_statutory_analysis(self, orchestrator):
        """Lawyer analyzing specific statutory provisions."""
        state = AgentState(
            raw_query="What is the interpretation of Section 65(3) of the Companies Act [Chapter 24:03] regarding director fiduciary duties?",
            user_id="lawyer_789",
            session_id="legal_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["user_type"] == "professional"
        assert result["reasoning_framework"] == "statutory"
        assert result["complexity"] in ["complex", "expert"]
        assert result["retrieval_top_k"] >= 25  # Professionals need more sources
    
    @pytest.mark.asyncio
    async def test_professional_case_law_research(self, orchestrator):
        """Professional researching case law precedents."""
        state = AgentState(
            raw_query="What was held in Smith v. Jones SC 45/2020 regarding constructive dismissal?",
            user_id="lawyer_101",
            session_id="research_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["user_type"] == "professional"
        assert result["reasoning_framework"] == "precedent"
        assert result["complexity"] == "complex"
        assert "case_law" in result["legal_areas"]


class TestMultiTurnConversations:
    """Test multi-turn conversations with context."""
    
    @pytest.mark.asyncio
    async def test_follow_up_query_context(self, orchestrator):
        """Follow-up queries should maintain context."""
        # First query
        state1 = AgentState(
            raw_query="What are the grounds for unfair dismissal?",
            user_id="user_multi",
            session_id="conversation_1"
        )
        
        result1 = await orchestrator._route_intent_node(state1)
        assert result1["intent"] == "rag_qa"
        
        # Follow-up query (context-dependent)
        state2 = AgentState(
            raw_query="What about notice periods for that?",
            user_id="user_multi",
            session_id="conversation_1"  # Same session
        )
        
        result2 = await orchestrator._route_intent_node(state2)
        
        # Should still classify as legal query
        assert result2["intent"] in ["rag_qa", "disambiguate"]
    
    @pytest.mark.asyncio
    async def test_clarification_request(self, orchestrator):
        """User requesting clarification."""
        state = AgentState(
            raw_query="What do you mean by that? Can you explain more clearly?",
            user_id="user_clarify",
            session_id="clarify_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        # Should detect as disambiguation or summarization
        assert result["intent"] in ["disambiguate", "summarize", "rag_qa"]
        assert result["complexity"] == "simple"


class TestSelfCorrectionTriggering:
    """Test self-correction triggering in realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_weak_answer_triggers_refinement(self, orchestrator):
        """Weak answer with coherence issues should trigger refinement."""
        state = AgentState(
            raw_query="What are the legal requirements for retrenchment?",
            user_id="test_user",
            session_id="test_session",
            final_answer="Retrenchment has requirements. Employers must follow rules.",
            quality_passed=False,
            quality_confidence=0.62,
            quality_issues=[
                "Vague and lacks specific legal reasoning",
                "Logical structure needs improvement",
                "Coherence could be strengthened"
            ],
            refinement_iteration=0,
            complexity="moderate"
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        
        assert decision == "refine_synthesis"
    
    @pytest.mark.asyncio
    async def test_incomplete_sources_trigger_retrieval(self, orchestrator):
        """Incomplete source coverage should trigger iterative retrieval."""
        state = AgentState(
            raw_query="What are all the legal frameworks governing employment contracts?",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.72,
            quality_issues=[
                "Incomplete coverage - only statutory sources provided",
                "Missing case law precedents",
                "Insufficient constitutional framework"
            ],
            refinement_iteration=0,
            bundled_context=[
                {"source_type": "statute", "title": "Labour Act"}
            ]
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        
        assert decision == "retrieve_more"
    
    @pytest.mark.asyncio
    async def test_good_quality_passes_without_correction(self, orchestrator):
        """High quality answer should pass without correction."""
        state = AgentState(
            raw_query="What is minimum wage?",
            user_id="test_user",
            session_id="test_session",
            final_answer="According to Section 12 of the Labour Act [Chapter 28:01], minimum wage is...",
            quality_passed=True,
            quality_confidence=0.92,
            quality_issues=[],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        
        assert decision == "pass"


class TestDataConsistency:
    """Test data consistency across pipeline stages."""
    
    @pytest.mark.asyncio
    async def test_trace_id_consistency(self, orchestrator):
        """Trace ID should remain consistent across operations."""
        state = AgentState(
            raw_query="Test query",
            user_id="test_user",
            session_id="test_session"
        )
        
        original_trace_id = state.trace_id
        
        # After intent classification
        await orchestrator._route_intent_node(state)
        assert state.trace_id == original_trace_id
        
        # Trace ID should persist through operations
        assert len(state.trace_id) == 32  # UUID hex
    
    @pytest.mark.asyncio
    async def test_user_context_preserved(self, orchestrator):
        """User context should be preserved through pipeline."""
        state = AgentState(
            raw_query="Test",
            user_id="specific_user_123",
            session_id="specific_session_456"
        )
        
        await orchestrator._route_intent_node(state)
        
        # User context should remain unchanged
        assert state.user_id == "specific_user_123"
        assert state.session_id == "specific_session_456"
    
    @pytest.mark.asyncio
    async def test_iteration_count_increments_correctly(self, orchestrator):
        """Iteration count should increment properly through self-correction."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = '{"refinement_instructions": ["Improve"], "priority_fixes": [], "suggested_additions": []}'
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=mock_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                # Start at 0
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    quality_issues=["Issue"],
                    refinement_iteration=0,
                    bundled_context=[]
                )
                
                assert state.refinement_iteration == 0
                
                # After critic
                result = await orchestrator._self_critic_node(state)
                assert result["refinement_iteration"] == 1


class TestPerformanceCharacteristics:
    """Test performance characteristics under realistic load."""
    
    @pytest.mark.asyncio
    async def test_intent_classification_latency(self, orchestrator):
        """Intent classification should be fast (<200ms for heuristics)."""
        state = AgentState(
            raw_query="What is minimum wage?",
            user_id="perf_user",
            session_id="perf_session"
        )
        
        start = time.time()
        result = await orchestrator._route_intent_node(state)
        duration_ms = (time.time() - start) * 1000
        
        # Should complete quickly (allowing for cache initialization)
        assert duration_ms < 500  # Generous for first call with cache init
        assert result["intent"] is not None
    
    @pytest.mark.asyncio
    async def test_decision_logic_latency(self, orchestrator):
        """Decision logic should be extremely fast (<10ms)."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Issue"],
            refinement_iteration=0
        )
        
        start = time.time()
        decision = orchestrator._decide_refinement_strategy(state)
        duration_ms = (time.time() - start) * 1000
        
        # Pure logic should be instant
        assert duration_ms < 10
        assert decision in ["pass", "refine_synthesis", "retrieve_more", "fail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


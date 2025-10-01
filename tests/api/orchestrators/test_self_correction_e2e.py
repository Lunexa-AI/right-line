"""
Tests for ARCH-056: Self-Correction End-to-End Integration Tests

Tests the complete self-correction system end-to-end including:
- Full refinement path (quality_gate → self_critic → refined_synthesis)
- Full iterative retrieval path (quality_gate → iterative_retrieval → rerank)
- Max iteration enforcement
- Quality improvement verification
- Complete flow from query to corrected answer
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
def sample_bundled_context():
    """Sample bundled context for testing."""
    return [
        {
            "parent_doc_id": "labour_act_ch28",
            "title": "Labour Act [Chapter 28:01]",
            "content": "Section 12 governs minimum wage provisions. Employers must comply with prescribed rates...",
            "source_type": "statute",
            "confidence": 0.9
        },
        {
            "parent_doc_id": "employment_regs",
            "title": "Employment Regulations SI 15/2020",
            "content": "Regulations specify implementation details for employment contracts...",
            "source_type": "regulation",
            "confidence": 0.75
        }
    ]


class TestRefinementPathE2E:
    """Test complete refinement path end-to-end."""
    
    @pytest.mark.asyncio
    async def test_coherence_issues_trigger_refinement(self, orchestrator, sample_bundled_context):
        """Coherence issues should trigger full refinement flow."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM, \
             patch('api.composer.prompts.get_prompt_template') as mock_template, \
             patch('api.composer.prompts.build_synthesis_context') as mock_context:
            
            # Mock self-critic response
            critic_response = MagicMock()
            critic_response.content = '''{
                "refinement_instructions": ["Improve legal reasoning", "Add more citations"],
                "priority_fixes": ["Strengthen analysis"],
                "suggested_additions": ["Reference case law"]
            }'''
            
            # Mock refined synthesis response
            synthesis_response = MagicMock()
            synthesis_response.content = "This is an improved legal analysis with stronger reasoning and proper citations to Section 12 of the Labour Act."
            
            # Create mock LLM that returns different responses
            mock_llm = AsyncMock()
            call_count = [0]
            
            async def mock_invoke(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return critic_response
                else:
                    return synthesis_response
            
            mock_llm.ainvoke = mock_invoke
            MockLLM.return_value = mock_llm
            
            # Mock templates
            mock_tmpl = MagicMock()
            mock_tmpl.format_messages = MagicMock(return_value=[])
            mock_template.return_value = mock_tmpl
            mock_context.return_value = {"query": "test", "context_documents": []}
            
            # Test self-critic node
            state_critic = AgentState(
                raw_query="What is minimum wage?",
                user_id="test_user",
                session_id="test_session",
                final_answer="Minimum wage is defined by law.",
                quality_issues=["Coherence issues in reasoning", "Weak legal analysis"],
                quality_confidence=0.65,
                refinement_iteration=0,
                bundled_context=sample_bundled_context
            )
            
            critic_result = await orchestrator._self_critic_node(state_critic)
            
            assert "refinement_instructions" in critic_result
            assert len(critic_result["refinement_instructions"]) >= 2
            assert critic_result["refinement_iteration"] == 1
            
            # Apply critic results to state
            state_refined = AgentState(
                raw_query="What is minimum wage?",
                user_id="test_user",
                session_id="test_session",
                final_answer="Minimum wage is defined by law.",
                refinement_instructions=critic_result["refinement_instructions"],
                priority_fixes=critic_result.get("priority_fixes", []),
                suggested_additions=critic_result.get("suggested_additions", []),
                refinement_iteration=1,
                bundled_context=sample_bundled_context
            )
            
            # Test refined synthesis node
            refined_result = await orchestrator._refined_synthesis_node(state_refined)
            
            assert "final_answer" in refined_result
            assert len(refined_result["final_answer"]) > 0
            assert "synthesis" in refined_result
            assert refined_result["synthesis"]["refined"] is True
    
    @pytest.mark.asyncio
    async def test_decision_routing_to_refinement(self, orchestrator):
        """Quality decision should route to refinement for coherence issues."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Logical coherence issues", "Reasoning gaps"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"


class TestIterativeRetrievalPathE2E:
    """Test complete iterative retrieval path end-to-end."""
    
    @pytest.mark.asyncio
    async def test_source_gaps_trigger_retrieval(self, orchestrator, sample_bundled_context):
        """Source gaps should trigger iterative retrieval flow."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Mock additional documents
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "Additional statute content"
            mock_doc1.metadata = {
                "chunk_id": "new_chunk_1",
                "parent_doc_id": "new_doc_1",
                "score": 0.8,
                "confidence": 0.8
            }
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=[mock_doc1]
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            # Test gap query generation
            gap_query = await orchestrator._generate_gap_filling_query(
                "What are employee rights?",
                ["Insufficient sources for comprehensive analysis", "Missing key authorities"],
                sample_bundled_context
            )
            
            assert "What are employee rights?" in gap_query
            assert len(gap_query) > len("What are employee rights?")
            
            # Test iterative retrieval
            existing_result = MagicMock()
            existing_result.chunk_id = "existing_1"
            
            state_retrieval = AgentState(
                raw_query="What are employee rights?",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient sources"],
                bundled_context=sample_bundled_context,
                combined_results=[existing_result],
                refinement_iteration=0
            )
            
            retrieval_result = await orchestrator._iterative_retrieval_node(state_retrieval)
            
            assert "combined_results" in retrieval_result
            assert len(retrieval_result["combined_results"]) >= 1
            assert retrieval_result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_decision_routing_to_retrieval(self, orchestrator):
        """Quality decision should route to retrieval for source gaps."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.7,
            quality_issues=["Insufficient sources", "Missing coverage"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "retrieve_more"


class TestMaxIterationsE2E:
    """Test max iterations enforcement end-to-end."""
    
    @pytest.mark.asyncio
    async def test_iteration_0_to_1_refinement(self, orchestrator, sample_bundled_context):
        """First refinement should work (iteration 0 → 1)."""
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
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Original",
                    quality_issues=["Issue"],
                    refinement_iteration=0,
                    bundled_context=sample_bundled_context
                )
                
                result = await orchestrator._self_critic_node(state)
                assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_iteration_1_to_2_allowed(self, orchestrator, sample_bundled_context):
        """Second refinement should work (iteration 1 → 2)."""
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
                
                state = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Original",
                    quality_issues=["Issue"],
                    refinement_iteration=1,  # Already at iteration 1
                    bundled_context=sample_bundled_context
                )
                
                result = await orchestrator._self_critic_node(state)
                assert result["refinement_iteration"] == 2  # Now at max
    
    @pytest.mark.asyncio
    async def test_iteration_2_blocks_further_refinement(self, orchestrator):
        """At iteration 2 (max), should not allow further refinement."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.5,
            quality_issues=["Still has issues"],
            refinement_iteration=2  # At max
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "fail"  # Should not refine further


class TestQualityImprovementE2E:
    """Test quality improvement through self-correction."""
    
    @pytest.mark.asyncio
    async def test_refinement_improves_answer_length(self, orchestrator, sample_bundled_context):
        """Refined answer should typically be longer/more detailed."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock refined synthesis with longer response
            refined_response = MagicMock()
            refined_response.content = "This is a comprehensive legal analysis with detailed reasoning, " \
                                      "proper citations to Section 12 of the Labour Act [Chapter 28:01], " \
                                      "and thorough coverage of employee rights and employer obligations. " \
                                      "The analysis addresses potential counterarguments and provides clear guidance."
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=refined_response)
            MockLLM.return_value = mock_llm
            
            with patch('api.composer.prompts.get_prompt_template') as mock_template, \
                 patch('api.composer.prompts.build_synthesis_context') as mock_context:
                
                mock_tmpl = MagicMock()
                mock_tmpl.format_messages = MagicMock(return_value=[])
                mock_template.return_value = mock_tmpl
                mock_context.return_value = {"query": "test", "context_documents": []}
                
                original_answer = "Minimum wage is set by law."  # Short, weak answer
                
                state = AgentState(
                    raw_query="What is minimum wage?",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer=original_answer,
                    refinement_instructions=["Add specific citations", "Strengthen reasoning"],
                    priority_fixes=["Improve citation density"],
                    refinement_iteration=1,
                    bundled_context=sample_bundled_context
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                assert "final_answer" in result
                assert len(result["final_answer"]) > len(original_answer)
                assert "Section 12" in result["final_answer"]
    
    @pytest.mark.asyncio
    async def test_retrieval_adds_more_sources(self, orchestrator, sample_bundled_context):
        """Iterative retrieval should add more unique sources."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Mock 5 new documents
            new_docs = []
            for i in range(5):
                doc = MagicMock()
                doc.page_content = f"Additional legal content {i}"
                doc.metadata = {
                    "chunk_id": f"new_chunk_{i}",
                    "parent_doc_id": f"new_doc_{i}",
                    "score": 0.75,
                    "confidence": 0.75
                }
                new_docs.append(doc)
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.milvus_retriever = MagicMock()
            mock_engine_instance.milvus_retriever.aget_relevant_documents = AsyncMock(
                return_value=new_docs
            )
            mock_engine_instance.__aenter__ = AsyncMock(return_value=mock_engine_instance)
            mock_engine_instance.__aexit__ = AsyncMock(return_value=None)
            
            MockEngine.return_value = mock_engine_instance
            
            # Start with 2 sources
            existing_results = [
                MagicMock(chunk_id="existing_1"),
                MagicMock(chunk_id="existing_2")
            ]
            
            state = AgentState(
                raw_query="What are employee dismissal rules?",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient sources for comprehensive analysis"],
                bundled_context=sample_bundled_context,
                combined_results=existing_results,
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should have 2 existing + 5 new = 7 total
            assert len(result["combined_results"]) == 7


class TestCompleteFlowScenarios:
    """Test complete scenarios from query to self-corrected answer."""
    
    def test_high_quality_passes_immediately(self, orchestrator):
        """High quality answer should pass without correction."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=True,
            quality_confidence=0.95,
            quality_issues=[],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "pass"
    
    def test_moderate_quality_triggers_one_refinement(self, orchestrator):
        """Moderate quality should trigger one refinement."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Some coherence issues"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "refine_synthesis"
    
    def test_low_quality_multiple_iterations(self, orchestrator):
        """Low quality should allow up to 2 iterations."""
        # First iteration
        state_iter0 = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.55,
            quality_issues=["Multiple issues"],
            refinement_iteration=0
        )
        
        decision0 = orchestrator._decide_refinement_strategy(state_iter0)
        # Should try to improve
        assert decision0 in ["refine_synthesis", "pass"]
        
        # Second iteration (after first refinement)
        state_iter1 = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Still has issues"],
            refinement_iteration=1
        )
        
        decision1 = orchestrator._decide_refinement_strategy(state_iter1)
        # Can still refine at iteration 1
        assert decision1 in ["refine_synthesis", "pass"]
        
        # Third attempt (at max iterations)
        state_iter2 = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.6,
            quality_issues=["Still has issues"],
            refinement_iteration=2
        )
        
        decision2 = orchestrator._decide_refinement_strategy(state_iter2)
        # Should block at iteration 2
        assert decision2 == "fail"


class TestSelfCorrectionSystemIntegration:
    """Test integration of all self-correction components."""
    
    def test_all_components_present(self, orchestrator):
        """All self-correction methods should be present."""
        # Decision logic
        assert hasattr(orchestrator, '_decide_refinement_strategy')
        
        # Nodes
        assert hasattr(orchestrator, '_self_critic_node')
        assert hasattr(orchestrator, '_refined_synthesis_node')
        assert hasattr(orchestrator, '_iterative_retrieval_node')
        
        # Helper
        assert hasattr(orchestrator, '_generate_gap_filling_query')
    
    def test_graph_has_all_nodes(self, orchestrator):
        """Graph should include all self-correction nodes."""
        nodes = list(orchestrator.graph.nodes.keys())
        
        assert "08b_quality_gate" in nodes
        assert "08c_self_critic" in nodes
        assert "08d_iterative_retrieval" in nodes
        assert "08e_refined_synthesis" in nodes
        assert "09_answer_composer" in nodes
    
    def test_graph_compiles_with_loops(self, orchestrator):
        """Graph should compile successfully with self-correction loops."""
        # Graph compilation tested in __init__
        assert orchestrator.graph is not None
        assert len(orchestrator.graph.nodes) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


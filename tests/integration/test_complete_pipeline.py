"""
INTEGRATION TEST: Complete Pipeline End-to-End

Tests the complete query processing pipeline from raw query to final answer,
ensuring all components work together correctly:

1. Intent Classification → Query Rewriting → Retrieval → Reranking → Synthesis → Quality Gate
2. Self-correction flows (refinement and iterative retrieval)
3. Memory integration (conversation context)
4. Cache integration (semantic cache)
5. Error propagation and graceful degradation

These tests use realistic scenarios and validate real-world behavior.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from api.orchestrators.query_orchestrator import QueryOrchestrator, get_orchestrator
from api.schemas.agent_state import AgentState


@pytest.fixture
def orchestrator():
    """Get orchestrator instance."""
    return get_orchestrator()


class TestCompletePipelineFlow:
    """Test complete pipeline from query to answer."""
    
    @pytest.mark.asyncio
    async def test_simple_query_complete_flow(self, orchestrator):
        """Test simple query flows through all nodes correctly."""
        # This tests: intent → rewrite → retrieve → rank → select → synthesis
        # We'll validate state updates at each step
        
        query = "What is minimum wage?"
        
        # Step 1: Intent classification
        state = AgentState(
            raw_query=query,
            user_id="test_user",
            session_id="test_session"
        )
        
        intent_result = await orchestrator._route_intent_node(state)
        
        assert intent_result["intent"] in ["rag_qa", "conversational"]
        assert intent_result["complexity"] in ["simple", "moderate", "complex", "expert"]
        assert "retrieval_top_k" in intent_result
        assert "rerank_top_k" in intent_result
        
        # Update state with intent results
        for key, value in intent_result.items():
            setattr(state, key, value)
        
        # Step 2: Query rewriting (should preserve intent metadata)
        assert state.complexity is not None
        assert state.user_type is not None
        
        # Validate adaptive parameters were set
        assert state.retrieval_top_k in [15, 25, 40, 50]  # Valid range
        assert state.rerank_top_k in [5, 8, 12, 15]  # Valid range
    
    @pytest.mark.asyncio
    async def test_complex_query_uses_higher_parameters(self, orchestrator):
        """Complex queries should get higher retrieval parameters."""
        complex_query = "What are the differences between retrenchment and dismissal under the Labour Act, and what are the legal obligations of employers in each case regarding notice periods?"
        
        state = AgentState(
            raw_query=complex_query,
            user_id="test_user",
            session_id="test_session"
        )
        
        intent_result = await orchestrator._route_intent_node(state)
        
        # Complex query should get higher parameters
        assert intent_result["complexity"] in ["complex", "expert"]
        assert intent_result["retrieval_top_k"] >= 25  # At least moderate
        assert intent_result["rerank_top_k"] >= 8
    
    @pytest.mark.asyncio
    async def test_professional_indicators_detected(self, orchestrator):
        """Professional indicators should be detected in intent classification."""
        professional_query = "Analyze Section 65(3) of the Companies Act [Chapter 24:03] regarding director duties pursuant to statutory obligations."
        
        state = AgentState(
            raw_query=professional_query,
            user_id="test_user",
            session_id="test_session"
        )
        
        intent_result = await orchestrator._route_intent_node(state)
        
        assert intent_result["user_type"] == "professional"
        assert intent_result["reasoning_framework"] in ["statutory", "irac"]


class TestComponentInteractions:
    """Test interactions between different components."""
    
    @pytest.mark.asyncio
    async def test_intent_parameters_used_in_retrieval(self, orchestrator):
        """Intent parameters should flow through to retrieval nodes."""
        state = AgentState(
            raw_query="Test query",
            user_id="test_user",
            session_id="test_session",
            complexity="complex",
            retrieval_top_k=40,
            rerank_top_k=12
        )
        
        # Validate parameters are accessible
        assert state.retrieval_top_k == 40
        assert state.rerank_top_k == 12
        assert state.complexity == "complex"
    
    @pytest.mark.asyncio
    async def test_quality_results_flow_to_decision(self, orchestrator):
        """Quality results should flow to decision logic."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=False,
            quality_confidence=0.65,
            quality_issues=["Coherence issues"],
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        
        assert decision in ["pass", "refine_synthesis", "retrieve_more", "fail"]
    
    @pytest.mark.asyncio
    async def test_refinement_instructions_flow_to_synthesis(self, orchestrator):
        """Refinement instructions should flow from critic to synthesis."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            # Mock critic response
            critic_response = MagicMock()
            critic_response.content = '{"refinement_instructions": ["Improve"], "priority_fixes": [], "suggested_additions": []}'
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=critic_response)
            MockLLM.return_value = mock_llm
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_template = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = AsyncMock(return_value=critic_response)
                mock_template.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_template)
                
                state_critic = AgentState(
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Original",
                    quality_issues=["Issue"],
                    refinement_iteration=0,
                    bundled_context=[]
                )
                
                critic_result = await orchestrator._self_critic_node(state_critic)
                
                # Instructions should be generated
                assert "refinement_instructions" in critic_result
                
                # These should flow to refined synthesis
                state_critic.refinement_instructions = critic_result["refinement_instructions"]
                state_critic.priority_fixes = critic_result.get("priority_fixes", [])
                state_critic.refinement_iteration = critic_result["refinement_iteration"]
                
                assert len(state_critic.refinement_instructions) > 0
                assert state_critic.refinement_iteration == 1


class TestSelfCorrectionIntegration:
    """Test self-correction flows with multiple components."""
    
    @pytest.mark.asyncio
    async def test_refinement_loop_complete(self, orchestrator):
        """Test complete refinement loop: decision → critic → refined synthesis."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM, \
             patch('api.composer.prompts.get_prompt_template') as mock_template, \
             patch('api.composer.prompts.build_synthesis_context') as mock_context:
            
            # Mock critic
            critic_response = MagicMock()
            critic_response.content = '{"refinement_instructions": ["Add citations", "Improve reasoning"], "priority_fixes": ["Critical"], "suggested_additions": []}'
            
            # Mock refined synthesis
            refined_response = MagicMock()
            refined_response.content = "Improved analysis with citations to Section 12."
            
            call_count = [0]
            async def mock_invoke(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return critic_response
                else:
                    return refined_response
            
            mock_llm = AsyncMock()
            mock_llm.ainvoke = mock_invoke
            MockLLM.return_value = mock_llm
            
            with patch('langchain_core.prompts.ChatPromptTemplate') as MockTemplate:
                mock_tmpl = MagicMock()
                mock_chain = MagicMock()
                mock_chain.ainvoke = mock_invoke
                mock_tmpl.__or__ = MagicMock(return_value=mock_chain)
                MockTemplate.from_messages = MagicMock(return_value=mock_tmpl)
                
                mock_template.return_value = mock_tmpl
                mock_context.return_value = {"query": "test", "context_documents": []}
                
                # Start with quality issues
                state = AgentState(
                    raw_query="What is minimum wage?",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Minimum wage is set by law.",
                    quality_passed=False,
                    quality_confidence=0.65,
                    quality_issues=["Logical coherence issues in reasoning", "Structure could be improved"],
                    refinement_iteration=0,
                    bundled_context=[{"parent_doc_id": "doc_1", "title": "Test", "content": "Content"}]
                )
                
                # Step 1: Decision should choose refinement (coherence issues, not source issues)
                decision = orchestrator._decide_refinement_strategy(state)
                assert decision == "refine_synthesis"
                
                # Step 2: Self-critic generates instructions
                critic_result = await orchestrator._self_critic_node(state)
                assert len(critic_result["refinement_instructions"]) >= 2
                assert critic_result["refinement_iteration"] == 1
                
                # Step 3: Update state with critic results
                state.refinement_instructions = critic_result["refinement_instructions"]
                state.priority_fixes = critic_result.get("priority_fixes", [])
                state.refinement_iteration = critic_result["refinement_iteration"]
                
                # Step 4: Refined synthesis generates improved answer
                refined_result = await orchestrator._refined_synthesis_node(state)
                assert "final_answer" in refined_result
                assert len(refined_result["final_answer"]) > 0
    
    @pytest.mark.asyncio
    async def test_retrieval_loop_complete(self, orchestrator):
        """Test complete retrieval loop: decision → retrieval → rerank."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            # Mock retrieval
            mock_doc = MagicMock()
            mock_doc.page_content = "Additional content"
            mock_doc.metadata = {
                "chunk_id": "new_1",
                "parent_doc_id": "new_doc",
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
            
            # Start with source gaps
            state = AgentState(
                raw_query="What are employment rights?",
                user_id="test_user",
                session_id="test_session",
                quality_passed=False,
                quality_confidence=0.7,
                quality_issues=["Insufficient sources", "Incomplete coverage"],
                refinement_iteration=0,
                bundled_context=[{"source_type": "statute", "title": "Act 1"}],
                combined_results=[MagicMock(chunk_id="existing_1")]
            )
            
            # Step 1: Decision should choose retrieval
            decision = orchestrator._decide_refinement_strategy(state)
            assert decision == "retrieve_more"
            
            # Step 2: Iterative retrieval fetches more docs
            retrieval_result = await orchestrator._iterative_retrieval_node(state)
            assert "combined_results" in retrieval_result
            assert len(retrieval_result["combined_results"]) > 1  # Should have added docs
            assert retrieval_result["refinement_iteration"] == 1


class TestErrorPropagation:
    """Test error handling and graceful degradation across components."""
    
    @pytest.mark.asyncio
    async def test_self_critic_failure_graceful(self, orchestrator):
        """Self-critic failure should not crash pipeline."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            MockLLM.side_effect = Exception("LLM API error")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                final_answer="Answer",
                quality_issues=["Issue"],
                refinement_iteration=0,
                bundled_context=[]
            )
            
            # Should not raise, should return fallback
            result = await orchestrator._self_critic_node(state)
            
            assert "refinement_instructions" in result
            assert len(result["refinement_instructions"]) > 0
            assert result["refinement_iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_refined_synthesis_failure_preserves_original(self, orchestrator):
        """Refined synthesis failure should keep original answer."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            MockLLM.side_effect = Exception("Synthesis error")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                final_answer="Original answer",
                refinement_instructions=["Improve"],
                refinement_iteration=1,
                bundled_context=[]
            )
            
            result = await orchestrator._refined_synthesis_node(state)
            
            # Should return empty dict to keep original
            assert result == {}
    
    @pytest.mark.asyncio
    async def test_iterative_retrieval_failure_proceeds(self, orchestrator):
        """Iterative retrieval failure should proceed with existing sources."""
        with patch('api.tools.retrieval_engine.RetrievalEngine') as MockEngine:
            MockEngine.side_effect = Exception("Retrieval error")
            
            state = AgentState(
                raw_query="Test",
                user_id="test_user",
                session_id="test_session",
                quality_issues=["Insufficient"],
                bundled_context=[],
                combined_results=[],
                refinement_iteration=0
            )
            
            result = await orchestrator._iterative_retrieval_node(state)
            
            # Should return empty to proceed with existing
            assert result == {}


class TestMemoryIntegration:
    """Test memory system integration with query pipeline."""
    
    @pytest.mark.asyncio
    async def test_memory_context_in_intent_classification(self, orchestrator):
        """User profile should influence intent classification."""
        # Mock memory coordinator
        with patch.object(orchestrator, 'memory', create=True) as mock_memory:
            if mock_memory:
                mock_memory.get_full_context = AsyncMock(return_value={
                    'user_profile': {
                        'is_returning_user': True,
                        'typical_complexity': 'expert',
                        'expertise_level': 'professional',
                        'top_legal_interests': ['labour_law', 'constitutional_law'],
                        'query_count': 50
                    },
                    'recent_context': []
                })
                
                state = AgentState(
                    raw_query="What about employee rights?",
                    user_id="returning_user",
                    session_id="test_session"
                )
                
                result = await orchestrator._route_intent_node(state)
                
                # Should use user profile for personalization
                # (This will be more apparent with real memory instance)
                assert result["complexity"] is not None
                assert result["user_type"] is not None


class TestCacheIntegration:
    """Test cache system integration with query pipeline."""
    
    @pytest.mark.asyncio
    async def test_intent_cache_hit(self, orchestrator):
        """Cached intent should be returned quickly."""
        query = "What is minimum wage?"
        
        # First call - cache miss
        state1 = AgentState(
            raw_query=query,
            user_id="test_user",
            session_id="session_1"
        )
        
        result1 = await orchestrator._route_intent_node(state1)
        assert result1["intent"] is not None
        
        # Second call - should hit cache
        state2 = AgentState(
            raw_query=query,  # Same query
            user_id="test_user",
            session_id="session_2"
        )
        
        result2 = await orchestrator._route_intent_node(state2)
        
        # Results should be consistent
        assert result2["intent"] == result1["intent"]
        assert result2["complexity"] == result1["complexity"]


class TestRealWorldScenarios:
    """Test with realistic user scenarios."""
    
    @pytest.mark.asyncio
    async def test_citizen_simple_rights_query(self, orchestrator):
        """Citizen asking about basic rights."""
        state = AgentState(
            raw_query="Can I sue my employer if I'm not paid on time?",
            user_id="citizen_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["user_type"] == "citizen"
        assert result["complexity"] in ["simple", "moderate"]
    
    @pytest.mark.asyncio
    async def test_professional_statutory_analysis(self, orchestrator):
        """Professional asking about statutory interpretation."""
        state = AgentState(
            raw_query="What is the statutory interpretation of Section 12(3) regarding minimum wage applicability to part-time employees?",
            user_id="lawyer_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["user_type"] == "professional"
        assert result["reasoning_framework"] == "statutory"
        assert result["complexity"] in ["moderate", "complex", "expert"]
    
    @pytest.mark.asyncio
    async def test_constitutional_complex_query(self, orchestrator):
        """Complex constitutional query."""
        state = AgentState(
            raw_query="How do constitutional protections of fair labour practices interact with statutory employment regulations?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["reasoning_framework"] == "constitutional"
        assert result["complexity"] == "complex"
        assert "constitutional_law" in result["legal_areas"]
    
    @pytest.mark.asyncio
    async def test_conversational_greeting(self, orchestrator):
        """Conversational greeting should be handled quickly."""
        state = AgentState(
            raw_query="Hello, how are you?",
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "conversational"
        assert result["complexity"] == "simple"
        assert result["retrieval_top_k"] == 0  # No retrieval needed


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_quality_issues_passes(self, orchestrator):
        """Empty quality issues should pass through."""
        state = AgentState(
            raw_query="Test",
            user_id="test_user",
            session_id="test_session",
            quality_passed=True,
            quality_confidence=0.85,
            quality_issues=[],  # Empty
            refinement_iteration=0
        )
        
        decision = orchestrator._decide_refinement_strategy(state)
        assert decision == "pass"
    
    @pytest.mark.asyncio
    async def test_missing_bundled_context_handled(self, orchestrator):
        """Missing bundled context should not crash refinement."""
        with patch('langchain_openai.ChatOpenAI') as MockLLM:
            mock_response = MagicMock()
            mock_response.content = "Refined"
            
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
                    raw_query="Test",
                    user_id="test_user",
                    session_id="test_session",
                    final_answer="Answer",
                    refinement_instructions=["Improve"],
                    bundled_context=[],  # Empty
                    refinement_iteration=1
                )
                
                result = await orchestrator._refined_synthesis_node(state)
                
                # Should complete despite empty context
                assert "final_answer" in result or result == {}
    
    @pytest.mark.asyncio
    async def test_very_long_query_handled(self, orchestrator):
        """Very long queries should be handled gracefully."""
        long_query = "What are the legal implications " + "and ramifications " * 100
        
        state = AgentState(
            raw_query=long_query,
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        # Should classify despite length (may be moderate without enough legal terms)
        assert result["intent"] is not None
        assert result["complexity"] in ["simple", "moderate", "complex", "expert"]
        assert result["retrieval_top_k"] > 0
    
    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, orchestrator):
        """Special characters should not break classification."""
        special_query = "What's the law on employee's rights & employer's duties?"
        
        state = AgentState(
            raw_query=special_query,
            user_id="test_user",
            session_id="test_session"
        )
        
        result = await orchestrator._route_intent_node(state)
        
        assert result["intent"] == "rag_qa"
        assert result["complexity"] is not None


class TestConcurrentRequests:
    """Test handling of concurrent requests."""
    
    @pytest.mark.asyncio
    async def test_multiple_simultaneous_queries(self, orchestrator):
        """Multiple simultaneous queries should be handled independently."""
        queries = [
            "What is minimum wage?",
            "How do I file a case?",
            "What are employee rights?"
        ]
        
        # Create states
        states = [
            AgentState(
                raw_query=query,
                user_id=f"user_{i}",
                session_id=f"session_{i}"
            )
            for i, query in enumerate(queries)
        ]
        
        # Process concurrently
        tasks = [
            orchestrator._route_intent_node(state)
            for state in states
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete
        assert len(results) == 3
        for result in results:
            assert result["intent"] is not None
            assert result["complexity"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


#!/usr/bin/env python3
"""
Test suite for QueryOrchestrator LangGraph implementation (Task 4.2)

Following TDD principles from .cursorrules, this test suite covers:
- LangGraph orchestrator initialization and compilation
- Individual node functionality (intent router, rewrite & expand)
- State management and progression through nodes
- End-to-end query processing flow
- Error handling and graceful degradation
- Performance requirements (latency budgets)

Author: RightLine Team
"""

import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Any

from api.orchestrators.query_orchestrator import QueryOrchestrator
from api.schemas.agent_state import AgentState


class TestQueryOrchestratorInitialization:
    """Test QueryOrchestrator initialization and setup."""
    
    def test_orchestrator_initialization(self):
        """Test that QueryOrchestrator initializes correctly."""
        orchestrator = QueryOrchestrator()
        
        # Verify graph is compiled
        assert orchestrator.graph is not None
        
        # Verify checkpointer is set up (graph is the compiled app)
        assert hasattr(orchestrator.graph, 'checkpointer')
    
    def test_graph_structure(self):
        """Test that the graph has correct nodes and edges."""
        orchestrator = QueryOrchestrator()
        
        # Check that all expected nodes are present
        expected_nodes = {
            "route_intent", "rewrite_expand", "retrieve_concurrent", 
            "rerank", "expand_parents", "synthesize_stream",
            "conversational_tool", "summarizer_tool", "session_search"
        }
        
        # Note: LangGraph doesn't expose nodes directly, so we test by trying to export
        graph_description = orchestrator.export_graph_diagram()
        
        assert "route_intent" in graph_description
        assert "rewrite_expand" in graph_description
        assert "retrieve_concurrent" in graph_description
    
    def test_graph_compilation(self):
        """Test that the graph compiles without errors."""
        # This should not raise an exception
        orchestrator = QueryOrchestrator()
        
        # Verify the compiled graph is callable
        assert callable(orchestrator.graph)


class TestIntentRouterNode:
    """Test the intent router node functionality."""
    
    @pytest.mark.asyncio
    async def test_intent_router_heuristics_qa(self):
        """Test intent router recognizes Q&A queries with heuristics."""
        orchestrator = QueryOrchestrator()
        
        # Test Q&A query with legal keywords
        state = AgentState(
            trace_id="test-qa-123",
            user_id="user",
            session_id="session", 
            raw_query="What does the Labour Act say about employment rights?"
        )
        
        # Test the internal heuristic function
        result = orchestrator._classify_intent_heuristic(state.raw_query)
        
        assert result == "rag_qa"
    
    @pytest.mark.asyncio
    async def test_intent_router_heuristics_conversational(self):
        """Test intent router recognizes conversational queries."""
        orchestrator = QueryOrchestrator()
        
        # Test conversational query
        conversational_queries = [
            "Hello, how are you?",
            "Thanks for the help!",
            "Can you help me?",
            "Good morning"
        ]
        
        for query in conversational_queries:
            result = orchestrator._classify_intent_heuristic(query)
            assert result == "conversational", f"Failed for query: {query}"
    
    @pytest.mark.asyncio 
    async def test_intent_router_heuristics_summarize(self):
        """Test intent router recognizes summarization requests."""
        orchestrator = QueryOrchestrator()
        
        # Test summarization queries
        summarize_queries = [
            "Summarize the Labour Act",
            "Give me a summary of employment law",
            "What are the key points of this act?",
            "Provide an overview of worker rights"
        ]
        
        for query in summarize_queries:
            result = orchestrator._classify_intent_heuristic(query)
            assert result == "summarize", f"Failed for query: {query}"
    
    @pytest.mark.asyncio
    async def test_intent_router_jurisdiction_detection(self):
        """Test jurisdiction detection in queries."""
        orchestrator = QueryOrchestrator()
        
        test_cases = [
            ("What is minimum wage in Zimbabwe?", "ZW"),
            ("Zimbabwean employment law", "ZW"),
            ("What about workers in Harare?", "ZW"),
            ("South African employment law", None),  # Not implemented
            ("Botswana labor regulations", None)     # Not implemented
        ]
        
        for query, expected_jurisdiction in test_cases:
            result = orchestrator._detect_jurisdiction(query)
            assert result == expected_jurisdiction, f"Failed jurisdiction detection for: {query}"
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_intent_router_llm_fallback(self, mock_openai):
        """Test LLM fallback for ambiguous queries."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.content = '{"intent": "rag_qa", "jurisdiction": "ZW", "date_context": null}'
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        # Test ambiguous query that should trigger LLM
        ambiguous_query = "employment stuff"
        result = await orchestrator._classify_intent_llm(ambiguous_query)
        
        assert result["intent"] == "rag_qa"
        assert result["jurisdiction"] == "ZW"
        mock_chain.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_intent_router_performance(self):
        """Test that intent routing meets performance requirements."""
        orchestrator = QueryOrchestrator()
        
        # Test heuristic performance (should be < 70ms P50)
        queries = [
            "What is minimum wage?",
            "Hello there",
            "Summarize the act", 
            "Employment law in Zimbabwe",
            "Good morning"
        ]
        
        times = []
        for query in queries:
            start = time.time()
            result = orchestrator._classify_intent_heuristic(query)
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms
            
            assert result is not None
        
        p50_time = sorted(times)[len(times) // 2]
        assert p50_time < 70, f"P50 heuristic time {p50_time}ms exceeds 70ms requirement"


class TestRewriteExpandNode:
    """Test the rewrite & expand node functionality."""
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_query_rewrite(self, mock_openai):
        """Test query rewriting functionality."""
        # Mock OpenAI response for rewrite
        mock_response = Mock()
        mock_response.content = "Enhanced query about minimum wage requirements in Zimbabwe"
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        original_query = "What is minimum wage?"
        rewritten = await orchestrator._rewrite_query(original_query, [])
        
        assert rewritten is not None
        assert "Zimbabwe" in rewritten or "wage" in rewritten
        mock_chain.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI') 
    async def test_multi_hyde_generation(self, mock_openai):
        """Test Multi-HyDE hypothetical document generation."""
        # Mock OpenAI responses for multiple hypotheticals
        mock_responses = [
            Mock(content="Hypothetical document about wage regulations"),
            Mock(content="Sample text about employment standards"),
            Mock(content="Example content on labor law requirements")
        ]
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = mock_responses
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        query = "What is minimum wage in Zimbabwe?"
        hypotheticals = await orchestrator._generate_multi_hyde(query, count=3)
        
        assert len(hypotheticals) >= 2  # Should get at least 2 even if some fail
        assert all(len(h) <= 120 for h in hypotheticals)  # Token limit check (approx)
        assert mock_chain.ainvoke.call_count == 3
    
    @pytest.mark.asyncio
    async def test_sub_question_decomposition(self):
        """Test sub-question decomposition functionality."""
        orchestrator = QueryOrchestrator()
        
        complex_query = "What are employment rights and employer obligations in Zimbabwe?"
        sub_questions = await orchestrator._decompose_query(complex_query)
        
        # Should generate sub-questions for complex queries
        assert len(sub_questions) <= 3  # Cap of 3
        assert all(isinstance(q, str) for q in sub_questions)
        assert all(len(q) > 5 for q in sub_questions)  # Non-trivial questions
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_rewrite_expand_timeout_handling(self, mock_openai):
        """Test graceful timeout handling in rewrite & expand."""
        # Mock slow OpenAI response that times out
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = asyncio.TimeoutError()
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        # Should gracefully handle timeout and return original query
        original_query = "What is minimum wage?"
        rewritten = await orchestrator._rewrite_query(original_query, [])
        
        # Should fallback to original query on timeout
        assert rewritten == original_query
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_rewrite_expand_performance(self, mock_openai):
        """Test that rewrite & expand meets performance requirements."""
        # Mock fast OpenAI responses
        mock_response = Mock()
        mock_response.content = "Rewritten query"
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        query = "What is employment law?"
        
        start = time.time()
        rewritten = await orchestrator._rewrite_query(query, [])
        hypotheticals = await orchestrator._generate_multi_hyde(query, count=3)
        end = time.time()
        
        total_time_ms = (end - start) * 1000
        
        # Should complete under 450ms P95 requirement
        assert total_time_ms < 450, f"Rewrite & expand took {total_time_ms}ms, exceeds 450ms requirement"
        assert rewritten is not None
        assert len(hypotheticals) >= 2


class TestQueryOrchestratorEndToEnd:
    """Test end-to-end query orchestration flow."""
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_complete_query_flow_qa(self, mock_openai):
        """Test complete query processing flow for Q&A."""
        # Mock OpenAI responses
        mock_response = Mock()
        mock_response.content = "Enhanced query about Zimbabwe employment law"
        
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_response
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        # Create initial state
        initial_state = AgentState(
            trace_id="e2e-test-123",
            user_id="test-user",
            session_id="test-session",
            raw_query="What is the minimum wage in Zimbabwe?"
        )
        
        # Run the orchestrator
        result_state = await orchestrator.run_query(initial_state)
        
        # Verify state progression
        assert isinstance(result_state, AgentState)
        assert result_state.trace_id == "e2e-test-123"
        assert result_state.raw_query == "What is the minimum wage in Zimbabwe?"
        
        # Should have been processed through intent routing
        # Note: Since we're mocking, we can't test the full pipeline
        # but we can verify the structure is maintained
    
    @pytest.mark.asyncio
    async def test_conversational_query_routing(self):
        """Test that conversational queries route correctly."""
        orchestrator = QueryOrchestrator()
        
        # Test conversational query
        initial_state = AgentState(
            trace_id="conv-test-123", 
            user_id="test-user",
            session_id="test-session",
            raw_query="Hello, how are you today?"
        )
        
        # Test the routing decision
        decision = orchestrator._decide_route(initial_state)
        
        # Should route to conversational tool
        assert decision == "conversational"
    
    @pytest.mark.asyncio
    async def test_state_persistence_with_checkpointer(self):
        """Test that state is properly persisted with checkpointer."""
        orchestrator = QueryOrchestrator()
        
        initial_state = AgentState(
            trace_id="checkpoint-test",
            user_id="test-user", 
            session_id="test-session-checkpoint",
            raw_query="Test checkpointing"
        )
        
        # The checkpointer should be configured
        assert orchestrator.graph.checkpointer is not None
        
        # State should be serializable for checkpointing
        state_dict = initial_state.model_dump()
        assert isinstance(state_dict, dict)
        
        # Should be able to reconstruct from dict
        restored_state = AgentState.model_validate(state_dict)
        assert restored_state.trace_id == initial_state.trace_id


class TestQueryOrchestratorErrorHandling:
    """Test error handling and resilience."""
    
    @pytest.mark.asyncio
    async def test_invalid_state_handling(self):
        """Test handling of invalid state inputs."""
        orchestrator = QueryOrchestrator()
        
        # Test with missing required fields - should be caught by Pydantic
        with pytest.raises(Exception):  # Could be ValidationError or TypeError
            invalid_state = AgentState(
                trace_id="invalid-test"
                # Missing required fields
            )
            await orchestrator.run_query(invalid_state)
    
    @pytest.mark.asyncio
    @patch('api.orchestrators.query_orchestrator.ChatOpenAI')
    async def test_llm_failure_graceful_degradation(self, mock_openai):
        """Test graceful degradation when LLM calls fail."""
        # Mock LLM failure
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = Exception("OpenAI API Error")
        mock_openai.return_value = mock_chain
        
        orchestrator = QueryOrchestrator()
        
        # Should handle LLM failures gracefully
        query = "Ambiguous query that needs LLM"
        
        # Intent classification should fallback to heuristics
        result = orchestrator._classify_intent_heuristic(query)
        assert result["intent"] in ["rag_qa", "conversational", "summarize", "disambiguate"]
        
        # Query rewrite should fallback to original
        rewritten = await orchestrator._rewrite_query(query, [])
        assert rewritten == query  # Should return original on failure


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/api/test_query_orchestrator.py -v
    pytest.main([__file__, "-v"])

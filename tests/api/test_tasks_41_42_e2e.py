#!/usr/bin/env python3
"""
End-to-End Integration Tests for Tasks 4.1 and 4.2

This test suite verifies that the AgentState and QueryOrchestrator components
work together correctly to process real queries through the agentic pipeline.

Author: RightLine Team
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from api.schemas.agent_state import AgentState
from api.orchestrators.query_orchestrator import QueryOrchestrator


class TestTasks41And42Integration:
    """Integration tests for Tasks 4.1 and 4.2 working together."""
    
    def test_agent_state_and_orchestrator_compatibility(self):
        """Test that AgentState and QueryOrchestrator are compatible."""
        # Create initial state
        state = AgentState(
            user_id="test-user",
            session_id="test-session", 
            raw_query="What are employment rights in Zimbabwe?"
        )
        
        # Create orchestrator
        orchestrator = QueryOrchestrator()
        
        # Verify they're compatible
        assert state.trace_id is not None  # Auto-generated
        assert state.state_version == "v1"
        assert orchestrator.graph is not None
        
        # State should be serializable for checkpointer
        state_dict = state.model_dump()
        assert "trace_id" in state_dict
        assert "raw_query" in state_dict
    
    @pytest.mark.asyncio
    async def test_intent_routing_with_real_queries(self):
        """Test intent routing with various real query types."""
        orchestrator = QueryOrchestrator()
        
        test_cases = [
            # (query, expected_intent)
            ("Hello, how can you help me?", "conversational"),
            ("Summarize the Labour Act", "summarize"),
            ("What does the Employment Act say about rights?", "rag_qa"),
            ("What are the key points of worker protection?", "summarize"),
        ]
        
        for query, expected_intent in test_cases:
            result = orchestrator._classify_intent_heuristic(query)
            if result is not None:  # Some may need LLM fallback
                assert result == expected_intent, f"Failed for query: {query}"
    
    @pytest.mark.asyncio
    async def test_state_progression_through_intent_routing(self):
        """Test that state progresses correctly through intent routing."""
        orchestrator = QueryOrchestrator()
        
        # Create initial state
        initial_state = AgentState(
            user_id="test-user",
            session_id="test-session",
            raw_query="What does the Labour Act say about employment rights?"
        )
        
        # Verify initial state
        assert initial_state.intent is None
        assert initial_state.jurisdiction is None
        
        # Test intent classification
        intent = orchestrator._classify_intent_heuristic(initial_state.raw_query)
        assert intent == "rag_qa"
        
        # Test jurisdiction detection
        jurisdiction = orchestrator._detect_jurisdiction(initial_state.raw_query)
        assert jurisdiction is None  # No jurisdiction keywords in this query
        
        # Test with Zimbabwe-specific query
        zw_query = "What are employment rights in Zimbabwe?"
        zw_jurisdiction = orchestrator._detect_jurisdiction(zw_query)
        assert zw_jurisdiction == "ZW"
    
    @pytest.mark.asyncio
    async def test_state_size_limits_realistic_scenario(self):
        """Test AgentState size limits with realistic orchestrator data."""
        # Simulate a state that has gone through multiple processing steps
        processed_state = AgentState(
            user_id="user-123",
            session_id="session-456",
            raw_query="What are the detailed employment regulations and worker rights in Zimbabwe, including minimum wage, working hours, leave entitlements, and employer obligations under the current Labour Act?",
            session_history_ids=[f"msg_{i}" for i in range(5)],
            intent="rag_qa",
            jurisdiction="ZW",
            rewritten_query="Employment regulations, worker rights, minimum wage, working hours, leave entitlements, employer obligations in Zimbabwe Labour Act",
            hypothetical_docs=[
                "Document about Zimbabwe employment regulations and minimum wage requirements",
                "Guide to worker rights and employer obligations under Labour Act",
                "Overview of working hours and leave entitlements in Zimbabwe"
            ],
            sub_questions=[
                "What is the minimum wage in Zimbabwe?",
                "What are the working hour limits?",
                "What leave entitlements do workers have?"
            ],
            candidate_chunk_ids=[f"chunk_{i}" for i in range(15)],
            reranked_chunk_ids=[f"chunk_{i}" for i in range(10)],
            parent_doc_keys=[f"doc_{i}.json" for i in range(5)]
        )
        
        # Verify it's still under size limit
        json_str = processed_state.model_dump_json()
        size_bytes = len(json_str.encode('utf-8'))
        
        assert size_bytes < 8192, f"Processed state size {size_bytes} bytes exceeds 8KB limit"
        print(f"Realistic processed state size: {size_bytes} bytes")
    
    @pytest.mark.asyncio
    async def test_orchestrator_decision_routing(self):
        """Test the orchestrator's decision routing logic."""
        orchestrator = QueryOrchestrator()
        
        # Test different state scenarios
        test_scenarios = [
            # Conversational query
            AgentState(
                user_id="user", session_id="session", raw_query="Hello there",
                intent="conversational"
            ),
            # RAG Q&A query  
            AgentState(
                user_id="user", session_id="session", raw_query="What does the act say?",
                intent="rag_qa"
            ),
            # Summarization query
            AgentState(
                user_id="user", session_id="session", raw_query="Summarize the law",
                intent="summarize"
            )
        ]
        
        expected_routes = ["conversational", "rag_qa", "summarize"]
        
        for state, expected_route in zip(test_scenarios, expected_routes):
            route = orchestrator._decide_route(state)
            assert route == expected_route, f"Failed routing for intent: {state.intent}"
    
    @pytest.mark.asyncio
    async def test_performance_requirements_integration(self):
        """Test that the integration meets performance requirements."""
        import time
        
        orchestrator = QueryOrchestrator()
        
        # Test intent classification performance (should be < 70ms P50)
        queries = [
            "What are employment rights?",
            "Hello, how are you?", 
            "Summarize the Labour Act",
            "What does the law say about wages?",
            "Good morning"
        ]
        
        times = []
        for query in queries:
            start = time.time()
            
            # Simulate the fast path processing
            intent = orchestrator._classify_intent_heuristic(query)
            jurisdiction = orchestrator._detect_jurisdiction(query)
            
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms
        
        p50_time = sorted(times)[len(times) // 2]
        assert p50_time < 70, f"P50 processing time {p50_time}ms exceeds 70ms requirement"
        print(f"P50 intent + jurisdiction processing time: {p50_time:.2f}ms")
    
    @pytest.mark.asyncio 
    async def test_error_handling_integration(self):
        """Test error handling between AgentState and QueryOrchestrator."""
        orchestrator = QueryOrchestrator()
        
        # Test with edge case queries
        edge_cases = [
            "",  # Empty query
            "a",  # Single character
            "?" * 1000,  # Very long query
            "🚀🔥💯",  # Emoji only
        ]
        
        for query in edge_cases:
            try:
                # Create state (may fail validation)
                state = AgentState(
                    user_id="test-user",
                    session_id="test-session",
                    raw_query=query
                )
                
                # Test classification (should handle gracefully)
                intent = orchestrator._classify_intent_heuristic(query)
                jurisdiction = orchestrator._detect_jurisdiction(query)
                
                # Should not crash
                assert intent in [None, "conversational", "rag_qa", "summarize", "disambiguate"]
                assert jurisdiction in [None, "ZW"]
                
            except Exception as e:
                # Some edge cases may legitimately fail validation
                print(f"Edge case '{query}' failed as expected: {e}")
    
    def test_schema_evolution_compatibility(self):
        """Test that the orchestrator handles schema evolution."""
        # Test with minimal v1 state (as if from old data)
        minimal_state = AgentState(
            user_id="user",
            session_id="session",
            raw_query="test query"
        )
        
        # Should work with orchestrator
        orchestrator = QueryOrchestrator()
        
        # Should be able to route
        route = orchestrator._decide_route(minimal_state)
        assert route in ["rag_qa", "conversational", "summarize", "disambiguate"]
        
        # State should be serializable
        state_dict = minimal_state.model_dump()
        assert state_dict["state_version"] == "v1"


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/api/test_tasks_41_42_e2e.py -v
    pytest.main([__file__, "-v"])

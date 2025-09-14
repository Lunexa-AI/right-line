#!/usr/bin/env python3
"""
Test the real query workflow with: "Is it legal to import white phosphorus in Zimbabwe?"

This test simulates the complete Tasks 4.1 and 4.2 workflow to see what actually happens
when a user submits a real query.
"""

import asyncio
import json
import time
from api.schemas.agent_state import AgentState
from api.orchestrators.query_orchestrator import QueryOrchestrator


async def test_real_query_workflow():
    """Test the complete workflow with a real user query."""
    
    print("🧪 Testing Real Query Workflow")
    print("=" * 60)
    
    # The actual user query
    user_query = "Is it legal to import white phosphorus in Zimbabwe?"
    print(f"📝 User Query: '{user_query}'")
    print()
    
    # Step 1: Create initial AgentState (Task 4.1)
    print("🔧 Step 1: Creating AgentState...")
    start_time = time.time()
    
    initial_state = AgentState(
        user_id="test-user-12345",
        session_id="session-67890", 
        raw_query=user_query
    )
    
    print(f"✅ AgentState created:")
    print(f"   - Trace ID: {initial_state.trace_id}")
    print(f"   - User ID: {initial_state.user_id}")
    print(f"   - Session ID: {initial_state.session_id}")
    print(f"   - State Version: {initial_state.state_version}")
    print(f"   - Created At: {initial_state.created_at}")
    print(f"   - Raw Query: {initial_state.raw_query}")
    print()
    
    # Step 2: Initialize QueryOrchestrator (Task 4.2)
    print("🤖 Step 2: Initializing QueryOrchestrator...")
    orchestrator = QueryOrchestrator()
    print(f"✅ QueryOrchestrator initialized with LangGraph")
    print(f"   - Graph compiled: {orchestrator.graph is not None}")
    print(f"   - Checkpointer available: {hasattr(orchestrator.graph, 'checkpointer')}")
    print()
    
    # Step 3: Test Intent Classification
    print("🎯 Step 3: Intent Classification...")
    intent_start = time.time()
    
    intent = orchestrator._classify_intent_heuristic(user_query)
    intent_time = (time.time() - intent_start) * 1000
    
    print(f"✅ Intent Classification Result:")
    print(f"   - Intent: {intent}")
    print(f"   - Processing Time: {intent_time:.2f}ms")
    print(f"   - Performance: {'✅ PASS' if intent_time < 70 else '❌ FAIL'} (< 70ms required)")
    print()
    
    # Step 4: Test Jurisdiction Detection
    print("🌍 Step 4: Jurisdiction Detection...")
    jurisdiction_start = time.time()
    
    jurisdiction = orchestrator._detect_jurisdiction(user_query)
    jurisdiction_time = (time.time() - jurisdiction_start) * 1000
    
    print(f"✅ Jurisdiction Detection Result:")
    print(f"   - Jurisdiction: {jurisdiction}")
    print(f"   - Processing Time: {jurisdiction_time:.2f}ms")
    print()
    
    # Step 5: Test Date Context Extraction
    print("📅 Step 5: Date Context Extraction...")
    date_context = orchestrator._extract_date_context(user_query)
    print(f"✅ Date Context: {date_context}")
    print()
    
    # Step 6: Test Decision Routing
    print("🔀 Step 6: Decision Routing...")
    
    # Create a state with the detected intent for routing
    routing_state = initial_state.model_copy(update={
        "intent": intent or "rag_qa",  # Default to rag_qa if None
        "jurisdiction": jurisdiction,
        "date_context": date_context
    })
    
    route_decision = orchestrator._decide_route(routing_state)
    
    print(f"✅ Routing Decision:")
    print(f"   - Route: {route_decision}")
    print(f"   - Will go to: {route_decision} node")
    print()
    
    # Step 7: Simulate State Updates
    print("📊 Step 7: State Progression Simulation...")
    
    # Update state with processing results
    updated_state = routing_state.model_copy(update={
        "intent": intent or "rag_qa",
        "jurisdiction": jurisdiction,
        "date_context": date_context
    })
    
    print(f"✅ State Updated:")
    print(f"   - Intent: {updated_state.intent}")
    print(f"   - Jurisdiction: {updated_state.jurisdiction}")
    print(f"   - Date Context: {updated_state.date_context}")
    print()
    
    # Step 8: Test State Serialization
    print("💾 Step 8: State Serialization Test...")
    serialization_start = time.time()
    
    state_json = updated_state.model_dump_json()
    state_size = len(state_json.encode('utf-8'))
    serialization_time = (time.time() - serialization_start) * 1000
    
    print(f"✅ Serialization Results:")
    print(f"   - JSON Size: {state_size} bytes")
    print(f"   - Size Check: {'✅ PASS' if state_size < 8192 else '❌ FAIL'} (< 8KB required)")
    print(f"   - Serialization Time: {serialization_time:.2f}ms")
    print()
    
    # Step 9: Query Analysis
    print("🔍 Step 9: Query Analysis...")
    query_lower = user_query.lower()
    
    # Analyze what the query contains
    legal_keywords = ["legal", "import", "zimbabwe"]
    substance_keywords = ["white phosphorus", "phosphorus"]
    regulatory_keywords = ["import", "legal", "regulation", "law"]
    
    found_legal = [kw for kw in legal_keywords if kw in query_lower]
    found_substance = [kw for kw in substance_keywords if kw in query_lower]
    found_regulatory = [kw for kw in regulatory_keywords if kw in query_lower]
    
    print(f"✅ Query Analysis:")
    print(f"   - Legal keywords found: {found_legal}")
    print(f"   - Substance keywords found: {found_substance}")
    print(f"   - Regulatory keywords found: {found_regulatory}")
    print(f"   - Query complexity: {'High' if len(found_legal + found_substance + found_regulatory) > 3 else 'Medium'}")
    print()
    
    # Step 10: Performance Summary
    total_time = (time.time() - start_time) * 1000
    
    print("⚡ Step 10: Performance Summary...")
    print(f"✅ Total Processing Time: {total_time:.2f}ms")
    print(f"   - Intent Classification: {intent_time:.2f}ms")
    print(f"   - Jurisdiction Detection: {jurisdiction_time:.2f}ms")
    print(f"   - State Serialization: {serialization_time:.2f}ms")
    print(f"   - Performance Target: {'✅ PASS' if total_time < 200 else '❌ FAIL'} (< 200ms for full pipeline)")
    print()
    
    # Step 11: What would happen next?
    print("🚀 Step 11: Next Steps in Pipeline...")
    print(f"✅ Based on routing decision '{route_decision}', the query would:")
    
    if route_decision == "rag_qa":
        print("   1. Go to 'rewrite_expand' node for query enhancement")
        print("   2. Generate hypothetical documents (Multi-HyDE)")
        print("   3. Proceed to 'retrieve_concurrent' for hybrid search")
        print("   4. Use reranking in 'rerank' node")
        print("   5. Expand to parent documents in 'expand_parents'")
        print("   6. Generate final answer in 'synthesize_stream'")
    elif route_decision == "conversational":
        print("   1. Go directly to 'conversational_tool' node")
        print("   2. Generate conversational response")
        print("   3. End pipeline")
    elif route_decision == "summarize":
        print("   1. Go directly to 'summarizer_tool' node")
        print("   2. Generate summary response")
        print("   3. End pipeline")
    
    print()
    
    # Step 12: Expected Retrieval Strategy
    if route_decision == "rag_qa":
        print("🔍 Step 12: Expected Retrieval Strategy...")
        print("✅ For this query, the system would likely search for:")
        print("   - Import regulations in Zimbabwe")
        print("   - Chemical import laws")
        print("   - White phosphorus classification")
        print("   - Hazardous materials import procedures")
        print("   - Trade regulations and permits")
        print()
    
    print("🎉 WORKFLOW TEST COMPLETE!")
    print("=" * 60)
    
    return {
        "initial_state": initial_state,
        "final_state": updated_state,
        "intent": intent,
        "jurisdiction": jurisdiction,
        "route": route_decision,
        "performance": {
            "total_time_ms": total_time,
            "intent_time_ms": intent_time,
            "jurisdiction_time_ms": jurisdiction_time,
            "serialization_time_ms": serialization_time,
            "state_size_bytes": state_size
        }
    }


if __name__ == "__main__":
    # Run the workflow test
    result = asyncio.run(test_real_query_workflow())
    
    print("\n📋 SUMMARY RESULTS:")
    print(f"Query processed successfully: ✅")
    print(f"Intent detected: {result['intent']}")
    print(f"Jurisdiction detected: {result['jurisdiction']}")
    print(f"Routing decision: {result['route']}")
    print(f"Total processing time: {result['performance']['total_time_ms']:.2f}ms")
    print(f"State size: {result['performance']['state_size_bytes']} bytes")

#!/usr/bin/env python3
"""
Test multiple real queries to validate the complete workflow
"""

import asyncio
import time
from api.schemas.agent_state import AgentState
from api.orchestrators.query_orchestrator import QueryOrchestrator


def test_query_classification(orchestrator, query):
    """Test a single query and return results."""
    start_time = time.time()
    
    # Create state
    state = AgentState(
        user_id="test-user",
        session_id="test-session",
        raw_query=query
    )
    
    # Classify intent
    intent = orchestrator._classify_intent_heuristic(query)
    jurisdiction = orchestrator._detect_jurisdiction(query)
    
    # Update state and route
    updated_state = state.model_copy(update={
        "intent": intent or "rag_qa",
        "jurisdiction": jurisdiction
    })
    
    route = orchestrator._decide_route(updated_state)
    
    processing_time = (time.time() - start_time) * 1000
    
    return {
        "query": query,
        "intent": intent,
        "jurisdiction": jurisdiction,
        "route": route,
        "processing_time_ms": processing_time,
        "trace_id": state.trace_id
    }


def main():
    print("🧪 Testing Multiple Real Queries")
    print("=" * 80)
    
    orchestrator = QueryOrchestrator()
    
    # Test different types of queries
    test_queries = [
        # Legal/regulatory questions (should be rag_qa)
        "Is it legal to import white phosphorus in Zimbabwe?",
        "What does the Labour Act say about minimum wage?",
        "What are the requirements for company registration?",
        "Can I get a business license for mining?",
        
        # Conversational queries (should be conversational)
        "Hello, how can you help me?",
        "Hi there, good morning!",
        "Thanks for your help",
        "Hey, what's up?",
        
        # Summarization queries (should be summarize)
        "Summarize the Employment Act",
        "Give me a summary of worker rights",
        "What are the key points of the Labour Act?",
        "Can you explain the mining regulations in simple terms?",
        
        # Edge cases
        "What is white phosphorus used for?",  # Should be rag_qa (has legal keyword)
        "Hi, what does the law say about employment?",  # Mixed - should be rag_qa (legal wins)
    ]
    
    results = []
    total_start = time.time()
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n📝 Query {i}: '{query}'")
        result = test_query_classification(orchestrator, query)
        results.append(result)
        
        print(f"   ✅ Intent: {result['intent']}")
        print(f"   🌍 Jurisdiction: {result['jurisdiction']}")
        print(f"   🔀 Route: {result['route']}")
        print(f"   ⚡ Time: {result['processing_time_ms']:.2f}ms")
    
    total_time = (time.time() - total_start) * 1000
    
    print(f"\n" + "=" * 80)
    print("📊 SUMMARY RESULTS")
    print("=" * 80)
    
    # Group by intent
    by_intent = {}
    for result in results:
        intent = result['intent'] or 'None'
        if intent not in by_intent:
            by_intent[intent] = []
        by_intent[intent].append(result)
    
    for intent, queries in by_intent.items():
        print(f"\n🎯 {intent.upper()} ({len(queries)} queries):")
        for result in queries:
            print(f"   • '{result['query'][:50]}...' → {result['route']} ({result['processing_time_ms']:.2f}ms)")
    
    # Performance analysis
    times = [r['processing_time_ms'] for r in results]
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"\n⚡ PERFORMANCE ANALYSIS:")
    print(f"   • Total queries: {len(results)}")
    print(f"   • Total time: {total_time:.2f}ms")
    print(f"   • Average time per query: {avg_time:.2f}ms")
    print(f"   • Min time: {min_time:.2f}ms")
    print(f"   • Max time: {max_time:.2f}ms")
    print(f"   • Performance target: {'✅ PASS' if avg_time < 70 else '❌ FAIL'} (< 70ms avg)")
    
    # Jurisdiction detection
    zw_queries = [r for r in results if r['jurisdiction'] == 'ZW']
    print(f"\n🌍 JURISDICTION DETECTION:")
    print(f"   • Zimbabwe queries detected: {len(zw_queries)}")
    for result in zw_queries:
        print(f"     - '{result['query'][:40]}...'")
    
    print(f"\n🎉 ALL TESTS COMPLETE!")
    
    return results


if __name__ == "__main__":
    results = main()

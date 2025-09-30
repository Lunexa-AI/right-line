#!/usr/bin/env python3
"""
Phase 2 Performance Measurement Script.

Measures performance improvements from:
- Caching (50-80% latency reduction for cached queries)
- Speculative execution (parent prefetch optimization)

Usage:
    python tests/evaluation/measure_phase2_performance.py
    python tests/evaluation/measure_phase2_performance.py --iterations 10

Author: RightLine Team
"""

import asyncio
import time
import sys
from pathlib import Path
from typing import List, Dict, Any
from statistics import mean, median

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.orchestrators.query_orchestrator import get_orchestrator
from api.schemas.agent_state import AgentState


TEST_QUERIES = [
    "What are employee rights under labour law?",
    "Can an employer dismiss without a hearing?",
    "What is the notice period for termination?",
    "What is the right to freedom of assembly?",
    "How do I register a company in Zimbabwe?",
]


async def measure_query_latency(query: str, cache_enabled: bool = True) -> Dict[str, Any]:
    """Measure latency for a single query."""
    
    orchestrator = get_orchestrator()
    
    # Optionally disable cache for baseline
    original_cache = orchestrator.cache
    if not cache_enabled:
        orchestrator.cache = None
    
    try:
        state = AgentState(
            user_id="perf_test_user",
            session_id=f"perf_{time.time()}",
            raw_query=query
        )
        
        start = time.time()
        result = await orchestrator.run_query(state)
        duration_ms = (time.time() - start) * 1000
        
        # Check if from cache
        from_cache = result.safety_flags.get("from_cache", False)
        cache_hit_type = result.safety_flags.get("cache_hit_type", "none")
        
        # Get node timings
        prefetch_time = result.node_timings.get("07a_parent_prefetch", 0)
        select_time = result.node_timings.get("07b_parent_select", 0)
        parent_total = prefetch_time + select_time
        
        return {
            "query": query[:50],
            "total_ms": round(duration_ms, 2),
            "from_cache": from_cache,
            "cache_hit_type": cache_hit_type,
            "parent_prefetch_ms": round(prefetch_time, 2) if prefetch_time else None,
            "parent_select_ms": round(select_time, 2) if select_time else None,
            "parent_total_ms": round(parent_total, 2) if parent_total else None,
            "has_answer": bool(result.final_answer)
        }
    
    finally:
        # Restore cache
        if not cache_enabled:
            orchestrator.cache = original_cache


async def run_performance_evaluation(iterations: int = 5):
    """Run complete performance evaluation."""
    
    print("="*80)
    print("PHASE 2 PERFORMANCE EVALUATION")
    print("="*80)
    print(f"\nTesting with {len(TEST_QUERIES)} queries, {iterations} iterations each\n")
    
    results = {
        "cached": [],
        "uncached": []
    }
    
    # Test each query multiple times
    for iteration in range(iterations):
        print(f"\n--- Iteration {iteration + 1}/{iterations} ---")
        
        for query in TEST_QUERIES:
            # First run might be cached from previous iterations
            result = await measure_query_latency(query, cache_enabled=True)
            
            print(f"  {result['query']}")
            print(f"    Time: {result['total_ms']}ms")
            print(f"    Cache: {result['cache_hit_type'] if result['from_cache'] else 'miss'}")
            
            if result['from_cache']:
                results['cached'].append(result['total_ms'])
            else:
                results['uncached'].append(result['total_ms'])
                if result['parent_total_ms']:
                    print(f"    Parent ops: {result['parent_total_ms']}ms")
            
            # Small delay
            await asyncio.sleep(0.5)
    
    # Calculate statistics
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    
    if results['cached']:
        print(f"\n📊 Cached Queries ({len(results['cached'])} samples):")
        print(f"  Mean: {mean(results['cached']):.2f}ms")
        print(f"  Median: {median(results['cached']):.2f}ms")
        print(f"  Min: {min(results['cached']):.2f}ms")
        print(f"  Max: {max(results['cached']):.2f}ms")
    
    if results['uncached']:
        print(f"\n📊 Uncached Queries ({len(results['uncached'])} samples):")
        print(f"  Mean: {mean(results['uncached']):.2f}ms")
        print(f"  Median: {median(results['uncached']):.2f}ms")
        print(f"  Min: {min(results['uncached']):.2f}ms")
        print(f"  Max: {max(results['uncached']):.2f}ms")
    
    if results['cached'] and results['uncached']:
        speedup = mean(results['uncached']) / mean(results['cached'])
        improvement = ((mean(results['uncached']) - mean(results['cached'])) / mean(results['uncached'])) * 100
        
        print(f"\n🚀 Performance Impact:")
        print(f"  Speedup: {speedup:.1f}x faster")
        print(f"  Improvement: {improvement:.1f}% latency reduction")
        
        if improvement >= 50:
            print(f"\n✅ EXCELLENT: {improvement:.1f}% improvement exceeds 50% target!")
        elif improvement >= 30:
            print(f"\n✅ GOOD: {improvement:.1f}% improvement meets target")
        else:
            print(f"\n⚠️  BELOW TARGET: {improvement:.1f}% improvement")
    
    print("\n" + "="*80)
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Measure Phase 2 performance improvements")
    parser.add_argument('--iterations', type=int, default=5, help='Number of iterations per query')
    
    args = parser.parse_args()
    
    # Run evaluation
    results = asyncio.run(run_performance_evaluation(iterations=args.iterations))
    
    # Exit with appropriate code
    if results['cached'] and results['uncached']:
        improvement = ((mean(results['uncached']) - mean(results['cached'])) / mean(results['uncached'])) * 100
        if improvement >= 30:
            print("\n✅ PASS: Performance targets met")
            sys.exit(0)
        else:
            print(f"\n⚠️  WARNING: {improvement:.1f}% improvement below 30% target")
            sys.exit(1)
    else:
        print("\n⚠️  Insufficient data for comparison")
        sys.exit(1)


if __name__ == "__main__":
    main()

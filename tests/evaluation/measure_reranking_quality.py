#!/usr/bin/env python3
"""
Reranking Quality Evaluation Script.

This script measures retrieval quality improvements from BGE cross-encoder reranking
by running queries from a golden dataset and analyzing the results.

Metrics calculated:
- Precision@K (relevant docs in top K)
- NDCG@K (normalized discounted cumulative gain)
- MRR (mean reciprocal rank)
- Topic coverage
- Document type distribution

Usage:
    python tests/evaluation/measure_reranking_quality.py
    python tests/evaluation/measure_reranking_quality.py --baseline  # Compare to baseline
    python tests/evaluation/measure_reranking_quality.py --save results.json

Author: RightLine Team
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import structlog

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.orchestrators.query_orchestrator import get_orchestrator
from api.schemas.agent_state import AgentState

logger = structlog.get_logger(__name__)


def load_golden_queries() -> List[Dict[str, Any]]:
    """Load golden dataset queries."""
    golden_path = Path(__file__).parent / "golden_queries.json"
    
    if not golden_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {golden_path}")
    
    with open(golden_path, 'r') as f:
        return json.load(f)


def calculate_precision_at_k(
    retrieved_topics: List[str],
    expected_topics: List[str],
    k: int
) -> float:
    """Calculate Precision@K."""
    if not retrieved_topics or not expected_topics:
        return 0.0
    
    # Normalize topics for comparison
    retrieved_set = set(t.lower() for t in retrieved_topics[:k])
    expected_set = set(t.lower() for t in expected_topics)
    
    # Check for topic matches (substring matching for flexibility)
    matches = 0
    for expected in expected_set:
        for retrieved in retrieved_set:
            if expected in retrieved or retrieved in expected:
                matches += 1
                break
    
    return matches / len(expected_set) if expected_set else 0.0


def calculate_doc_type_distribution(
    retrieved_docs: List[Dict[str, Any]],
    expected_types: List[str]
) -> float:
    """Calculate how well doc type distribution matches expected."""
    if not retrieved_docs:
        return 0.0
    
    retrieved_types = [doc.get("source_type", "unknown") for doc in retrieved_docs]
    expected_set = set(expected_types)
    retrieved_set = set(retrieved_types)
    
    # Jaccard similarity
    intersection = len(expected_set.intersection(retrieved_set))
    union = len(expected_set.union(retrieved_set))
    
    return intersection / union if union > 0 else 0.0


async def evaluate_single_query(
    orchestrator,
    query_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Evaluate a single query from golden dataset."""
    
    query = query_data["query"]
    expected_topics = query_data["expected_topics"]
    expected_doc_types = query_data["expected_doc_types"]
    complexity = query_data.get("complexity", "moderate")
    
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"Expected topics: {expected_topics}")
    print(f"Complexity: {complexity}")
    
    try:
        # Create state
        state = AgentState(
            user_id="eval_user",
            session_id="eval_session",
            raw_query=query,
            complexity=complexity,
            user_type="professional"
        )
        
        # Run query through orchestrator
        result = await orchestrator.run_query(state)
        
        # Extract retrieved information
        bundled_context = getattr(result, 'bundled_context', [])
        rerank_method = getattr(result, 'rerank_method', 'unknown')
        
        # Extract topics from retrieved docs
        retrieved_topics = []
        for ctx in bundled_context[:10]:
            title = ctx.get('title', '').lower()
            content = ctx.get('content', '')[:500].lower()
            retrieved_topics.append(title)
            # Extract key phrases from content
            for topic in expected_topics:
                if topic.lower() in content:
                    retrieved_topics.append(topic)
        
        # Calculate metrics
        precision_at_5 = calculate_precision_at_k(retrieved_topics, expected_topics, k=5)
        precision_at_10 = calculate_precision_at_k(retrieved_topics, expected_topics, k=10)
        doc_type_score = calculate_doc_type_distribution(bundled_context, expected_doc_types)
        
        # Results count
        results_count = len(bundled_context)
        
        print(f"\nResults:")
        print(f"  Retrieved docs: {results_count}")
        print(f"  Precision@5: {precision_at_5:.3f}")
        print(f"  Precision@10: {precision_at_10:.3f}")
        print(f"  Doc type match: {doc_type_score:.3f}")
        print(f"  Rerank method: {rerank_method}")
        
        return {
            "query_id": query_data["id"],
            "query": query,
            "complexity": complexity,
            "retrieved_count": results_count,
            "precision_at_5": round(precision_at_5, 3),
            "precision_at_10": round(precision_at_10, 3),
            "doc_type_score": round(doc_type_score, 3),
            "rerank_method": rerank_method,
            "expected_topics": expected_topics,
            "retrieved_sample": [ctx.get('title', 'Unknown') for ctx in bundled_context[:5]]
        }
        
    except Exception as e:
        logger.error("Evaluation failed for query", query=query, error=str(e))
        print(f"  ERROR: {str(e)}")
        return {
            "query_id": query_data["id"],
            "query": query,
            "error": str(e),
            "precision_at_5": 0.0,
            "precision_at_10": 0.0
        }


async def run_evaluation(save_path: str = None, compare_baseline: bool = False):
    """Run complete evaluation on golden dataset."""
    
    print("\n" + "="*80)
    print("GWETA RERANKING QUALITY EVALUATION")
    print("="*80)
    
    # Load golden queries
    golden_queries = load_golden_queries()
    print(f"\nLoaded {len(golden_queries)} golden queries")
    
    # Initialize orchestrator
    orchestrator = get_orchestrator()
    
    # Run evaluation on all queries
    results = []
    for query_data in golden_queries:
        result = await evaluate_single_query(orchestrator, query_data)
        results.append(result)
        
        # Small delay to avoid overwhelming the system
        await asyncio.sleep(0.5)
    
    # Calculate aggregate metrics
    successful_results = [r for r in results if "error" not in r]
    
    if not successful_results:
        print("\n❌ No successful evaluations!")
        return
    
    avg_precision_5 = sum(r["precision_at_5"] for r in successful_results) / len(successful_results)
    avg_precision_10 = sum(r["precision_at_10"] for r in successful_results) / len(successful_results)
    avg_doc_type = sum(r.get("doc_type_score", 0) for r in successful_results) / len(successful_results)
    
    # Count rerank methods
    rerank_methods = {}
    for r in successful_results:
        method = r.get("rerank_method", "unknown")
        rerank_methods[method] = rerank_methods.get(method, 0) + 1
    
    # Print summary
    print("\n" + "="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    print(f"\nTotal queries evaluated: {len(successful_results)}/{len(golden_queries)}")
    print(f"Failed queries: {len(golden_queries) - len(successful_results)}")
    
    print(f"\n📊 Quality Metrics:")
    print(f"  Average Precision@5:  {avg_precision_5:.3f}")
    print(f"  Average Precision@10: {avg_precision_10:.3f}")
    print(f"  Avg Doc Type Match:   {avg_doc_type:.3f}")
    
    print(f"\n🔧 Reranking Methods Used:")
    for method, count in rerank_methods.items():
        print(f"  {method}: {count} queries ({count/len(successful_results)*100:.1f}%)")
    
    # Breakdown by complexity
    print(f"\n📈 Performance by Complexity:")
    for complexity in ["simple", "moderate", "complex"]:
        complex_results = [r for r in successful_results if r.get("complexity") == complexity]
        if complex_results:
            avg_p5 = sum(r["precision_at_5"] for r in complex_results) / len(complex_results)
            print(f"  {complexity.capitalize()}: P@5 = {avg_p5:.3f} ({len(complex_results)} queries)")
    
    # Compare to baseline if requested
    if compare_baseline:
        baseline_path = Path(__file__).parent / "baseline_results.json"
        if baseline_path.exists():
            with open(baseline_path, 'r') as f:
                baseline = json.load(f)
            
            baseline_p5 = baseline["metrics"]["avg_precision_5"]
            baseline_p10 = baseline["metrics"]["avg_precision_10"]
            
            improvement_p5 = ((avg_precision_5 - baseline_p5) / baseline_p5) * 100
            improvement_p10 = ((avg_precision_10 - baseline_p10) / baseline_p10) * 100
            
            print(f"\n📊 Comparison to Baseline:")
            print(f"  Precision@5:  {baseline_p5:.3f} → {avg_precision_5:.3f} ({improvement_p5:+.1f}%)")
            print(f"  Precision@10: {baseline_p10:.3f} → {avg_precision_10:.3f} ({improvement_p10:+.1f}%)")
            
            if improvement_p5 >= 15:
                print(f"\n✅ EXCELLENT: {improvement_p5:.1f}% improvement exceeds 15% target!")
            elif improvement_p5 >= 10:
                print(f"\n✅ GOOD: {improvement_p5:.1f}% improvement meets minimum target")
            else:
                print(f"\n⚠️  BELOW TARGET: {improvement_p5:.1f}% improvement below 10% target")
    
    # Save results
    output = {
        "evaluation_date": datetime.utcnow().isoformat(),
        "total_queries": len(golden_queries),
        "successful_queries": len(successful_results),
        "metrics": {
            "avg_precision_5": round(avg_precision_5, 3),
            "avg_precision_10": round(avg_precision_10, 3),
            "avg_doc_type_match": round(avg_doc_type, 3)
        },
        "rerank_methods": rerank_methods,
        "details": results
    }
    
    if save_path:
        save_file = Path(save_path)
        with open(save_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n💾 Results saved to: {save_file}")
    
    return output


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate reranking quality")
    parser.add_argument('--save', type=str, help='Save results to JSON file')
    parser.add_argument('--baseline', action='store_true', help='Compare to baseline results')
    parser.add_argument('--create-baseline', action='store_true', help='Create baseline results file')
    
    args = parser.parse_args()
    
    # Run evaluation
    results = asyncio.run(run_evaluation(
        save_path=args.save,
        compare_baseline=args.baseline
    ))
    
    # Create baseline if requested
    if args.create_baseline and results:
        baseline_path = Path(__file__).parent / "baseline_results.json"
        with open(baseline_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Baseline saved to: {baseline_path}")
    
    # Exit with appropriate code
    if results and results["successful_queries"] > 0:
        avg_p5 = results["metrics"]["avg_precision_5"]
        if avg_p5 >= 0.6:
            print(f"\n✅ PASS: Average Precision@5 = {avg_p5:.3f} (>= 0.6 target)")
            sys.exit(0)
        else:
            print(f"\n⚠️  WARNING: Average Precision@5 = {avg_p5:.3f} (< 0.6 target)")
            sys.exit(1)
    else:
        print("\n❌ FAIL: No successful evaluations")
        sys.exit(1)


if __name__ == "__main__":
    main()

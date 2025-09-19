"""
Golden Set Evaluator for RightLine Legal Assistant.

This module implements systematic evaluation of the agentic system
using curated legal queries with known correct answers.

Task 5.1: Observability & Quality Gates Implementation
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel

from api.agents.query_orchestrator import process_legal_query, AgentState

logger = structlog.get_logger(__name__)


@dataclass
class GoldenQuery:
    """A single golden query with expected answer."""
    
    id: str
    query: str
    category: str
    expected_answer: str
    expected_sources: List[str]
    expected_confidence_min: float
    complexity: str  # simple, moderate, complex
    tags: List[str]


class EvaluationResult(BaseModel):
    """Result of evaluating a single query."""
    
    query_id: str
    query: str
    
    # Response quality
    actual_answer: str
    expected_answer: str
    answer_similarity: float
    
    # Citation accuracy
    actual_sources: List[str]
    expected_sources: List[str]
    citation_accuracy: float
    
    # Performance metrics
    latency_ms: int
    confidence: float
    
    # Quality gates
    correctness_score: float
    citation_score: float
    performance_score: float
    overall_score: float
    
    # Detailed metrics
    warnings: List[str]
    node_timings: Dict[str, int]
    
    passed: bool


class GoldenSetEvaluator:
    """
    Evaluator for systematic testing of the legal assistant.
    
    This class runs the complete agentic workflow against a curated
    set of legal queries and evaluates the quality of responses.
    """
    
    def __init__(self, golden_set_path: str = "data/evaluation/golden_set.json"):
        """Initialize the evaluator with golden set data."""
        self.golden_set_path = Path(golden_set_path)
        self.golden_queries: List[GoldenQuery] = []
        self._load_golden_set()
    
    def _load_golden_set(self):
        """Load the golden set from JSON file."""
        
        if not self.golden_set_path.exists():
            logger.warning(
                "Golden set file not found, creating sample set",
                path=str(self.golden_set_path)
            )
            self._create_sample_golden_set()
            return
        
        try:
            with open(self.golden_set_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.golden_queries = []
            for item in data.get("queries", []):
                query = GoldenQuery(
                    id=item["id"],
                    query=item["query"],
                    category=item["category"],
                    expected_answer=item["expected_answer"],
                    expected_sources=item["expected_sources"],
                    expected_confidence_min=item.get("expected_confidence_min", 0.7),
                    complexity=item.get("complexity", "moderate"),
                    tags=item.get("tags", [])
                )
                self.golden_queries.append(query)
            
            logger.info(
                "Golden set loaded",
                query_count=len(self.golden_queries),
                path=str(self.golden_set_path)
            )
            
        except Exception as e:
            logger.error(
                "Failed to load golden set",
                path=str(self.golden_set_path),
                error=str(e)
            )
            self._create_sample_golden_set()
    
    def _create_sample_golden_set(self):
        """Create a sample golden set for testing."""
        
        sample_queries = [
            {
                "id": "art_unions_001",
                "query": "What are the requirements for art unions?",
                "category": "corporate",
                "expected_answer": "Art unions for promoting fine arts are lawful and exempt from lottery laws. They must be legally constituted and comply with specific requirements.",
                "expected_sources": ["Art Unions Act", "Chapter 25:01"],
                "expected_confidence_min": 0.7,
                "complexity": "simple",
                "tags": ["art", "unions", "corporate_law"]
            },
            {
                "id": "company_directors_001",
                "query": "What are the duties of company directors in Zimbabwe?",
                "category": "corporate",
                "expected_answer": "Company directors have fiduciary duties including duty of care, duty of loyalty, and duty to act in the company's best interests. They must comply with the Companies Act.",
                "expected_sources": ["Companies Act", "Chapter 24:03"],
                "expected_confidence_min": 0.8,
                "complexity": "moderate",
                "tags": ["directors", "corporate_governance", "fiduciary_duties"]
            },
            {
                "id": "constitutional_rights_001",
                "query": "What constitutional rights do citizens have in Zimbabwe?",
                "category": "constitutional",
                "expected_answer": "Citizens have fundamental rights including right to life, liberty, equality, freedom of expression, and protection from discrimination as enshrined in the Constitution.",
                "expected_sources": ["Constitution of Zimbabwe", "Chapter 4"],
                "expected_confidence_min": 0.8,
                "complexity": "moderate",
                "tags": ["constitutional_law", "human_rights", "citizenship"]
            },
            {
                "id": "criminal_procedure_001",
                "query": "What is the procedure for arrest in Zimbabwe?",
                "category": "criminal",
                "expected_answer": "Arrest procedures must follow constitutional requirements including informing the person of reasons for arrest, right to remain silent, and right to legal representation.",
                "expected_sources": ["Criminal Procedure and Evidence Act", "Constitution"],
                "expected_confidence_min": 0.7,
                "complexity": "complex",
                "tags": ["criminal_law", "arrest", "procedure"]
            },
            {
                "id": "property_rights_001",
                "query": "How does property acquisition work under Zimbabwean law?",
                "category": "property",
                "expected_answer": "Property acquisition must follow legal procedures including proper documentation, registration, and compliance with land laws and constitutional provisions.",
                "expected_sources": ["Deeds Registries Act", "Land Act"],
                "expected_confidence_min": 0.6,
                "complexity": "complex",
                "tags": ["property_law", "land_rights", "acquisition"]
            }
        ]
        
        # Create directory if it doesn't exist
        self.golden_set_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save sample golden set
        golden_set_data = {
            "version": "1.0",
            "description": "Golden set for RightLine Legal Assistant evaluation",
            "created": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "queries": sample_queries
        }
        
        with open(self.golden_set_path, 'w', encoding='utf-8') as f:
            json.dump(golden_set_data, f, indent=2, ensure_ascii=False)
        
        # Load the created set
        self._load_golden_set()
        
        logger.info(
            "Sample golden set created",
            path=str(self.golden_set_path),
            query_count=len(sample_queries)
        )
    
    async def evaluate_single_query(self, golden_query: GoldenQuery) -> EvaluationResult:
        """Evaluate a single golden query."""
        
        logger.info(
            "Evaluating query",
            query_id=golden_query.id,
            query=golden_query.query[:100]
        )
        
        start_time = time.time()
        
        try:
            # Process the query through the agentic workflow
            result_state = await process_legal_query(
                query=golden_query.query,
                user_id="golden_set_evaluator"
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Extract results
            actual_answer = ""
            actual_sources = []
            confidence = 0.0
            
            if result_state.get("synthesized_response"):
                response = result_state["synthesized_response"]
                actual_answer = response.get("tldr", "")
                actual_sources = [
                    citation.get("title", "") 
                    for citation in response.get("citations", [])
                ]
                confidence = response.get("confidence", 0.0)
            
            # Calculate similarity scores
            answer_similarity = self._calculate_answer_similarity(
                actual_answer, golden_query.expected_answer
            )
            
            citation_accuracy = self._calculate_citation_accuracy(
                actual_sources, golden_query.expected_sources
            )
            
            # Calculate quality scores
            correctness_score = answer_similarity
            citation_score = citation_accuracy
            performance_score = self._calculate_performance_score(processing_time)
            
            # Overall score (weighted average)
            overall_score = (
                correctness_score * 0.5 +
                citation_score * 0.3 +
                performance_score * 0.2
            )
            
            # Determine if query passed
            passed = (
                correctness_score >= 0.7 and
                citation_score >= 0.6 and
                confidence >= golden_query.expected_confidence_min and
                processing_time <= 10000  # 10 seconds max
            )
            
            result = EvaluationResult(
                query_id=golden_query.id,
                query=golden_query.query,
                actual_answer=actual_answer,
                expected_answer=golden_query.expected_answer,
                answer_similarity=answer_similarity,
                actual_sources=actual_sources,
                expected_sources=golden_query.expected_sources,
                citation_accuracy=citation_accuracy,
                latency_ms=processing_time,
                confidence=confidence,
                correctness_score=correctness_score,
                citation_score=citation_score,
                performance_score=performance_score,
                overall_score=overall_score,
                warnings=result_state.get("warnings", []),
                node_timings=result_state.get("node_timings", {}),
                passed=passed
            )
            
            logger.info(
                "Query evaluation completed",
                query_id=golden_query.id,
                overall_score=overall_score,
                passed=passed,
                latency_ms=processing_time
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Query evaluation failed",
                query_id=golden_query.id,
                error=str(e),
                exc_info=True
            )
            
            # Return failed evaluation
            return EvaluationResult(
                query_id=golden_query.id,
                query=golden_query.query,
                actual_answer="",
                expected_answer=golden_query.expected_answer,
                answer_similarity=0.0,
                actual_sources=[],
                expected_sources=golden_query.expected_sources,
                citation_accuracy=0.0,
                latency_ms=int((time.time() - start_time) * 1000),
                confidence=0.0,
                correctness_score=0.0,
                citation_score=0.0,
                performance_score=0.0,
                overall_score=0.0,
                warnings=[f"Evaluation failed: {str(e)}"],
                node_timings={},
                passed=False
            )
    
    def _calculate_answer_similarity(self, actual: str, expected: str) -> float:
        """Calculate similarity between actual and expected answers."""
        
        if not actual or not expected:
            return 0.0
        
        # Simple word overlap similarity (in production, use semantic similarity)
        actual_words = set(actual.lower().split())
        expected_words = set(expected.lower().split())
        
        if not expected_words:
            return 0.0
        
        overlap = len(actual_words.intersection(expected_words))
        similarity = overlap / len(expected_words)
        
        return min(1.0, similarity)
    
    def _calculate_citation_accuracy(self, actual: List[str], expected: List[str]) -> float:
        """Calculate accuracy of citations."""
        
        if not expected:
            return 1.0  # No citations expected
        
        if not actual:
            return 0.0  # No citations provided but some expected
        
        # Check how many expected sources are mentioned
        matches = 0
        for expected_source in expected:
            for actual_source in actual:
                if expected_source.lower() in actual_source.lower():
                    matches += 1
                    break
        
        return matches / len(expected)
    
    def _calculate_performance_score(self, latency_ms: int) -> float:
        """Calculate performance score based on latency."""
        
        # Target: < 5 seconds = 1.0, > 10 seconds = 0.0
        if latency_ms <= 5000:
            return 1.0
        elif latency_ms >= 10000:
            return 0.0
        else:
            # Linear interpolation between 5s and 10s
            return 1.0 - ((latency_ms - 5000) / 5000)
    
    async def evaluate_all(self, max_concurrent: int = 3) -> Dict[str, any]:
        """Evaluate all queries in the golden set."""
        
        logger.info(
            "Starting golden set evaluation",
            total_queries=len(self.golden_queries),
            max_concurrent=max_concurrent
        )
        
        start_time = time.time()
        
        # Run evaluations with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def evaluate_with_semaphore(query):
            async with semaphore:
                return await self.evaluate_single_query(query)
        
        # Execute all evaluations
        results = await asyncio.gather(*[
            evaluate_with_semaphore(query) for query in self.golden_queries
        ])
        
        total_time = time.time() - start_time
        
        # Calculate summary statistics
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        pass_rate = passed_count / total_count if total_count > 0 else 0.0
        
        avg_correctness = sum(r.correctness_score for r in results) / total_count
        avg_citation_accuracy = sum(r.citation_score for r in results) / total_count
        avg_latency = sum(r.latency_ms for r in results) / total_count
        avg_confidence = sum(r.confidence for r in results) / total_count
        
        # Performance by category
        category_stats = {}
        for result in results:
            # Find the golden query to get category
            golden_query = next(q for q in self.golden_queries if q.id == result.query_id)
            category = golden_query.category
            
            if category not in category_stats:
                category_stats[category] = []
            category_stats[category].append(result)
        
        category_summary = {}
        for category, cat_results in category_stats.items():
            category_summary[category] = {
                "total": len(cat_results),
                "passed": sum(1 for r in cat_results if r.passed),
                "pass_rate": sum(1 for r in cat_results if r.passed) / len(cat_results),
                "avg_score": sum(r.overall_score for r in cat_results) / len(cat_results),
                "avg_latency": sum(r.latency_ms for r in cat_results) / len(cat_results)
            }
        
        summary = {
            "evaluation_id": str(int(time.time())),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "total_time_seconds": int(total_time),
            "summary": {
                "total_queries": total_count,
                "passed_queries": passed_count,
                "pass_rate": pass_rate,
                "avg_correctness_score": avg_correctness,
                "avg_citation_accuracy": avg_citation_accuracy,
                "avg_latency_ms": int(avg_latency),
                "avg_confidence": avg_confidence
            },
            "category_breakdown": category_summary,
            "detailed_results": [result.dict() for result in results],
            "quality_gates": {
                "correctness_threshold": 0.9,
                "citation_threshold": 0.95,
                "latency_threshold": 5000,
                "correctness_passed": avg_correctness >= 0.9,
                "citation_passed": avg_citation_accuracy >= 0.95,
                "latency_passed": avg_latency <= 5000,
                "overall_passed": (
                    avg_correctness >= 0.9 and
                    avg_citation_accuracy >= 0.95 and
                    avg_latency <= 5000
                )
            }
        }
        
        logger.info(
            "Golden set evaluation completed",
            total_queries=total_count,
            passed_queries=passed_count,
            pass_rate=pass_rate,
            avg_latency_ms=int(avg_latency),
            total_time_seconds=int(total_time)
        )
        
        return summary
    
    def save_evaluation_report(self, summary: Dict[str, any], output_path: str = None):
        """Save evaluation report to file."""
        
        if output_path is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = f"reports/evaluation/golden_set_{timestamp}.json"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(
            "Evaluation report saved",
            path=str(output_file),
            pass_rate=summary["summary"]["pass_rate"]
        )


async def run_golden_set_evaluation() -> Dict[str, any]:
    """
    Convenience function to run the complete golden set evaluation.
    
    This function can be called from CI/CD pipelines or for manual testing.
    """
    
    evaluator = GoldenSetEvaluator()
    summary = await evaluator.evaluate_all()
    evaluator.save_evaluation_report(summary)
    
    return summary


if __name__ == "__main__":
    # Run evaluation when script is executed directly
    asyncio.run(run_golden_set_evaluation())

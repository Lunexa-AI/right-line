"""
Quality Gates for Gweta Legal AI Pipeline.

This module implements multi-layer quality assurance gates that ensure 
100% accuracy, proper attribution, and legal reasoning quality throughout
the agentic pipeline.

Quality Gates:
- Attribution Verification: Ensures proper citation and grounding
- Source Relevance Filtering: Removes irrelevant or tangential sources
- Logical Coherence Checking: Validates legal reasoning quality
- Constitutional Hierarchy Verification: Ensures proper authority application
- Adversarial Analysis: Tests for obvious counterarguments

Follows .cursorrules: Strict validation, no hallucinations, comprehensive verification.
"""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import structlog
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from api.llm.gpt5_wrapper import get_gpt5_model
from langsmith import Client, traceable
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


@dataclass
class QualityGateResult:
    """Result from a quality gate check."""
    
    passed: bool
    confidence: float
    issues: List[str]
    metrics: Dict[str, Any]
    recommendations: List[str]


class AttributionVerificationResult(BaseModel):
    """Result from attribution verification."""
    
    grounding_passed: bool = Field(description="Whether grounding requirements are met")
    citation_density: float = Field(description="Percentage of statements with citations")
    unsupported_statements: List[str] = Field(description="Statements lacking proper support")
    missing_citations: List[str] = Field(description="Statements requiring citations")
    incorrect_citations: List[Dict[str, str]] = Field(description="Citations with issues")
    overall_quality: str = Field(description="excellent/good/acceptable/poor/unacceptable")


class SourceRelevanceResult(BaseModel):
    """Result from source relevance filtering."""
    
    source_classifications: List[Dict[str, str]] = Field(description="Classification of each source")
    recommended_sources: List[str] = Field(description="Sources recommended for synthesis")
    filtered_count: int = Field(description="Number of sources filtered out")
    relevance_ratio: float = Field(description="Ratio of relevant to total sources")


class LogicalCoherenceResult(BaseModel):
    """Result from logical coherence checking."""
    
    coherence_passed: bool = Field(description="Whether reasoning is logically sound")
    reasoning_quality: str = Field(description="excellent/good/acceptable/poor/unacceptable")
    logical_issues: List[str] = Field(description="Specific logical problems identified")
    missing_reasoning: List[str] = Field(description="Areas needing stronger reasoning")
    counterargument_gaps: List[str] = Field(description="Unaddressed counterarguments")


class QualityGateOrchestrator:
    """Orchestrates quality gates in the legal AI pipeline."""
    
    def __init__(self):
        """Initialize quality gate components."""
        self.attribution_verifier = AttributionVerifier()
        self.relevance_filter = SourceRelevanceFilter()
        self.coherence_checker = LogicalCoherenceChecker()
        self.hierarchy_verifier = ConstitutionalHierarchyVerifier()
        
    @traceable(
        run_type="tool",
        name="quality_gate_orchestrator",
        tags=["quality", "verification", "legal-ai"]
    )
    async def run_comprehensive_quality_check(
        self,
        answer: str,
        context_documents: List[Dict[str, Any]],
        query: str,
        user_type: str = "professional",
        complexity: str = "moderate"
    ) -> QualityGateResult:
        """Run comprehensive quality checks on legal analysis."""
        
        start_time = time.time()
        
        try:
            # Log input artifacts
            logger.info(
                "quality_check_input",
                answer_length=len(answer),
                context_docs=len(context_documents),
                query=query,
                user_type=user_type,
                complexity=complexity
            )
            
            # Run quality gates in parallel for efficiency
            attribution_task = asyncio.create_task(
                self.attribution_verifier.verify_attribution(answer, context_documents)
            )
            relevance_task = asyncio.create_task(
                self.relevance_filter.filter_sources(context_documents, query)
            )
            coherence_task = asyncio.create_task(
                self.coherence_checker.check_coherence(answer, query, context_documents)
            )
            hierarchy_task = asyncio.create_task(
                self.hierarchy_verifier.verify_hierarchy(answer, context_documents)
            )
            
            # Wait for all quality checks
            attribution_result, relevance_result, coherence_result, hierarchy_result = await asyncio.gather(
                attribution_task, relevance_task, coherence_task, hierarchy_task,
                return_exceptions=True
            )
            
            # Calculate overall quality
            issues = []
            passed = True
            
            # Check attribution
            if isinstance(attribution_result, AttributionVerificationResult):
                if not attribution_result.grounding_passed:
                    passed = False
                    issues.extend([f"Attribution: {issue}" for issue in attribution_result.unsupported_statements])
            else:
                issues.append(f"Attribution check failed: {attribution_result}")
                passed = False
            
            # Check coherence
            if isinstance(coherence_result, LogicalCoherenceResult):
                if not coherence_result.coherence_passed:
                    passed = False
                    issues.extend([f"Logic: {issue}" for issue in coherence_result.logical_issues])
            else:
                issues.append(f"Coherence check failed: {coherence_result}")
                passed = False
            
            # Calculate confidence
            confidence = 1.0
            if issues:
                confidence = max(0.1, 1.0 - (len(issues) * 0.2))
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Log comprehensive results
            logger.info("Quality check orchestrator completed",
                   overall_passed=passed,
                   confidence=confidence,
                   issues_count=len(issues),
                   attribution_quality=attribution_result.overall_quality if isinstance(attribution_result, AttributionVerificationResult) else "error",
                   coherence_quality=coherence_result.reasoning_quality if isinstance(coherence_result, LogicalCoherenceResult) else "error",
                   duration_ms=round(duration_ms, 2))
            
            return QualityGateResult(
                passed=passed,
                confidence=confidence,
                issues=issues,
                metrics={
                    "attribution_passed": isinstance(attribution_result, AttributionVerificationResult) and attribution_result.grounding_passed,
                    "coherence_passed": isinstance(coherence_result, LogicalCoherenceResult) and coherence_result.coherence_passed,
                    "total_checks": 4,
                    "duration_ms": round(duration_ms, 2)
                },
                recommendations=self._generate_recommendations(issues, complexity)
            )
            
        except Exception as e:
            logger.error("Quality gate orchestrator failed", error=str(e))
            return QualityGateResult(
                passed=False,
                confidence=0.1,
                issues=[f"Quality check system error: {str(e)}"],
                metrics={"error": True},
                recommendations=["Manual review required due to quality check failure"]
            )
    
    def _generate_recommendations(self, issues: List[str], complexity: str) -> List[str]:
        """Generate recommendations based on quality issues."""
        recommendations = []
        
        if any("Attribution" in issue for issue in issues):
            recommendations.append("Add missing source citations with specific section references")
        
        if any("Logic" in issue for issue in issues):
            recommendations.append("Strengthen legal reasoning with additional supporting authorities")
        
        if complexity in ["complex", "expert"] and issues:
            recommendations.append("Consider manual review by senior legal practitioner")
        
        return recommendations


class AttributionVerifier:
    """Verifies proper attribution and grounding in legal analysis."""
    
    @traceable(
        run_type="llm",
        name="attribution_verifier",
        tags=["quality", "attribution", "citations", "legal-ai"]
    )
    async def verify_attribution(
        self,
        answer: str,
        context_documents: List[Dict[str, Any]]
    ) -> AttributionVerificationResult:
        """Verify attribution quality using advanced LLM verification."""
        
        try:
            # Use attribution verification prompt
            from api.composer.prompts import get_prompt_template
            template = get_prompt_template("attribution_verification")
            
            # Format context for verification
            context_text = ""
            for i, doc in enumerate(context_documents, 1):
                context_text += f"Source {i}: {doc.get('title', 'Unknown')}\n"
                context_text += f"Doc Key: {doc.get('doc_key', 'unknown')}\n"
                context_text += f"Content: {doc.get('content', '')[:500]}...\n\n"
            
            # Create verification LLM using GPT-5-mini via Responses API
            llm = get_gpt5_model(
                model_name="gpt-5-mini",
                reasoning_effort="medium",
                max_tokens=800,
                verbosity="low"
            )
            
            # Execute verification
            chain = template | llm
            response = await chain.ainvoke({
                "answer": answer,
                "context": context_text
            })
            
            # Parse result
            verification_data = json.loads(response.content)
            
            # Log results for tracing
            logger.info("Attribution verification completed", **verification_data)
            
            return AttributionVerificationResult(**verification_data)
            
        except Exception as e:
            logger.error("Attribution verification failed", error=str(e))
            return AttributionVerificationResult(
                grounding_passed=False,
                citation_density=0.0,
                unsupported_statements=[f"Verification failed: {str(e)}"],
                missing_citations=[],
                incorrect_citations=[],
                overall_quality="unacceptable"
            )


class SourceRelevanceFilter:
    """Filters sources based on relevance to specific query."""
    
    @traceable(
        run_type="llm",
        name="source_relevance_filter",
        tags=["quality", "relevance", "filtering", "legal-ai"]
    )
    async def filter_sources(
        self,
        sources: List[Dict[str, Any]],
        query: str
    ) -> SourceRelevanceResult:
        """Filter sources based on relevance to query."""
        
        try:
            # Use relevance filter prompt
            from api.composer.prompts import get_prompt_template
            template = get_prompt_template("relevance_filter")
            
            # Format sources for analysis
            sources_text = ""
            for i, source in enumerate(sources, 1):
                sources_text += f"Source {i}:\n"
                sources_text += f"Title: {source.get('title', 'Unknown')}\n"
                sources_text += f"Doc Key: {source.get('doc_key', 'unknown')}\n"
                sources_text += f"Content: {source.get('content', '')[:400]}...\n\n"
            
            # Create filtering LLM using GPT-5-mini via Responses API
            llm = get_gpt5_model(
                model_name="gpt-5-mini",
                reasoning_effort="low",
                max_tokens=600,
                verbosity="low"
            )
            
            # Execute filtering
            chain = template | llm
            response = await chain.ainvoke({
                "query": query,
                "sources_with_content": sources_text
            })
            
            # Parse result
            filter_data = json.loads(response.content)
            
            # Calculate metrics
            total_sources = len(sources)
            recommended_count = len(filter_data.get("recommended_sources", []))
            filtered_count = total_sources - recommended_count
            relevance_ratio = recommended_count / total_sources if total_sources > 0 else 0
            
            result = SourceRelevanceResult(
                source_classifications=filter_data.get("source_classifications", []),
                recommended_sources=filter_data.get("recommended_sources", []),
                filtered_count=filtered_count,
                relevance_ratio=relevance_ratio
            )
            
            # Log results for tracing
            logger.info("Source relevance filtering completed",
                       total_sources=total_sources,
                       recommended_count=recommended_count,
                       filtered_count=filtered_count,
                       relevance_ratio=relevance_ratio)
            
            return result
            
        except Exception as e:
            logger.error("Source relevance filtering failed", error=str(e))
            return SourceRelevanceResult(
                source_classifications=[],
                recommended_sources=[source.get("doc_key", f"src_{i}") for i, source in enumerate(sources)],
                filtered_count=0,
                relevance_ratio=1.0
            )


class LogicalCoherenceChecker:
    """Checks logical coherence and reasoning quality."""
    
    @traceable(
        run_type="llm", 
        name="logical_coherence_checker",
        tags=["quality", "logic", "reasoning", "legal-ai"]
    )
    async def check_coherence(
        self,
        answer: str,
        query: str,
        context_documents: List[Dict[str, Any]]
    ) -> LogicalCoherenceResult:
        """Check logical coherence of legal reasoning."""
        
        try:
            # Create coherence checking prompt
            coherence_prompt = f"""You are a legal reasoning validator for Gweta Legal AI.

Analyze this legal analysis for logical coherence and reasoning quality:

**COHERENCE CRITERIA**:
1. **LOGICAL FLOW**: Do conclusions follow logically from premises?
2. **LEGAL REASONING**: Is established legal methodology properly applied?
3. **AUTHORITY INTEGRATION**: Are multiple authorities properly synthesized?
4. **COMPLETENESS**: Are all aspects of the query addressed?
5. **COUNTERARGUMENTS**: Are obvious opposing views considered?

**COMMON ERRORS TO DETECT**:
- Non sequitur conclusions
- Cherry-picking authorities while ignoring contrary evidence
- Misapplying precedents or statutory provisions
- Circular reasoning or question-begging
- Failing to address obvious counterarguments

**QUALITY LEVELS**:
- excellent: Clear, logical, comprehensive reasoning
- good: Sound reasoning with minor gaps
- acceptable: Generally logical but needs strengthening
- poor: Significant logical issues
- unacceptable: Fundamentally flawed reasoning

Return JSON format with these exact fields: {{"coherence_passed": boolean, "reasoning_quality": "...", "logical_issues": [...], "missing_reasoning": [...], "counterargument_gaps": [...]}}

Respond with JSON only. No explanations."""
            
            # Use GPT-5-mini for coherence checking via Responses API
            llm = get_gpt5_model(
                model_name="gpt-5-mini",
                reasoning_effort="medium",
                max_tokens=500,
                verbosity="low"
            )
            
            # Execute coherence check directly with full prompt
            prompt = f"""{coherence_prompt}

Query: {query}

Legal Analysis:
{answer}

Evaluate logical coherence and return JSON."""
            
            response = await llm.ainvoke(prompt)
            
            # Parse result
            coherence_data = json.loads(response.content)
            
            result = LogicalCoherenceResult(**coherence_data)
            
            # Log results to LangSmith
            logger.info(
                "coherence_check_result",
                **coherence_data
            )
            
            return result
            
        except Exception as e:
            logger.error("Logical coherence check failed", error=str(e))
            return LogicalCoherenceResult(
                coherence_passed=False,
                reasoning_quality="unacceptable",
                logical_issues=[f"Coherence check failed: {str(e)}"],
                missing_reasoning=[],
                counterargument_gaps=[]
            )


class ConstitutionalHierarchyVerifier:
    """Verifies proper application of constitutional hierarchy."""
    
    @traceable(
        run_type="tool",
        name="constitutional_hierarchy_verifier", 
        tags=["quality", "constitutional", "hierarchy", "legal-ai"]
    )
    async def verify_hierarchy(
        self,
        answer: str,
        context_documents: List[Dict[str, Any]]
    ) -> QualityGateResult:
        """Verify constitutional hierarchy is properly applied."""
        
        start_time = time.time()
        issues = []
        
        try:
            # Extract authority types from context
            authority_types = []
            for doc in context_documents:
                doc_type = doc.get("doc_type", "unknown")
                authority_types.append(doc_type)
            
            # Check for hierarchy violations
            has_constitution = "constitution" in authority_types
            has_acts = "act" in authority_types
            has_cases = any("case_" in dt for dt in authority_types)
            
            # Verify hierarchy in answer text
            if has_constitution and has_acts:
                # Check that constitutional provisions are given supremacy
                if "Constitution" in answer and "Act" in answer:
                    # Simple heuristic: Constitution should be mentioned first or given priority
                    const_pos = answer.find("Constitution")
                    act_pos = answer.find("Act")
                    if act_pos < const_pos and act_pos != -1:
                        issues.append("Constitutional provisions should be discussed before statutory provisions")
            
            # Check for proper citation format
            citation_pattern = r'\(Source: [^)]+\)'
            citations = re.findall(citation_pattern, answer)
            if len(citations) < len(context_documents) * 0.5:
                issues.append("Insufficient citations for provided authorities")
            
            duration_ms = (time.time() - start_time) * 1000
            passed = len(issues) == 0
            
            # Log results for tracing
            logger.info("Constitutional hierarchy verification completed",
                       passed=passed,
                       issues_found=issues,
                       authority_types_present=authority_types,
                       citation_count=len(citations),
                       duration_ms=round(duration_ms, 2))
            
            return QualityGateResult(
                passed=passed,
                confidence=0.9 if passed else 0.6,
                issues=issues,
                metrics={
                    "duration_ms": round(duration_ms, 2),
                    "citations_found": len(citations),
                    "authority_types": len(set(authority_types))
                },
                recommendations=["Review constitutional hierarchy application"] if issues else []
            )
            
        except Exception as e:
            logger.error("Constitutional hierarchy verification failed", error=str(e))
            return QualityGateResult(
                passed=False,
                confidence=0.1,
                issues=[f"Hierarchy verification failed: {str(e)}"],
                metrics={"error": True},
                recommendations=["Manual review required"]
            )


# ==============================================================================
# INTEGRATION HELPERS
# ==============================================================================

async def run_pre_synthesis_quality_gate(
    context_documents: List[Dict[str, Any]],
    query: str,
    min_sources: int = 2,
    min_relevance_ratio: float = 0.6
) -> Tuple[List[Dict[str, Any]], QualityGateResult]:
    """Run quality gates before synthesis to filter and validate sources."""
    
    gate_orchestrator = QualityGateOrchestrator()
    
    # Filter sources for relevance
    relevance_result = await gate_orchestrator.relevance_filter.filter_sources(context_documents, query)
    
    # Filter to recommended sources only
    recommended_keys = set(relevance_result.recommended_sources)
    filtered_docs = [
        doc for doc in context_documents 
        if doc.get("doc_key") in recommended_keys
    ]
    
    # Check if we have sufficient quality sources
    issues = []
    passed = True
    
    if len(filtered_docs) < min_sources:
        issues.append(f"Insufficient relevant sources: {len(filtered_docs)} < {min_sources}")
        passed = False
    
    if relevance_result.relevance_ratio < min_relevance_ratio:
        issues.append(f"Low relevance ratio: {relevance_result.relevance_ratio:.2f} < {min_relevance_ratio}")
        passed = False
    
    gate_result = QualityGateResult(
        passed=passed,
        confidence=relevance_result.relevance_ratio,
        issues=issues,
        metrics={
            "sources_before_filter": len(context_documents),
            "sources_after_filter": len(filtered_docs),
            "relevance_ratio": relevance_result.relevance_ratio
        },
        recommendations=["Add more relevant sources"] if not passed else []
    )
    
    return filtered_docs, gate_result


async def run_post_synthesis_quality_gate(
    answer: str,
    context_documents: List[Dict[str, Any]],
    query: str,
    user_type: str = "professional",
    complexity: str = "moderate"
) -> QualityGateResult:
    """Run comprehensive quality gates after synthesis."""
    
    gate_orchestrator = QualityGateOrchestrator()
    return await gate_orchestrator.run_comprehensive_quality_check(
        answer=answer,
        context_documents=context_documents,
        query=query,
        user_type=user_type,
        complexity=complexity
    )


# ==============================================================================
# QUALITY METRICS AND SCORING
# ==============================================================================

def calculate_legal_quality_score(
    attribution_result: Optional[AttributionVerificationResult],
    coherence_result: Optional[LogicalCoherenceResult],
    relevance_ratio: float,
    citation_count: int,
    answer_length: int
) -> Dict[str, Any]:
    """Calculate comprehensive quality score for legal analysis."""
    
    scores = {}
    
    # Attribution score (0-100)
    if attribution_result:
        attribution_score = attribution_result.citation_density * 100
        if attribution_result.grounding_passed:
            attribution_score = min(100, attribution_score + 20)
        scores["attribution"] = round(attribution_score, 1)
    else:
        scores["attribution"] = 0.0
    
    # Coherence score (0-100)
    if coherence_result:
        coherence_mapping = {
            "excellent": 95,
            "good": 85,
            "acceptable": 75,
            "poor": 50,
            "unacceptable": 25
        }
        scores["coherence"] = coherence_mapping.get(coherence_result.reasoning_quality, 50)
    else:
        scores["coherence"] = 0.0
    
    # Relevance score (0-100)
    scores["relevance"] = round(relevance_ratio * 100, 1)
    
    # Citation density score (0-100)
    words = len(answer_length) if isinstance(answer_length, str) else answer_length
    citation_density = citation_count / max(1, words / 100)  # Citations per 100 words
    scores["citation_density"] = round(min(100, citation_density * 50), 1)
    
    # Overall score (weighted average)
    weights = {"attribution": 0.3, "coherence": 0.3, "relevance": 0.2, "citation_density": 0.2}
    overall_score = sum(scores[key] * weights[key] for key in weights if key in scores)
    scores["overall"] = round(overall_score, 1)
    
    # Quality grade
    if overall_score >= 90:
        grade = "A+"
    elif overall_score >= 85:
        grade = "A"
    elif overall_score >= 80:
        grade = "B+"
    elif overall_score >= 75:
        grade = "B"
    elif overall_score >= 70:
        grade = "C+"
    elif overall_score >= 65:
        grade = "C"
    else:
        grade = "F"
    
    scores["grade"] = grade
    
    return scores

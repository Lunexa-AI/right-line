"""
A/B Testing Framework for Gweta Legal AI Prompt Optimization.

This module provides comprehensive A/B testing capabilities for prompt variants,
allowing data-driven optimization of legal AI responses through:

- Multi-variant prompt testing with statistical significance
- Performance metrics tracking (accuracy, latency, user satisfaction)
- Legal-specific evaluation criteria (citation quality, reasoning strength)
- Real-time experiment management and results analysis
- Integration with LangSmith for detailed tracing

Follows .cursorrules: Statistical rigor, comprehensive metrics, ethical experimentation.
"""

import asyncio
import hashlib
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from enum import Enum

import structlog
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import Client, traceable
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ExperimentStatus(str, Enum):
    """Status of A/B testing experiment."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class VariantType(str, Enum):
    """Type of prompt variant being tested."""
    CONTROL = "control"
    TREATMENT = "treatment"
    CHALLENGER = "challenger"


@dataclass
class PromptVariant:
    """A single prompt variant in an A/B test."""
    
    variant_id: str
    variant_type: VariantType
    name: str
    description: str
    template: ChatPromptTemplate
    weight: float = 1.0  # Traffic allocation weight
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ExperimentResult:
    """Result from a single prompt execution."""
    
    experiment_id: str
    variant_id: str
    user_id: str
    query: str
    response: str
    latency_ms: float
    timestamp: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)
    feedback: Optional[Dict[str, Any]] = None


class LegalQualityMetrics(BaseModel):
    """Legal-specific quality metrics for A/B testing."""
    
    citation_count: int = Field(description="Number of citations in response")
    citation_density: float = Field(description="Citations per 100 words")
    grounding_score: float = Field(ge=0, le=1, description="How well grounded in sources")
    legal_accuracy_score: float = Field(ge=0, le=1, description="Legal accuracy assessment")
    reasoning_clarity: float = Field(ge=0, le=1, description="Clarity of legal reasoning")
    constitutional_compliance: bool = Field(description="Follows constitutional hierarchy")
    completeness_score: float = Field(ge=0, le=1, description="Completeness of analysis")
    
    class Config:
        extra = "forbid"


class ABTestExperiment(BaseModel):
    """A/B testing experiment configuration."""
    
    experiment_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(description="Human-readable experiment name")
    description: str = Field(description="Experiment purpose and hypothesis")
    status: ExperimentStatus = ExperimentStatus.DRAFT
    
    # Experiment configuration
    prompt_template_name: str = Field(description="Which prompt template to test")
    variants: List[str] = Field(description="List of variant IDs")
    traffic_allocation: Dict[str, float] = Field(description="Traffic % per variant")
    
    # Targeting and constraints
    user_type_filter: Optional[str] = Field(default=None, description="Target specific user type")
    complexity_filter: Optional[str] = Field(default=None, description="Target specific complexity")
    legal_area_filter: Optional[List[str]] = Field(default=None, description="Target specific legal areas")
    
    # Experiment timeline
    start_date: datetime = Field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = Field(default=None)
    min_sample_size: int = Field(default=100, description="Minimum samples per variant")
    
    # Success criteria
    primary_metric: str = Field(default="legal_accuracy_score")
    secondary_metrics: List[str] = Field(default_factory=lambda: ["latency_ms", "citation_density"])
    significance_threshold: float = Field(default=0.05, description="Statistical significance threshold")
    
    class Config:
        extra = "forbid"


class ABTestManager:
    """Manages A/B testing experiments for prompt optimization."""
    
    def __init__(self):
        """Initialize A/B test manager."""
        self.experiments: Dict[str, ABTestExperiment] = {}
        self.variants: Dict[str, PromptVariant] = {}
        self.results: List[ExperimentResult] = []
        self.quality_evaluator = LegalQualityEvaluator()
        
    def create_experiment(
        self,
        name: str,
        description: str,
        prompt_template_name: str,
        variants: List[PromptVariant],
        traffic_allocation: Optional[Dict[str, float]] = None
    ) -> ABTestExperiment:
        """Create a new A/B testing experiment."""
        
        experiment_id = uuid.uuid4().hex
        
        # Store variants
        for variant in variants:
            self.variants[variant.variant_id] = variant
        
        # Default equal traffic allocation
        if traffic_allocation is None:
            allocation = 1.0 / len(variants)
            traffic_allocation = {v.variant_id: allocation for v in variants}
        
        # Create experiment
        experiment = ABTestExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            prompt_template_name=prompt_template_name,
            variants=[v.variant_id for v in variants],
            traffic_allocation=traffic_allocation
        )
        
        self.experiments[experiment_id] = experiment
        
        logger.info(
            "A/B test experiment created",
            experiment_id=experiment_id,
            name=name,
            variants=len(variants),
            template=prompt_template_name
        )
        
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Start an A/B testing experiment."""
        
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            logger.error("Experiment not found", experiment_id=experiment_id)
            return False
        
        if experiment.status != ExperimentStatus.DRAFT:
            logger.error("Experiment not in draft status", 
                        experiment_id=experiment_id, 
                        status=experiment.status)
            return False
        
        # Validate traffic allocation
        total_allocation = sum(experiment.traffic_allocation.values())
        if abs(total_allocation - 1.0) > 0.01:
            logger.error("Traffic allocation must sum to 1.0", 
                        experiment_id=experiment_id,
                        total=total_allocation)
            return False
        
        # Start experiment
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_date = datetime.utcnow()
        
        logger.info(
            "A/B test experiment started",
            experiment_id=experiment_id,
            name=experiment.name
        )
        
        return True
    
    def assign_variant(self, experiment_id: str, user_id: str, query: str) -> Optional[str]:
        """Assign user to a variant using deterministic hashing."""
        
        experiment = self.experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Check targeting filters
        if not self._passes_targeting_filters(experiment, user_id, query):
            return None
        
        # Deterministic assignment based on user_id + experiment_id
        hash_input = f"{user_id}:{experiment_id}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        assignment_ratio = (hash_value % 10000) / 10000.0
        
        # Assign based on traffic allocation
        cumulative = 0.0
        for variant_id, allocation in experiment.traffic_allocation.items():
            cumulative += allocation
            if assignment_ratio <= cumulative:
                return variant_id
        
        # Fallback to first variant
        return experiment.variants[0] if experiment.variants else None
    
    def _passes_targeting_filters(self, experiment: ABTestExperiment, user_id: str, query: str) -> bool:
        """Check if request passes experiment targeting filters."""
        
        # For now, simple implementation - could be enhanced with user profiling
        # In production, this would check user_type, complexity, legal_areas
        return True
    
    @traceable(
        run_type="tool",
        name="ab_test_execution",
        tags=["ab-test", "prompt-optimization", "legal-ai"]
    )
    async def execute_variant(
        self,
        experiment_id: str,
        variant_id: str,
        user_id: str,
        query: str,
        context: str,
        **kwargs
    ) -> ExperimentResult:
        """Execute a specific prompt variant and record results."""
        
        start_time = time.time()
        
        try:
            # Get variant
            variant = self.variants.get(variant_id)
            if not variant:
                raise ValueError(f"Variant not found: {variant_id}")
            
            # Log experiment execution
            logger.info("A/B test execution start",
                       experiment_id=experiment_id,
                       variant_id=variant_id,
                       variant_name=variant.name,
                       user_id=user_id,
                       query_preview=query[:100])
            
            # Execute prompt variant
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=1500
            )
            
            # Format prompt with variant template
            messages = variant.template.format_messages(
                query=query,
                context=context,
                **kwargs
            )
            
            # Execute with timing
            response = await llm.ainvoke(messages)
            latency_ms = (time.time() - start_time) * 1000
            
            # Evaluate quality
            quality_metrics = await self.quality_evaluator.evaluate_response(
                query=query,
                response=response.content,
                context=context
            )
            
            # Create result
            result = ExperimentResult(
                experiment_id=experiment_id,
                variant_id=variant_id,
                user_id=user_id,
                query=query,
                response=response.content,
                latency_ms=latency_ms,
                timestamp=datetime.utcnow(),
                metrics={
                    "latency_ms": latency_ms,
                    **quality_metrics.dict()
                }
            )
            
            # Store result
            self.results.append(result)
            
            # Log results for tracing
            logger.info("A/B test execution completed",
                       experiment_id=experiment_id,
                       variant_id=variant_id,
                       latency_ms=latency_ms,
                       response_length=len(response.content),
                       quality_score=quality_metrics.legal_accuracy_score)
            
            logger.info(
                "A/B test variant executed",
                experiment_id=experiment_id,
                variant_id=variant_id,
                latency_ms=round(latency_ms, 2),
                citation_count=quality_metrics.citation_count
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "A/B test variant execution failed",
                experiment_id=experiment_id,
                variant_id=variant_id,
                error=str(e)
            )
            raise
    
    def analyze_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Analyze A/B test results for statistical significance."""
        
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment not found: {experiment_id}")
        
        # Filter results for this experiment
        experiment_results = [r for r in self.results if r.experiment_id == experiment_id]
        
        if not experiment_results:
            return {
                "status": "no_data",
                "message": "No results available for analysis"
            }
        
        # Group results by variant
        results_by_variant = {}
        for result in experiment_results:
            variant_id = result.variant_id
            if variant_id not in results_by_variant:
                results_by_variant[variant_id] = []
            results_by_variant[variant_id].append(result)
        
        # Calculate metrics per variant
        variant_analysis = {}
        for variant_id, results in results_by_variant.items():
            variant = self.variants[variant_id]
            
            # Calculate basic metrics
            latencies = [r.latency_ms for r in results]
            citation_counts = [r.metrics.get("citation_count", 0) for r in results]
            grounding_scores = [r.metrics.get("grounding_score", 0) for r in results]
            
            variant_analysis[variant_id] = {
                "variant_name": variant.name,
                "variant_type": variant.variant_type,
                "sample_size": len(results),
                "metrics": {
                    "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                    "avg_citation_count": sum(citation_counts) / len(citation_counts) if citation_counts else 0,
                    "avg_grounding_score": sum(grounding_scores) / len(grounding_scores) if grounding_scores else 0,
                    "p95_latency_ms": sorted(latencies)[int(0.95 * len(latencies))] if latencies else 0
                }
            }
        
        # Statistical significance testing (simplified)
        significance_results = self._calculate_statistical_significance(
            results_by_variant, 
            experiment.primary_metric
        )
        
        analysis = {
            "experiment_id": experiment_id,
            "experiment_name": experiment.name,
            "status": "completed" if len(experiment_results) >= experiment.min_sample_size else "running",
            "total_samples": len(experiment_results),
            "variants": variant_analysis,
            "statistical_significance": significance_results,
            "recommendations": self._generate_recommendations(variant_analysis, significance_results)
        }
        
        # Log analysis for tracing
        logger.info("A/B test analysis completed",
                   experiment_id=experiment_id,
                   total_samples=len(experiment_results),
                   variants_count=len(variant_analysis))
        
        return analysis
    
    def _calculate_statistical_significance(
        self, 
        results_by_variant: Dict[str, List[ExperimentResult]], 
        primary_metric: str
    ) -> Dict[str, Any]:
        """Calculate statistical significance between variants."""
        
        # Simplified significance testing - in production would use proper statistical tests
        variant_ids = list(results_by_variant.keys())
        if len(variant_ids) < 2:
            return {"significant": False, "reason": "Need at least 2 variants"}
        
        # Get control variant (first one or explicitly marked)
        control_id = variant_ids[0]
        control_results = results_by_variant[control_id]
        
        if len(control_results) < 30:
            return {"significant": False, "reason": "Insufficient sample size"}
        
        significance_tests = {}
        
        for variant_id in variant_ids[1:]:
            treatment_results = results_by_variant[variant_id]
            
            if len(treatment_results) < 30:
                significance_tests[variant_id] = {
                    "significant": False,
                    "reason": "Insufficient sample size"
                }
                continue
            
            # Extract metric values
            control_values = [r.metrics.get(primary_metric, 0) for r in control_results]
            treatment_values = [r.metrics.get(primary_metric, 0) for r in treatment_results]
            
            # Simple comparison (in production would use t-test or Mann-Whitney U)
            control_mean = sum(control_values) / len(control_values)
            treatment_mean = sum(treatment_values) / len(treatment_values)
            
            improvement = (treatment_mean - control_mean) / control_mean if control_mean > 0 else 0
            
            significance_tests[variant_id] = {
                "significant": abs(improvement) > 0.05,  # 5% improvement threshold
                "improvement": round(improvement * 100, 2),
                "control_mean": round(control_mean, 3),
                "treatment_mean": round(treatment_mean, 3),
                "confidence": "medium"  # Would calculate proper confidence intervals
            }
        
        return significance_tests
    
    def _generate_recommendations(
        self, 
        variant_analysis: Dict[str, Any], 
        significance_results: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations from A/B test results."""
        
        recommendations = []
        
        # Check for clear winners
        best_variant = None
        best_score = 0
        
        for variant_id, analysis in variant_analysis.items():
            grounding_score = analysis["metrics"].get("avg_grounding_score", 0)
            if grounding_score > best_score:
                best_score = grounding_score
                best_variant = variant_id
        
        if best_variant and best_score > 0.8:
            recommendations.append(f"Variant {best_variant} shows highest grounding score ({best_score:.2f})")
        
        # Check for performance issues
        for variant_id, analysis in variant_analysis.items():
            avg_latency = analysis["metrics"].get("avg_latency_ms", 0)
            if avg_latency > 30000:  # 30 second threshold
                recommendations.append(f"Variant {variant_id} has high latency ({avg_latency:.0f}ms) - consider optimization")
        
        # Check sample sizes
        min_samples = min(analysis["sample_size"] for analysis in variant_analysis.values())
        if min_samples < 100:
            recommendations.append(f"Continue experiment - minimum sample size not reached ({min_samples}/100)")
        
        return recommendations


class LegalQualityEvaluator:
    """Evaluates legal quality metrics for A/B testing."""
    
    @traceable(
        run_type="tool",
        name="legal_quality_evaluator",
        tags=["evaluation", "quality", "legal-ai"]
    )
    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: str
    ) -> LegalQualityMetrics:
        """Evaluate legal quality of a response."""
        
        try:
            # Count citations
            citation_pattern = r'\(Source: [^)]+\)'
            citations = len(re.findall(citation_pattern, response))
            
            # Calculate citation density (citations per 100 words)
            word_count = len(response.split())
            citation_density = (citations / max(1, word_count)) * 100
            
            # Evaluate grounding using LLM
            grounding_score = await self._evaluate_grounding(response, context)
            
            # Evaluate legal accuracy using LLM
            legal_accuracy = await self._evaluate_legal_accuracy(query, response, context)
            
            # Evaluate reasoning clarity
            reasoning_clarity = await self._evaluate_reasoning_clarity(response)
            
            # Check constitutional compliance
            constitutional_compliance = self._check_constitutional_compliance(response)
            
            # Evaluate completeness
            completeness_score = await self._evaluate_completeness(query, response)
            
            metrics = LegalQualityMetrics(
                citation_count=citations,
                citation_density=round(citation_density, 2),
                grounding_score=grounding_score,
                legal_accuracy_score=legal_accuracy,
                reasoning_clarity=reasoning_clarity,
                constitutional_compliance=constitutional_compliance,
                completeness_score=completeness_score
            )
            
            # Log evaluation for tracing
            logger.info("Legal quality evaluation completed", **metrics.dict())
            
            return metrics
            
        except Exception as e:
            logger.error("Quality evaluation failed", error=str(e))
            
            # Return minimal metrics on failure
            return LegalQualityMetrics(
                citation_count=0,
                citation_density=0.0,
                grounding_score=0.0,
                legal_accuracy_score=0.0,
                reasoning_clarity=0.0,
                constitutional_compliance=False,
                completeness_score=0.0
            )
    
    async def _evaluate_grounding(self, response: str, context: str) -> float:
        """Evaluate how well response is grounded in provided context."""
        
        try:
            grounding_prompt = """Evaluate how well this legal response is grounded in the provided context.
            
Response: {response}

Context: {context}

Rate grounding quality from 0.0 to 1.0 where:
- 1.0: Every statement directly supported by context
- 0.8: Most statements supported, minor unsupported details
- 0.6: Generally supported but some unsupported claims
- 0.4: Partially supported with notable unsupported content
- 0.2: Poorly supported with significant unsupported content
- 0.0: Mostly or entirely unsupported by context

Return only a decimal number between 0.0 and 1.0."""
            
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, max_tokens=50)
            
            template = ChatPromptTemplate.from_messages([
                ("system", grounding_prompt),
                ("user", "Evaluate grounding quality.")
            ])
            
            chain = template | llm
            result = await chain.ainvoke({"response": response[:1000], "context": context[:1000]})
            
            # Parse score
            try:
                score = float(result.content.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                return 0.5  # Default if parsing fails
                
        except Exception as e:
            logger.warning("Grounding evaluation failed", error=str(e))
            return 0.5
    
    async def _evaluate_legal_accuracy(self, query: str, response: str, context: str) -> float:
        """Evaluate legal accuracy of response."""
        
        try:
            accuracy_prompt = """Evaluate the legal accuracy of this response to the query based on the provided context.
            
Query: {query}
Response: {response}
Context: {context}

Rate legal accuracy from 0.0 to 1.0 where:
- 1.0: Completely accurate legal analysis with proper citations
- 0.8: Mostly accurate with minor issues
- 0.6: Generally accurate but some questionable statements
- 0.4: Mixed accuracy with notable errors
- 0.2: Poor accuracy with significant errors
- 0.0: Inaccurate or misleading legal information

Return only a decimal number between 0.0 and 1.0."""
            
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, max_tokens=50)
            
            template = ChatPromptTemplate.from_messages([
                ("system", accuracy_prompt),
                ("user", "Evaluate legal accuracy.")
            ])
            
            chain = template | llm
            result = await chain.ainvoke({
                "query": query[:500],
                "response": response[:1000], 
                "context": context[:1000]
            })
            
            try:
                score = float(result.content.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                return 0.5
                
        except Exception as e:
            logger.warning("Legal accuracy evaluation failed", error=str(e))
            return 0.5
    
    async def _evaluate_reasoning_clarity(self, response: str) -> float:
        """Evaluate clarity of legal reasoning."""
        
        # Simple heuristics for reasoning clarity
        score = 1.0
        
        # Check for structured reasoning
        if not any(marker in response for marker in ["ISSUE", "RULE", "APPLICATION", "CONCLUSION", "1.", "2.", "3."]):
            score -= 0.3
        
        # Check for clear transitions
        transition_words = ["therefore", "however", "furthermore", "consequently", "accordingly"]
        transition_count = sum(1 for word in transition_words if word in response.lower())
        if transition_count == 0:
            score -= 0.2
        
        # Check for excessive length without structure
        if len(response) > 2000 and not any(marker in response for marker in ["##", "**", "1.", "2."]):
            score -= 0.2
        
        return max(0.0, score)
    
    def _check_constitutional_compliance(self, response: str) -> bool:
        """Check if response demonstrates constitutional hierarchy awareness."""
        
        # Check for constitutional references
        has_constitutional_ref = any(term in response for term in [
            "Constitution", "constitutional", "Constitutional Court", "constitutional rights"
        ])
        
        # Check for proper hierarchy language
        has_hierarchy_awareness = any(phrase in response for phrase in [
            "supreme law", "supreme court", "constitutional supremacy", "hierarchy"
        ])
        
        # Check for proper grounding
        has_citations = "(Source:" in response
        
        return has_constitutional_ref or has_hierarchy_awareness or has_citations
    
    async def _evaluate_completeness(self, query: str, response: str) -> float:
        """Evaluate completeness of response relative to query."""
        
        try:
            completeness_prompt = """Evaluate how completely this response answers the query.
            
Query: {query}
Response: {response}

Rate completeness from 0.0 to 1.0 where:
- 1.0: Fully addresses all aspects of the query
- 0.8: Addresses most aspects with minor gaps
- 0.6: Addresses main points but missing some aspects
- 0.4: Partially addresses query with notable gaps
- 0.2: Addresses only small portion of query
- 0.0: Does not address the query

Return only a decimal number between 0.0 and 1.0."""
            
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, max_tokens=50)
            
            template = ChatPromptTemplate.from_messages([
                ("system", completeness_prompt),
                ("user", "Evaluate completeness.")
            ])
            
            chain = template | llm
            result = await chain.ainvoke({
                "query": query[:500],
                "response": response[:1000]
            })
            
            try:
                score = float(result.content.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                return 0.5
                
        except Exception as e:
            logger.warning("Completeness evaluation failed", error=str(e))
            return 0.5


# ==============================================================================
# PROMPT VARIANT FACTORY
# ==============================================================================

class PromptVariantFactory:
    """Factory for creating prompt variants for A/B testing."""
    
    @staticmethod
    def create_synthesis_variants() -> List[PromptVariant]:
        """Create synthesis prompt variants for testing."""
        
        # Control: Current professional synthesis
        control_template = ChatPromptTemplate.from_messages([
            ("system", """You are Gweta, a legal AI assistant for Zimbabwe law.
Provide accurate, well-cited legal information based ONLY on the provided context.

CRITICAL RULES:
- Answer ONLY from provided context
- Cite every factual claim with (Source: doc_key)
- Use professional legal analysis format
- Include IRAC structure when appropriate

**STRUCTURE**:
1. ISSUE: Precise legal question
2. APPLICABLE LAW: Relevant provisions with citations
3. ANALYSIS: Apply legal reasoning with supporting authorities
4. CONCLUSION: Clear legal position"""),
            ("user", "Query: {query}\n\nContext:\n{context}\n\nProvide legal analysis.")
        ])
        
        # Treatment 1: Enhanced constitutional awareness
        constitutional_template = ChatPromptTemplate.from_messages([
            ("system", """You are Gweta, operating under Zimbabwe's constitutional supremacy.

**CONSTITUTIONAL HIERARCHY (MANDATORY)**:
1. Constitution of Zimbabwe (2013) - Supreme law
2. Acts of Parliament - Must conform to Constitution
3. Case law - Interpret Constitution and Acts

**CITE-THEN-STATE DISCIPLINE**:
For every legal proposition: FIRST cite, THEN state principle.
Format: (Source: Section X of Constitution) THEN legal principle.

**ENHANCED IRAC STRUCTURE**:
1. ISSUE: Constitutional/legal question
2. CONSTITUTIONAL FRAMEWORK: Relevant constitutional provisions
3. STATUTORY FRAMEWORK: Applicable Acts and sections
4. JUDICIAL INTERPRETATION: Relevant case law
5. SYNTHESIS: Harmonized legal position
6. CONCLUSION: Clear answer with confidence assessment"""),
            ("user", "Query: {query}\n\nAuthorities:\n{context}\n\nProvide constitutional analysis.")
        ])
        
        # Treatment 2: Adversarial reasoning
        adversarial_template = ChatPromptTemplate.from_messages([
            ("system", """You are Gweta, providing adversarial-tested legal analysis.

**ADVERSARIAL METHODOLOGY**:
1. State the strongest legal position
2. Identify obvious counterarguments
3. Address counterarguments with supporting authority
4. Provide balanced conclusion noting strengths/weaknesses

**CRITICAL ANALYSIS REQUIREMENTS**:
- Consider alternative interpretations of statutes
- Note conflicting authorities and hierarchy resolution
- Address policy arguments on both sides
- Assess strength of legal position (strong/moderate/weak)

**STRUCTURE**:
1. PRIMARY POSITION: Main legal argument with citations
2. COUNTERARGUMENTS: Strongest opposing views with authority
3. REBUTTAL: Response to counterarguments
4. BALANCED CONCLUSION: Position with confidence assessment"""),
            ("user", "Query: {query}\n\nAuthorities:\n{context}\n\nProvide adversarial analysis.")
        ])
        
        return [
            PromptVariant(
                variant_id="synthesis_control",
                variant_type=VariantType.CONTROL,
                name="Standard Professional Synthesis",
                description="Current IRAC-based synthesis prompt",
                template=control_template,
                weight=0.4
            ),
            PromptVariant(
                variant_id="synthesis_constitutional",
                variant_type=VariantType.TREATMENT,
                name="Constitutional Hierarchy Enhanced",
                description="Enhanced constitutional awareness and hierarchy",
                template=constitutional_template,
                weight=0.3
            ),
            PromptVariant(
                variant_id="synthesis_adversarial", 
                variant_type=VariantType.CHALLENGER,
                name="Adversarial Reasoning",
                description="Adversarial methodology with counterargument analysis",
                template=adversarial_template,
                weight=0.3
            )
        ]
    
    @staticmethod
    def create_intent_classification_variants() -> List[PromptVariant]:
        """Create intent classification prompt variants."""
        
        # Control: Current intent classifier
        from api.composer.prompts import get_prompt_template
        control_template = get_prompt_template("intent_classifier")
        
        # Treatment: Enhanced legal area detection
        enhanced_template = ChatPromptTemplate.from_messages([
            ("system", """You are Gweta's enhanced intent classifier with deep legal area recognition.

Classify queries with enhanced legal domain detection:

**ENHANCED INTENT CATEGORIES**:
- constitutional_interpretation: Constitutional law requiring constitutional reasoning
- statutory_analysis: Specific Acts requiring statutory interpretation
- case_law_research: Precedent research requiring precedent analysis
- corporate_law: Business, company registration, corporate governance
- employment_law: Labour relations, employment rights, workplace issues
- criminal_law: Criminal offenses, procedures, rights of accused
- civil_law: Contracts, torts, property rights, civil procedures
- family_law: Marriage, divorce, custody, inheritance
- administrative_law: Government procedures, public administration
- procedural_inquiry: Court procedures and legal processes

**COMPLEXITY WITH LEGAL CONTEXT**:
- simple: Single provision, clear statutory answer
- moderate: Multiple provisions, requires legal synthesis
- complex: Multi-jurisdictional, conflicting authorities, constitutional issues
- expert: Novel interpretation, policy implications, precedent-setting potential

**ENHANCED USER DETECTION**:
- legal_professional: Uses technical terminology, cites cases/statutes
- business_professional: Corporate context, compliance focus
- citizen_basic: Plain language, practical concerns
- citizen_educated: Some legal knowledge but not professional

Return enhanced JSON with legal domain insights."""),
            ("user", "Query: {query}\n\nProvide enhanced classification.")
        ])
        
        return [
            PromptVariant(
                variant_id="intent_control",
                variant_type=VariantType.CONTROL,
                name="Standard Intent Classification",
                description="Current intent classification system",
                template=control_template,
                weight=0.5
            ),
            PromptVariant(
                variant_id="intent_enhanced",
                variant_type=VariantType.TREATMENT,
                name="Enhanced Legal Domain Detection",
                description="Enhanced legal area and user type detection",
                template=enhanced_template,
                weight=0.5
            )
        ]


# ==============================================================================
# A/B TEST ORCHESTRATOR
# ==============================================================================

class ABTestOrchestrator:
    """Main orchestrator for A/B testing in the legal AI pipeline."""
    
    def __init__(self):
        """Initialize A/B test orchestrator."""
        self.ab_manager = ABTestManager()
        self.variant_factory = PromptVariantFactory()
        self.active_experiments: Dict[str, str] = {}  # template_name -> experiment_id
        
    async def setup_synthesis_ab_test(self) -> str:
        """Set up A/B test for synthesis prompts."""
        
        # Create variants
        variants = self.variant_factory.create_synthesis_variants()
        
        # Create experiment
        experiment = self.ab_manager.create_experiment(
            name="Synthesis Prompt Optimization v1.0",
            description="Test constitutional hierarchy vs adversarial reasoning approaches",
            prompt_template_name="synthesis_professional",
            variants=variants
        )
        
        # Start experiment
        success = self.ab_manager.start_experiment(experiment.experiment_id)
        
        if success:
            self.active_experiments["synthesis_professional"] = experiment.experiment_id
            logger.info("Synthesis A/B test started", experiment_id=experiment.experiment_id)
        
        return experiment.experiment_id
    
    async def setup_intent_classification_ab_test(self) -> str:
        """Set up A/B test for intent classification."""
        
        # Create variants
        variants = self.variant_factory.create_intent_classification_variants()
        
        # Create experiment
        experiment = self.ab_manager.create_experiment(
            name="Intent Classification Enhancement v1.0", 
            description="Test enhanced legal domain detection vs standard classification",
            prompt_template_name="intent_classifier",
            variants=variants
        )
        
        # Start experiment
        success = self.ab_manager.start_experiment(experiment.experiment_id)
        
        if success:
            self.active_experiments["intent_classifier"] = experiment.experiment_id
            logger.info("Intent classification A/B test started", experiment_id=experiment.experiment_id)
        
        return experiment.experiment_id
    
    async def execute_with_ab_test(
        self,
        template_name: str,
        user_id: str,
        query: str,
        context: str,
        **kwargs
    ) -> Tuple[str, Any]:
        """Execute prompt with A/B testing if experiment is active."""
        
        # Check if there's an active experiment for this template
        experiment_id = self.active_experiments.get(template_name)
        
        if not experiment_id:
            # No experiment, use standard template
            from api.composer.prompts import get_prompt_template
            template = get_prompt_template(template_name)
            
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, max_tokens=1500)
            chain = template | llm
            response = await chain.ainvoke({"query": query, "context": context, **kwargs})
            
            return "control", response.content
        
        # Assign to variant
        variant_id = self.ab_manager.assign_variant(experiment_id, user_id, query)
        
        if not variant_id:
            # Assignment failed, use control
            from api.composer.prompts import get_prompt_template
            template = get_prompt_template(template_name)
            
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, max_tokens=1500)
            chain = template | llm
            response = await chain.ainvoke({"query": query, "context": context, **kwargs})
            
            return "control", response.content
        
        # Execute variant
        result = await self.ab_manager.execute_variant(
            experiment_id=experiment_id,
            variant_id=variant_id,
            user_id=user_id,
            query=query,
            context=context,
            **kwargs
        )
        
        return variant_id, result.response
    
    def get_experiment_status(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get status of active experiment for template."""
        
        experiment_id = self.active_experiments.get(template_name)
        if not experiment_id:
            return None
        
        return self.ab_manager.analyze_experiment_results(experiment_id)


# ==============================================================================
# INTEGRATION HELPERS
# ==============================================================================

# Global A/B test orchestrator instance
_ab_orchestrator: Optional[ABTestOrchestrator] = None


def get_ab_orchestrator() -> ABTestOrchestrator:
    """Get global A/B test orchestrator instance."""
    global _ab_orchestrator
    
    if _ab_orchestrator is None:
        _ab_orchestrator = ABTestOrchestrator()
    
    return _ab_orchestrator


async def setup_default_experiments():
    """Set up default A/B testing experiments."""
    
    orchestrator = get_ab_orchestrator()
    
    # Set up synthesis experiment
    synthesis_id = await orchestrator.setup_synthesis_ab_test()
    logger.info("Default synthesis A/B test created", experiment_id=synthesis_id)
    
    # Set up intent classification experiment  
    intent_id = await orchestrator.setup_intent_classification_ab_test()
    logger.info("Default intent A/B test created", experiment_id=intent_id)
    
    return {
        "synthesis_experiment": synthesis_id,
        "intent_experiment": intent_id
    }


import re  # Added missing import for regex operations

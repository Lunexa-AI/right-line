"""
LangGraph-based Query Orchestrator for RightLine Legal Assistant.

This module implements the complete agentic workflow using LangGraph for full
observability and state management. Every step is traceable in LangGraph Studio.

Task 5.1: Observability & Quality Gates Implementation
"""

import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional, TypedDict

import structlog
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from api.models import ChunkV3, ParentDocumentV3
from api.tools.retrieval_engine import RetrievalEngine, RetrievalConfig, RetrievalResult
from api.composer.synthesis import compose_legal_answer

logger = structlog.get_logger(__name__)


class AgentState(TypedDict):
    """
    Complete agent state for the legal query processing workflow.
    
    This state is fully observable in LangGraph Studio, allowing us to
    inspect every step of the agentic process.
    """
    # Request metadata
    request_id: str
    query: str
    user_id: str
    timestamp: str
    
    # Query processing
    intent: Optional[Dict[str, Any]]
    query_variants: List[str]
    processing_stage: str
    
    # Retrieval results
    retrieval_results: List[Dict[str, Any]]  # Serializable version of RetrievalResult
    retrieval_confidence: float
    retrieval_latency_ms: int
    
    # Synthesis
    synthesized_response: Optional[Dict[str, Any]]
    synthesis_latency_ms: int
    
    # Quality gates
    quality_checks: Dict[str, Any]
    warnings: List[str]
    
    # Performance metrics
    total_latency_ms: int
    node_timings: Dict[str, int]
    
    # Messages for LangGraph
    messages: List[BaseMessage]


class QueryIntent(BaseModel):
    """Structured intent classification result."""
    category: str = Field(description="Legal category (e.g., 'corporate', 'constitutional', 'criminal')")
    subcategory: Optional[str] = Field(description="Specific subcategory if applicable")
    entities: List[str] = Field(description="Extracted legal entities")
    complexity: str = Field(description="Query complexity: 'simple', 'moderate', 'complex'")
    confidence: float = Field(description="Intent classification confidence")


class LegalQueryOrchestrator:
    """
    LangGraph-based orchestrator for legal query processing.
    
    This orchestrator provides full observability through LangGraph Studio,
    allowing us to inspect and optimize every step of the agentic workflow.
    """
    
    def __init__(self):
        """Initialize the orchestrator with LangGraph components."""
        
        # Initialize core components
        self.retrieval_engine = RetrievalEngine()
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=2000,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        
        # Set up checkpointer for state persistence
        checkpointer_type = os.getenv("LANGGRAPH_CHECKPOINTER_TYPE", "memory")
        if checkpointer_type == "memory":
            self.checkpointer = MemorySaver()
        else:
            # For production, use Redis or Firestore (fallback to memory for now)
            self.checkpointer = MemorySaver()
        
        # Build the LangGraph workflow
        self.workflow = self._build_workflow()
        
        logger.info("LegalQueryOrchestrator initialized with LangGraph observability")
    
    def _build_workflow(self) -> StateGraph:
        """Build the complete LangGraph workflow with full observability."""
        
        # Create the state graph
        workflow = StateGraph(AgentState)
        
        # Add nodes for each step of the process
        workflow.add_node("initialize", self._initialize_request)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("generate_variants", self._generate_query_variants)
        workflow.add_node("retrieve_documents", self._retrieve_documents)
        workflow.add_node("quality_check_retrieval", self._quality_check_retrieval)
        workflow.add_node("synthesize_response", self._synthesize_response)
        workflow.add_node("quality_check_synthesis", self._quality_check_synthesis)
        workflow.add_node("finalize_response", self._finalize_response)
        
        # Define the workflow edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "classify_intent")
        workflow.add_edge("classify_intent", "generate_variants")
        workflow.add_edge("generate_variants", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "quality_check_retrieval")
        
        # Conditional edge based on retrieval quality
        workflow.add_conditional_edges(
            "quality_check_retrieval",
            self._should_proceed_to_synthesis,
            {
                "synthesize": "synthesize_response",
                "fallback": "finalize_response"
            }
        )
        
        workflow.add_edge("synthesize_response", "quality_check_synthesis")
        workflow.add_edge("quality_check_synthesis", "finalize_response")
        workflow.add_edge("finalize_response", END)
        
        # Compile with checkpointer for state persistence
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _initialize_request(self, state: AgentState) -> AgentState:
        """Initialize the request with metadata and timing."""
        
        start_time = time.time()
        
        # Set up request metadata
        state["request_id"] = str(uuid.uuid4())
        state["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S UTC")
        state["processing_stage"] = "initialized"
        state["node_timings"] = {}
        state["quality_checks"] = {}
        state["warnings"] = []
        state["messages"] = [HumanMessage(content=state["query"])]
        
        # Log initialization
        logger.info(
            "Query processing initialized",
            request_id=state["request_id"],
            query=state["query"][:100],
            user_id=state.get("user_id", "unknown")
        )
        
        # Record timing
        state["node_timings"]["initialize"] = int((time.time() - start_time) * 1000)
        
        return state
    
    async def _classify_intent(self, state: AgentState) -> AgentState:
        """Classify the query intent using structured LLM output."""
        
        start_time = time.time()
        state["processing_stage"] = "classifying_intent"
        
        # Intent classification prompt
        intent_prompt = f"""
        Analyze this legal query and classify its intent:
        
        Query: {state['query']}
        
        Provide a JSON response with:
        - category: Main legal category
        - subcategory: Specific subcategory if applicable
        - entities: List of legal entities mentioned
        - complexity: simple/moderate/complex
        - confidence: 0.0-1.0 confidence score
        
        Focus on Zimbabwean law context.
        """
        
        try:
            # Get structured intent classification
            response = await self.llm.ainvoke([HumanMessage(content=intent_prompt)])
            
            # Parse the JSON response
            import json
            intent_data = json.loads(response.content)
            
            state["intent"] = intent_data
            state["messages"].append(AIMessage(content=f"Intent classified: {intent_data['category']}"))
            
            logger.info(
                "Intent classified",
                request_id=state["request_id"],
                category=intent_data.get("category"),
                confidence=intent_data.get("confidence", 0.0)
            )
            
        except Exception as e:
            logger.warning(
                "Intent classification failed, using fallback",
                request_id=state["request_id"],
                error=str(e)
            )
            
            # Fallback intent
            state["intent"] = {
                "category": "general",
                "subcategory": None,
                "entities": [],
                "complexity": "moderate",
                "confidence": 0.5
            }
            state["warnings"].append("Intent classification failed, using fallback")
        
        # Record timing
        state["node_timings"]["classify_intent"] = int((time.time() - start_time) * 1000)
        
        return state
    
    async def _generate_query_variants(self, state: AgentState) -> AgentState:
        """Generate query variants for improved retrieval recall."""
        
        start_time = time.time()
        state["processing_stage"] = "generating_variants"
        
        # For now, use the original query plus simple variants
        # In production, this would use the LLM to generate semantic variants
        original_query = state["query"]
        variants = [original_query]
        
        # Add simple variants based on intent
        if state["intent"]["category"] == "corporate":
            variants.append(f"{original_query} company law")
            variants.append(f"{original_query} business regulations")
        elif state["intent"]["category"] == "constitutional":
            variants.append(f"{original_query} constitutional law")
            variants.append(f"{original_query} rights")
        
        state["query_variants"] = variants
        state["messages"].append(AIMessage(content=f"Generated {len(variants)} query variants"))
        
        logger.info(
            "Query variants generated",
            request_id=state["request_id"],
            variant_count=len(variants)
        )
        
        # Record timing
        state["node_timings"]["generate_variants"] = int((time.time() - start_time) * 1000)
        
        return state
    
    async def _retrieve_documents(self, state: AgentState) -> AgentState:
        """Retrieve relevant documents using the hybrid search engine."""
        
        start_time = time.time()
        state["processing_stage"] = "retrieving_documents"
        
        try:
            # Use the primary query for retrieval
            config = RetrievalConfig(top_k=10)
            results = await self.retrieval_engine.retrieve(state["query"], config)
            
            # Convert RetrievalResult objects to serializable format
            serializable_results = []
            for result in results:
                serializable_results.append({
                    "chunk_id": result.chunk_id,
                    "doc_id": result.doc_id,
                    "chunk_text": result.chunk_text[:1000],  # Truncate for state storage
                    "confidence": result.confidence,
                    "source": result.source,
                    "metadata": result.metadata,
                    "has_parent_doc": result.parent_doc is not None
                })
            
            state["retrieval_results"] = serializable_results
            state["retrieval_confidence"] = self.retrieval_engine.calculate_confidence(results)
            
            state["messages"].append(
                AIMessage(content=f"Retrieved {len(results)} relevant documents")
            )
            
            logger.info(
                "Document retrieval completed",
                request_id=state["request_id"],
                results_count=len(results),
                confidence=state["retrieval_confidence"]
            )
            
        except Exception as e:
            logger.error(
                "Document retrieval failed",
                request_id=state["request_id"],
                error=str(e)
            )
            
            state["retrieval_results"] = []
            state["retrieval_confidence"] = 0.0
            state["warnings"].append(f"Document retrieval failed: {str(e)}")
        
        # Record timing
        retrieval_time = int((time.time() - start_time) * 1000)
        state["node_timings"]["retrieve_documents"] = retrieval_time
        state["retrieval_latency_ms"] = retrieval_time
        
        return state
    
    async def _quality_check_retrieval(self, state: AgentState) -> AgentState:
        """Perform quality checks on retrieval results."""
        
        start_time = time.time()
        state["processing_stage"] = "checking_retrieval_quality"
        
        # Quality checks
        checks = {
            "has_results": len(state["retrieval_results"]) > 0,
            "confidence_threshold": state["retrieval_confidence"] >= 0.3,
            "diverse_sources": len(set(r["source"] for r in state["retrieval_results"])) > 1,
            "has_parent_docs": any(r["has_parent_doc"] for r in state["retrieval_results"])
        }
        
        state["quality_checks"]["retrieval"] = checks
        
        # Add warnings for failed checks
        if not checks["has_results"]:
            state["warnings"].append("No relevant documents found")
        if not checks["confidence_threshold"]:
            state["warnings"].append("Low retrieval confidence")
        if not checks["diverse_sources"]:
            state["warnings"].append("Results from single source only")
        
        logger.info(
            "Retrieval quality check completed",
            request_id=state["request_id"],
            checks=checks,
            warnings_count=len(state["warnings"])
        )
        
        # Record timing
        state["node_timings"]["quality_check_retrieval"] = int((time.time() - start_time) * 1000)
        
        return state
    
    def _should_proceed_to_synthesis(self, state: AgentState) -> str:
        """Decide whether to proceed with synthesis or use fallback."""
        
        retrieval_checks = state["quality_checks"]["retrieval"]
        
        # Proceed to synthesis if we have results and minimum confidence
        if retrieval_checks["has_results"] and retrieval_checks["confidence_threshold"]:
            return "synthesize"
        else:
            return "fallback"
    
    async def _synthesize_response(self, state: AgentState) -> AgentState:
        """Synthesize the final response using AI composition."""
        
        start_time = time.time()
        state["processing_stage"] = "synthesizing_response"
        
        try:
            # Convert serializable results back to RetrievalResult objects for synthesis
            # This is a simplified conversion - in production, we'd maintain full objects
            mock_results = []
            for result_data in state["retrieval_results"]:
                # Create a mock RetrievalResult for synthesis
                # In production, we'd have a proper deserialization method
                mock_result = type('MockResult', (), {
                    'chunk_id': result_data['chunk_id'],
                    'doc_id': result_data['doc_id'],
                    'chunk_text': result_data['chunk_text'],
                    'score': result_data['confidence'],
                    'source': result_data['source'],
                    'metadata': result_data['metadata']
                })()
                mock_results.append(mock_result)
            
            # Perform synthesis
            composed_answer = await compose_legal_answer(
                results=mock_results,
                query=state["query"],
                confidence=state["retrieval_confidence"],
                lang="en",
                use_openai=True
            )
            
            # Store synthesized response
            state["synthesized_response"] = {
                "tldr": composed_answer.tldr,
                "key_points": composed_answer.key_points,
                "citations": composed_answer.citations,
                "confidence": state["retrieval_confidence"]
            }
            
            state["messages"].append(
                AIMessage(content=f"Response synthesized: {composed_answer.tldr[:100]}...")
            )
            
            logger.info(
                "Response synthesis completed",
                request_id=state["request_id"],
                tldr_length=len(composed_answer.tldr),
                key_points_count=len(composed_answer.key_points)
            )
            
        except Exception as e:
            logger.error(
                "Response synthesis failed",
                request_id=state["request_id"],
                error=str(e)
            )
            
            # Fallback response
            state["synthesized_response"] = {
                "tldr": "I encountered an issue processing your legal query. Please try rephrasing your question.",
                "key_points": ["System temporarily unavailable", "Please try again"],
                "citations": [],
                "confidence": 0.1
            }
            state["warnings"].append(f"Response synthesis failed: {str(e)}")
        
        # Record timing
        synthesis_time = int((time.time() - start_time) * 1000)
        state["node_timings"]["synthesize_response"] = synthesis_time
        state["synthesis_latency_ms"] = synthesis_time
        
        return state
    
    async def _quality_check_synthesis(self, state: AgentState) -> AgentState:
        """Perform quality checks on the synthesized response."""
        
        start_time = time.time()
        state["processing_stage"] = "checking_synthesis_quality"
        
        if state["synthesized_response"]:
            response = state["synthesized_response"]
            
            # Quality checks for synthesis
            checks = {
                "has_tldr": bool(response["tldr"]),
                "tldr_length": len(response["tldr"]) >= 50,
                "has_key_points": len(response["key_points"]) > 0,
                "has_citations": len(response["citations"]) > 0,
                "confidence_acceptable": response["confidence"] >= 0.3
            }
            
            state["quality_checks"]["synthesis"] = checks
            
            # Add warnings for failed checks
            if not checks["tldr_length"]:
                state["warnings"].append("Response summary too short")
            if not checks["has_key_points"]:
                state["warnings"].append("No key points generated")
            if not checks["has_citations"]:
                state["warnings"].append("No citations provided")
        else:
            state["quality_checks"]["synthesis"] = {"error": "No synthesized response"}
            state["warnings"].append("Synthesis quality check failed - no response")
        
        logger.info(
            "Synthesis quality check completed",
            request_id=state["request_id"],
            checks=state["quality_checks"]["synthesis"],
            total_warnings=len(state["warnings"])
        )
        
        # Record timing
        state["node_timings"]["quality_check_synthesis"] = int((time.time() - start_time) * 1000)
        
        return state
    
    async def _finalize_response(self, state: AgentState) -> AgentState:
        """Finalize the response with complete metrics and logging."""
        
        start_time = time.time()
        state["processing_stage"] = "finalizing"
        
        # Calculate total processing time
        total_time = sum(state["node_timings"].values())
        state["total_latency_ms"] = total_time
        
        # Add final message
        if state.get("synthesized_response"):
            final_message = f"Legal analysis completed in {total_time}ms"
        else:
            final_message = f"Query processed with fallback response in {total_time}ms"
        
        state["messages"].append(AIMessage(content=final_message))
        
        # Final logging
        logger.info(
            "Query processing completed",
            request_id=state["request_id"],
            total_latency_ms=total_time,
            node_timings=state["node_timings"],
            warnings_count=len(state["warnings"]),
            quality_checks=state["quality_checks"]
        )
        
        # Record timing
        state["node_timings"]["finalize_response"] = int((time.time() - start_time) * 1000)
        state["processing_stage"] = "completed"
        
        return state
    
    async def process_query(
        self,
        query: str,
        user_id: str = "anonymous",
        config: Optional[RunnableConfig] = None
    ) -> AgentState:
        """
        Process a legal query through the complete LangGraph workflow.
        
        This method provides full observability through LangGraph Studio.
        """
        
        # Initialize state
        initial_state: AgentState = {
            "request_id": "",
            "query": query,
            "user_id": user_id,
            "timestamp": "",
            "intent": None,
            "query_variants": [],
            "processing_stage": "starting",
            "retrieval_results": [],
            "retrieval_confidence": 0.0,
            "retrieval_latency_ms": 0,
            "synthesized_response": None,
            "synthesis_latency_ms": 0,
            "quality_checks": {},
            "warnings": [],
            "total_latency_ms": 0,
            "node_timings": {},
            "messages": []
        }
        
        # Process through the workflow
        if config is None:
            config = RunnableConfig(
                configurable={"thread_id": str(uuid.uuid4())},
                tags=["legal-query", "production"]
            )
        
        try:
            # Execute the workflow
            final_state = await self.workflow.ainvoke(initial_state, config)
            return final_state
            
        except Exception as e:
            logger.error(
                "Workflow execution failed",
                query=query[:100],
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            
            # Return error state
            initial_state["processing_stage"] = "error"
            initial_state["warnings"] = [f"Workflow failed: {str(e)}"]
            return initial_state


# Global orchestrator instance
_orchestrator_instance: Optional[LegalQueryOrchestrator] = None


def get_orchestrator() -> LegalQueryOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        _orchestrator_instance = LegalQueryOrchestrator()
    
    return _orchestrator_instance


async def process_legal_query(
    query: str,
    user_id: str = "anonymous",
    config: Optional[RunnableConfig] = None
) -> AgentState:
    """
    Convenience function to process a legal query with full observability.
    
    This function provides the main entry point for the agentic workflow
    with complete LangGraph Studio integration.
    """
    
    orchestrator = get_orchestrator()
    return await orchestrator.process_query(query, user_id, config)

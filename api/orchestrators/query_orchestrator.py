"""Query Orchestrator using LangGraph for the Gweta agentic system.

This module implements the main orchestrator that routes user queries through
a graph of specialized nodes for intent detection, query processing, retrieval,
and synthesis.

Follows .cursorrules principles: LangChain ecosystem first, explicit state machine,
observability, and robust error handling.
"""

import asyncio
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers import LangChainTracer
from langchain_openai import ChatOpenAI
from langsmith import Client, traceable

from api.schemas.agent_state import AgentState, update_intent_routing, update_query_processing, update_retrieval_results, update_final_output

logger = structlog.get_logger(__name__)

# LangSmith configuration
LANGSMITH_API_KEY = os.environ.get("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "rightline-legal-ai")
LANGSMITH_ENDPOINT = os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")


class QueryOrchestrator:
    """Main orchestrator for agentic query processing using LangGraph."""
    
    def __init__(self):
        """Initialize the orchestrator with a compiled graph and caching."""
        self.graph = self._build_graph()
        
        # Initialize semantic cache for performance optimization
        self.cache = None
        try:
            from libs.caching.semantic_cache import SemanticCache
            import os
            
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            cache_enabled = os.getenv("CACHE_ENABLED", "true").lower() == "true"
            
            if cache_enabled:
                self.cache = SemanticCache(
                    redis_url=redis_url,
                    similarity_threshold=float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95")),
                    default_ttl=int(os.getenv("CACHE_DEFAULT_TTL", "3600"))
                )
                logger.info("Semantic cache initialized", redis_url=redis_url.split("@")[-1] if "@" in redis_url else redis_url)
            else:
                logger.info("Caching disabled by configuration")
        except Exception as e:
            logger.warning("Failed to initialize cache, caching disabled", error=str(e))
            self.cache = None
        
        # Initialize memory coordinator for conversation intelligence
        self.memory = None
        self.memory_enabled = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
        
        if self.memory_enabled:
            logger.info("Memory enabled, will initialize on first use")
        else:
            logger.info("Memory disabled by configuration")
    
    async def _ensure_memory_connected(self):
        """Ensure memory coordinator is initialized (lazy initialization)."""
        if not self.memory_enabled or self.memory is not None:
            return
        
        try:
            from libs.memory.coordinator import MemoryCoordinator
            from libs.firebase.client import get_firestore_async_client
            
            # Ensure cache is connected first (need Redis for short-term memory)
            await self._ensure_cache_connected()
            
            if not self.cache or not self.cache._redis_client:
                logger.warning("Cannot initialize memory without Redis")
                return
            
            # Get Firestore client (already configured!)
            firestore_client = get_firestore_async_client()
            
            # Create memory coordinator
            self.memory = MemoryCoordinator(
                redis_client=self.cache._redis_client,
                firestore_client=firestore_client
            )
            logger.info("Memory coordinator initialized successfully with Firestore")
            
        except Exception as e:
            logger.warning("Failed to initialize memory", error=str(e))
            self.memory = None
    
    async def _ensure_cache_connected(self):
        """Ensure cache is connected (lazy initialization)."""
        if self.cache and self.cache._redis_client is None:
            try:
                await self.cache.connect()
                logger.info("Cache connected on first use")
            except Exception as e:
                logger.warning("Failed to connect cache", error=str(e))
                self.cache = None
        
    def _build_graph(self) -> StateGraph:
        """Build and compile the LangGraph state machine."""
        
        # Create the state graph
        graph = StateGraph(AgentState)
        
        # Add nodes (renamed to explicit numbered stages with quality gates)
        graph.add_node("01_intent_classifier", self._route_intent_node)
        graph.add_node("02_query_rewriter", self._rewrite_expand_node)
        graph.add_node("03_retrieval_parallel", self._retrieve_concurrent_node)
        graph.add_node("04_merge_results", self._merge_results_node)
        graph.add_node("04b_relevance_filter", self._relevance_filter_node)
        graph.add_node("05_rerank", self._rerank_node)
        graph.add_node("06_select_topk", self._select_topk_node)
        graph.add_node("07_parent_expansion", self._expand_parents_node)
        graph.add_node("08_synthesis", self._synthesize_stream_node)
        graph.add_node("08b_quality_gate", self._quality_gate_node)
        graph.add_node("09_answer_composer", self._answer_composer_node)
        graph.add_node("session_search", self._session_search_node)
        graph.add_node("conversational_tool", self._conversational_tool_node)
        graph.add_node("summarizer_tool", self._summarizer_tool_node)
        
        # Set entry point
        graph.set_entry_point("01_intent_classifier")
        
        # Add conditional edges
        graph.add_conditional_edges(
            "01_intent_classifier",
            self._decide_route,
            {
                "rag_qa": "02_query_rewriter",
                "conversational": "conversational_tool",
                "summarize": "summarizer_tool",
                "disambiguate": "02_query_rewriter"
            }
        )
        
        # Add nodes for speculative execution
        graph.add_node("07a_parent_prefetch", self._parent_prefetch_speculative)
        graph.add_node("07b_parent_select", self._parent_final_select)
        
        # Add linear edges for RAG flow with speculative execution
        graph.add_edge("02_query_rewriter", "03_retrieval_parallel")
        graph.add_edge("03_retrieval_parallel", "04_merge_results")
        graph.add_edge("04_merge_results", "05_rerank")
        graph.add_edge("05_rerank", "06_select_topk")
        
        # Speculative execution path: prefetch → select
        graph.add_edge("06_select_topk", "07a_parent_prefetch")
        graph.add_edge("07a_parent_prefetch", "07b_parent_select")
        
        # Continue to synthesis
        graph.add_edge("07b_parent_select", "08_synthesis")
        graph.add_edge("08_synthesis", "09_answer_composer")
        
        # Terminal edges
        graph.add_edge("conversational_tool", END)
        graph.add_edge("summarizer_tool", END)
        graph.add_edge("09_answer_composer", END)
        
        # Compile with checkpointer
        checkpointer = MemorySaver()
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        logger.info("LangGraph orchestrator compiled successfully")
        return compiled_graph

    async def _merge_results_node(self, state: AgentState) -> Dict[str, Any]:
        """04_merge_results: Deduplicate and union BM25 + Milvus results, keep provenance."""
        start_time = time.time()
        try:
            bm25_results = getattr(state, 'bm25_results', [])
            milvus_results = getattr(state, 'milvus_results', [])
            combined_map = {}
            for r in (bm25_results + milvus_results):
                key = getattr(r, 'chunk_id', None)
                if not key:
                    continue
                score = getattr(r, 'score', getattr(r, 'confidence', 0.0))
                prev = combined_map.get(key)
                if prev is None or score > getattr(prev, 'score', getattr(prev, 'confidence', 0.0)):
                    combined_map[key] = r
            combined = list(combined_map.values())
            duration_ms = (time.time() - start_time) * 1000
            logger.info("04_merge_results completed",
                        bm25_count=len(bm25_results),
                        milvus_count=len(milvus_results),
                        combined_count=len(combined),
                        duration_ms=round(duration_ms, 2))
            return {"combined_results": combined, "retrieval_results": combined}
        except Exception as e:
            logger.error("04_merge_results failed", error=str(e))
            return {"combined_results": getattr(state, 'combined_results', []), "retrieval_results": getattr(state, 'combined_results', [])}

    async def _select_topk_node(self, state: AgentState) -> Dict[str, Any]:
        """06_select_topk: Select final top-K with adaptive parameters and quality threshold."""
        start_time = time.time()
        try:
            candidates = getattr(state, 'reranked_results', [])
            if not candidates:
                # build from ids if necessary
                id_set = set(getattr(state, 'reranked_chunk_ids', [])[:8])
                candidates = [r for r in getattr(state, 'combined_results', []) if r.chunk_id in id_set]
            
            # Get adaptive top_k for final selection
            rerank_top_k = getattr(state, 'rerank_top_k', None)
            if rerank_top_k is None:
                complexity = getattr(state, 'complexity', 'moderate')
                rerank_top_k = {
                    'simple': 5,
                    'moderate': 8,
                    'complex': 12,
                    'expert': 15
                }.get(complexity, 8)
            
            # Apply minimum score threshold (0.3)
            quality_candidates = [c for c in candidates if c.score >= 0.3]
            
            # Select top_k
            top = quality_candidates[:rerank_top_k]
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("06_select_topk completed with adaptive parameters",
                        selected=len(top),
                        target_top_k=rerank_top_k,
                        candidates_after_threshold=len(quality_candidates),
                        complexity=getattr(state, 'complexity', 'moderate'),
                        adaptive_params_used=True,
                        duration_ms=round(duration_ms, 2),
                        trace_id=state.trace_id)
            return {"topk_results": top}
        except Exception as e:
            logger.error("06_select_topk failed", error=str(e), trace_id=state.trace_id)
            return {"topk_results": getattr(state, 'reranked_results', [])[:8]}

    async def _answer_composer_node(self, state: AgentState) -> Dict[str, Any]:
        """09_answer_composer: Produce final answer text and confidence."""
        start_time = time.time()
        try:
            # Prefer synthesis result if present
            final_answer = getattr(state, 'final_answer', None)
            if not final_answer:
                syn = getattr(state, 'synthesis', {}) or {}
                tldr = syn.get('tldr') if isinstance(syn, dict) else None
                final_answer = tldr or "Answer generated."
            # Simple confidence proxy from top result
            conf = 0.0
            if getattr(state, 'reranked_results', None):
                conf = getattr(state.reranked_results[0], 'confidence', 0.7)
            elif getattr(state, 'combined_results', None):
                conf = getattr(state.combined_results[0], 'confidence', 0.6)
            duration_ms = (time.time() - start_time) * 1000
            logger.info("09_answer_composer completed", answer_len=len(final_answer), duration_ms=round(duration_ms, 2))
            return {"final_answer": final_answer, "confidence": conf}
        except Exception as e:
            logger.error("09_answer_composer failed", error=str(e))
            return {"final_answer": "I encountered an error composing the answer.", "confidence": 0.3}
    
    @traceable(
        run_type="tool",
        name="04b_relevance_filter",
        tags=["quality", "relevance", "filtering", "legal-ai"]
    )
    async def _relevance_filter_node(self, state: AgentState) -> Dict[str, Any]:
        """04b_relevance_filter: Filter sources for relevance to specific query."""
        start_time = time.time()
        
        try:
            logger.info("04b_relevance_filter start", trace_id=state.trace_id)
            
            # Get combined results from previous step
            combined_results = getattr(state, 'combined_results', [])
            if not combined_results:
                logger.warning("No combined results for relevance filtering", trace_id=state.trace_id)
                return {"filtered_results": [], "relevance_metrics": {}}
            
            # Import quality gates
            from api.composer.quality_gates import run_pre_synthesis_quality_gate
            
            # Convert results to context documents format
            context_docs = []
            for r in combined_results:
                context_docs.append({
                    "doc_key": r.chunk_id,
                    "title": r.metadata.get("title", "Unknown Document"),
                    "content": getattr(r, 'chunk_text', '') or "",
                    "doc_type": r.metadata.get("doc_type", "unknown"),
                    "confidence": getattr(r, 'confidence', 0.0),
                    "source": r.metadata.get("source", "unknown")
                })
            
            # Run relevance filtering
            filtered_docs, gate_result = await run_pre_synthesis_quality_gate(
                context_documents=context_docs,
                query=state.raw_query,
                min_sources=2,
                min_relevance_ratio=0.5
            )
            
            # Map back to results objects
            filtered_doc_keys = set(doc["doc_key"] for doc in filtered_docs)
            filtered_results = [
                r for r in combined_results 
                if r.chunk_id in filtered_doc_keys
            ]
            
            duration_ms = (time.time() - start_time) * 1000
            
            # LangSmith: Log filtering results
            logger.info(
                "relevance_filter_output",
                {
                    "sources_before": len(combined_results),
                    "sources_after": len(filtered_results),
                    "filtered_count": len(combined_results) - len(filtered_results),
                    "relevance_ratio": gate_result.confidence,
                    "quality_passed": gate_result.passed,
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            logger.info("04b_relevance_filter completed",
                       sources_before=len(combined_results),
                       sources_after=len(filtered_results),
                       quality_passed=gate_result.passed,
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "filtered_results": filtered_results,
                "combined_results": filtered_results,  # Update for downstream
                "relevance_metrics": gate_result.metrics,
                "quality_passed": gate_result.passed
            }
            
        except Exception as e:
            logger.error("04b_relevance_filter failed", error=str(e), trace_id=state.trace_id)
            return {"filtered_results": getattr(state, 'combined_results', []), "relevance_metrics": {}}
    
    @traceable(
        run_type="tool",
        name="08b_quality_gate",
        tags=["quality", "verification", "legal-ai"]
    )
    async def _quality_gate_node(self, state: AgentState) -> Dict[str, Any]:
        """08b_quality_gate: Comprehensive quality verification of legal analysis."""
        start_time = time.time()
        
        try:
            logger.info("08b_quality_gate start", trace_id=state.trace_id)
            
            # Get final answer and context for verification
            final_answer = getattr(state, 'final_answer', '')
            bundled_context = getattr(state, 'bundled_context', [])
            
            if not final_answer:
                logger.warning("No final answer for quality verification", trace_id=state.trace_id)
                return {"quality_passed": False, "quality_issues": ["No answer to verify"]}
            
            # Import quality gates
            from api.composer.quality_gates import run_post_synthesis_quality_gate
            
            # Convert context for quality checking
            context_docs = []
            for ctx in bundled_context:
                context_docs.append({
                    "doc_key": ctx.get('parent_doc_id', 'unknown'),
                    "title": ctx.get('title', 'Unknown Document'),
                    "content": ctx.get('content', ''),
                    "doc_type": ctx.get('source_type', 'unknown')
                })
            
            # Run comprehensive quality check
            quality_result = await run_post_synthesis_quality_gate(
                answer=final_answer,
                context_documents=context_docs,
                query=state.raw_query,
                user_type=getattr(state, 'user_type', 'professional'),
                complexity=getattr(state, 'complexity', 'moderate')
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # LangSmith: Log quality verification results
            logger.info(
                "quality_gate_output",
                {
                    "quality_passed": quality_result.passed,
                    "confidence": quality_result.confidence,
                    "issues_count": len(quality_result.issues),
                    "quality_issues": quality_result.issues,
                    "recommendations": quality_result.recommendations,
                    "metrics": quality_result.metrics,
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            logger.info("08b_quality_gate completed",
                       quality_passed=quality_result.passed,
                       confidence=quality_result.confidence,
                       issues_count=len(quality_result.issues),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            # If quality check fails, add warnings to answer
            if not quality_result.passed and final_answer:
                quality_warning = "\n\n⚠️ This analysis may require additional review for completeness and accuracy."
                final_answer += quality_warning
            
            return {
                "quality_passed": quality_result.passed,
                "quality_confidence": quality_result.confidence,
                "quality_issues": quality_result.issues,
                "quality_recommendations": quality_result.recommendations,
                "final_answer": final_answer  # Updated with warnings if needed
            }
            
        except Exception as e:
            logger.error("08b_quality_gate failed", error=str(e), trace_id=state.trace_id)
            
            # LangSmith: Log error
            logger.info(
                "quality_gate_error",
                {"error": str(e), "fallback_used": True}
            )
            
            return {"quality_passed": False, "quality_issues": [f"Quality check failed: {str(e)}"]}
    
    @traceable(
        run_type="llm",
        name="01_intent_classifier",
        tags=["intent", "classification", "legal-ai"]
    )
    async def _route_intent_node(self, state: AgentState) -> Dict[str, Any]:
        """01_intent_classifier: Classify user intent with advanced legal reasoning framework."""
        start_time = time.time()
        
        try:
            # LangSmith: Record input metadata
            input_metadata = {
                "query": state.raw_query,
                "query_length": len(state.raw_query),
                "trace_id": state.trace_id
            }
            
            logger.info("01_intent_classifier start", 
                       query_preview=state.raw_query[:50],
                       trace_id=state.trace_id)
            
            # Check intent cache first (performance optimization)
            if self.cache:
                try:
                    await self._ensure_cache_connected()
                    if self.cache:  # Might be None if connection failed
                        cached_intent = await self.cache.get_intent_cache(state.raw_query)
                        if cached_intent:
                            duration_ms = (time.time() - start_time) * 1000
                            logger.info("01_intent_classifier completed (from cache)",
                                       intent=cached_intent.get("intent"),
                                       complexity=cached_intent.get("complexity"),
                                       cache_hit=True,
                                       duration_ms=round(duration_ms, 2),
                                       trace_id=state.trace_id)
                            return cached_intent
                except Exception as e:
                    logger.warning("Intent cache check failed", error=str(e))
            
            # Get user profile for personalization (ARCH-036)
            user_profile = None
            if self.memory:
                try:
                    await self._ensure_memory_connected()
                    if self.memory:
                        full_context = await self.memory.get_full_context(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            max_tokens=500  # Small budget for intent classification
                        )
                        user_profile = full_context.get('user_profile', {})
                        logger.debug("User profile retrieved for intent classification",
                                    query_count=user_profile.get('query_count', 0))
                except Exception as e:
                    logger.warning("Failed to get user profile", error=str(e))
            
            # Cache miss - perform classification
            # ARCH-048: Use enhanced heuristics with confidence threshold
            heuristic_result = self._classify_intent_heuristic(state.raw_query)
            jurisdiction = self._detect_jurisdiction(state.raw_query)
            date_context = self._extract_date_context(state.raw_query)
            
            # If heuristics are confident (>=0.8), use them directly
            if heuristic_result and heuristic_result.get("confidence", 0) >= 0.8:
                logger.debug("Using heuristic classification",
                           intent=heuristic_result.get("intent"),
                           confidence=heuristic_result.get("confidence"),
                           trace_id=state.trace_id)
                intent_data = heuristic_result
                
                # Override with user profile if available and user is returning
                if user_profile and user_profile.get('is_returning_user'):
                    intent_data["complexity"] = user_profile.get('typical_complexity', intent_data.get("complexity"))
                    intent_data["user_type"] = user_profile.get('expertise_level', intent_data.get("user_type"))
                    intent_data["legal_areas"] = user_profile.get('top_legal_interests', intent_data.get("legal_areas", ["general"]))
            
            # If heuristics are uncertain or low confidence, fall back to LLM
            else:
                logger.debug("Heuristic uncertain, using LLM fallback",
                           heuristic_confidence=heuristic_result.get("confidence", 0) if heuristic_result else None,
                           trace_id=state.trace_id)
                
                llm_intent = await self._classify_intent_llm(state.raw_query)
                
                # Use user profile for personalization if available
                default_complexity = "moderate"
                default_user_type = "professional"
                
                if user_profile:
                    # Use user's typical complexity if they're a returning user
                    if user_profile.get('is_returning_user'):
                        default_complexity = user_profile.get('typical_complexity', 'moderate')
                        default_user_type = user_profile.get('expertise_level', 'professional')
                
                # Create intent data structure from LLM result
                intent_data = {
                    "intent": llm_intent or "rag_qa",
                    "complexity": default_complexity,
                    "user_type": default_user_type,
                    "jurisdiction": jurisdiction or "ZW",
                    "legal_areas": user_profile.get('top_legal_interests', ["general"]) if user_profile else ["general"],
                    "reasoning_framework": "irac",
                    "confidence": 0.8 if llm_intent else 0.5
                }
                
                # Calculate adaptive retrieval parameters based on complexity
                complexity = intent_data.get("complexity", "moderate")
                retrieval_params = {
                    "simple": {"retrieval_top_k": 15, "rerank_top_k": 5},
                    "moderate": {"retrieval_top_k": 25, "rerank_top_k": 8},
                    "complex": {"retrieval_top_k": 40, "rerank_top_k": 12},
                    "expert": {"retrieval_top_k": 50, "rerank_top_k": 15}
                }
                params = retrieval_params.get(complexity, retrieval_params["moderate"])
                intent_data["retrieval_top_k"] = params["retrieval_top_k"]
                intent_data["rerank_top_k"] = params["rerank_top_k"]
            
            # Add jurisdiction and date context
            intent_data["jurisdiction"] = intent_data.get("jurisdiction") or jurisdiction or "ZW"
            intent_data["date_context"] = date_context
            
            # Extract params for logging
            complexity = intent_data.get("complexity", "moderate")
            params = {
                "retrieval_top_k": intent_data.get("retrieval_top_k", 25),
                "rerank_top_k": intent_data.get("rerank_top_k", 8)
            }
            
            duration_ms = (time.time() - start_time) * 1000
            
            # LangSmith: Record output metadata
            output_metadata = {
                "intent_classification": intent_data,
                "duration_ms": round(duration_ms, 2),
                "reasoning_framework": intent_data.get("reasoning_framework", "irac"),
                "complexity_assessment": intent_data.get("complexity", "moderate"),
                "retrieval_params": params
            }
            
            logger.info("01_intent_classifier completed",
                       intent=intent_data.get("intent"),
                       complexity=intent_data.get("complexity"),
                       user_type=intent_data.get("user_type"),
                       confidence=intent_data.get("confidence"),
                       retrieval_top_k=params["retrieval_top_k"],
                       rerank_top_k=params["rerank_top_k"],
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            # Prepare result
            result = {
                "intent": intent_data.get("intent", "rag_qa"),
                "intent_confidence": intent_data.get("confidence", 0.8),
                "complexity": intent_data.get("complexity", "moderate"),
                "user_type": intent_data.get("user_type", "professional"),
                "legal_areas": intent_data.get("legal_areas", []),
                "reasoning_framework": intent_data.get("reasoning_framework", "irac"),
                "jurisdiction": intent_data.get("jurisdiction", "ZW"),
                "date_context": intent_data.get("date_context"),
                "retrieval_top_k": params["retrieval_top_k"],
                "rerank_top_k": params["rerank_top_k"]
            }
            
            # Cache the intent for future queries (2 hour TTL)
            if self.cache:
                try:
                    await self.cache.cache_intent(state.raw_query, result, ttl=7200)
                except Exception as e:
                    logger.warning("Failed to cache intent", error=str(e))
            
            return result
            
        except Exception as e:
            logger.error("01_intent_classifier failed", error=str(e), trace_id=state.trace_id)
            
            # LangSmith: Record error metadata
            error_metadata = {"error": str(e), "fallback_used": True}
            
            # Fallback to default classification
            return {
                "intent": "rag_qa",
                "intent_confidence": 0.5,
                "complexity": "moderate",
                "user_type": "professional",
                "reasoning_framework": "irac"
            }
    
    @traceable(
        run_type="llm",
        name="02_query_rewriter", 
        tags=["rewrite", "query-processing", "legal-ai"]
    )
    async def _rewrite_expand_node(self, state: AgentState) -> Dict[str, Any]:
        """02_query_rewriter: Rewrite query with legal precision, conversation context, and generate hypotheticals."""
        start_time = time.time()
        
        try:
            # Get memory context if available (ARCH-035: Memory in query rewriter)
            memory_context = None
            if self.memory:
                try:
                    await self._ensure_memory_connected()
                    if self.memory:
                        memory_context = await self.memory.get_full_context(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            max_tokens=1000  # Limited budget for rewriter
                        )
                        logger.info("Memory context retrieved for query rewriting",
                                   conversation_msgs=len(memory_context.get('conversation_history', [])),
                                   trace_id=state.trace_id)
                except Exception as e:
                    logger.warning("Failed to get memory for query rewriting", error=str(e))
            
            # LangSmith: Log input artifacts (avoid positional dict that breaks logging formatting)
            logger.info(
                "query_rewriter_input",
                raw_query=state.raw_query,
                intent=getattr(state, 'intent', None),
                complexity=getattr(state, 'complexity', 'moderate'),
                user_type=getattr(state, 'user_type', 'professional'),
                has_memory_context=memory_context is not None,
                trace_id=state.trace_id,
            )
            
            logger.info("02_query_rewriter start", trace_id=state.trace_id)
            
            # Resolve context references if this is a follow-up (ARCH-043)
            query_to_rewrite = state.raw_query
            if memory_context and memory_context.get('conversation_history'):
                query_to_rewrite = await self._resolve_context_references(
                    state.raw_query,
                    memory_context['conversation_history']
                )
            
            # History-aware rewrite (simplified for stability)
            rewritten_query = await self._rewrite_query_with_context(state, query_to_rewrite, memory_context)
            
            # Generate hypothetical documents (simplified for now)
            hypothetical_docs = [f"Hypothetical legal document for: {rewritten_query}"]
            sub_questions = []  # Simplified for initial implementation
            
            duration_ms = (time.time() - start_time) * 1000
            
            # LangSmith: Log output artifacts
            logger.info(
                "query_rewriter_output",
                original_query=state.raw_query,
                rewritten_query=rewritten_query,
                hypotheticals_count=len(hypothetical_docs),
                sub_questions_count=len(sub_questions),
                duration_ms=round(duration_ms, 2),
                enhancement_applied=rewritten_query != state.raw_query,
            )
            
            logger.info("02_query_rewriter completed",
                       original_length=len(state.raw_query),
                       rewritten_length=len(rewritten_query),
                       hypotheticals_count=len(hypothetical_docs),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "rewritten_query": rewritten_query,
                "hypothetical_docs": hypothetical_docs,
                "sub_questions": sub_questions
            }
            
        except Exception as e:
            logger.error("02_query_rewriter failed", error=str(e), trace_id=state.trace_id)
            
            # LangSmith: Log error
            logger.info(
                "query_rewriter_error",
                {"error": str(e), "fallback_to_original": True}
            )
            
            # Fallback to original query
            return {"rewritten_query": state.raw_query}
    
    @traceable(
        run_type="retriever",
        name="03_retrieval_parallel",
        tags=["retrieval", "bm25", "milvus", "parallel", "legal-ai"]
    )
    async def _retrieve_concurrent_node(self, state: AgentState) -> Dict[str, Any]:
        """03_retrieval_parallel: Run BM25 and Milvus with adaptive top_k."""
        start_time = time.time()
        
        try:
            query = state.rewritten_query or state.raw_query
            
            # Get adaptive top_k from state or calculate from complexity
            retrieval_top_k = getattr(state, 'retrieval_top_k', None)
            if retrieval_top_k is None:
                # Fallback to complexity-based calculation
                complexity = getattr(state, 'complexity', 'moderate')
                retrieval_top_k = {
                    'simple': 15,
                    'moderate': 25,
                    'complex': 40,
                    'expert': 50
                }.get(complexity, 25)
            
            # LangSmith: Log input artifacts
            logger.info(
                "retrieval_input",
                query=query,
                original_query=state.raw_query,
                query_enhanced=(query != state.raw_query),
                retrieval_top_k=retrieval_top_k,
                complexity=getattr(state, 'complexity', 'moderate'),
                trace_id=state.trace_id,
            )
            
            logger.info("03_retrieval_parallel start with adaptive parameters",
                       retrieval_top_k=retrieval_top_k,
                       complexity=getattr(state, 'complexity', 'moderate'),
                       trace_id=state.trace_id)
            
            # Use RetrievalEngine components directly to access both branches
            from api.tools.retrieval_engine import RetrievalEngine
            engine = RetrievalEngine()
            
            # Update retrievers with adaptive top_k
            engine.milvus_retriever.top_k = retrieval_top_k
            engine.bm25_retriever.top_k = retrieval_top_k
            
            # Launch BM25 and Milvus in parallel with timing
            bm25_start = time.time()
            milvus_start = time.time()
            
            bm25_task = asyncio.create_task(engine.bm25_retriever.aget_relevant_documents(query))
            milvus_task = asyncio.create_task(engine.milvus_retriever.aget_relevant_documents(query))
            bm25_docs, milvus_docs = await asyncio.gather(bm25_task, milvus_task, return_exceptions=False)
            
            bm25_time = time.time() - bm25_start
            milvus_time = time.time() - milvus_start
            
            # Convert LangChain Documents back to RetrievalResult
            bm25_results = [doc.metadata.get("retrieval_result") for doc in bm25_docs if doc.metadata.get("retrieval_result")]
            milvus_results = [doc.metadata.get("retrieval_result") for doc in milvus_docs if doc.metadata.get("retrieval_result")]
            
            # Merge with dedupe by chunk_id keeping max score
            combined_map = {}
            for r in (bm25_results + milvus_results):
                key = r.chunk_id
                current_score = getattr(r, 'score', r.confidence)
                existing = combined_map.get(key)
                if not existing or current_score > getattr(existing, 'score', existing.confidence):
                    combined_map[key] = r
            combined_results = list(combined_map.values())
            
            candidate_chunk_ids = [r.chunk_id for r in combined_results]
            
            duration_ms = (time.time() - start_time) * 1000
            
            # LangSmith: Log detailed output artifacts
            logger.info(
                "retrieval_output",
                bm25_count=len(bm25_results),
                milvus_count=len(milvus_results),
                combined_count=len(combined_results),
                deduplication_ratio=(len(combined_results) / (len(bm25_results) + len(milvus_results)) if (bm25_results or milvus_results) else 0),
                top_confidence=(combined_results[0].confidence if combined_results else 0),
                bm25_time_ms=round(bm25_time * 1000, 2),
                milvus_time_ms=round(milvus_time * 1000, 2),
                total_duration_ms=round(duration_ms, 2),
                parallel_efficiency=(max(bm25_time, milvus_time) / (bm25_time + milvus_time) if (bm25_time + milvus_time) > 0 else 0),
            )
            
            logger.info("03_retrieval_parallel completed",
                       bm25_count=len(bm25_results),
                       milvus_count=len(milvus_results), 
                       combined_count=len(combined_results),
                       retrieval_top_k=retrieval_top_k,
                       adaptive_params_used=True,
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id,
                       top_confidence=combined_results[0].confidence if combined_results else 0)
            
            return {
                "candidate_chunk_ids": candidate_chunk_ids,
                "bm25_results": bm25_results,
                "milvus_results": milvus_results,
                "combined_results": combined_results,
                "retrieval_results": combined_results
            }
            
        except Exception as e:
            logger.error("03_retrieval_parallel failed", error=str(e), trace_id=state.trace_id)
            
            # LangSmith: Log error
            logger.info(
                "retrieval_error",
                {"error": str(e), "fallback_used": True}
            )
            
            return {"candidate_chunk_ids": [], "bm25_results": [], "milvus_results": [], "combined_results": [], "retrieval_results": []}
    
    def _apply_diversity_filter(
        self,
        results: List[Any],
        target_count: int
    ) -> List[Any]:
        """
        Apply diversity filtering to prevent over-representation from single documents.
        
        Args:
            results: Reranked results to filter
            target_count: Target number of final results
            
        Returns:
            Filtered results with diversity enforced (max 40% from one document)
        """
        if len(results) <= target_count:
            return results
        
        selected = []
        parent_counts = {}
        max_per_parent = max(2, int(target_count * 0.4))  # Max 40% from one doc
        
        # First pass: enforce diversity constraint
        for result in results:
            parent_id = result.parent_doc.doc_id if result.parent_doc else result.chunk.doc_id
            current_count = parent_counts.get(parent_id, 0)
            
            if current_count < max_per_parent:
                selected.append(result)
                parent_counts[parent_id] = current_count + 1
                
                if len(selected) >= target_count:
                    break
        
        # Second pass: fill remaining slots if needed (relaxes diversity constraint)
        if len(selected) < target_count:
            remaining = [r for r in results if r not in selected]
            selected.extend(remaining[:target_count - len(selected)])
        
        return selected[:target_count]
    
    async def _rerank_node(self, state: AgentState) -> Dict[str, Any]:
        """05_rerank: Use BGE cross-encoder for semantic reranking."""
        start_time = time.time()
        
        try:
            retrieval_results = getattr(state, 'combined_results', [])
            if not retrieval_results:
                logger.warning("No results for reranking", trace_id=state.trace_id)
                return {"reranked_chunk_ids": [], "reranked_results": [], "rerank_method": "no_results"}
            
            query = state.rewritten_query or state.raw_query
            
            # Get complexity-based top_k
            complexity = getattr(state, 'complexity', 'moderate')
            top_k_map = {
                'simple': 5,
                'moderate': 8,
                'complex': 12,
                'expert': 15
            }
            target_top_k = top_k_map.get(complexity, 8)
            
            logger.info("Starting cross-encoder reranking",
                       candidates=len(retrieval_results),
                       target_top_k=target_top_k,
                       complexity=complexity,
                       trace_id=state.trace_id)
            
            # Use BGE cross-encoder reranker
            from api.tools.reranker import get_reranker
            reranker = await get_reranker()
            
            # Rerank with 2x buffer for quality filtering
            reranked_results = await reranker.rerank(
                query=query,
                candidates=retrieval_results,
                top_k=target_top_k * 2
            )
            
            # Apply quality threshold (reranker score >= 0.3)
            quality_filtered = [r for r in reranked_results if r.score >= 0.3]
            
            # Apply diversity filtering
            final_results = self._apply_diversity_filter(
                quality_filtered,
                target_count=target_top_k
            )
            
            reranked_chunk_ids = [r.chunk_id for r in final_results]
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Calculate quality metrics
            avg_score_before = sum(getattr(r, 'score', r.confidence) for r in retrieval_results) / len(retrieval_results)
            avg_score_after = sum(r.score for r in final_results) / len(final_results) if final_results else 0.0
            
            # Calculate parent diversity (handle None parent_doc)
            parent_ids = set()
            for r in final_results:
                try:
                    pid = r.parent_doc.doc_id if (r.parent_doc and hasattr(r.parent_doc, 'doc_id')) else r.chunk.doc_id
                    parent_ids.add(pid)
                except (AttributeError, TypeError):
                    # Fallback to chunk_id if we can't get parent
                    parent_ids.add(r.chunk_id)
            parent_diversity = len(parent_ids)
            
            # LangSmith metrics
            logger.info(
                "rerank_metrics",
                method="bge_crossencoder",
                candidates_in=len(retrieval_results),
                reranked_out=len(reranked_results),
                quality_filtered=len(quality_filtered),
                diversity_filtered=len(final_results),
                target_top_k=target_top_k,
                complexity=complexity,
                avg_score_before=round(avg_score_before, 3),
                avg_score_after=round(avg_score_after, 3),
                score_improvement=round(avg_score_after - avg_score_before, 3),
                min_score_after=round(min(r.score for r in final_results), 3) if final_results else 0,
                max_score_after=round(max(r.score for r in final_results), 3) if final_results else 0,
                parent_diversity=parent_diversity,
                duration_ms=round(duration_ms, 2)
            )
            
            logger.info("Cross-encoder reranking completed",
                       reranked_count=len(reranked_chunk_ids),
                       quality_filtered=len(quality_filtered),
                       final_count=len(final_results),
                       avg_score_improvement=round(avg_score_after - avg_score_before, 3),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "reranked_chunk_ids": reranked_chunk_ids,
                "reranked_results": final_results,
                "rerank_method": "bge_crossencoder"
            }
            
        except Exception as e:
            logger.error("Cross-encoder reranking failed, falling back to score sort",
                        error=str(e), trace_id=state.trace_id)
            
            # Graceful fallback to score-based sorting
            ranked = sorted(retrieval_results, 
                           key=lambda r: getattr(r, 'score', r.confidence), 
                           reverse=True)
            fallback_results = ranked[:12]
            
            return {
                "reranked_chunk_ids": [r.chunk_id for r in fallback_results],
                "reranked_results": fallback_results,
                "rerank_method": "fallback_score_sort"
            }
    
    async def _parent_prefetch_speculative(self, state: AgentState) -> Dict[str, Any]:
        """
        07a_parent_prefetch_speculative: Speculatively prefetch parent docs for top 15 results.
        
        This fetches more parent documents than we'll ultimately use, so the final
        selection can be very fast (just reads from cache, no R2 fetches).
        """
        start_time = time.time()
        
        try:
            reranked_results = getattr(state, 'reranked_results', [])
            
            if not reranked_results:
                logger.warning("No reranked results for speculative prefetch", trace_id=state.trace_id)
                return {"parent_doc_cache": {}}
            
            # Speculative prefetch: get top 15 docs (will use 5-12 based on final selection)
            prefetch_count = min(15, len(reranked_results))
            prefetch_results = reranked_results[:prefetch_count]
            
            logger.info("Starting speculative parent prefetch",
                       prefetch_count=prefetch_count,
                       total_results=len(reranked_results),
                       trace_id=state.trace_id)
            
            # Extract unique parent doc IDs for batching
            parent_doc_requests = []
            seen_parents = set()
            
            for result in prefetch_results:
                if result.parent_doc:
                    # Parent already attached
                    parent_id = result.parent_doc.doc_id
                else:
                    # Need to fetch parent
                    parent_id = result.chunk.doc_id
                
                if parent_id not in seen_parents:
                    seen_parents.add(parent_id)
                    doc_type = result.metadata.get("doc_type", "")
                    parent_doc_requests.append((parent_id, doc_type))
            
            # Batch fetch from R2 with high parallelism (speculative = aggressive)
            parent_doc_cache = {}
            
            if parent_doc_requests:
                from api.tools.retrieval_engine import RetrievalEngine
                async with RetrievalEngine() as engine:
                    parent_docs = await engine._fetch_parent_documents_batch(parent_doc_requests)
                    
                    # Build cache dict
                    for (doc_id, _), parent_doc in zip(parent_doc_requests, parent_docs):
                        if parent_doc:
                            parent_doc_cache[doc_id] = parent_doc
            
            # Also add already-attached parents to cache
            for result in prefetch_results:
                if result.parent_doc:
                    parent_doc_cache[result.parent_doc.doc_id] = result.parent_doc
            
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info("Speculative parent prefetch completed",
                       prefetched=len(parent_doc_cache),
                       unique_parents=len(parent_doc_requests),
                       cache_size=len(parent_doc_cache),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "parent_doc_cache": parent_doc_cache,
                "prefetch_count": prefetch_count
            }
            
        except Exception as e:
            logger.error("Speculative prefetch failed", error=str(e), trace_id=state.trace_id)
            return {"_parent_doc_cache": {}}
    
    async def _parent_final_select(self, state: AgentState) -> Dict[str, Any]:
        """
        07b_parent_final_select: Final selection using prefetched parent docs (near-zero latency).
        
        Uses the speculatively prefetched parent documents from cache, avoiding R2 fetches.
        """
        start_time = time.time()
        
        try:
            parent_doc_cache = getattr(state, 'parent_doc_cache', {})
            topk_results = getattr(state, 'topk_results', [])
            
            logger.info("Starting parent final selection from cache",
                       cached_parents=len(parent_doc_cache),
                       topk_count=len(topk_results),
                       trace_id=state.trace_id)
            
            # Build context from cache (no R2 fetch needed!)
            bundled_context = []
            authoritative_sources = set()
            current_tokens = 0
            MAX_CONTEXT_TOKENS = 8000
            
            for result in topk_results:
                parent_id = result.parent_doc.doc_id if result.parent_doc else result.chunk.doc_id
                parent_doc = parent_doc_cache.get(parent_id)
                
                if not parent_doc:
                    logger.warning("Cache miss for parent doc (fetching directly)",
                                 parent_id=parent_id,
                                 trace_id=state.trace_id)
                    # Fallback: use attached parent if available
                    parent_doc = result.parent_doc
                    
                if not parent_doc:
                    continue
                
                # Estimate tokens
                content = parent_doc.pageindex_markdown or ""
                estimated_tokens = len(content) // 4
                
                # Check token budget
                if current_tokens + estimated_tokens > MAX_CONTEXT_TOKENS:
                    logger.info("Token cap reached during parent selection",
                               trace_id=state.trace_id,
                               current_tokens=current_tokens)
                    break
                
                # Add to context
                bundled_context.append({
                    "chunk_id": result.chunk_id,
                    "parent_doc_id": parent_doc.doc_id,
                    "title": parent_doc.title or parent_doc.canonical_citation,
                    "content": content[:2000],  # Cap individual doc size
                    "confidence": result.confidence,
                    "source_type": result.metadata.get("doc_type", "unknown")
                })
                
                current_tokens += min(estimated_tokens, 500)
                authoritative_sources.add(parent_doc.canonical_citation or parent_doc.title)
            
            duration_ms = (time.time() - start_time) * 1000
            cache_hits = len([r for r in topk_results if (r.parent_doc.doc_id if r.parent_doc else r.chunk.doc_id) in parent_doc_cache])
            
            logger.info("Parent final selection completed (from cache)",
                       selected=len(bundled_context),
                       cache_hits=cache_hits,
                       cache_misses=len(topk_results) - cache_hits,
                       duration_ms=round(duration_ms, 2),  # Should be <20ms!
                       trace_id=state.trace_id)
            
            return {
                "bundled_context": bundled_context,
                "authoritative_sources": list(authoritative_sources),
                "context_tokens": current_tokens
            }
            
        except Exception as e:
            logger.error("Parent final selection failed", error=str(e), trace_id=state.trace_id)
            return {"bundled_context": [], "authoritative_sources": [], "context_tokens": 0}
    
    async def _expand_parents_node(self, state: AgentState) -> Dict[str, Any]:
        """07_parent_expansion: Fetch parent docs and bundle context under token caps."""
        start_time = time.time()
        
        try:
            logger.info("Starting parent document expansion", 
                       chunks_to_expand=len(state.reranked_chunk_ids),
                       trace_id=state.trace_id)
            
            # Get retrieval results to access parent document information
            retrieval_results = getattr(state, 'reranked_results', []) or getattr(state, 'retrieval_results', [])
            if not retrieval_results:
                logger.warning("No retrieval results for parent expansion", trace_id=state.trace_id)
                return {"parent_doc_keys": []}
            
            # Prefer already provided reranked_results; otherwise filter by IDs
            if not retrieval_results or not getattr(state, 'reranked_chunk_ids', None):
                reranked_results = retrieval_results[:12]
            else:
                reranked_results = []
                reranked_ids_set = set(state.reranked_chunk_ids)
                for result in retrieval_results:
                    if result.chunk_id in reranked_ids_set:
                        reranked_results.append(result)
                reranked_results = reranked_results[:12]
            
            # Extract unique parent document keys for batching
            parent_doc_requests = []
            chunk_to_parent_map = {}
            
            for result in reranked_results:
                if result.parent_doc:
                    # Parent already fetched during retrieval
                    parent_key = f"{result.parent_doc.doc_id}"
                    chunk_to_parent_map[result.chunk_id] = result.parent_doc
                else:
                    # Need to fetch parent document
                    parent_key = f"{result.chunk.doc_id}"
                    parent_doc_requests.append((result.chunk.doc_id, result.metadata.get("doc_type", "")))
            
            # Batch fetch missing parent documents from R2
            if parent_doc_requests:
                from api.tools.retrieval_engine import RetrievalEngine
                async with RetrievalEngine() as engine:
                    parent_docs = await engine._fetch_parent_documents_batch(parent_doc_requests)
                    
                    # Map fetched parents back to chunks
                    for i, (doc_id, doc_type) in enumerate(parent_doc_requests):
                        if i < len(parent_docs) and parent_docs[i]:
                            # Find chunks with this parent
                            for result in reranked_results:
                                if result.chunk.doc_id == doc_id:
                                    chunk_to_parent_map[result.chunk_id] = parent_docs[i]
            
            # Build context with token caps (following bundling policy)
            MAX_CONTEXT_TOKENS = 8000  # Conservative limit for synthesis
            current_tokens = 0
            bundled_context = []
            authoritative_sources = set()
            
            for result in reranked_results:
                parent_doc = chunk_to_parent_map.get(result.chunk_id)
                if not parent_doc:
                    continue
                
                # Estimate tokens (rough: 4 chars per token)
                content = parent_doc.pageindex_markdown or ""
                estimated_tokens = len(content) // 4
                
                # Check token budget
                if current_tokens + estimated_tokens > MAX_CONTEXT_TOKENS:
                    logger.info("Token cap reached during parent expansion", 
                               trace_id=state.trace_id,
                               current_tokens=current_tokens,
                               max_tokens=MAX_CONTEXT_TOKENS)
                    break
                
                # Add to context
                bundled_context.append({
                    "chunk_id": result.chunk_id,
                    "parent_doc_id": parent_doc.doc_id,
                    "title": parent_doc.title or parent_doc.canonical_citation,
                    "content": content[:2000],  # Cap individual document size
                    "confidence": result.confidence,
                    "source_type": result.metadata.get("doc_type", "unknown")
                })
                
                current_tokens += min(estimated_tokens, 500)  # Cap contribution per doc
                authoritative_sources.add(parent_doc.canonical_citation or parent_doc.title)
            
            # Extract parent document keys for state
            parent_doc_keys = [ctx["parent_doc_id"] for ctx in bundled_context]
            context_bundle_key = f"context_bundle_{state.trace_id}"
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("Parent document expansion completed",
                       parent_docs_count=len(parent_doc_keys),
                       authoritative_sources=len(authoritative_sources),
                       context_tokens=current_tokens,
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "parent_doc_keys": parent_doc_keys,
                "context_bundle_key": context_bundle_key,
                "bundled_context": bundled_context,
                "context_tokens": current_tokens,
                "authoritative_sources": list(authoritative_sources)
            }
            
        except Exception as e:
            logger.error("Parent document expansion failed", error=str(e), trace_id=state.trace_id)
            return {"parent_doc_keys": [], "context_bundle_key": None}
    
    @traceable(
        run_type="llm",
        name="08_synthesis",
        tags=["synthesis", "legal-analysis", "constitutional", "legal-ai"]
    )
    async def _synthesize_stream_node(self, state: AgentState) -> Dict[str, Any]:
        """08_synthesis: Generate comprehensive legal analysis with constitutional awareness and memory context."""
        start_time = time.time()
        
        try:
            # Get complexity and user type for appropriate synthesis
            complexity = getattr(state, 'complexity', 'moderate')
            user_type = getattr(state, 'user_type', 'professional')
            reasoning_framework = getattr(state, 'reasoning_framework', 'irac')
            
            # Get memory context if available (ARCH-041: Memory-aware synthesis)
            memory_context = None
            if self.memory:
                try:
                    await self._ensure_memory_connected()
                    if self.memory:
                        memory_context = await self.memory.get_full_context(
                            user_id=state.user_id,
                            session_id=state.session_id,
                            max_tokens=1500  # Leave room for other context
                        )
                        logger.info("Memory context retrieved for synthesis",
                                   conversation_msgs=len(memory_context.get('conversation_history', [])),
                                   memory_tokens=memory_context.get('tokens_used', {}).get('total', 0),
                                   trace_id=state.trace_id)
                except Exception as e:
                    logger.warning("Failed to get memory context", error=str(e))
            
            # LangSmith: Log input artifacts
            logger.info(
                "synthesis_input",
                query=state.raw_query,
                rewritten_query=getattr(state, 'rewritten_query', None),
                context_documents=len(getattr(state, 'bundled_context', [])),
                complexity=complexity,
                user_type=user_type,
                reasoning_framework=reasoning_framework,
                legal_areas=getattr(state, 'legal_areas', []),
                has_memory_context=memory_context is not None,
                trace_id=state.trace_id,
            )
            
            logger.info("08_synthesis start", 
                       complexity=complexity,
                       user_type=user_type,
                       reasoning_framework=reasoning_framework,
                       trace_id=state.trace_id)
            
            # Use new constitutional prompting system
            from api.composer.prompts import get_prompt_template, get_max_tokens_for_complexity, build_synthesis_context
            
            # Get appropriate synthesis template
            template_name = f"synthesis_{user_type}"
            template = get_prompt_template(template_name)
            
            # Build context using new formatter
            context_docs = []
            for i, ctx in enumerate(getattr(state, 'bundled_context', [])[:12], 1):
                context_docs.append({
                    "doc_key": ctx.get('parent_doc_id', f'doc_{i}'),
                    "title": ctx.get('title', 'Unknown Document'),
                    "content": ctx.get('content', '')[:2000],
                    "doc_type": ctx.get('source_type', 'unknown'),
                    "authority_level": "high" if ctx.get('confidence', 0) > 0.8 else "medium"
                })
            
            # Add conversation context to synthesis if available (ARCH-041)
            conversation_context = ""
            if memory_context and memory_context.get('conversation_history'):
                recent_exchanges = memory_context['conversation_history'][-2:]  # Last 2 exchanges
                if recent_exchanges:
                    conversation_context = "\n\nRecent Conversation Context:\n"
                    for msg in recent_exchanges:
                        role = msg.get('role', 'unknown').capitalize()
                        content = msg.get('content', '')[:200]  # First 200 chars
                        conversation_context += f"{role}: {content}\n"
            
            # Build comprehensive context with memory
            synthesis_context = build_synthesis_context(
                query=state.raw_query,
                context_documents=context_docs,
                user_type=user_type,
                complexity=complexity,
                legal_areas=getattr(state, 'legal_areas', []),
                reasoning_framework=reasoning_framework
            )
            
            # Enhance with conversation context if available
            if conversation_context and 'context' in synthesis_context:
                synthesis_context['context'] = synthesis_context['context'] + conversation_context
            
            # Create LLM with appropriate configuration
            max_tokens = get_max_tokens_for_complexity(complexity)
            llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                max_tokens=max_tokens,
                streaming=True
            )
            
            # Execute synthesis with LangSmith tracing
            final_answer = ""
            first_token_time = None
            
            async for chunk in llm.astream(template.format_messages(**synthesis_context)):
                if first_token_time is None:
                    first_token_time = time.time()
                    first_token_ms = (first_token_time - start_time) * 1000
                    logger.info("08_synthesis first token", 
                               first_token_ms=round(first_token_ms, 2),
                               trace_id=state.trace_id)
                
                if chunk.content:
                    final_answer += chunk.content
            
            # Extract citations and create synthesis object
            cited_sources = self._extract_citations(final_answer, getattr(state, 'bundled_context', []))
            
            duration_ms = (time.time() - start_time) * 1000
            first_token_ms = (first_token_time - start_time) * 1000 if first_token_time else duration_ms
            
            # LangSmith: Log comprehensive output artifacts
            logger.info(
                "synthesis_output",
                answer_length=len(final_answer),
                citations_count=len(cited_sources),
                complexity_used=complexity,
                max_tokens_allocated=max_tokens,
                reasoning_framework_applied=reasoning_framework,
                first_token_ms=round(first_token_ms, 2),
                total_duration_ms=round(duration_ms, 2),
                tokens_per_second=(len(final_answer.split()) / (duration_ms / 1000) if duration_ms > 0 else 0),
                synthesis_prompt_length=len(str(template.format_messages(**synthesis_context))),
                context_documents_used=len(context_docs),
            )
            
            logger.info("08_synthesis completed",
                       answer_length=len(final_answer),
                       citations_count=len(cited_sources),
                       first_token_ms=round(first_token_ms, 2),
                       total_duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "final_answer": final_answer,
                "synthesis": {
                    "tldr": final_answer,
                    "citations": cited_sources,
                    "reasoning_framework": reasoning_framework,
                    "complexity": complexity
                },
                "cited_sources": cited_sources,
                "first_token_ms": round(first_token_ms, 2)
            }
            
        except Exception as e:
            logger.error("08_synthesis failed", error=str(e), trace_id=state.trace_id)
            
            # LangSmith: Log error with context
            logger.info(
                "synthesis_error",
                {
                    "error": str(e),
                    "fallback_used": True,
                    "context_available": len(getattr(state, 'bundled_context', [])),
                    "query": state.raw_query[:100]
                }
            )
            
            return {
                "final_answer": "I apologize, but I encountered an error while generating your answer.",
                "synthesis": {"tldr": "Error in synthesis", "citations": []},
                "cited_sources": [],
                "attribution_passed": False,
                "quotes_verified": False
            }
    
    async def _session_search_node(self, state: AgentState) -> Dict[str, Any]:
        """Session search node - placeholder for conversational queries."""
        return {"final_answer": f"Conversational response to: {state.raw_query}"}
    
    async def _conversational_tool_node(self, state: AgentState) -> Dict[str, Any]:
        """Conversational tool node - placeholder."""
        return {"final_answer": f"Conversational response to: {state.raw_query}"}
    
    async def _summarizer_tool_node(self, state: AgentState) -> Dict[str, Any]:
        """Summarizer tool node - placeholder."""
        return {"final_answer": f"Summary response to: {state.raw_query}"}
    
    def _decide_route(self, state: AgentState) -> str:
        """Conditional routing based on intent."""
        return state.intent or "rag_qa"
    
    def _detect_follow_up(self, query: str, previous_query: Optional[str]) -> bool:
        """
        Detect if query is a follow-up to previous conversation.
        
        Args:
            query: Current query
            previous_query: Previous query (if any)
            
        Returns:
            True if this appears to be a follow-up question
        """
        import re
        
        query_lower = query.lower()
        
        # Follow-up patterns
        follow_up_patterns = [
            r"^(what about|how about|and if|but if|also|additionally)",
            r"\b(it|that|this|those|these)\b",
            r"(as you (said|mentioned)|as mentioned)",
            r"^(yes,?\s|no,?\s|okay,?\s)",
            r"(tell me more|explain|clarify|elaborate)",
            r"(the same|similar)"
        ]
        
        # Check if query matches any follow-up pattern
        for pattern in follow_up_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    async def _resolve_context_references(
        self,
        query: str,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """
        Resolve pronouns and context references in query.
        
        Args:
            query: Query with potential pronouns/references
            conversation_history: Recent conversation messages
            
        Returns:
            Query with resolved references
        """
        if not conversation_history:
            return query
        
        # Check if this looks like a follow-up
        previous_query = None
        if len(conversation_history) > 0:
            for msg in reversed(conversation_history):
                if msg.get("role") == "user":
                    previous_query = msg.get("content")
                    break
        
        if not self._detect_follow_up(query, previous_query):
            return query
        
        # Get last exchange for context
        last_user_query = ""
        last_assistant_response = ""
        
        for i in range(len(conversation_history) - 1, -1, -1):
            msg = conversation_history[i]
            if msg.get("role") == "assistant" and not last_assistant_response:
                last_assistant_response = msg.get("content", "")[:500]  # First 500 chars
            elif msg.get("role") == "user" and not last_user_query:
                last_user_query = msg.get("content", "")
            
            if last_user_query and last_assistant_response:
                break
        
        if not last_user_query:
            return query
        
        # Use mini LLM to resolve references
        try:
            from langchain_openai import ChatOpenAI
            
            resolution_prompt = f"""Resolve context references in this follow-up query.

Previous query: {last_user_query}
Previous response summary: {last_assistant_response}

Current query: {query}

Rewrite the current query to be self-contained (resolve "it", "this", "that", "what about", etc.).
Return ONLY the rewritten query, no explanation."""
            
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                max_tokens=100,
                timeout=3.0
            )
            
            response = await llm.ainvoke(resolution_prompt)
            resolved = response.content.strip()
            
            logger.info("Resolved follow-up query",
                       original=query[:50],
                       resolved=resolved[:50])
            
            return resolved
            
        except Exception as e:
            logger.warning("Failed to resolve context references", error=str(e))
            return query
    
    def _classify_intent_heuristic(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Advanced heuristic intent classification with complexity assessment.
        
        Returns a dictionary with intent, complexity, user_type, confidence,
        reasoning_framework, and retrieval parameters, or None if uncertain.
        
        ARCH-047: Enhanced heuristic classifier with better pattern matching
        and complexity assessment.
        """
        import re
        
        query_lower = query.lower().strip()
        intent = None
        complexity = "moderate"
        user_type = "citizen"  # Default assumption
        confidence = 0.0
        reasoning_framework = "irac"
        legal_areas = []
        
        # User type detection (professional vs citizen)
        professional_indicators = [
            r"\bact\b.*\[chapter", r"section \d+\(", r"\bsi \d+/", 
            r"\bv\.", r"\bsc \d+/", r"constitutional court",
            r"precedent", r"ratio decidendi", r"obiter dicta",
            r"statutory interpretation", r"\birac\b", r"legal framework",
            r"pursuant to", r"notwithstanding", r"hereinafter"
        ]
        
        if any(re.search(pattern, query_lower) for pattern in professional_indicators):
            user_type = "professional"
        
        # Conversational patterns (simple queries)
        conversational_patterns = [
            r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bthanks\b", 
            r"\bthank you\b", r"\bbye\b", r"\bgoodbye\b", 
            r"\bhow are you\b", r"\bgood morning\b", 
            r"\bgood afternoon\b", r"\bgood evening\b"
        ]
        if any(re.search(pattern, query_lower) for pattern in conversational_patterns):
            return {
                "intent": "conversational",
                "complexity": "simple",
                "user_type": "citizen",
                "confidence": 0.95,
                "reasoning_framework": "none",
                "legal_areas": [],
                "retrieval_top_k": 0,
                "rerank_top_k": 0
            }
        
        # Summarization patterns
        summarize_patterns = [
            "summarize", "summary", "tl;dr", "tldr", "explain differently",
            "what did you say", "what did you just say", "repeat that",
            "can you explain", "break it down", "in simple terms"
        ]
        if any(pattern in query_lower for pattern in summarize_patterns):
            return {
                "intent": "summarize",
                "complexity": "simple",
                "user_type": user_type,
                "confidence": 0.9,
                "reasoning_framework": "none",
                "legal_areas": [],
                "retrieval_top_k": 0,
                "rerank_top_k": 0
            }
        
        # Constitutional interpretation detection
        if any(word in query_lower for word in ["constitution", "constitutional", "fundamental right", "bill of rights"]):
            intent = "rag_qa"  # Use existing intent type
            reasoning_framework = "constitutional"
            complexity = "complex"  # Constitutional questions are inherently complex
            confidence = 0.9
            legal_areas = ["constitutional_law"]
        
        # Statutory analysis detection
        elif re.search(r"(act|statute|section|chapter \d+)", query_lower):
            intent = "rag_qa"
            reasoning_framework = "statutory"
            confidence = 0.85
            
            # Assess complexity based on query characteristics even for statutory queries
            word_count = len(query.split())
            has_multiple_concepts = any(conn in query_lower for conn in [" and ", " or ", "versus", "compare", "between", "differences"])
            
            if word_count >= 25 or has_multiple_concepts:
                complexity = "complex"
            else:
                complexity = "moderate" if user_type == "citizen" else "complex"
            
            # Extract legal areas from common statutory domains
            if any(word in query_lower for word in ["labour", "employment", "worker"]):
                legal_areas = ["labour_law"]
            elif any(word in query_lower for word in ["company", "director", "shareholder"]):
                legal_areas = ["company_law"]
            elif any(word in query_lower for word in ["criminal", "offence", "penalty"]):
                legal_areas = ["criminal_law"]
            else:
                legal_areas = ["general"]
        
        # Procedural inquiry detection (check before case law to avoid "file a case" confusion)
        elif any(word in query_lower for word in ["procedure", "file", "court process", "how to", "steps"]):
            intent = "rag_qa"
            reasoning_framework = "irac"
            complexity = "simple"
            confidence = 0.8
            legal_areas = ["procedure"]
        
        # Case law research detection
        elif any(word in query_lower for word in ["precedent", "judgment", "court held", "ruling", "held in"]):
            intent = "rag_qa"
            reasoning_framework = "precedent"
            complexity = "complex"
            confidence = 0.85
            legal_areas = ["case_law"]
        
        # Rights inquiry (citizen-focused)
        elif any(word in query_lower for word in ["my rights", "can i", "am i allowed", "do i have to"]):
            intent = "rag_qa"
            reasoning_framework = "irac"
            complexity = "simple"
            user_type = "citizen"
            confidence = 0.85
            legal_areas = ["general"]
        
        # Disambiguation patterns
        elif any(pattern in query_lower for pattern in ["what do you mean", "clarify", "i don't understand", "unclear"]):
            intent = "disambiguate"
            complexity = "simple"
            confidence = 0.8
            legal_areas = []
        
        # Default to RAG Q&A
        else:
            # Check if query contains legal keywords
            legal_keywords = [
                "act", "law", "legal", "statute", "regulation", "chapter", "section",
                "court", "judge", "penalty", "fine", "employment", "labour", "contract",
                "company", "registration", "license", "permit", "rights", "obligations",
                "wage", "salary", "tax", "duty", "liability", "damages", "compensation"
            ]
            if any(keyword in query_lower for keyword in legal_keywords):
                intent = "rag_qa"
                reasoning_framework = "irac"
                
                # Assess complexity based on query characteristics
                word_count = len(query.split())
                has_multiple_concepts = any(conn in query_lower for conn in [" and ", " or ", "versus", "compare", "between"])
                has_legal_terms = sum(1 for term in legal_keywords if term in query_lower)
                
                if word_count >= 25 or (has_multiple_concepts and has_legal_terms >= 3):
                    complexity = "complex"
                elif word_count > 15 or has_legal_terms >= 2:
                    complexity = "moderate"
                else:
                    complexity = "simple"
                
                confidence = 0.7
                
                # Extract legal areas from keywords
                if any(word in query_lower for word in ["labour", "employment", "worker", "salary", "wage"]):
                    legal_areas = ["labour_law"]
                elif any(word in query_lower for word in ["company", "director", "shareholder", "corporation"]):
                    legal_areas = ["company_law"]
                elif any(word in query_lower for word in ["criminal", "offence", "penalty"]):
                    legal_areas = ["criminal_law"]
                elif any(word in query_lower for word in ["contract", "agreement", "breach", "damages"]):
                    legal_areas = ["contract_law"]
                else:
                    legal_areas = ["general"]
            else:
                # Unclear - return None to trigger LLM fallback
                return None
        
        # Set retrieval parameters based on complexity
        retrieval_params = {
            "simple": {"retrieval_top_k": 15, "rerank_top_k": 5},
            "moderate": {"retrieval_top_k": 25, "rerank_top_k": 8},
            "complex": {"retrieval_top_k": 40, "rerank_top_k": 12},
            "expert": {"retrieval_top_k": 50, "rerank_top_k": 15}
        }
        params = retrieval_params.get(complexity, retrieval_params["moderate"])
        
        return {
            "intent": intent,
            "complexity": complexity,
            "user_type": user_type,
            "confidence": confidence,
            "reasoning_framework": reasoning_framework,
            "legal_areas": legal_areas or ["general"],
            "retrieval_top_k": params["retrieval_top_k"],
            "rerank_top_k": params["rerank_top_k"]
        }
    
    def _detect_jurisdiction(self, query: str) -> Optional[str]:
        """Detect jurisdiction from query."""
        query_lower = query.lower()
        if any(word in query_lower for word in ["zimbabwe", "zimbabwean", "zw", "harare"]):
            return "ZW"
        return None
    
    def _extract_date_context(self, query: str) -> Optional[str]:
        """Extract date context from query."""
        # Placeholder for date extraction
        return None
    
    async def _classify_intent_llm(self, query: str) -> str:
        """LLM-based intent classification fallback."""
        try:
            from langchain_openai import ChatOpenAI
            from api.composer.prompts import get_prompt_template
            
            # Use mini model for fast classification
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                max_tokens=50,
                timeout=5.0
            )
            
            # Get the intent router prompt
            prompt = get_prompt_template("intent_router")
            
            # Run classification
            chain = prompt | llm
            response = await chain.ainvoke({"query": query})
            
            # Parse JSON response
            import json
            try:
                result = json.loads(response.content)
                intent = result.get("intent", "rag_qa")
                
                # Validate intent
                valid_intents = ["rag_qa", "conversational", "summarize", "disambiguate"]
                if intent not in valid_intents:
                    intent = "rag_qa"
                    
                return intent
                
            except json.JSONDecodeError:
                logger.warning("LLM intent classification returned invalid JSON", response=response.content)
                return "rag_qa"
                
        except Exception as e:
            logger.warning("LLM intent classification failed", error=str(e))
            return "rag_qa"
    
    async def _rewrite_query_with_context(self, state: AgentState, query: str, memory_context: Optional[Dict] = None) -> str:
        """Rewrite query with conversation context and legal enhancement."""
        try:
            enhanced_query = query
            
            # Add conversation context hints if available
            if memory_context:
                user_profile = memory_context.get('user_profile', {})
                top_interests = user_profile.get('top_legal_interests', [])
                
                # Add relevant context based on user interests
                if top_interests and len(top_interests) > 0:
                    main_interest = top_interests[0]
                    if main_interest not in enhanced_query.lower():
                        # Subtle context hint
                        enhanced_query = f"{query} (user context: {main_interest})"
            
            # Add legal context based on query content
            if "rights" in query.lower() or "constitution" in query.lower():
                enhanced_query += " constitutional law Zimbabwe fundamental rights"
            elif "act" in query.lower() or "law" in query.lower():
                enhanced_query += " Zimbabwe legislation statutory provisions"
            
            # Add jurisdiction
            if state.jurisdiction:
                enhanced_query += f" [Jurisdiction: {state.jurisdiction}]"
            
            return enhanced_query
            
        except Exception as e:
            logger.warning("Query rewriting failed", error=str(e))
            return query
    
    async def _rewrite_query(self, state: AgentState) -> str:
        """Rewrite query with conversation context (simplified for testing)."""
        try:
            # Temporary simplification to bypass prompt template issues
            raw_query = state.raw_query
            
            # Simple legal query enhancement
            enhanced_query = raw_query
            
            # Add constitutional context for rights queries
            if "rights" in raw_query.lower() or "constitution" in raw_query.lower():
                enhanced_query += " constitutional law Zimbabwe fundamental rights"
            
            # Add statutory context for act queries
            elif "act" in raw_query.lower() or "law" in raw_query.lower():
                enhanced_query += " Zimbabwe legislation statutory provisions"
            
            # Add jurisdiction and date context if detected
            if state.jurisdiction:
                enhanced_query += f" [Jurisdiction: {state.jurisdiction}]"
            if state.date_context:
                enhanced_query += f" [As of: {state.date_context}]"
                
            return enhanced_query
            
        except Exception as e:
            logger.warning("Query rewriting failed", error=str(e))
            return state.raw_query
    
    async def _generate_multi_hyde(self, query: str) -> List[str]:
        """Generate multiple hypothetical documents using Multi-HyDE."""
        try:
            from langchain_openai import ChatOpenAI
            from api.composer.prompts import get_prompt_template
            
            # Use mini model for fast generation
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,  # Higher temp for diversity
                max_tokens=120,
                timeout=2.0
            )
            
            # Get the Multi-HyDE prompt
            prompt = get_prompt_template("multi_hyde")
            
            # Generate hypotheticals in parallel for different styles
            styles = ["statute", "case_law", "procedure", "commentary"]
            
            async def generate_hypothetical(style: str) -> str:
                try:
                    chain = prompt | llm
                    response = await chain.ainvoke({
                        "rewritten_query": query,
                        "style": style
                    })
                    return response.content.strip()
                except Exception as e:
                    logger.warning(f"Failed to generate {style} hypothetical", error=str(e))
                    return f"Hypothetical {style} document for: {query}"
            
            # Run all generations in parallel with timeout
            tasks = [generate_hypothetical(style) for style in styles]
            try:
                hypotheticals = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=0.6  # 600ms budget
                )
                
                # Filter out exceptions and empty results
                valid_hypotheticals = [
                    h for h in hypotheticals 
                    if isinstance(h, str) and len(h.strip()) > 10
                ]
                
                return valid_hypotheticals[:5]  # Cap at 5
                
            except asyncio.TimeoutError:
                logger.warning("Multi-HyDE generation timed out, using fallback")
                return [f"Hypothetical document for: {query}"]
                
        except Exception as e:
            logger.warning("Multi-HyDE generation failed", error=str(e))
            return [f"Hypothetical document for: {query}"]
    
    async def _decompose_query(self, query: str) -> List[str]:
        """Decompose complex queries into sub-questions."""
        try:
            # Simple heuristics to detect if decomposition is needed
            query_lower = query.lower()
            complexity_indicators = [
                " and ", " or ", "compare", "versus", "vs", "difference between",
                "both", "either", "as well as", "in addition to", "also"
            ]
            
            # Only decompose if query seems complex
            if not any(indicator in query_lower for indicator in complexity_indicators):
                return []
            
            from langchain_openai import ChatOpenAI
            from api.composer.prompts import get_prompt_template
            
            # Use mini model for fast decomposition
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                max_tokens=150,
                timeout=2.0
            )
            
            # Get the sub-question prompt
            prompt = get_prompt_template("sub_question")
            
            # Run decomposition
            chain = prompt | llm
            response = await chain.ainvoke({"rewritten_query": query})
            
            # Parse JSON response
            import json
            try:
                sub_questions = json.loads(response.content)
                if isinstance(sub_questions, list):
                    return sub_questions[:3]  # Cap at 3
                else:
                    return []
            except json.JSONDecodeError:
                logger.warning("Sub-question decomposition returned invalid JSON")
                return []
                
        except Exception as e:
            logger.warning("Query decomposition failed", error=str(e))
            return []
    
    async def run_query(self, state: AgentState) -> AgentState:
        """Run a query through the orchestrator with semantic caching."""
        config = RunnableConfig(
            configurable={"thread_id": state.session_id},
            metadata={"trace_id": state.trace_id}
        )
        
        logger.info("Starting query orchestration", 
                   trace_id=state.trace_id,
                   user_id=state.user_id,
                   query_preview=state.raw_query[:50])
        
        try:
            # Check cache first (performance optimization)
            if self.cache:
                try:
                    await self._ensure_cache_connected()
                    
                    if self.cache:  # Might be None if connection failed
                        user_type = getattr(state, 'user_type', 'professional')
                        cached_response = await self.cache.get_cached_response(
                            query=state.raw_query,
                            user_type=user_type,
                            check_semantic=True  # Enable semantic matching
                        )
                        
                        if cached_response:
                            # Cache hit - populate state and return
                            logger.info("Returning cached response",
                                       trace_id=state.trace_id,
                                       cache_hit_type=cached_response.get("_cache_hit", "unknown"),
                                       cache_similarity=cached_response.get("_cache_similarity"))
                            
                            # Update state with cached data
                            state.final_answer = cached_response.get("final_answer")
                            state.synthesis = cached_response.get("synthesis", {})
                            state.cited_sources = cached_response.get("cited_sources", [])
                            
                            # Add cache metadata to state
                            state.safety_flags["from_cache"] = True
                            state.safety_flags["cache_hit_type"] = cached_response.get("_cache_hit")
                            
                            # Record minimal timing (very fast!)
                            state.node_timings["total_cached"] = 50  # Approximate cache hit time
                            
                            return state
                except Exception as e:
                    logger.warning("Cache check failed, continuing with full pipeline", error=str(e))
            
            # Cache miss - run full pipeline
            logger.info("Cache miss, running full pipeline", trace_id=state.trace_id)
            
            # Run the graph
            result = await self.graph.ainvoke(state, config=config)
            
            # LangGraph returns the updated state as a dict-like object
            # Convert it back to AgentState for type safety
            if isinstance(result, dict):
                # Update the original state with the results
                updated_state = state.model_copy(update=result)
                result = updated_state
            
            logger.info("Query orchestration completed successfully",
                       trace_id=state.trace_id,
                       final_answer_length=len(result.final_answer or ""))
            
            # Cache the response for future queries
            if self.cache and result.final_answer:
                try:
                    cache_data = {
                        "final_answer": result.final_answer,
                        "synthesis": result.synthesis or {},
                        "cited_sources": result.cited_sources,
                        "_cached_at": datetime.utcnow().isoformat()
                    }
                    
                    # Determine TTL based on complexity and confidence
                    ttl_seconds = self._get_cache_ttl(result)
                    
                    user_type = getattr(result, 'user_type', 'professional')
                    
                    await self.cache.cache_response(
                        query=state.raw_query,
                        response=cache_data,
                        user_type=user_type,
                        ttl_seconds=ttl_seconds
                    )
                    
                    logger.info("Response cached for future queries",
                               trace_id=state.trace_id,
                               ttl_seconds=ttl_seconds)
                except Exception as e:
                    logger.warning("Failed to cache response", error=str(e), trace_id=state.trace_id)
            
            # Update memory systems after successful query (ARCH-037)
            if self.memory and result.final_answer:
                try:
                    await self.memory.update_memories(
                        user_id=state.user_id,
                        session_id=state.session_id,
                        query=state.raw_query,
                        response=result.final_answer,
                        metadata={
                            "complexity": getattr(result, 'complexity', 'moderate'),
                            "legal_areas": getattr(result, 'legal_areas', []),
                            "user_type": getattr(result, 'user_type', 'professional'),
                            "intent": getattr(result, 'intent', 'rag_qa')
                        }
                    )
                    logger.debug("Memories updated", trace_id=state.trace_id)
                except Exception as e:
                    logger.warning("Failed to update memories", error=str(e), trace_id=state.trace_id)
            
            return result
            
        except Exception as e:
            logger.error("Query orchestration failed", 
                        error=str(e), 
                        trace_id=state.trace_id)
            raise
    
    def _decide_refinement_strategy(self, state: AgentState) -> str:
        """
        ARCH-049: Decide whether to refine synthesis or request more sources.
        
        This method analyzes quality gate results and decides the next action:
        - "pass": Quality is good, proceed to finalization
        - "refine_synthesis": Synthesis has coherence/logic issues, re-synthesize
        - "retrieve_more": Insufficient sources, retrieve additional documents
        - "fail": Max iterations reached or unrecoverable error
        
        Args:
            state: Agent state with quality results and iteration count
            
        Returns:
            Strategy decision: "pass", "refine_synthesis", "retrieve_more", or "fail"
        """
        quality_passed = getattr(state, 'quality_passed', False)
        quality_confidence = getattr(state, 'quality_confidence', None)
        quality_issues = getattr(state, 'quality_issues', [])
        complexity = getattr(state, 'complexity', 'moderate')
        iteration_count = getattr(state, 'refinement_iteration', 0)
        
        # Handle missing quality data - default to pass to avoid blocking
        if quality_confidence is None:
            logger.info(
                "No quality data available, proceeding",
                trace_id=state.trace_id
            )
            return "pass"
        
        # Max 2 iterations to prevent infinite loops
        if iteration_count >= 2:
            logger.warning(
                "Max refinement iterations reached, proceeding with current answer",
                iteration_count=iteration_count,
                trace_id=state.trace_id
            )
            return "fail"  # Changed from "pass" to "fail" to add warning
        
        # If quality is good, proceed
        if quality_passed and quality_confidence > 0.8:
            logger.info(
                "Quality passed with high confidence, proceeding",
                quality_confidence=quality_confidence,
                trace_id=state.trace_id
            )
            return "pass"
        
        # Analyze quality issues to determine strategy
        issues_lower = [issue.lower() for issue in quality_issues]
        
        # Check for coherence/logic issues (suggests refinement)
        has_coherence_issues = any(
            keyword in issue for issue in issues_lower
            for keyword in ["coherence", "logic", "reasoning", "structure", "organization"]
        )
        
        # Check for source/coverage issues (suggests more retrieval)
        has_source_issues = any(
            keyword in issue for issue in issues_lower
            for keyword in ["insufficient", "missing", "incomplete", "coverage", "source"]
        )
        
        # Priority 1: If insufficient sources detected, retrieve more (checked first)
        if has_source_issues:
            logger.info(
                "Insufficient sources detected, running iterative retrieval",
                issues_count=len(quality_issues),
                trace_id=state.trace_id
            )
            return "retrieve_more"
        
        # Priority 2: If borderline quality with coherence issues, refine synthesis
        if 0.5 < quality_confidence < 0.8 and has_coherence_issues:
            logger.info(
                "Quality borderline with coherence issues, running self-criticism and refinement",
                quality_confidence=quality_confidence,
                issues_count=len(quality_issues),
                trace_id=state.trace_id
            )
            return "refine_synthesis"
        
        # For expert complexity, be stricter about quality
        if complexity == "expert" and quality_confidence < 0.7:
            logger.info(
                "Expert complexity with low confidence, attempting refinement",
                complexity=complexity,
                quality_confidence=quality_confidence,
                trace_id=state.trace_id
            )
            return "refine_synthesis"
        
        # For moderate confidence with some issues, try refinement
        if 0.6 <= quality_confidence < 0.8 and quality_issues:
            logger.info(
                "Moderate confidence with issues, attempting refinement",
                quality_confidence=quality_confidence,
                trace_id=state.trace_id
            )
            return "refine_synthesis"
        
        # Default: proceed even if quality is lower (for simple queries or final attempt)
        logger.info(
            "Quality below threshold but proceeding to avoid over-iteration",
            quality_confidence=quality_confidence,
            quality_passed=quality_passed,
            trace_id=state.trace_id
        )
        return "pass"
    
    def _get_cache_ttl(self, state: AgentState) -> int:
        """
        Determine cache TTL based on query characteristics.
        
        Args:
            state: Agent state with query metadata
            
        Returns:
            TTL in seconds
        """
        complexity = getattr(state, 'complexity', 'moderate')
        
        # Longer TTL for simple queries (more stable), shorter for complex (may need updates)
        ttl_map = {
            'simple': 7200,    # 2 hours
            'moderate': 3600,  # 1 hour
            'complex': 1800,   # 30 minutes
            'expert': 900      # 15 minutes
        }
        
        return ttl_map.get(complexity, 3600)
    
    def _build_synthesis_prompt(self, state: AgentState) -> str:
        """Build synthesis prompt using new constitutional prompting architecture."""
        from api.composer.prompts import get_prompt_template, build_synthesis_context
        
        # Determine user type (default to professional for test endpoint)
        user_type = getattr(state, 'user_type', 'professional')
        complexity = getattr(state, 'complexity', 'moderate') 
        reasoning_framework = getattr(state, 'reasoning_framework', 'irac')
        
        # Build context using new formatter
        context_docs = []
        for i, ctx in enumerate(state.bundled_context[:12], 1):  # Increased from 8 to 12
            context_docs.append({
                "doc_key": ctx.get('parent_doc_id', f'doc_{i}'),
                "title": ctx.get('title', 'Unknown Document'),
                "content": ctx.get('content', '')[:2000],  # Increased from 1500 to 2000
                "doc_type": ctx.get('source_type', 'unknown'),
                "authority_level": "high" if ctx.get('confidence', 0) > 0.8 else "medium"
            })
        
        # Get appropriate synthesis template
        template_name = f"synthesis_{user_type}"
        template = get_prompt_template(template_name)
        
        # Build comprehensive context
        synthesis_context = build_synthesis_context(
            query=state.raw_query,
            context_documents=context_docs,
            user_type=user_type,
            complexity=complexity,
            legal_areas=getattr(state, 'legal_areas', []),
            reasoning_framework=reasoning_framework
        )
        
        # Format the prompt
        messages = template.format_messages(**synthesis_context)
        return "\n".join([msg.content for msg in messages])
    
    def _extract_citations(self, answer: str, bundled_context: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract citations from the generated answer."""
        import re
        
        citations = []
        # Find [Source X] patterns in the answer
        source_pattern = r'\[Source (\d+)\]'
        matches = re.findall(source_pattern, answer)
        
        for match in matches:
            source_num = int(match) - 1  # Convert to 0-based index
            if source_num < len(bundled_context):
                ctx = bundled_context[source_num]
                citations.append({
                    "source_id": str(source_num + 1),
                    "title": ctx.get('title', 'Unknown Document'),
                    "doc_id": ctx.get('parent_doc_id', ''),
                    "confidence": str(ctx.get('confidence', 0.0)),
                    "type": ctx.get('source_type', 'unknown')
                })
        
        return citations

    def export_graph_diagram(self, output_path: str = "docs/diagrams/agent_graph.txt") -> None:
        """Export the graph structure as a text representation."""
        try:
            # Create the directory if it doesn't exist
            import os
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create a simple text representation of the graph
            graph_description = """
Gweta Agentic Core Graph Structure
=================================

Entry Point: route_intent

Nodes:
- route_intent: Classify user intent and extract context
- rewrite_expand: Rewrite query and generate hypotheticals
- retrieve_concurrent: Run hybrid retrieval (placeholder)
- rerank: Rerank results with BGE (placeholder)  
- expand_parents: Fetch parent documents (placeholder)
- synthesize_stream: Generate final answer (placeholder)
- conversational_tool: Handle conversational queries
- summarizer_tool: Handle summarization requests
- session_search: Search session history

Flow:
route_intent -> {
  rag_qa -> rewrite_expand -> retrieve_concurrent -> rerank -> expand_parents -> synthesize_stream -> END
  conversational -> conversational_tool -> END
  summarize -> summarizer_tool -> END
  disambiguate -> rewrite_expand -> ... (same as rag_qa)
}

State: AgentState (versioned, JSON-serializable, <8KB)
Checkpointer: MemorySaver (in-memory for dev)
Tracing: LangSmith integration ready
"""
            
            with open(output_path, "w") as f:
                f.write(graph_description.strip())
                
            logger.info("Graph diagram exported", output_path=output_path)
            
        except Exception as e:
            logger.warning("Failed to export graph diagram", error=str(e))


# Global orchestrator instance
_orchestrator: Optional[QueryOrchestrator] = None

def get_orchestrator() -> QueryOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = QueryOrchestrator()
    return _orchestrator


# Attribution Gate and Quote Verifier Classes

class AttributionGate:
    """Gate to validate that claims are properly cited."""
    
    async def validate_citations(self, answer: str, context: List[Dict[str, Any]]) -> 'AttributionResult':
        """Validate that answer has proper citations for claims."""
        import re
        
        # Simple heuristic: check for citation patterns
        citation_pattern = r'\[Source \d+\]'
        citations = re.findall(citation_pattern, answer)
        
        # Split answer into sentences and check citation density
        sentences = answer.split('.')
        factual_sentences = [s for s in sentences if len(s.strip()) > 20 and not s.strip().startswith('⚠️')]
        
        citation_ratio = len(citations) / max(len(factual_sentences), 1)
        
        # Require at least 1 citation per 3 factual sentences
        passed = citation_ratio >= 0.33
        
        missing_citations = []
        if not passed:
            # Identify sentences without citations
            for sentence in factual_sentences:
                if not re.search(citation_pattern, sentence):
                    missing_citations.append(sentence.strip()[:100] + "...")
        
        return AttributionResult(
            passed=passed,
            citation_ratio=citation_ratio,
            missing_citations=missing_citations[:5]  # Limit to 5 examples
        )


class QuoteVerifier:
    """Verifier to check quote accuracy against source documents."""
    
    def __init__(self, context: List[Dict[str, Any]]):
        self.context = context
    
    async def verify_quotes(self, answer: str) -> 'QuoteResult':
        """Verify that quotes in the answer match source documents."""
        import re
        
        # Find quoted text patterns
        quote_pattern = r'"([^"]{20,})"'
        quotes = re.findall(quote_pattern, answer)
        
        verified_quotes = []
        unverified_quotes = []
        
        for quote in quotes:
            verified = False
            # Check if quote appears in any context document
            for ctx in self.context:
                content = ctx.get('content', '')
                if quote.lower() in content.lower():
                    verified = True
                    verified_quotes.append(quote)
                    break
            
            if not verified:
                unverified_quotes.append(quote[:100] + "..." if len(quote) > 100 else quote)
        
        return QuoteResult(
            all_verified=len(unverified_quotes) == 0,
            verified_count=len(verified_quotes),
            unverified_quotes=unverified_quotes[:3]  # Limit to 3 examples
        )


# Result classes for gates
class AttributionResult:
    def __init__(self, passed: bool, citation_ratio: float, missing_citations: List[str]):
        self.passed = passed
        self.citation_ratio = citation_ratio
        self.missing_citations = missing_citations


class QuoteResult:
    def __init__(self, all_verified: bool, verified_count: int, unverified_quotes: List[str]):
        self.all_verified = all_verified
        self.verified_count = verified_count
        self.unverified_quotes = unverified_quotes

"""Query Orchestrator using LangGraph for the Gweta agentic system.

This module implements the main orchestrator that routes user queries through
a graph of specialized nodes for intent detection, query processing, retrieval,
and synthesis.

Follows .cursorrules principles: LangChain ecosystem first, explicit state machine,
observability, and robust error handling.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from api.schemas.agent_state import AgentState, update_intent_routing, update_query_processing, update_retrieval_results, update_final_output

logger = structlog.get_logger(__name__)


class QueryOrchestrator:
    """Main orchestrator for agentic query processing using LangGraph."""
    
    def __init__(self):
        """Initialize the orchestrator with a compiled graph."""
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build and compile the LangGraph state machine."""
        
        # Create the state graph
        graph = StateGraph(AgentState)
        
        # Add nodes (renamed to explicit numbered stages)
        graph.add_node("01_intent_classifier", self._route_intent_node)
        graph.add_node("02_query_rewriter", self._rewrite_expand_node)
        graph.add_node("03_retrieval_parallel", self._retrieve_concurrent_node)
        graph.add_node("04_merge_results", self._merge_results_node)
        graph.add_node("05_rerank", self._rerank_node)
        graph.add_node("06_select_topk", self._select_topk_node)
        graph.add_node("07_parent_expansion", self._expand_parents_node)
        graph.add_node("08_synthesis", self._synthesize_stream_node)
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
        
        # Add linear edges for RAG flow
        graph.add_edge("02_query_rewriter", "03_retrieval_parallel")
        graph.add_edge("03_retrieval_parallel", "04_merge_results")
        graph.add_edge("04_merge_results", "05_rerank")
        graph.add_edge("05_rerank", "06_select_topk")
        graph.add_edge("06_select_topk", "07_parent_expansion")
        graph.add_edge("07_parent_expansion", "08_synthesis")
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
        """06_select_topk: Select final top-K after rerank with thresholding."""
        start_time = time.time()
        try:
            candidates = getattr(state, 'reranked_results', [])
            if not candidates:
                # build from ids if necessary
                id_set = set(getattr(state, 'reranked_chunk_ids', [])[:5])
                candidates = [r for r in getattr(state, 'combined_results', []) if r.chunk_id in id_set]
            # Threshold/limit
            K = 5
            top = []
            for r in candidates:
                top.append(r)
                if len(top) >= K:
                    break
            duration_ms = (time.time() - start_time) * 1000
            logger.info("06_select_topk completed",
                        selected=len(top),
                        duration_ms=round(duration_ms, 2))
            return {"topk_results": top}
        except Exception as e:
            logger.error("06_select_topk failed", error=str(e))
            return {"topk_results": getattr(state, 'reranked_results', [])[:5]}

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
    
    async def _route_intent_node(self, state: AgentState) -> Dict[str, Any]:
        """Intent router node - classify user intent and extract context."""
        start_time = time.time()
        
        try:
            logger.info("Starting intent routing", 
                       query_preview=state.raw_query[:50],
                       trace_id=state.trace_id)
            
            # Fast heuristics first
            intent = self._classify_intent_heuristic(state.raw_query)
            jurisdiction = self._detect_jurisdiction(state.raw_query)
            date_context = self._extract_date_context(state.raw_query)
            
            # If heuristics are ambiguous, fall back to mini-LLM
            if intent is None:
                intent = await self._classify_intent_llm(state.raw_query)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("Intent routing completed",
                       intent=intent,
                       jurisdiction=jurisdiction,
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "intent": intent or "rag_qa",  # Default to RAG Q&A
                "intent_confidence": 0.8 if intent else 0.5,
                "jurisdiction": jurisdiction,
                "date_context": date_context
            }
            
        except Exception as e:
            logger.error("Intent routing failed", error=str(e), trace_id=state.trace_id)
            # Fallback to RAG Q&A
            return {"intent": "rag_qa"}
    
    async def _rewrite_expand_node(self, state: AgentState) -> Dict[str, Any]:
        """Rewrite & expand node - rewrite query and generate hypotheticals."""
        start_time = time.time()
        
        try:
            logger.info("Starting query rewrite and expansion", trace_id=state.trace_id)
            
            # History-aware rewrite (placeholder)
            rewritten_query = await self._rewrite_query(state)
            
            # Multi-HyDE generation (placeholder - run in parallel)
            hypothetical_docs = await self._generate_multi_hyde(rewritten_query)
            
            # Optional sub-question decomposition
            sub_questions = await self._decompose_query(rewritten_query)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("Query rewrite and expansion completed",
                       hypotheticals_count=len(hypothetical_docs),
                       sub_questions_count=len(sub_questions),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {
                "rewritten_query": rewritten_query,
                "hypothetical_docs": hypothetical_docs,
                "sub_questions": sub_questions
            }
            
        except Exception as e:
            logger.error("Query rewrite and expansion failed", error=str(e), trace_id=state.trace_id)
            # Fallback to original query
            return {"rewritten_query": state.raw_query}
    
    async def _retrieve_concurrent_node(self, state: AgentState) -> Dict[str, Any]:
        """03_retrieval_parallel: Run BM25 and Milvus in parallel and merge.
        Writes bm25_results, milvus_results, combined_results, retrieval_results.
        """
        start_time = time.time()
        
        try:
            logger.info("03_retrieval_parallel start", trace_id=state.trace_id)
            
            # Use the rewritten query for retrieval
            query = state.rewritten_query or state.raw_query
            
            # Use RetrievalEngine components directly to access both branches
            from api.tools.retrieval_engine import RetrievalEngine
            engine = RetrievalEngine()
            
            # Launch BM25 and Milvus in parallel
            bm25_task = asyncio.create_task(engine.bm25_retriever.aget_relevant_documents(query))
            milvus_task = asyncio.create_task(engine.milvus_retriever.aget_relevant_documents(query))
            bm25_docs, milvus_docs = await asyncio.gather(bm25_task, milvus_task, return_exceptions=False)
            
            # Convert LangChain Documents back to RetrievalResult for downstream compatibility
            bm25_results = [doc.metadata.get("retrieval_result") for doc in bm25_docs if doc.metadata.get("retrieval_result")]
            milvus_results = [doc.metadata.get("retrieval_result") for doc in milvus_docs if doc.metadata.get("retrieval_result")]
            
            # Merge with simple dedupe by chunk_id keeping max score
            combined_map = {}
            for r in (bm25_results + milvus_results):
                key = r.chunk_id
                if key not in combined_map or (getattr(r, 'score', r.confidence) > getattr(combined_map[key], 'score', combined_map[key].confidence)):
                    combined_map[key] = r
            combined_results = list(combined_map.values())
            
            # Candidate IDs for reranking
            candidate_chunk_ids = [r.chunk_id for r in combined_results]
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("03_retrieval_parallel completed",
                       bm25_count=len(bm25_results),
                       milvus_count=len(milvus_results),
                       combined_count=len(combined_results),
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
            return {"candidate_chunk_ids": [], "bm25_results": [], "milvus_results": [], "combined_results": [], "retrieval_results": []}
    
    async def _rerank_node(self, state: AgentState) -> Dict[str, Any]:
        """05_rerank: Rerank combined_results and select reranked_chunk_ids."""
        start_time = time.time()
        
        try:
            logger.info("05_rerank start", 
                       candidates=len(getattr(state, 'combined_results', [])),
                       trace_id=state.trace_id)
            
            retrieval_results = getattr(state, 'combined_results', [])
            if not retrieval_results:
                logger.warning("No combined results available for reranking", trace_id=state.trace_id)
                return {"reranked_chunk_ids": state.candidate_chunk_ids[:12], "reranked_results": []}
            
            # Get query for reranking
            query = state.rewritten_query or state.raw_query
            
            # Lightweight rerank: sort by confidence/score descending and keep top 12
            ranked = sorted(retrieval_results, key=lambda r: getattr(r, 'score', r.confidence), reverse=True)
            reranked_results = ranked[:12]
            reranked_chunk_ids = [r.chunk_id for r in reranked_results]
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("05_rerank completed",
                       reranked_count=len(reranked_chunk_ids),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id)
            
            return {"reranked_chunk_ids": reranked_chunk_ids, "reranked_results": reranked_results}
            
        except Exception as e:
            logger.error("05_rerank failed", error=str(e), trace_id=state.trace_id)
            return {"reranked_chunk_ids": state.candidate_chunk_ids[:12], "reranked_results": []}
    
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
    
    async def _synthesize_stream_node(self, state: AgentState) -> Dict[str, Any]:
        """08_synthesis: Compose final answer and attach citations.
        Keeps existing prompt/gates but writes fields expected by new state.
        """
        start_time = time.time()
        
        try:
            logger.info("Starting synthesis with attribution gates", trace_id=state.trace_id)
            
            # Build structured synthesis prompt
            synthesis_prompt = self._build_synthesis_prompt(state)
            
            # Import synthesis components
            from langchain_openai import ChatOpenAI
            
            # Create streaming LLM
            llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0.1,
                max_tokens=2000,
                streaming=True
            )
            
            # Initialize attribution gates
            attribution_gate = AttributionGate()
            quote_verifier = QuoteVerifier(state.bundled_context)
            
            # Stream synthesis with gates
            final_answer = ""
            first_token_time = None
            
            async for chunk in llm.astream(synthesis_prompt):
                if first_token_time is None:
                    first_token_time = time.time()
                    first_token_ms = (first_token_time - start_time) * 1000
                    logger.info("First token received", 
                               first_token_ms=round(first_token_ms, 2),
                               trace_id=state.trace_id)
                
                if chunk.content:
                    final_answer += chunk.content
            
            # Apply attribution gate
            attribution_result = await attribution_gate.validate_citations(final_answer, state.bundled_context)
            if not attribution_result.passed:
                logger.warning("Attribution gate failed", 
                              missing_citations=attribution_result.missing_citations,
                              trace_id=state.trace_id)
                # Add warning to response
                final_answer += "\n\n⚠️ Some statements may lack proper citations."
            
            # Apply quote verifier
            quote_result = await quote_verifier.verify_quotes(final_answer)
            if not quote_result.all_verified:
                logger.warning("Quote verification failed",
                              unverified_quotes=quote_result.unverified_quotes,
                              trace_id=state.trace_id)
                # Add warning to response
                final_answer += "\n\n⚠️ Some quotes may not be accurately attributed."
            
            # Extract citations from answer
            cited_sources = self._extract_citations(final_answer, state.bundled_context)
            synthesis_prompt_key = f"prompt_{state.trace_id}"
            
            duration_ms = (time.time() - start_time) * 1000
            first_token_ms = (first_token_time - start_time) * 1000 if first_token_time else duration_ms
            
            logger.info("Synthesis completed with gates",
                       answer_length=len(final_answer),
                       citations_count=len(cited_sources),
                       first_token_ms=round(first_token_ms, 2),
                       total_duration_ms=round(duration_ms, 2),
                       attribution_passed=attribution_result.passed,
                       quotes_verified=quote_result.all_verified,
                       trace_id=state.trace_id)
            
            return {
                "final_answer": final_answer,
                "synthesis": {
                    "tldr": final_answer[:220],
                    "citations": cited_sources
                },
                "cited_sources": cited_sources,
                "synthesis_prompt_key": synthesis_prompt_key,
                "attribution_passed": attribution_result.passed,
                "quotes_verified": quote_result.all_verified,
                "first_token_ms": round(first_token_ms, 2)
            }
            
        except Exception as e:
            logger.error("Synthesis failed", error=str(e), trace_id=state.trace_id)
            return {
                "final_answer": "I apologize, but I encountered an error while generating your answer.",
                "cited_sources": [],
                "synthesis_prompt_key": None,
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
    
    def _classify_intent_heuristic(self, query: str) -> Optional[str]:
        """Fast heuristic intent classification."""
        query_lower = query.lower().strip()
        
        # Conversational patterns (use word boundaries to avoid false matches)
        import re
        conversational_patterns = [
            r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bthanks\b", r"\bthank you\b", 
            r"\bbye\b", r"\bgoodbye\b", r"\bhow are you\b", r"\bgood morning\b", 
            r"\bgood afternoon\b", r"\bgood evening\b"
        ]
        if any(re.search(pattern, query_lower) for pattern in conversational_patterns):
            return "conversational"
        
        # Summarization patterns  
        summarize_patterns = [
            "summarize", "summary", "tl;dr", "tldr", "explain differently",
            "what did you say", "what did you just say", "repeat that",
            "can you explain", "break it down", "in simple terms"
        ]
        if any(pattern in query_lower for pattern in summarize_patterns):
            return "summarize"
        
        # Disambiguation patterns
        disambiguate_patterns = [
            "what do you mean", "clarify", "i don't understand", "unclear",
            "what about", "but what if", "however", "on the other hand"
        ]
        if any(pattern in query_lower for pattern in disambiguate_patterns):
            return "disambiguate"
        
        # Legal question patterns - if it contains legal keywords, it's likely RAG Q&A
        legal_keywords = [
            "act", "law", "legal", "statute", "regulation", "chapter", "section",
            "court", "judge", "penalty", "fine", "employment", "labour", "contract",
            "company", "registration", "license", "permit", "rights", "obligations"
        ]
        if any(keyword in query_lower for keyword in legal_keywords):
            return "rag_qa"
        
        # If unclear, let LLM decide
        return None
    
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
    
    async def _rewrite_query(self, state: AgentState) -> str:
        """Rewrite query with conversation context."""
        try:
            from langchain_openai import ChatOpenAI
            from api.composer.prompts import get_prompt_template
            
            # Use mini model for fast rewriting
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.0,
                max_tokens=100,
                timeout=3.0
            )
            
            # Get conversation context (placeholder for now)
            conversation_context = "Previous conversation context would go here"
            user_interests = "User interests from profile would go here"
            
            # Get the rewrite prompt
            prompt = get_prompt_template("query_rewrite")
            
            # Run rewriting
            chain = prompt | llm
            response = await chain.ainvoke({
                "raw_query": state.raw_query,
                "conversation_context": conversation_context,
                "user_interests": user_interests
            })
            
            rewritten = response.content.strip()
            
            # Add jurisdiction and date context if detected
            if state.jurisdiction:
                rewritten += f" [Jurisdiction: {state.jurisdiction}]"
            if state.date_context:
                rewritten += f" [As of: {state.date_context}]"
                
            return rewritten
            
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
        """Run a query through the orchestrator."""
        config = RunnableConfig(
            configurable={"thread_id": state.session_id},
            metadata={"trace_id": state.trace_id}
        )
        
        logger.info("Starting query orchestration", 
                   trace_id=state.trace_id,
                   user_id=state.user_id,
                   query_preview=state.raw_query[:50])
        
        try:
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
            
            return result
            
        except Exception as e:
            logger.error("Query orchestration failed", 
                        error=str(e), 
                        trace_id=state.trace_id)
            raise
    
    def _build_synthesis_prompt(self, state: AgentState) -> str:
        """Build structured synthesis prompt with context and instructions."""
        from api.composer.prompts import SYNTHESIS_SYSTEM_PROMPT
        
        # Build context from bundled documents
        context_sections = []
        for i, ctx in enumerate(state.bundled_context[:8], 1):  # Limit to top 8
            context_sections.append(f"""
Source {i}: {ctx.get('title', 'Unknown Document')}
Confidence: {ctx.get('confidence', 0.0):.2f}
Type: {ctx.get('source_type', 'unknown')}

{ctx.get('content', '')[:1500]}...
""")
        
        context_text = "\n".join(context_sections)
        
        # Build the full prompt
        prompt = f"""{SYNTHESIS_SYSTEM_PROMPT}

QUERY: {state.raw_query}

JURISDICTION: {state.jurisdiction or 'Zimbabwe'}

RETRIEVED CONTEXT:
{context_text}

INSTRUCTIONS:
1. Provide a comprehensive legal analysis based on the retrieved context
2. Cite sources using [Source X] format for each claim
3. Include relevant quotes with proper attribution
4. Structure your response with clear paragraphs
5. If information is insufficient, state limitations clearly

RESPONSE:"""
        
        return prompt
    
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

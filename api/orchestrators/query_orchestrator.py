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
        
        # Add nodes
        graph.add_node("route_intent", self._route_intent_node)
        graph.add_node("rewrite_expand", self._rewrite_expand_node)
        graph.add_node("retrieve_concurrent", self._retrieve_concurrent_node)
        graph.add_node("rerank", self._rerank_node)
        graph.add_node("expand_parents", self._expand_parents_node)
        graph.add_node("synthesize_stream", self._synthesize_stream_node)
        graph.add_node("session_search", self._session_search_node)
        graph.add_node("conversational_tool", self._conversational_tool_node)
        graph.add_node("summarizer_tool", self._summarizer_tool_node)
        
        # Set entry point
        graph.set_entry_point("route_intent")
        
        # Add conditional edges
        graph.add_conditional_edges(
            "route_intent",
            self._decide_route,
            {
                "rag_qa": "rewrite_expand",
                "conversational": "conversational_tool",
                "summarize": "summarizer_tool",
                "disambiguate": "rewrite_expand"
            }
        )
        
        # Add linear edges for RAG flow
        graph.add_edge("rewrite_expand", "retrieve_concurrent")
        graph.add_edge("retrieve_concurrent", "rerank")
        graph.add_edge("rerank", "expand_parents")
        graph.add_edge("expand_parents", "synthesize_stream")
        
        # Terminal edges
        graph.add_edge("conversational_tool", END)
        graph.add_edge("summarizer_tool", END)
        graph.add_edge("synthesize_stream", END)
        
        # Compile with checkpointer
        checkpointer = MemorySaver()
        compiled_graph = graph.compile(checkpointer=checkpointer)
        
        logger.info("LangGraph orchestrator compiled successfully")
        return compiled_graph
    
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
        """Retrieve concurrent node - uses LangChain LCEL retrieval chain."""
        start_time = time.time()
        
        try:
            logger.info("Starting LangChain concurrent retrieval", trace_id=state.trace_id)
            
            # Use the rewritten query for retrieval
            query = state.rewritten_query or state.raw_query
            
            # Import and use the LangChain retrieval engine
            from api.tools.retrieval_engine import RetrievalEngine, RetrievalConfig
            
            # Create retrieval config
            config = RetrievalConfig(
                top_k=20,  # Get top 20 for reranking
                min_score=0.1
            )
            
            # Execute the LangChain LCEL retrieval chain
            async with RetrievalEngine() as engine:
                results = await engine.retrieve(query, config)
            
            # Extract chunk IDs for the next stage
            candidate_chunk_ids = [result.chunk_id for result in results]
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info("LangChain concurrent retrieval completed",
                       candidates_found=len(candidate_chunk_ids),
                       duration_ms=round(duration_ms, 2),
                       trace_id=state.trace_id,
                       top_confidence=results[0].confidence if results else 0)
            
            return {
                "candidate_chunk_ids": candidate_chunk_ids,
                "retrieval_results": results  # Store for reranking
            }
            
        except Exception as e:
            logger.error("LangChain concurrent retrieval failed", error=str(e), trace_id=state.trace_id)
            return {"candidate_chunk_ids": [], "retrieval_results": []}
    
    async def _rerank_node(self, state: AgentState) -> Dict[str, Any]:
        """Rerank node - BGE reranker with caching and 180ms timeout."""
        start_time = time.time()
        
        try:
            logger.info("Starting BGE reranking", 
                       candidates=len(state.candidate_chunk_ids),
                       trace_id=state.trace_id)
            
            # Get retrieval results from previous node
            retrieval_results = getattr(state, 'retrieval_results', [])
            if not retrieval_results:
                logger.warning("No retrieval results available for reranking", trace_id=state.trace_id)
                return {"reranked_chunk_ids": state.candidate_chunk_ids[:12]}
            
            # Import reranker
            from api.tools.reranker import get_reranker, RerankerConfig
            
            # Create reranker config with caching and timeout
            reranker_config = RerankerConfig(
                model_name="BAAI/bge-reranker-base",
                top_k=12,  # Final top-k after reranking
                batch_size=16,
                cache_enabled=True,
                timeout_seconds=0.18  # 180ms timeout
            )
            
            # Get query for reranking
            query = state.rewritten_query or state.raw_query
            
            # Execute reranking with timeout
            try:
                reranker = get_reranker(reranker_config)
                
                # Prepare documents for reranking
                documents = []
                chunk_id_map = {}
                for i, result in enumerate(retrieval_results):
                    documents.append(result.chunk_text or "")
                    chunk_id_map[i] = result.chunk_id
                
                # Rerank with timeout
                import asyncio
                reranked_indices = await asyncio.wait_for(
                    reranker.rerank_async(query, documents, top_k=12),
                    timeout=0.18
                )
                
                # Map back to chunk IDs
                reranked_chunk_ids = [chunk_id_map[idx] for idx in reranked_indices]
                
                duration_ms = (time.time() - start_time) * 1000
                logger.info("BGE reranking completed",
                           reranked_count=len(reranked_chunk_ids),
                           duration_ms=round(duration_ms, 2),
                           trace_id=state.trace_id,
                           cache_hit=reranker.cache_hit_rate if hasattr(reranker, 'cache_hit_rate') else None)
                
                return {"reranked_chunk_ids": reranked_chunk_ids}
                
            except asyncio.TimeoutError:
                logger.warning("Reranking timeout, using original order", 
                              trace_id=state.trace_id,
                              timeout_ms=180)
                return {"reranked_chunk_ids": state.candidate_chunk_ids[:12]}
            
        except Exception as e:
            logger.error("BGE reranking failed", error=str(e), trace_id=state.trace_id)
            # Fallback to original order
            return {"reranked_chunk_ids": state.candidate_chunk_ids[:12]}
    
    async def _expand_parents_node(self, state: AgentState) -> Dict[str, Any]:
        """Expand parents node - fetch parent docs with R2 batching and token caps."""
        start_time = time.time()
        
        try:
            logger.info("Starting parent document expansion", 
                       chunks_to_expand=len(state.reranked_chunk_ids),
                       trace_id=state.trace_id)
            
            # Get retrieval results to access parent document information
            retrieval_results = getattr(state, 'retrieval_results', [])
            if not retrieval_results:
                logger.warning("No retrieval results for parent expansion", trace_id=state.trace_id)
                return {"parent_doc_keys": []}
            
            # Filter to reranked results only (M=8-12 as per task spec)
            reranked_results = []
            reranked_ids_set = set(state.reranked_chunk_ids)
            for result in retrieval_results:
                if result.chunk_id in reranked_ids_set:
                    reranked_results.append(result)
            
            # Cap at 12 parent documents maximum
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
        """Synthesis node - structured prompt with streaming and attribution gates."""
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

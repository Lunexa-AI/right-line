from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, List, Dict, Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.analytics import log_query
from api.auth import User, get_current_user
from api.composer.synthesis import compose_legal_answer
from api.models import (
    Citation,
    FeedbackRequest,
    FeedbackResponse,
    QueryRequest,
    QueryResponse,
)
from api.tools.retrieval_engine import search_legal_documents
from libs.firebase.client import get_firestore_async_client
from libs.firestore.feedback import save_feedback_to_firestore
from api.orchestrators.query_orchestrator import get_orchestrator
from api.schemas.agent_state import create_initial_state
from api.middleware.rate_limiter import query_rate_limiter

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/v1/query", response_model=QueryResponse, tags=["Query"])
async def query_legal_information(
    request: Request,
    query_request: QueryRequest,
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    """Query legal information using RAG (Retrieval-Augmented Generation).
    
    This endpoint uses vector search on legal documents combined with OpenAI 
    for intelligent answer composition. Falls back to hardcoded responses if RAG fails.
    
    Args:
        request: FastAPI request object
        query_request: User query with text and optional parameters
        
    Returns:
        QueryResponse: Legal information response with summary and citations
        
    Raises:
        HTTPException: 400 for invalid input, 429 for rate limits, 500 for errors
        
    Example:
        ```bash
        curl -X POST http://localhost:8000/v1/query \\
          -H "Content-Type: application/json" \\
          -d '{"text": "What is the minimum wage in Zimbabwe?"}'
        ```
    """
    # Rate limiting check
    await query_rate_limiter.check_rate_limit(request)
    
    request_id = getattr(request.state, "request_id", "unknown")
    start_time = time.time()
    
    # Get user identifier (from header or generate session)
    user_id = current_user.uid
    session_id = request.headers.get("x-session-id", None)
    
    logger.info(
        "Processing query",
        request_id=request_id,
        query_text=query_request.text[:100],  # Log first 100 chars only
        lang_hint=query_request.lang_hint,
        channel=query_request.channel,
    )
    
    try:
        # Use LangGraph orchestrator for query processing
        logger.info("Starting LangGraph orchestrator", query=query_request.text[:100])
        
        # Get the orchestrator and create initial state
        orchestrator = get_orchestrator()
        state = create_initial_state(
            user_id=user_id,
            session_id=session_id or f"web-{uuid.uuid4().hex[:8]}",
            raw_query=query_request.text,
        )
        state.request_id = request_id
        
        # Run the orchestrator pipeline
        result_state = await orchestrator.run_query(state)
        
        # Extract the synthesis and results from the orchestrator state
        synthesis_obj = getattr(result_state, "synthesis", {}) or {}
        final_answer = getattr(result_state, "final_answer", None) or synthesis_obj.get("tldr", "")
        
        # Build citations from the synthesis object
        api_citations = []
        for citation in synthesis_obj.get("citations", []):
            api_citations.append(Citation(
                title=citation.get("title", "Legal Document"),
                url=citation.get("url", citation.get("source_url", "")),
                page=citation.get("page"),
                sha=citation.get("sha")
            ))
        
        # Calculate confidence from the orchestrator results
        confidence = synthesis_obj.get("confidence", 0.5)
        if getattr(result_state, "reranked_results", None):
            confidence = max(confidence, 0.7)
        elif getattr(result_state, "combined_results", None):
            confidence = max(confidence, 0.6)
        
        # Build the response using orchestrator outputs
        tldr_text = synthesis_obj.get("tldr", final_answer if final_answer else "No summary available")
        # For production legal system, we use a reasonable 2000 char limit for comprehensive answers
        if len(tldr_text) > 2000:
            tldr_text = tldr_text[:1997] + "..."
        
        response = QueryResponse(
            tldr=tldr_text,
            key_points=synthesis_obj.get("key_points", []),  # Only show actual key points from synthesis
            citations=api_citations,
            suggestions=synthesis_obj.get("suggestions", []),  # Only show actual suggestions from synthesis
            confidence=confidence,
            source=synthesis_obj.get("source", "hybrid"),
            request_id=request_id,
            processing_time_ms=None,  # Will be set below
            full_analysis=final_answer  # Include full IRAC analysis for legal professionals
        )
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        response.processing_time_ms = response_time_ms
        
        # Log query to analytics (Vercel KV)
        try:
            await log_query(
                request_id=request_id,
                user_id=user_id,
                channel=query_request.channel,
                query_text=query_request.text,
                response_topic=response.source if response else None,
                confidence=response.confidence if response else None,
                response_time_ms=response_time_ms,
                status="success" if response else "no_match",
                session_id=session_id,
            )
        except Exception as e:
            # Don't fail the request if analytics logging fails
            logger.warning("Analytics logging failed", error=str(e))
        
        logger.info(
            "Query processed successfully",
            request_id=request_id,
            confidence=response.confidence,
            source=response.source,
            response_time_ms=response_time_ms,
        )
        
        return response
        
    except ValueError as e:
        # Log failed query
        response_time_ms = int((time.time() - start_time) * 1000)
        try:
            await log_query(
                request_id=request_id,
                user_id=user_id,
                channel=query_request.channel,
                query_text=query_request.text,
                response_topic=None,
                confidence=None,
                response_time_ms=response_time_ms,
                status="error",
                session_id=session_id,
            )
        except Exception:
            pass  # Don't fail on analytics errors
        
        logger.warning(
            "Invalid query input",
            request_id=request_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query: {str(e)}",
        )
        
    except Exception as e:
        # Log failed query
        response_time_ms = int((time.time() - start_time) * 1000)
        try:
            await log_query(
                request_id=request_id,
                user_id=user_id,
                channel=query_request.channel,
                query_text=query_request.text,
                response_topic=None,
                confidence=None,
                response_time_ms=response_time_ms,
                status="error",
                session_id=session_id,
            )
        except Exception:
            pass  # Don't fail on analytics errors
        
        logger.error(
            "Query processing failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please try again later.",
        )


@router.get("/v1/query/stream", tags=["Query"])
async def stream_legal_query(
    request: Request,
    query: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream legal information query with real-time updates via SSE.
    
    This endpoint provides real-time streaming of the agentic pipeline:
    1. Query processing and intent classification
    2. Retrieval progress updates
    3. AI synthesis with token streaming
    4. Final response with citations
    
    Args:
        request: FastAPI request object
        query: Legal query text
        current_user: Authenticated user
        
    Returns:
        StreamingResponse: Server-Sent Events stream
        
    Events:
        - meta: Query metadata and processing start
        - retrieval: Document retrieval progress
        - token: AI-generated response tokens
        - citation: Source document citations
        - warning: Quality gate warnings
        - final: Complete response summary
    """
    # Rate limiting check  
    await query_rate_limiter.check_rate_limit(request)
    
    async def generate_sse_stream() -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events for the query processing pipeline."""
        
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Event 1: Meta - Query processing start
            yield f"event: meta\n"
            meta_data = {
                'request_id': request_id,
                'query': query[:100] + '...' if len(query) > 100 else query,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC'),
                'user_id': current_user.uid,
                'status': 'processing'
            }
            yield f"data: {json.dumps(meta_data)}\n\n"
            
            # Event 2: Retrieval - Start document search
            yield f"event: retrieval\n"
            retrieval_data = {
                'status': 'searching',
                'message': 'Searching legal documents...',
                'progress': 0.2
            }
            yield f"data: {json.dumps(retrieval_data)}\n\n"
            
            # Execute retrieval
            retrieval_results, retrieval_confidence = await search_legal_documents(
                query=query,
                top_k=10,
                min_score=0.1
            )
            
            # Event 3: Retrieval - Results found
            yield f"event: retrieval\n"
            retrieval_results_data = {
                'status': 'completed',
                'message': f'Found {len(retrieval_results)} relevant documents',
                'results_count': len(retrieval_results),
                'confidence': retrieval_confidence,
                'progress': 0.5
            }
            yield f"data: {json.dumps(retrieval_results_data)}\n\n"
            
            if not retrieval_results:
                # Event: Warning - No results
                yield f"event: warning\n"
                warning_data = {
                    'type': 'no_results',
                    'message': 'No relevant documents found for this query'
                }
                yield f"data: {json.dumps(warning_data)}\n\n"
                
                # Event: Final - Fallback response
                yield f"event: final\n"
                final_fallback_data = {
                    'request_id': request_id,
                    'tldr': 'No specific legal information found for this query.',
                    'key_points': ['Query may be too specific or outside legal domain'],
                    'citations': [],
                    'confidence': 0.1,
                    'processing_time_ms': int((time.time() - start_time) * 1000)
                }
                yield f"data: {json.dumps(final_fallback_data)}\n\n"
                return
            
            # Event 4: Synthesis - Start AI processing
            yield f"event: meta\n"
            synthesis_start_data = {
                'status': 'synthesizing',
                'message': 'Generating AI legal analysis...',
                'progress': 0.7
            }
            yield f"data: {json.dumps(synthesis_start_data)}\n\n"
            
            # Execute synthesis
            composed_answer = await compose_legal_answer(
                results=retrieval_results,
                query=query,
                confidence=retrieval_confidence,
                lang="en",
                use_openai=True
            )
            
            # Event 5: Token streaming (simulate for now - real implementation would stream from OpenAI)
            tokens = composed_answer.tldr.split()
            for i, token in enumerate(tokens):
                yield f"event: token\n"
                token_data = {
                    'token': token + ' ',
                    'position': i,
                    'total_tokens': len(tokens)
                }
                yield f"data: {json.dumps(token_data)}\n\n"
                
                # Small delay to simulate real streaming
                await asyncio.sleep(0.05)
            
            # Event 6: Citations
            for i, citation in enumerate(composed_answer.citations):
                yield f"event: citation\n"
                citation_data = {
                    'index': i + 1,
                    'title': citation.get('title', 'Legal Document'),
                    'source': citation.get('source_url', ''),
                    'relevance': citation.get('relevance', 0.8)
                }
                yield f"data: {json.dumps(citation_data)}\n\n"
            
            # Event 7: Final - Complete response
            processing_time = int((time.time() - start_time) * 1000)
            yield f"event: final\n"
            final_data = {
                'request_id': request_id,
                'tldr': composed_answer.tldr,
                'key_points': composed_answer.key_points,
                'citations_count': len(composed_answer.citations),
                'confidence': retrieval_confidence,
                'processing_time_ms': processing_time,
                'status': 'completed'
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
            # Log successful query
            try:
                await log_query(
                    request_id=request_id,
                    user_id=current_user.uid,
                    channel="stream",
                    query_text=query,
                    response_topic=composed_answer.tldr[:100],
                    confidence=retrieval_confidence,
                    response_time_ms=processing_time,
                    status="success",
                    session_id=request.headers.get("x-session-id", "unknown"),
                )
            except Exception:
                pass  # Don't fail on analytics errors
            
        except Exception as e:
            logger.error("Streaming query failed", 
                        request_id=request_id, 
                        query=query[:100], 
                        error=str(e))
            
            # Event: Error
            yield f"event: error\n"
            error_data = {
                'request_id': request_id,
                'error': 'Query processing failed',
                'message': 'Please try again later',
                'processing_time_ms': int((time.time() - start_time) * 1000)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


@router.post("/v1/feedback", tags=["Feedback"])
async def submit_feedback(
    feedback: FeedbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """Submit feedback for a query response.
    
    Allows users to rate and comment on the quality of responses.
    
    Args:
        feedback: Feedback data including request_id, rating, and optional comment
        request: FastAPI request object
        
    Returns:
        FeedbackResponse with success status
        
    Example:
        ```bash
        curl -X POST http://localhost:8000/v1/feedback \\
          -H "Content-Type: application/json" \\
          -d '{"request_id": "req_123", "rating": 1, "comment": "Helpful!"}'
        ```
    """
    firestore_client = get_firestore_async_client()
    
    success = await save_feedback_to_firestore(
        client=firestore_client,
        request_id=feedback.request_id,
        user_id=current_user.uid,
        rating=feedback.rating,
        comment=feedback.comment,
    )
    
    return FeedbackResponse(
        success=success,
        message="Feedback saved successfully" if success else "Failed to save feedback"
    )


class TestQueryRequest(BaseModel):
    """Test query request (no auth required)."""
    query: str
    top_k: int = 3


class TestQueryResponse(BaseModel):
    """Test query response with synthesis."""
    query: str
    results: List[Dict[str, Any]]
    performance: Dict[str, Any]
    timestamp: str
    synthesis: Optional[Dict[str, Any]] = None


@router.post("/v1/test-query", response_model=TestQueryResponse, tags=["Query", "Debug"])
async def test_query_endpoint(request: TestQueryRequest) -> TestQueryResponse:
    """Test query endpoint with full agentic pipeline (no authentication required)."""
    
    start_time = time.time()
    
    try:
        # Prefer LangGraph orchestrator for full node-level tracing
        logger.info("Starting LangGraph node-based pipeline test", query=request.query[:100])
        orchestrator = get_orchestrator()
        state = create_initial_state(
            user_id="debug",
            session_id=f"debug-{uuid.uuid4().hex[:8]}",
            raw_query=request.query,
        )
        state.request_id = state.trace_id
        result_state = await orchestrator.run_query(state)
        
        # Choose best available result set for debug output
        result_list = (
            getattr(result_state, "topk_results", None)
            or getattr(result_state, "reranked_results", None)
            or getattr(result_state, "combined_results", None)
            or []
        )
        
        # Format results for debug display
        formatted_results = []
        for r in result_list:
            chunk_text = getattr(r, "chunk_text", "") or (getattr(r, "chunk", None).chunk_text if getattr(r, "chunk", None) else "")
            metadata = getattr(r, "metadata", {}) or {}
            formatted_results.append({
                "score": round(getattr(r, "score", getattr(r, "confidence", 0.0)), 4),
                "source": metadata.get("source", "hybrid"),
                "doc_id": getattr(r, "doc_id", ""),
                "chunk_id": getattr(r, "chunk_id", ""),
                "title": metadata.get("title", "Unknown"),
                "chapter": metadata.get("chapter", "N/A"),
                "tree_node_id": metadata.get("tree_node_id", "N/A"),
                "section_path": metadata.get("section_path", "N/A"),
                "content": (chunk_text[:500] + "...") if len(chunk_text) > 500 else chunk_text,
                "content_length": len(chunk_text)
            })
        
        # Synthesis and confidence from state
        final_answer = getattr(result_state, "final_answer", None) or ""
        retrieval_confidence = 0.0
        if getattr(result_state, "reranked_results", None):
            retrieval_confidence = getattr(result_state.reranked_results[0], "confidence", 0.7)
        elif getattr(result_state, "combined_results", None):
            retrieval_confidence = getattr(result_state.combined_results[0], "confidence", 0.6)
        
        # Build composed-like view from state.synthesis if present
        synthesis_obj = getattr(result_state, "synthesis", None) or {}
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        return TestQueryResponse(
            query=request.query,
            results=formatted_results,
            performance={
                "latency_ms": round(latency_ms, 2),
                "results_count": len(formatted_results),
                "top_score": formatted_results[0]["score"] if formatted_results else 0,
                "under_target": latency_ms < 5000
            },
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            synthesis={
                "tldr": synthesis_obj.get("tldr") or (final_answer[:220] if final_answer else ""),
                "key_points": synthesis_obj.get("key_points", []),
                "citations_count": len(synthesis_obj.get("citations", [])),
                "confidence": retrieval_confidence
            }
        )
            
    except Exception as e:
        logger.error("Test query failed", query=request.query, error=str(e))
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

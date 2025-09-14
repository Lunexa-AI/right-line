from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

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
        # Use RAG system for query processing
        try:
            # Step 1: Retrieve relevant chunks from Milvus
            logger.info("Starting RAG retrieval", query=query_request.text[:100])
            retrieval_results, retrieval_confidence = await search_legal_documents(
                query=query_request.text,
                top_k=10,
                date_filter=query_request.date_ctx,
                min_score=0.1
            )
            
            logger.info(
                "RAG retrieval completed",
                results_count=len(retrieval_results),
                confidence=retrieval_confidence
            )
            
            # Step 2: Compose answer from retrieved chunks
            composed_answer = await compose_legal_answer(
                results=retrieval_results,
                query=query_request.text,
                confidence=retrieval_confidence,
                lang=query_request.lang_hint or "en",
                use_openai=True  # Enable OpenAI enhancement
            )
            
            # Step 3: Convert ComposedAnswer to QueryResponse format
            # Convert citations from retrieval format to API format
            api_citations = []
            for citation in composed_answer.citations:
                api_citations.append(Citation(
                    title=citation.get("title", "Legal Document"),
                    url=citation.get("source_url", ""),
                    page=None,  # Not available in current format
                    sha=None    # Not available in current format
                ))
            
            response = QueryResponse(
                tldr=composed_answer.tldr,
                key_points=composed_answer.key_points,
                citations=api_citations,
                suggestions=composed_answer.suggestions,
                confidence=composed_answer.confidence,
                source=composed_answer.source,
                request_id=request_id,
                processing_time_ms=None  # Will be set below
            )
            
        except Exception as rag_error:
            # Fallback to simple error response if RAG fails
            logger.warning(
                "RAG system failed, using fallback response",
                error=str(rag_error)
            )
            response = QueryResponse(
                tldr="I'm having trouble accessing legal information right now. Please try again later.",
                key_points=[
                    "System temporarily unavailable",
                    "Please try again in a few minutes", 
                    "For urgent matters, contact legal counsel"
                ],
                citations=[],
                suggestions=[
                    "Try asking again",
                    "Contact legal support",
                    "Check system status"
                ],
                confidence=0.1,
                source="fallback",
                request_id=request_id,
                processing_time_ms=None
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

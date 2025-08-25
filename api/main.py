"""Gweta API Service - Serverless FastAPI for Vercel.

This is the main FastAPI application for Gweta's serverless MVP.
Optimized for Vercel functions with Mangum adapter.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles
from mangum import Mangum

from libs.common.settings import get_settings
from api.analytics import (
    get_analytics_summary,
    get_common_queries,
    log_query,
    save_feedback,
)
from api.models import (
    AnalyticsResponse,
    Citation,
    CommonQueriesResponse,
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from api.retrieval import search_legal_documents
from api.composer import compose_legal_answer
from api.whatsapp import (
    WhatsAppWebhookPayload,
    WhatsAppWebhookVerification,
    handle_whatsapp_webhook,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application for serverless deployment."""
    settings = get_settings()
    
    app = FastAPI(
        title="Gweta API",
        description="WhatsApp-first legal copilot for Zimbabwe (Serverless)",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        debug=settings.debug,
        # No lifespan for serverless - connections created per request
    )
    
    # Add CORS middleware - allow all localhost origins for development
    cors_origins = ["*"] if settings.is_development else settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False if settings.is_development else True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all requests with timing and structured data."""
        start_time = time.time()
        request_id = f"req_{int(start_time * 1000000)}"
        
        # Add request ID to context
        request.state.request_id = request_id
        
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            user_agent=request.headers.get("user-agent"),
        )
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            logger.info(
                "Request completed",
                request_id=request_id,
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
                exc_info=True,
            )
            raise
    
    return app


# Create the FastAPI app
app = create_app()

# Mount static files for local development
if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the web interface."""
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")
    else:
        raise HTTPException(status_code=404, detail="Web interface not found")


@app.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint for liveness probes.
    
    Returns:
        HealthResponse: Service health status
        
    Example:
        ```bash
        curl http://localhost:8000/healthz
        ```
    """
    return HealthResponse(
        status="healthy",
        service="api",
        version="0.1.0",
        timestamp=time.time(),
    )


@app.get("/readyz", response_model=HealthResponse, tags=["Health"])
async def readiness_check() -> HealthResponse:
    """Readiness check endpoint for readiness probes.
    
    In MVP phase, this is identical to health check.
    In production, this would check dependencies.
    
    Returns:
        HealthResponse: Service readiness status
        
    Example:
        ```bash
        curl http://localhost:8000/readyz
        ```
    """
    return HealthResponse(
        status="ready",
        service="api",
        version="0.1.0",
        timestamp=time.time(),
    )


@app.post("/api/v1/query", response_model=QueryResponse, tags=["Query"])
async def query_legal_information(
    request: Request,
    query_request: QueryRequest,
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
    user_id = request.headers.get("x-user-id", request.client.host if request.client else "anonymous")
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


@app.post("/v1/feedback", tags=["Feedback"])
async def submit_feedback(
    feedback: FeedbackRequest,
    request: Request,
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
    # Get user identifier
    user_id = request.headers.get("x-user-id", request.client.host if request.client else "anonymous")
    
    success = await save_feedback(
        request_id=feedback.request_id,
        user_id=user_id,
        rating=feedback.rating,
        comment=feedback.comment,
    )
    
    return FeedbackResponse(
        success=success,
        message="Feedback saved successfully" if success else "Failed to save feedback"
    )


@app.get("/v1/analytics", tags=["Analytics"])
async def get_analytics(
    hours: int = 24,
    api_key: str | None = None,
) -> AnalyticsResponse:
    """Get analytics summary.
    
    Returns query statistics for the specified time period.
    Protected endpoint - requires API key in production.
    
    Args:
        hours: Number of hours to look back (default: 24)
        api_key: Optional API key for authentication
        
    Returns:
        Analytics summary with statistics
        
    Example:
        ```bash
        curl http://localhost:8000/v1/analytics?hours=24
        ```
    """
    settings = get_settings()
    
    # Simple API key check for production
    if settings.app_env == "production" and api_key != settings.secret_key[:16]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    summary = await get_analytics_summary(hours=hours)
    
    return AnalyticsResponse(
        total_queries=summary.total_queries,
        unique_users=summary.unique_users,
        avg_response_time_ms=summary.avg_response_time_ms,
        success_rate=summary.success_rate,
        top_topics=summary.top_topics,
        feedback_stats=summary.feedback_stats,
        time_period=summary.time_period
    )


@app.get("/v1/analytics/common-queries", tags=["Analytics"])
async def get_common_unmatched_queries(
    limit: int = 20,
    api_key: str | None = None,
) -> CommonQueriesResponse:
    """Get common unmatched queries.
    
    Returns queries that frequently don't match any hardcoded responses.
    Useful for identifying gaps in coverage.
    
    Args:
        limit: Maximum number of queries to return
        api_key: Optional API key for authentication
        
    Returns:
        List of common unmatched queries with counts
        
    Example:
        ```bash
        curl http://localhost:8000/v1/analytics/common-queries?limit=10
        ```
    """
    settings = get_settings()
    
    # Simple API key check for production
    if settings.app_env == "production" and api_key != settings.secret_key[:16]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    queries = await get_common_queries(limit=limit)
    
    return CommonQueriesResponse(
        queries=queries,
        total=len(queries)
    )


@app.get("/webhook", tags=["WhatsApp"])
async def verify_whatsapp_webhook(
    hub_mode: str = "",
    hub_challenge: str = "",
    hub_verify_token: str = "",
) -> str:
    """WhatsApp webhook verification endpoint.
    
    WhatsApp sends a GET request to verify the webhook URL during setup.
    This endpoint validates the verify token and returns the challenge.
    
    Args:
        hub_mode: Should be "subscribe"
        hub_challenge: Challenge string to return
        hub_verify_token: Token to verify against settings
        
    Returns:
        Challenge string if verification succeeds
        
    Raises:
        HTTPException: 403 if verification fails
        
    Example:
        ```bash
        curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=CHALLENGE"
        ```
    """
    settings = get_settings()
    
    # Check if WhatsApp is configured
    if not settings.whatsapp_verify_token:
        logger.warning("WhatsApp webhook verification attempted but not configured")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WhatsApp webhook not configured",
        )
    
    # Verify the token
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return hub_challenge
    
    logger.warning(
        "WhatsApp webhook verification failed",
        hub_mode=hub_mode,
        token_match=hub_verify_token == settings.whatsapp_verify_token,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification failed",
    )


@app.post("/webhook", tags=["WhatsApp"])
async def receive_whatsapp_webhook(
    request: Request,
    payload: WhatsAppWebhookPayload,
) -> dict[str, str]:
    """WhatsApp webhook endpoint for receiving messages.
    
    This endpoint receives incoming WhatsApp messages and status updates.
    Messages are processed and responses are sent back via the WhatsApp API.
    
    Args:
        request: FastAPI request object (for signature verification)
        payload: WhatsApp webhook payload
        
    Returns:
        Status response
        
    Example webhook payload:
        ```json
        {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "ACCOUNT_ID",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {...},
                        "messages": [{
                            "from": "263771234567",
                            "id": "MESSAGE_ID",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "What is minimum wage?"}
                        }]
                    }
                }]
            }]
        }
        ```
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.info(
        "WhatsApp webhook received",
        request_id=request_id,
        object_type=payload.object,
        entry_count=len(payload.entry),
    )
    
    try:
        # Process the webhook
        result = await handle_whatsapp_webhook(request, payload)
        
        logger.info(
            "WhatsApp webhook processed",
            request_id=request_id,
            result=result,
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "WhatsApp webhook processing failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,
        )
        # Return 200 to prevent WhatsApp from retrying
        # Log the error for investigation
        return {"status": "error_logged"}


# Vercel serverless handler
handler = Mangum(app, lifespan="off")

if __name__ == "__main__":
    import uvicorn
    
    # For local development only
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

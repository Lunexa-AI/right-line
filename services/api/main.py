"""RightLine API Service - Minimal FastAPI MVP.

This is the main FastAPI application for RightLine's MVP phase.
Provides a single /query endpoint with hardcoded legal responses.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, ORJSONResponse
from fastapi.staticfiles import StaticFiles

from libs.common.settings import get_settings
from services.api.models import HealthResponse, QueryRequest, QueryResponse
from services.api.responses import get_hardcoded_response
from services.api.whatsapp import (
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    logger.info("Starting RightLine API", env=settings.app_env, version="0.1.0")
    
    # Startup
    yield
    
    # Shutdown
    logger.info("Shutting down RightLine API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="RightLine API",
        description="WhatsApp-first legal copilot for Zimbabwe",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        debug=settings.debug,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
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

# Mount static files directory (for CSS, JS, images if needed)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse, tags=["Web"])
async def serve_web_interface():
    """Serve the web interface for RightLine.
    
    Returns the main HTML page for the web interface.
    This provides a simple form for testing the legal query API.
    
    Returns:
        HTML file response
    """
    html_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        # Fallback if file doesn't exist
        return HTMLResponse(content="<h1>RightLine API</h1><p>Version 0.1.0</p><p><a href='/docs'>API Documentation</a></p>")


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


@app.post("/v1/query", response_model=QueryResponse, tags=["Query"])
async def query_legal_information(
    request: Request,
    query_request: QueryRequest,
) -> QueryResponse:
    """Query legal information with hardcoded responses.
    
    This MVP endpoint returns hardcoded legal responses based on keyword matching.
    Responses include exact statute sections, 3-line summaries, and citations.
    
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
    
    logger.info(
        "Processing query",
        request_id=request_id,
        query_text=query_request.text[:100],  # Log first 100 chars only
        lang_hint=query_request.lang_hint,
        channel=query_request.channel,
    )
    
    try:
        # Get hardcoded response based on query
        response = get_hardcoded_response(query_request.text, query_request.lang_hint)
        
        logger.info(
            "Query processed successfully",
            request_id=request_id,
            confidence=response.confidence,
            section_ref=f"{response.section_ref.act} §{response.section_ref.section}",
        )
        
        return response
        
    except ValueError as e:
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


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "services.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )

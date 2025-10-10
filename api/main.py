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
from fastapi.responses import ORJSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from libs.common.settings import get_settings
from api.models import HealthResponse
from api.routers import (
    analytics as analytics_router,
    documents as documents_router,
    query as query_router,
    users as users_router,
    waitlist as waitlist_router,
    whatsapp as whatsapp_router,
    debug as debug_router,
)

# Import observability components
try:
    from api.observability.tracing import initialize_observability
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
from libs.firebase.client import initialize_firebase_app

# Vercel Serverless environment requires initialization on startup
initialize_firebase_app()

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
    
    # Initialize observability components
    if OBSERVABILITY_AVAILABLE:
        try:
            observability_components = initialize_observability()
            logger.info(
                "Observability initialized",
                langsmith_enabled=observability_components.get("langsmith_handler") is not None,
                opentelemetry_enabled=observability_components.get("otel_tracer") is not None
            )
        except Exception as e:
            logger.warning("Failed to initialize observability", error=str(e))
    
    app = FastAPI(
        title="RightLine Legal Assistant API",
        description="AI-powered legal assistant for Zimbabwe with LangGraph observability",
        version="1.0.0",
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
    
    # Add request size limiter middleware
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        """Limit request body size to prevent abuse."""
        max_size = 1024 * 1024  # 1MB
        
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > max_size:
                return ORJSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error_code": "REQUEST_TOO_LARGE",
                        "message": f"Request body too large. Maximum size: {max_size} bytes"
                    }
                )
        
        return await call_next(request)
    
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

# Include API routers
app.include_router(query_router.router, prefix="/api", tags=["Legal Query"])
app.include_router(users_router.router, prefix="/api", tags=["Users"])
app.include_router(documents_router.router, prefix="/api", tags=["Documents"])  # Task 2.5: Secure document serving
app.include_router(waitlist_router.router, prefix="/api", tags=["Waitlist"])
app.include_router(analytics_router.router, prefix="/api", tags=["Analytics"])
app.include_router(whatsapp_router.router, prefix="/api", tags=["WhatsApp"])

# Debug endpoints (development only)
if get_settings().is_development:
    app.include_router(debug_router.router, prefix="/api/v1/debug", tags=["Debug"])
    
    @app.get("/debug", include_in_schema=False)
    async def debug_frontend():
        """Serve debug frontend for API testing."""
        import os
        debug_html = os.path.join(os.path.dirname(__file__), "..", "debug_simple.html")
        if os.path.exists(debug_html):
            return FileResponse(debug_html)
        return {"message": "Debug HTML not found"}
else:
    logger.info("Debug endpoints disabled in production")


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint to confirm the API is running."""
    return {"message": "Gweta API is running."}


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


# Vercel serverless handler is no longer needed
# handler = Mangum(app, lifespan="off")

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

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
from api.models import HealthResponse
from api.routers import analytics, query, whatsapp

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
if os.path.exists("public"):
    app.mount("/static", StaticFiles(directory="public"), name="static")

app.include_router(query.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(whatsapp.router)


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the web interface."""
    if os.path.exists("public/index.html"):
        return FileResponse("public/index.html")
    else:
        raise HTTPException(status_code=404, detail="Web interface not found")


# Favicon and icon routes
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    """Serve favicon.ico - use geometric G design, prioritize larger icons."""
    # Prioritize larger icons for better visibility in browser tabs
    if os.path.exists("public/icon-192.png"):
        response = FileResponse("public/icon-192.png", media_type="image/png")
        # Add cache-busting headers for dynamic favicon updates
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    elif os.path.exists("public/apple-touch-icon.png"):
        response = FileResponse("public/apple-touch-icon.png", media_type="image/png")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    elif os.path.exists("public/favicon-32x32.png"):
        response = FileResponse("public/favicon-32x32.png", media_type="image/png")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    elif os.path.exists("public/favicon.ico"):
        response = FileResponse("public/favicon.ico", media_type="image/x-icon")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon_svg():
    """Serve favicon.svg - fallback to 32x32 PNG if SVG doesn't exist."""
    if os.path.exists("public/favicon.svg"):
        return FileResponse("public/favicon.svg", media_type="image/svg+xml")
    elif os.path.exists("public/favicon-32x32.png"):
        return FileResponse("public/favicon-32x32.png", media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon SVG not found")


@app.get("/favicon-16x16.png", include_in_schema=False)
async def favicon_16():
    """Serve 16x16 favicon."""
    if os.path.exists("public/favicon-16x16.png"):
        return FileResponse("public/favicon-16x16.png", media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon 16x16 not found")


@app.get("/favicon-32x32.png", include_in_schema=False)
async def favicon_32():
    """Serve 32x32 favicon."""
    if os.path.exists("public/favicon-32x32.png"):
        return FileResponse("public/favicon-32x32.png", media_type="image/png")
    raise HTTPException(status_code=404, detail="Favicon 32x32 not found")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    """Serve Apple touch icon."""
    if os.path.exists("public/apple-touch-icon.png"):
        return FileResponse("public/apple-touch-icon.png", media_type="image/png")
    raise HTTPException(status_code=404, detail="Apple touch icon not found")


@app.get("/icon-192.png", include_in_schema=False)
async def icon_192():
    """Serve 192x192 icon."""
    if os.path.exists("public/icon-192.png"):
        response = FileResponse("public/icon-192.png", media_type="image/png")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    raise HTTPException(status_code=404, detail="Icon 192x192 not found")


@app.get("/icon-512.png", include_in_schema=False)
async def icon_512():
    """Serve 512x512 icon."""
    if os.path.exists("public/icon-512.png"):
        return FileResponse("public/icon-512.png", media_type="image/png")
    raise HTTPException(status_code=404, detail="Icon 512x512 not found")


@app.get("/site.webmanifest", include_in_schema=False)
async def web_manifest():
    """Serve web app manifest."""
    if os.path.exists("public/site.webmanifest"):
        return FileResponse("public/site.webmanifest", media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Web manifest not found")


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

"""Waitlist router for handling pre-launch email signups."""

from __future__ import annotations

import time
from typing import Dict, Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from api.models import WaitlistRequest, WaitlistResponse
from libs.firebase.client import get_firestore_async_client
from libs.firestore.waitlist import add_to_waitlist, get_waitlist_stats

logger = structlog.get_logger(__name__)
router = APIRouter()

# Rate limiting configuration (for future Redis implementation)
RATE_LIMIT_CONFIG = {
    "max_requests_per_hour": 5,
    "max_requests_per_minute": 2,
    "honeypot_ban_duration": 3600,  # 1 hour ban for honeypot violations
}

# In-memory rate limiting (temporary - replace with Redis in production)
_rate_limit_store: Dict[str, Dict[str, Any]] = {}
_honeypot_bans: Dict[str, float] = {}


@router.post(
    "/v1/waitlist",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Waitlist"],
    summary="Join the waitlist",
    description="Add an email address to the pre-launch waitlist. No authentication required.",
)
async def join_waitlist(
    request: Request,
    waitlist_request: WaitlistRequest,
) -> WaitlistResponse:
    """Add an email to the pre-launch waitlist.
    
    This endpoint allows users to sign up for the waitlist without authentication.
    It handles duplicate emails gracefully (idempotent behavior) and tracks the
    source of signups for analytics.
    
    The endpoint collects basic metadata (IP address, User-Agent) for analytics
    and rate limiting purposes but doesn't require user identification.
    
    Args:
        request: FastAPI request object (for IP/headers collection)
        waitlist_request: The waitlist signup request with email and optional source
        
    Returns:
        WaitlistResponse with success status, message, and duplicate flag
        
    Raises:
        HTTPException: 
            - 422 if email validation fails
            - 500 if database operation fails
            
    Examples:
        ```bash
        curl -X POST http://localhost:8000/api/v1/waitlist \\
          -H "Content-Type: application/json" \\
          -d '{"email": "user@example.com", "source": "web"}'
        ```
        
        Response for new signup:
        ```json
        {
          "success": true,
          "message": "Successfully added to waitlist!",
          "already_subscribed": false,
          "waitlist_id": "550e8400-e29b-41d4-a716-446655440000"
        }
        ```
        
        Response for duplicate email:
        ```json
        {
          "success": true,
          "message": "You're already on the waitlist!",
          "already_subscribed": true,
          "waitlist_id": null
        }
        ```
    """
    # Extract metadata for analytics and rate limiting
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    request_size = int(request.headers.get("content-length", 0))
    
    # Security validations
    await _validate_request_security(client_ip, request_size, user_agent)
    
    # Prepare metadata for storage
    metadata = {
        "ip_address": client_ip,
        "user_agent": user_agent[:200] if user_agent else "",  # Limit length
        "request_size": str(request_size),
        "timestamp": str(int(time.time())),
    }
    
    logger.info(
        "Processing waitlist signup request",
        email=waitlist_request.email,
        source=waitlist_request.source,
        ip_address=client_ip,
        user_agent_length=len(user_agent),
        request_size=request_size,
    )
    
    try:
        # Get Firestore client
        firestore_client = get_firestore_async_client()
        
        # Attempt to add to waitlist (idempotent operation)
        created, waitlist_entry = await add_to_waitlist(
            client=firestore_client,
            email=waitlist_request.email,
            source=waitlist_request.source,
            metadata=metadata,
        )
        
        if created:
            # New signup - KEY ANALYTICS EVENT
            logger.info(
                "🎯 WAITLIST_SIGNUP_SUCCESS",
                event_type="waitlist_signup",
                email=waitlist_request.email,
                source=waitlist_request.source,
                waitlist_id=waitlist_entry.waitlist_id,
                ip_address=client_ip,
                user_agent=user_agent[:50] if user_agent else "unknown",
                timestamp=metadata.get("timestamp"),
                analytics_priority="HIGH"  # For easy filtering
            )
            
            return WaitlistResponse(
                success=True,
                message="Successfully added to waitlist!",
                already_subscribed=False,
                waitlist_id=waitlist_entry.waitlist_id,
            )
        else:
            # Duplicate email - IMPORTANT FOR CONVERSION METRICS
            logger.info(
                "🔄 WAITLIST_DUPLICATE_ATTEMPT",
                event_type="waitlist_duplicate",
                email=waitlist_request.email,
                source=waitlist_request.source,
                existing_waitlist_id=waitlist_entry.waitlist_id,
                ip_address=client_ip,
                user_agent=user_agent[:50] if user_agent else "unknown",
                analytics_priority="MEDIUM"  # Track interest level
            )
            
            return WaitlistResponse(
                success=True,
                message="You're already on the waitlist!",
                already_subscribed=True,
                waitlist_id=None,  # Don't expose existing ID for privacy
            )
            
    except ValidationError as e:
        # Check if this is a honeypot violation
        if "Bot detected" in str(e):
            await _handle_bot_detection(client_ip, waitlist_request.email or "unknown")
            # CRITICAL: Bot detection for security metrics
            logger.warning(
                "🤖 WAITLIST_BOT_DETECTED",
                event_type="security_bot_detected",
                email=getattr(waitlist_request, 'email', 'unknown'),
                ip_address=client_ip,
                user_agent=user_agent[:50] if user_agent else "unknown",
                error_detail=str(e),
                security_priority="HIGH"
            )
        else:
            # Regular validation errors - track for UX improvements
            logger.warning(
                "⚠️ WAITLIST_VALIDATION_ERROR",
                event_type="validation_error",
                email=getattr(waitlist_request, 'email', 'unknown'),
                error=str(e),
                ip_address=client_ip,
                user_agent=user_agent[:50] if user_agent else "unknown",
                analytics_priority="LOW"
            )
        
        # Don't expose specific validation details to potential bots
        if "Bot detected" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request",
            )
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid input provided",
        )
        
    except RuntimeError as e:
        # Firestore operation failed - CRITICAL ERROR for monitoring
        logger.error(
            "🚨 WAITLIST_DATABASE_ERROR",
            event_type="database_error",
            email=waitlist_request.email,
            source=waitlist_request.source,
            error=str(e),
            ip_address=client_ip,
            user_agent=user_agent[:50] if user_agent else "unknown",
            error_priority="CRITICAL",  # Requires immediate attention
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,  # More appropriate for DB issues
            detail="Service temporarily unavailable. Please try again in a moment.",
        )
        
    except Exception as e:
        # Unexpected error - CRITICAL for debugging
        logger.error(
            "💥 WAITLIST_UNEXPECTED_ERROR",
            event_type="unexpected_error",
            email=waitlist_request.email,
            source=waitlist_request.source,
            error=str(e),
            error_type=type(e).__name__,
            ip_address=client_ip,
            user_agent=user_agent[:50] if user_agent else "unknown",
            error_priority="CRITICAL",
            request_metadata=metadata,
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
        )


async def _validate_request_security(
    client_ip: str, request_size: int, user_agent: str
) -> None:
    """Validate request for security concerns and apply rate limiting.
    
    Args:
        client_ip: Client IP address
        request_size: Size of request in bytes
        user_agent: User agent string
        
    Raises:
        HTTPException: If request violates security policies
    """
    # Check if IP is banned for honeypot violations
    if client_ip in _honeypot_bans:
        ban_time = _honeypot_bans[client_ip]
        if time.time() < ban_time:
            logger.warning(
                "Blocked request from banned IP",
                ip_address=client_ip,
                ban_expires_at=ban_time,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        else:
            # Ban expired, remove from store
            del _honeypot_bans[client_ip]
    
    # Request size validation (FastAPI handles most of this, but add explicit check)
    MAX_REQUEST_SIZE = 1024  # 1KB should be more than enough for email + source
    if request_size > MAX_REQUEST_SIZE:
        logger.warning(
            "Request too large",
            ip_address=client_ip,
            request_size=request_size,
            max_size=MAX_REQUEST_SIZE,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request too large",
        )
    
    # Basic rate limiting (in-memory for now - replace with Redis)
    await _check_rate_limits(client_ip)
    
    # User agent validation (basic bot detection)
    if not user_agent or len(user_agent) < 10:
        logger.info(
            "Suspicious user agent",
            ip_address=client_ip,
            user_agent=user_agent,
        )
        # Don't block entirely, but log for monitoring


async def _check_rate_limits(client_ip: str) -> None:
    """Check rate limits for the given IP address.
    
    Simple in-memory implementation - replace with Redis for production.
    
    Args:
        client_ip: Client IP address
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    current_time = time.time()
    
    # Initialize tracking for new IPs
    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = {
            "minute_requests": [],
            "hour_requests": [],
        }
    
    ip_data = _rate_limit_store[client_ip]
    
    # Clean old entries (older than 1 hour)
    ip_data["minute_requests"] = [
        req_time for req_time in ip_data["minute_requests"] 
        if current_time - req_time < 60
    ]
    ip_data["hour_requests"] = [
        req_time for req_time in ip_data["hour_requests"] 
        if current_time - req_time < 3600
    ]
    
    # Check minute limit
    if len(ip_data["minute_requests"]) >= RATE_LIMIT_CONFIG["max_requests_per_minute"]:
        # RATE LIMITING - Important for abuse monitoring
        logger.warning(
            "🚦 RATE_LIMIT_EXCEEDED_MINUTE",
            event_type="rate_limit_minute",
            ip_address=client_ip,
            requests_in_minute=len(ip_data["minute_requests"]),
            limit=RATE_LIMIT_CONFIG["max_requests_per_minute"],
            security_priority="MEDIUM"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment before trying again.",
        )
    
    # Check hour limit  
    if len(ip_data["hour_requests"]) >= RATE_LIMIT_CONFIG["max_requests_per_hour"]:
        # HOURLY RATE LIMITING - Track persistent abuse
        logger.warning(
            "🚦 RATE_LIMIT_EXCEEDED_HOUR", 
            event_type="rate_limit_hour",
            ip_address=client_ip,
            requests_in_hour=len(ip_data["hour_requests"]),
            limit=RATE_LIMIT_CONFIG["max_requests_per_hour"],
            security_priority="HIGH"  # Persistent abuse
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )
    
    # Record current request
    ip_data["minute_requests"].append(current_time)
    ip_data["hour_requests"].append(current_time)


async def _handle_bot_detection(client_ip: str, email: str) -> None:
    """Handle detected bot activity (honeypot violation).
    
    Args:
        client_ip: IP address of the potential bot
        email: Email address used in the request
    """
    # Add IP to temporary ban list
    ban_until = time.time() + RATE_LIMIT_CONFIG["honeypot_ban_duration"]
    _honeypot_bans[client_ip] = ban_until
    
    # SECURITY LOG - High priority for monitoring
    logger.warning(
        "🔒 SECURITY_BOT_BANNED",
        event_type="security_ban",
        ip_address=client_ip,
        email=email,
        ban_duration_seconds=RATE_LIMIT_CONFIG["honeypot_ban_duration"],
        ban_until=ban_until,
        security_action="IP_BANNED",
        security_priority="HIGH"
    )


def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request headers.
    
    Handles various proxy configurations and header formats commonly used
    in production deployments (Cloudflare, nginx, AWS ALB, etc.).
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Client IP address as string, defaults to "unknown" if not found
    """
    # Check common proxy headers in order of preference
    forwarded_ips = (
        request.headers.get("cf-connecting-ip") or  # Cloudflare
        request.headers.get("x-forwarded-for") or  # Standard proxy header
        request.headers.get("x-real-ip") or        # nginx proxy
        request.headers.get("forwarded") or        # RFC 7239
        ""
    )
    
    if forwarded_ips:
        # X-Forwarded-For can contain multiple IPs, take the first (original client)
        client_ip = forwarded_ips.split(",")[0].strip()
        if client_ip:
            return client_ip
    
    # Fallback to direct connection IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


@router.get(
    "/v1/admin/waitlist/stats",
    tags=["Admin", "Waitlist"],
    summary="Get waitlist statistics (Admin only)",
    description="Retrieve waitlist analytics and statistics. Future: Requires admin authentication.",
)
async def get_waitlist_statistics():
    """Get basic waitlist statistics for admin monitoring.
    
    This is a simple endpoint for tracking waitlist metrics during the pre-launch phase.
    In the future, this should be protected with admin authentication.
    
    Returns:
        Dict with waitlist statistics including total count and recent entries
        
    Example Response:
        {
            "total_count": 1247,
            "recent_entries": [...],
            "sources_breakdown": {"web": 980, "social": 267},
            "latest_signup": "2024-01-15T10:30:00Z"
        }
    """
    try:
        # Get Firestore client
        firestore_client = get_firestore_async_client()
        
        # Get waitlist statistics
        stats = await get_waitlist_stats(firestore_client, limit=5)
        
        # Log admin access for security
        logger.info(
            "📊 ADMIN_WAITLIST_STATS_ACCESSED",
            event_type="admin_stats_access",
            total_count=stats.get("total_count", 0),
            sources_count=len(stats.get("sources_breakdown", {})),
            security_priority="MEDIUM"
        )
        
        return stats
        
    except Exception as e:
        logger.error(
            "🚨 ADMIN_STATS_ERROR",
            event_type="admin_error",
            error=str(e),
            error_type=type(e).__name__,
            error_priority="HIGH",
            exc_info=True
        )
        
        # Return basic error response for admin endpoint
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve waitlist statistics"
        )

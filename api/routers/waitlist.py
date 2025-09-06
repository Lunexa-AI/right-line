"""Waitlist router for handling pre-launch email signups."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from api.models import WaitlistRequest, WaitlistResponse
from libs.firebase.client import get_firestore_async_client
from libs.firestore.waitlist import add_to_waitlist

logger = structlog.get_logger(__name__)
router = APIRouter()


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
    
    # Prepare metadata for storage
    metadata = {
        "ip_address": client_ip,
        "user_agent": user_agent[:200] if user_agent else "",  # Limit length
    }
    
    logger.info(
        "Processing waitlist signup request",
        email=waitlist_request.email,
        source=waitlist_request.source,
        ip_address=client_ip,
        user_agent_length=len(user_agent),
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
            # New signup
            logger.info(
                "Successfully added new email to waitlist",
                email=waitlist_request.email,
                source=waitlist_request.source,
                waitlist_id=waitlist_entry.waitlist_id,
                ip_address=client_ip,
            )
            
            return WaitlistResponse(
                success=True,
                message="Successfully added to waitlist!",
                already_subscribed=False,
                waitlist_id=waitlist_entry.waitlist_id,
            )
        else:
            # Duplicate email (idempotent behavior)
            logger.info(
                "Attempted to add existing email to waitlist",
                email=waitlist_request.email,
                source=waitlist_request.source,
                existing_waitlist_id=waitlist_entry.waitlist_id,
                ip_address=client_ip,
            )
            
            return WaitlistResponse(
                success=True,
                message="You're already on the waitlist!",
                already_subscribed=True,
                waitlist_id=None,  # Don't expose existing ID for privacy
            )
            
    except ValidationError as e:
        # This shouldn't happen due to Pydantic validation, but just in case
        logger.warning(
            "Waitlist signup validation error",
            email=waitlist_request.email,
            error=str(e),
            ip_address=client_ip,
        )
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Validation error: {str(e)}",
        )
        
    except RuntimeError as e:
        # Firestore operation failed
        logger.error(
            "Failed to process waitlist signup",
            email=waitlist_request.email,
            source=waitlist_request.source,
            error=str(e),
            ip_address=client_ip,
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process waitlist signup. Please try again later.",
        )
        
    except Exception as e:
        # Unexpected error
        logger.error(
            "Unexpected error during waitlist signup",
            email=waitlist_request.email,
            source=waitlist_request.source,
            error=str(e),
            error_type=type(e).__name__,
            ip_address=client_ip,
            exc_info=True,
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
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

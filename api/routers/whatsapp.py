from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from libs.common.settings import get_settings
from api.whatsapp import (
    WhatsAppWebhookPayload,
    handle_whatsapp_webhook,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/webhook", tags=["WhatsApp"])
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


@router.post("/webhook", tags=["WhatsApp"])
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

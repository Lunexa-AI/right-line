"""WhatsApp Business API integration for RightLine.

This module handles WhatsApp webhook verification and message processing.
Follows Meta's WhatsApp Business API specifications.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from libs.common.settings import get_settings
from services.api.models import QueryRequest, QueryResponse
from services.api.responses import get_hardcoded_response

logger = structlog.get_logger(__name__)


# WhatsApp webhook models
class WhatsAppWebhookVerification(BaseModel):
    """WhatsApp webhook verification request model."""
    
    hub_mode: str = Field(alias="hub.mode")
    hub_challenge: str = Field(alias="hub.challenge")
    hub_verify_token: str = Field(alias="hub.verify_token")


class WhatsAppMessage(BaseModel):
    """WhatsApp incoming message model."""
    
    model_config = {"populate_by_name": True}
    
    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: dict[str, str] | None = None


class WhatsAppValue(BaseModel):
    """WhatsApp webhook value model."""
    
    messaging_product: str
    metadata: dict[str, str]
    contacts: list[dict[str, Any]] | None = None
    messages: list[WhatsAppMessage] | None = None
    statuses: list[dict[str, Any]] | None = None


class WhatsAppChange(BaseModel):
    """WhatsApp webhook change model."""
    
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    """WhatsApp webhook entry model."""
    
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """WhatsApp webhook payload model."""
    
    object: str
    entry: list[WhatsAppEntry]


# WhatsApp message formatting
def format_whatsapp_response(response: QueryResponse) -> str:
    """Format QueryResponse for WhatsApp message.
    
    WhatsApp has specific formatting requirements:
    - Bold: *text*
    - Italic: _text_
    - Strikethrough: ~text~
    - Monospace: ```text```
    - Maximum message length: 4096 characters
    
    Args:
        response: Query response to format
        
    Returns:
        Formatted WhatsApp message string
    """
    # Format the summary with quotes
    summary = f"❝ {response.summary_3_lines} ❞"
    
    # Format section reference
    section = f"\n\n📄 *{response.section_ref.act}* [Chapter {response.section_ref.chapter}] §{response.section_ref.section}"
    
    # Format citations as links (WhatsApp will make them clickable)
    citations = "\n🔗 "
    if response.citations:
        citation_links = []
        for cite in response.citations[:2]:  # Limit to 2 citations for brevity
            # Shorten the URL for WhatsApp display
            citation_links.append(cite.url.replace("https://", ""))
        citations += " | ".join(citation_links)
    
    # Add confidence indicator
    confidence_emoji = "✅" if response.confidence > 0.7 else "⚠️" if response.confidence > 0.4 else "❓"
    confidence_text = f"\n\n{confidence_emoji} Confidence: {response.confidence:.0%}"
    
    # Add related sections if available
    related = ""
    if response.related_sections:
        related = f"\n\n📚 Related: §" + ", §".join(response.related_sections[:3])
    
    # Combine all parts
    message = summary + section + citations + confidence_text + related
    
    # Add footer
    footer = "\n\n_Reply 'HELP' for assistance or 'MORE' for related info_"
    
    # Ensure message doesn't exceed WhatsApp limit
    full_message = message + footer
    if len(full_message) > 4000:  # Leave some buffer
        # Truncate summary if needed
        truncated_summary = response.summary_3_lines.split('\n')[0] + "..."
        message = f"❝ {truncated_summary} ❞" + section + citations + confidence_text
        full_message = message + footer
    
    return full_message


def verify_webhook_signature(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify WhatsApp webhook signature.
    
    Args:
        request_body: Raw request body
        signature: Signature from X-Hub-Signature-256 header
        secret: Webhook secret from settings
        
    Returns:
        True if signature is valid
    """
    if not signature or not signature.startswith("sha256="):
        return False
    
    expected_signature = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    provided_signature = signature.replace("sha256=", "")
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, provided_signature)


async def send_whatsapp_message(
    phone_number: str,
    message: str,
    phone_id: str | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Send a message via WhatsApp Business API.
    
    Args:
        phone_number: Recipient phone number (with country code)
        message: Message text to send
        phone_id: WhatsApp Business phone number ID
        access_token: WhatsApp Business API access token
        
    Returns:
        API response dictionary
        
    Raises:
        HTTPException: If sending fails
    """
    settings = get_settings()
    phone_id = phone_id or settings.whatsapp_phone_id
    access_token = access_token or settings.whatsapp_token
    
    if not phone_id or not access_token:
        logger.error("WhatsApp credentials not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp service not configured",
        )
    
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {
            "preview_url": True,  # Enable URL previews
            "body": message,
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                "WhatsApp message sent",
                phone_number=phone_number[:6] + "****",  # Log partial number for privacy
                message_id=result.get("messages", [{}])[0].get("id"),
            )
            return result
            
    except httpx.HTTPStatusError as e:
        logger.error(
            "WhatsApp API error",
            status_code=e.response.status_code,
            error=e.response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send WhatsApp message",
        )
    except Exception as e:
        logger.error("WhatsApp send error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error sending message",
        )


async def process_whatsapp_message(message: WhatsAppMessage, from_number: str) -> str:
    """Process incoming WhatsApp message and generate response.
    
    Args:
        message: WhatsApp message object
        from_number: Sender's phone number
        
    Returns:
        Response message text
    """
    # Only process text messages for now
    if message.type != "text" or not message.text:
        return "I can only process text messages. Please send your legal question as text."
    
    message_text = message.text.get("body", "").strip()
    
    # Handle special commands
    if message_text.upper() == "HELP":
        return (
            "🤖 *RightLine Legal Assistant*\n\n"
            "I can help you with Zimbabwe labour law questions.\n\n"
            "*How to use:*\n"
            "• Send any legal question in plain language\n"
            "• I'll provide the relevant law section and summary\n"
            "• All responses include official citations\n\n"
            "*Example questions:*\n"
            "• What is the minimum wage?\n"
            "• How much leave am I entitled to?\n"
            "• Can my employer fire me without notice?\n\n"
            "_⚠️ This is legal information, not legal advice._"
        )
    
    if message_text.upper() == "MORE":
        return (
            "📚 *Popular Topics:*\n\n"
            "• Minimum wage and salary\n"
            "• Working hours and overtime\n"
            "• Annual and sick leave\n"
            "• Maternity leave\n"
            "• Termination and resignation\n"
            "• Workplace safety\n"
            "• Discrimination and harassment\n"
            "• NSSA and pension\n\n"
            "Send your question about any of these topics!"
        )
    
    # Process as legal query
    try:
        # Get response from hardcoded responses
        query_response = get_hardcoded_response(message_text, lang_hint="en")
        
        # Format for WhatsApp
        formatted_response = format_whatsapp_response(query_response)
        
        logger.info(
            "WhatsApp query processed",
            from_number=from_number[:6] + "****",
            query_length=len(message_text),
            confidence=query_response.confidence,
        )
        
        return formatted_response
        
    except Exception as e:
        logger.error(
            "Error processing WhatsApp query",
            error=str(e),
            from_number=from_number[:6] + "****",
        )
        return (
            "❌ Sorry, I couldn't process your question.\n\n"
            "Please try rephrasing or send 'HELP' for assistance."
        )


async def handle_whatsapp_webhook(request: Request, payload: WhatsAppWebhookPayload) -> dict[str, str]:
    """Handle incoming WhatsApp webhook.
    
    Args:
        request: FastAPI request object
        payload: Parsed webhook payload
        
    Returns:
        Response dictionary
    """
    settings = get_settings()
    
    # Verify webhook signature if configured
    if settings.whatsapp_verify_token:
        signature = request.headers.get("X-Hub-Signature-256", "")
        body = await request.body()
        
        if not verify_webhook_signature(body, signature, settings.whatsapp_verify_token):
            logger.warning("Invalid WhatsApp webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )
    
    # Process each entry
    for entry in payload.entry:
        for change in entry.changes:
            # Only process message events
            if change.field != "messages":
                continue
                
            value = change.value
            
            # Process each message
            if value.messages:
                for message in value.messages:
                    # Get sender info
                    from_number = message.from_
                    
                    # Process message and get response
                    response_text = await process_whatsapp_message(message, from_number)
                    
                    # Send response back
                    try:
                        await send_whatsapp_message(from_number, response_text)
                    except Exception as e:
                        logger.error(
                            "Failed to send WhatsApp response",
                            error=str(e),
                            to_number=from_number[:6] + "****",
                        )
    
    return {"status": "ok"}

"""WhatsApp Business API integration for Gweta.

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
from api.models import QueryRequest, QueryResponse
from api.retrieval import search_legal_documents
from api.composer import compose_legal_answer

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
    """Format QueryResponse for WhatsApp message with improved UX.
    
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
    message_parts = []
    
    # Header with act and section
    message_parts.append(f"📖 *{response.section_ref.act}*")
    message_parts.append(f"_Section {response.section_ref.section} • Chapter {response.section_ref.chapter}_")
    message_parts.append("")
    
    # Summary with better formatting
    message_parts.append("━━━━━━━━━━━━━━━")
    summary_lines = response.summary_3_lines.split('\n')
    for line in summary_lines:
        if line.strip():
            message_parts.append(f"▫️ {line.strip()}")
    message_parts.append("━━━━━━━━━━━━━━━")
    message_parts.append("")
    
    # Confidence with visual indicator
    conf_pct = int(response.confidence * 100)
    if conf_pct >= 90:
        conf_visual = "🟢🟢🟢🟢🟢"
        conf_text = "Very High"
    elif conf_pct >= 80:
        conf_visual = "🟢🟢🟢🟢⚪"
        conf_text = "High"
    elif conf_pct >= 70:
        conf_visual = "🟡🟡🟡⚪⚪"
        conf_text = "Moderate"
    else:
        conf_visual = "🟡🟡⚪⚪⚪"
        conf_text = "Low"
    
    message_parts.append(f"*Confidence:* {conf_text}")
    message_parts.append(f"{conf_visual} ({conf_pct}%)")
    
    # Citations if available
    if response.citations:
        message_parts.append("")
        message_parts.append("📚 *Learn More:*")
        for i, cite in enumerate(response.citations[:2], 1):
            # Truncate long titles
            title = cite.title[:40] + "..." if len(cite.title) > 40 else cite.title
            message_parts.append(f"{i}. {title}")
    
    # Related topics with better names
    if response.related_sections:
        message_parts.append("")
        message_parts.append("💡 *Related Topics:*")
        
        # Map technical names to user-friendly names
        topic_names = {
            "minimum_wage": "💰 Minimum Wage",
            "working_hours": "⏰ Working Hours",
            "leave_entitlement": "🏖️ Leave",
            "termination": "🚪 Termination",
            "maternity_leave": "👶 Maternity",
            "paternity_leave": "👨‍👧 Paternity",
            "overtime_pay": "💸 Overtime",
            "sick_leave": "🏥 Sick Leave",
            "public_holidays": "📅 Holidays",
            "workplace_safety": "⛑️ Safety",
            "notice_period": "📋 Notice Period",
            "retrenchment": "📉 Retrenchment",
        }
        
        related_formatted = []
        for topic in response.related_sections[:3]:
            name = topic_names.get(topic, topic.replace('_', ' ').title())
            related_formatted.append(name)
        
        message_parts.append(" • ".join(related_formatted))
    
    # Interactive footer
    message_parts.extend([
        "",
        "━━━━━━━━━━━━━━━",
        "💬 _Ask another question_",
        "👍 _Reply 'helpful' if this helped_",
        "",
        "⚠️ _Legal info only. Consult a lawyer for advice._"
    ])
    
    # Join and check length
    full_message = "\n".join(message_parts)
    
    # Truncate if too long
    if len(full_message) > 4000:
        # Remove some sections to fit
        message_parts = message_parts[:10] + message_parts[-3:]  # Keep header, summary, and footer
        full_message = "\n".join(message_parts)
    
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
            "🤖 *Gweta Legal Assistant*\n\n"
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
        # Use RAG system for query processing
        try:
            # Step 1: Retrieve relevant chunks from Milvus
            retrieval_results, retrieval_confidence = await search_legal_documents(
                query=message_text,
                top_k=5,  # Fewer results for WhatsApp
                min_score=0.1
            )
            
            # Step 2: Compose answer from retrieved chunks
            composed_answer = await compose_legal_answer(
                results=retrieval_results,
                query=message_text,
                confidence=retrieval_confidence,
                lang="en",
                use_openai=True
            )
            
            # Step 3: Convert to QueryResponse format for WhatsApp formatting
            query_response = QueryResponse(
                tldr=composed_answer.tldr,
                key_points=composed_answer.key_points,
                citations=[],  # Simplified for WhatsApp
                suggestions=composed_answer.suggestions,
                confidence=composed_answer.confidence,
                source=composed_answer.source,
                request_id=f"whatsapp_{int(time.time() * 1000)}"
            )
            
        except Exception as rag_error:
            # Fallback to simple error response if RAG fails
            logger.warning("RAG failed for WhatsApp, using fallback", error=str(rag_error))
            query_response = QueryResponse(
                tldr="I'm having trouble accessing legal information right now. Please try again later.",
                key_points=["System temporarily unavailable", "Please try again in a few minutes", "For urgent matters, contact legal counsel"],
                citations=[],
                suggestions=["Try asking again", "Contact legal support"],
                confidence=0.1,
                source="fallback",
                request_id=f"whatsapp_fallback_{int(time.time() * 1000)}"
            )
        
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

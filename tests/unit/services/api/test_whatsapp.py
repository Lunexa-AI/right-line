"""Unit tests for WhatsApp integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.whatsapp import (
    WhatsAppMessage,
    format_whatsapp_response,
    process_whatsapp_message,
    verify_webhook_signature,
)
from services.api.models import Citation, QueryResponse, SectionRef


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestWhatsAppFormatting:
    """Test WhatsApp message formatting."""
    
    def test_format_basic_response(self):
        """Test formatting a basic query response for WhatsApp."""
        response = QueryResponse(
            summary_3_lines="Line 1 of summary.\nLine 2 of summary.\nLine 3 of summary.",
            section_ref=SectionRef(
                act="Labour Act",
                chapter="28:01",
                section="12A",
                version="2024-01-01",
            ),
            citations=[
                Citation(
                    title="Labour Act",
                    url="https://veritas.org.zw/labour-act",
                    page=15,
                    sha="abc123",
                ),
            ],
            confidence=0.85,
            related_sections=["12B", "13"],
        )
        
        formatted = format_whatsapp_response(response)
        
        # Check key elements are present
        assert "❝" in formatted  # Quote marks
        assert "Line 1 of summary" in formatted
        assert "*Labour Act*" in formatted  # Bold formatting
        assert "§12A" in formatted
        assert "veritas.org.zw" in formatted  # URL without https://
        assert "✅" in formatted  # High confidence emoji
        assert "85%" in formatted  # Confidence percentage
        assert "§12B" in formatted  # Related sections
        assert "HELP" in formatted  # Footer
    
    def test_format_low_confidence_response(self):
        """Test formatting with low confidence shows warning."""
        response = QueryResponse(
            summary_3_lines="Uncertain response.",
            section_ref=SectionRef(
                act="General",
                chapter="N/A",
                section="FAQ",
                version=None,
            ),
            citations=[],
            confidence=0.3,
            related_sections=[],
        )
        
        formatted = format_whatsapp_response(response)
        
        assert "❓" in formatted  # Low confidence emoji
        assert "30%" in formatted
    
    def test_format_truncates_long_response(self):
        """Test that very long responses are truncated."""
        long_summary = "\n".join(["This is a very long line " * 10] * 3)
        response = QueryResponse(
            summary_3_lines=long_summary,
            section_ref=SectionRef(
                act="Labour Act",
                chapter="28:01",
                section="12A",
                version="2024-01-01",
            ),
            citations=[
                Citation(
                    title=f"Citation {i}",
                    url=f"https://example.com/cite{i}",
                    page=i,
                    sha=f"sha{i}",
                )
                for i in range(10)
            ],
            confidence=0.85,
            related_sections=[f"Section{i}" for i in range(10)],
        )
        
        formatted = format_whatsapp_response(response)
        
        # Should be under WhatsApp limit
        assert len(formatted) <= 4096
        assert "..." in formatted  # Truncation indicator


class TestWebhookSignature:
    """Test webhook signature verification."""
    
    def test_valid_signature(self):
        """Test valid webhook signature passes verification."""
        secret = "test_secret"
        body = b'{"test": "data"}'
        
        # Generate valid signature
        import hashlib
        import hmac
        
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_sig}"
        
        assert verify_webhook_signature(body, signature, secret) is True
    
    def test_invalid_signature(self):
        """Test invalid signature fails verification."""
        secret = "test_secret"
        body = b'{"test": "data"}'
        signature = "sha256=invalid_signature"
        
        assert verify_webhook_signature(body, signature, secret) is False
    
    def test_missing_signature_prefix(self):
        """Test signature without sha256= prefix fails."""
        secret = "test_secret"
        body = b'{"test": "data"}'
        signature = "just_a_hash"
        
        assert verify_webhook_signature(body, signature, secret) is False


class TestMessageProcessing:
    """Test WhatsApp message processing."""
    
    @pytest.mark.asyncio
    async def test_process_text_message(self):
        """Test processing a text message returns legal response."""
        message = WhatsAppMessage(
            from_="263771234567",
            id="msg_123",
            timestamp="1234567890",
            type="text",
            text={"body": "What is the minimum wage?"},
        )
        
        response = await process_whatsapp_message(message, "263771234567")
        
        assert "minimum wage" in response.lower()
        assert "❝" in response  # Has formatted quotes
        assert "Labour Act" in response
    
    @pytest.mark.asyncio
    async def test_process_help_command(self):
        """Test HELP command returns help message."""
        message = WhatsAppMessage(
            from_="263771234567",
            id="msg_123",
            timestamp="1234567890",
            type="text",
            text={"body": "HELP"},
        )
        
        response = await process_whatsapp_message(message, "263771234567")
        
        assert "RightLine Legal Assistant" in response
        assert "How to use:" in response
        assert "Example questions:" in response
    
    @pytest.mark.asyncio
    async def test_process_more_command(self):
        """Test MORE command returns topic list."""
        message = WhatsAppMessage(
            from_="263771234567",
            id="msg_123",
            timestamp="1234567890",
            type="text",
            text={"body": "MORE"},
        )
        
        response = await process_whatsapp_message(message, "263771234567")
        
        assert "Popular Topics" in response
        assert "Minimum wage" in response
        assert "Maternity leave" in response
    
    @pytest.mark.asyncio
    async def test_process_non_text_message(self):
        """Test non-text message returns error message."""
        message = WhatsAppMessage(
            from_="263771234567",
            id="msg_123",
            timestamp="1234567890",
            type="image",
            text=None,
        )
        
        response = await process_whatsapp_message(message, "263771234567")
        
        assert "only process text messages" in response


class TestWebhookEndpoints:
    """Test WhatsApp webhook endpoints."""
    
    def test_webhook_verification_success(self, client: TestClient):
        """Test successful webhook verification."""
        with patch("services.api.main.get_settings") as mock_settings:
            mock_settings.return_value.whatsapp_verify_token = "test_token"
            
            response = client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.challenge": "challenge_string",
                    "hub.verify_token": "test_token",
                },
            )
            
            assert response.status_code == 200
            assert response.text == '"challenge_string"'  # FastAPI returns JSON string
    
    def test_webhook_verification_wrong_token(self, client: TestClient):
        """Test webhook verification with wrong token."""
        with patch("services.api.main.get_settings") as mock_settings:
            mock_settings.return_value.whatsapp_verify_token = "correct_token"
            
            response = client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.challenge": "challenge_string",
                    "hub.verify_token": "wrong_token",
                },
            )
            
            assert response.status_code == 403
    
    def test_webhook_verification_not_configured(self, client: TestClient):
        """Test webhook verification when not configured."""
        with patch("services.api.main.get_settings") as mock_settings:
            mock_settings.return_value.whatsapp_verify_token = None
            
            response = client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.challenge": "challenge_string",
                    "hub.verify_token": "any_token",
                },
            )
            
            assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_webhook_receive_message(self, client: TestClient):
        """Test receiving a WhatsApp message via webhook."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "ACCOUNT_ID",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "messages": [
                                    {
                                        "from": "263771234567",
                                        "id": "MESSAGE_ID",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "What is minimum wage?"},
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
        
        with patch("services.api.whatsapp.send_whatsapp_message") as mock_send:
            mock_send.return_value = {"messages": [{"id": "sent_msg_id"}]}
            
            with patch("services.api.main.get_settings") as mock_settings:
                mock_settings.return_value.whatsapp_verify_token = None  # Skip signature verification
                mock_settings.return_value.whatsapp_phone_id = "PHONE_ID"
                mock_settings.return_value.whatsapp_token = "TOKEN"
                
                response = client.post("/webhook", json=payload)
                
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
                
                # Check that send was called
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                assert call_args[0][0] == "263771234567"  # Phone number
                assert "minimum wage" in call_args[0][1].lower()  # Response contains topic
    
    def test_webhook_receive_non_message_event(self, client: TestClient):
        """Test receiving a non-message webhook event."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "ACCOUNT_ID",
                    "changes": [
                        {
                            "field": "account_update",  # Not a message
                            "value": {"some": "data"},
                        }
                    ],
                }
            ],
        }
        
        with patch("services.api.main.get_settings") as mock_settings:
            mock_settings.return_value.whatsapp_verify_token = None
            
            response = client.post("/webhook", json=payload)
            
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

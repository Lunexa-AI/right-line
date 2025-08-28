import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app
from libs.common.settings import Settings

client = TestClient(app)

@pytest.fixture
def mock_get_settings():
    with patch('api.routers.whatsapp.get_settings') as mock_get:
        mock_get.return_value = Settings(whatsapp_verify_token="test_token")
        yield mock_get

@pytest.fixture
def mock_handle_whatsapp_webhook():
    with patch('api.routers.whatsapp.handle_whatsapp_webhook') as mock_handle:
        mock_handle.return_value = {"status": "ok"}
        yield mock_handle

def test_verify_whatsapp_webhook_success(mock_get_settings):
    """
    Tests the GET /webhook endpoint for a successful verification.
    """
    # Act
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.challenge": "challenge_string",
        "hub.verify_token": "test_token"
    })
    
    # Assert
    assert response.status_code == 200
    assert response.text == '"challenge_string"'

def test_verify_whatsapp_webhook_failure(mock_get_settings):
    """
    Tests the GET /webhook endpoint for a failed verification due to an invalid token.
    """
    # Act
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.challenge": "challenge_string",
        "hub.verify_token": "invalid_token"
    })
    
    # Assert
    assert response.status_code == 403
    assert "Verification failed" in response.json()["detail"]

def test_receive_whatsapp_webhook_success(mock_handle_whatsapp_webhook):
    """
    Tests the POST /webhook endpoint for successfully receiving a message.
    """
    # Act
    response = client.post("/webhook", json={
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "ACCOUNT_ID",
            "changes": [{"field": "messages", "value": {}}]
        }]
    })
    
    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_handle_whatsapp_webhook.assert_called_once()

def test_receive_whatsapp_webhook_handler_error(mock_handle_whatsapp_webhook):
    """
    Tests that the POST /webhook endpoint returns a 200 status even if the handler fails,
    to prevent WhatsApp from retrying.
    """
    # Arrange
    mock_handle_whatsapp_webhook.side_effect = Exception("Processing error")
    
    # Act
    response = client.post("/webhook", json={
        "object": "whatsapp_business_account",
        "entry": [{"changes": []}] 
    })
    
    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "error_logged"}

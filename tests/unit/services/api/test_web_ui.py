"""Unit tests for the enhanced web UI."""

import pytest
from fastapi.testclient import TestClient
from services.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_web_ui_serves_successfully(client):
    """Test that the web UI serves successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RightLine" in response.text
    assert "Zimbabwe Legal Information" in response.text


def test_web_ui_has_chat_interface(client):
    """Test that the web UI has chat interface elements."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for chat container
    assert "chatContainer" in response.text
    assert "messagesContainer" in response.text
    
    # Check for floating input
    assert "floating-input" in response.text
    assert "queryInput" in response.text
    assert "auto-expand" in response.text


def test_web_ui_has_message_bubbles(client):
    """Test that the web UI has message bubble styles."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for message bubble classes
    assert "message-bubble" in response.text
    assert "message.user" in response.text
    assert "message.bot" in response.text
    

def test_web_ui_has_loading_animations(client):
    """Test that the web UI has loading animations."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for loading dots animation
    assert "loading-dots" in response.text
    assert "pulse-dot" in response.text
    assert "typing-indicator" in response.text


def test_web_ui_has_keyboard_shortcuts(client):
    """Test that the web UI implements keyboard shortcuts."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for Enter/Shift+Enter handling
    assert "Enter" in response.text
    assert "Shift+Enter" in response.text
    assert "!e.shiftKey" in response.text


def test_web_ui_has_clear_functionality(client):
    """Test that the web UI has clear conversation functionality."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for clear button
    assert "clearBtn" in response.text
    assert "Clear" in response.text
    assert "chatHistory = []" in response.text


def test_web_ui_has_character_counter(client):
    """Test that the web UI has character counter."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for character counter
    assert "charCount" in response.text
    assert "0/1000" in response.text
    assert "maxlength=\"1000\"" in response.text


def test_web_ui_has_suggestion_buttons(client):
    """Test that the web UI has suggestion buttons."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for suggestion buttons
    assert "suggestion-btn" in response.text
    assert "What is the minimum wage?" in response.text
    assert "How much annual leave" in response.text


def test_web_ui_has_confidence_display(client):
    """Test that the web UI has confidence display."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for confidence bar
    assert "confidence-bar" in response.text
    assert "confidence-fill" in response.text
    assert "confidence-high" in response.text
    assert "confidence-medium" in response.text
    assert "confidence-low" in response.text


def test_web_ui_has_responsive_design(client):
    """Test that the web UI has responsive design elements."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for responsive classes
    assert "sm:grid-cols-2" in response.text
    assert "max-w-4xl" in response.text
    assert "mx-auto" in response.text
    

def test_web_ui_has_accessibility_features(client):
    """Test that the web UI has accessibility features."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for accessibility attributes
    assert "aria-label" in response.text
    assert "focus:ring-2" in response.text
    assert "focus-visible" in response.text
    

def test_web_ui_has_system_fonts(client):
    """Test that the web UI uses system fonts."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for system font stack
    assert "-apple-system" in response.text
    assert "BlinkMacSystemFont" in response.text
    assert "'Segoe UI'" in response.text
    assert "Roboto" in response.text
    
    # Ensure no external font imports
    assert "fonts.googleapis.com" not in response.text
    assert "@font-face" not in response.text


def test_web_ui_has_touch_targets(client):
    """Test that the web UI has proper touch targets."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for touch target class
    assert "touch-target" in response.text
    assert "min-height: 44px" in response.text
    assert "min-width: 44px" in response.text


def test_web_ui_has_transitions(client):
    """Test that the web UI has smooth transitions."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for transition utilities
    assert "--transition-fast: 150ms" in response.text
    assert "--transition-normal: 200ms" in response.text
    assert "transition-all" in response.text


def test_web_ui_has_chat_history_limit(client):
    """Test that the web UI limits chat history."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for history limit
    assert "MAX_HISTORY = 3" in response.text
    assert "chatHistory.shift()" in response.text


def test_web_ui_has_xss_protection(client):
    """Test that the web UI has XSS protection."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for HTML escaping function
    assert "escapeHtml" in response.text
    assert "&amp;" in response.text
    assert "&lt;" in response.text
    assert "&gt;" in response.text


def test_web_ui_has_error_handling(client):
    """Test that the web UI has error handling."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for error handling
    assert "catch (error)" in response.text
    assert "Sorry, I couldn't process your request" in response.text
    

def test_web_ui_has_legal_disclaimer(client):
    """Test that the web UI has legal disclaimer."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for disclaimer
    assert "Legal Information Only" in response.text
    assert "not legal advice" in response.text
    assert "consult a qualified lawyer" in response.text

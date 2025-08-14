"""Unit tests for Phase 3.1 and 3.2 UI improvements."""

import pytest
from fastapi.testclient import TestClient
from services.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# Phase 3.1: Micro-interactions Tests

def test_hover_elevation_effects(client):
    """Test that hover elevation effects are implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for elevation animation
    assert "@keyframes elevate" in response.text
    assert "hover-elevate" in response.text
    assert "--elevation-2" in response.text
    assert "translateY(-2px)" in response.text


def test_card_slide_up_animation(client):
    """Test that card slide-up animation is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for slide-up animation
    assert "@keyframes slideUpFadeIn" in response.text
    assert "card-enter" in response.text
    assert "cubic-bezier(0.4, 0, 0.2, 1)" in response.text
    assert "translateY(20px)" in response.text


def test_success_flash_animation(client):
    """Test that success flash animation is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for success flash
    assert "@keyframes successFlash" in response.text
    assert "success-flash" in response.text
    assert "400ms ease-out" in response.text
    assert "buttonElement.classList.add('success-flash')" in response.text


def test_enhanced_focus_indicators(client):
    """Test that enhanced focus indicators are implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for enhanced focus styles
    assert "*:focus-visible" in response.text
    assert "outline: 2px solid var(--primary)" in response.text
    assert "outline-offset: 4px" in response.text
    assert "box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1)" in response.text


def test_confidence_meter_pulse(client):
    """Test that confidence meter has gentle pulse animation."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for pulse animation
    assert "@keyframes gentlePulse" in response.text
    assert "pulse-gentle" in response.text
    assert "2s ease-in-out infinite" in response.text
    assert "opacity: 0.8" in response.text


def test_message_bubble_hover_effects(client):
    """Test that message bubbles have hover effects."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for bubble hover
    assert ".message-bubble:hover" in response.text
    assert "transition: box-shadow" in response.text


def test_card_hover_elevation(client):
    """Test that cards have hover elevation."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for card hover
    assert ".card:hover" in response.text
    assert "--elevation-3" in response.text
    assert "transform: translateY(-2px)" in response.text


def test_suggestion_pill_enhanced_hover(client):
    """Test that suggestion pills have enhanced hover effects."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for enhanced pill hover
    assert ".suggestion-pill:hover" in response.text
    assert "scale(1.02)" in response.text
    assert "--elevation-2" in response.text


def test_theme_toggle_hover_effects(client):
    """Test that theme toggle has hover effects."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for theme toggle hover
    assert ".theme-toggle:hover" in response.text
    assert "scale(1.05)" in response.text
    assert "box-shadow: var(--elevation-2)" in response.text


def test_copy_button_feedback(client):
    """Test that copy button has visual feedback."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for copy feedback
    assert "copyToClipboard" in response.text
    assert "buttonElement" in response.text
    assert "classList.add('success-flash')" in response.text


# Phase 3.2: Mobile Refinements Tests

def test_viewport_meta_tag(client):
    """Test that viewport meta tag is properly configured."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check viewport settings
    assert 'name="viewport"' in response.text
    assert "width=device-width" in response.text
    assert "initial-scale=1.0" in response.text
    assert "maximum-scale=5.0" in response.text
    assert "user-scalable=yes" in response.text


def test_safe_area_support(client):
    """Test that safe area insets are supported."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for safe area CSS
    assert "--safe-area-top: env(safe-area-inset-top)" in response.text
    assert "--safe-area-bottom: env(safe-area-inset-bottom)" in response.text
    assert "--safe-area-left: env(safe-area-inset-left)" in response.text
    assert "--safe-area-right: env(safe-area-inset-right)" in response.text
    assert "@supports (padding: max(0px))" in response.text
    assert "safe-top" in response.text
    assert "safe-bottom" in response.text


def test_ios_zoom_prevention(client):
    """Test that iOS zoom on input focus is prevented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for font-size fix
    assert "@media screen and (max-width: 640px)" in response.text
    assert "font-size: 16px !important" in response.text
    assert "handleMobileKeyboard" in response.text


def test_touch_target_sizes(client):
    """Test that touch targets meet minimum size requirements."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for touch target sizing
    assert ".touch-target" in response.text
    assert "min-height: 44px" in response.text
    assert "min-width: 44px" in response.text
    
    # Mobile specific
    assert "min-height: 48px" in response.text
    assert "min-width: 48px" in response.text


def test_thumb_navigation_zones(client):
    """Test that thumb navigation zones are implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for thumb zones
    assert ".thumb-zone" in response.text
    assert "height: 80px" in response.text
    assert "pointer-events: none" in response.text
    assert "pointer-events: auto" in response.text


def test_smooth_scrolling_ios(client):
    """Test that smooth scrolling is enabled for iOS."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for iOS smooth scrolling
    assert "-webkit-overflow-scrolling: touch" in response.text
    assert "scroll-behavior: smooth" in response.text
    assert "smooth-scroll" in response.text


def test_mobile_keyboard_handling(client):
    """Test that mobile keyboard handling is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for keyboard handling
    assert "handleMobileKeyboard" in response.text
    assert "keyboard-open" in response.text
    assert "window.innerHeight < viewportHeight * 0.75" in response.text
    assert "scrollIntoView" in response.text


def test_touch_feedback(client):
    """Test that touch feedback is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for touch feedback
    assert "addTouchFeedback" in response.text
    assert "touchstart" in response.text
    assert "touchend" in response.text
    assert "scale(0.98)" in response.text


def test_textarea_mobile_attributes(client):
    """Test that textarea has proper mobile attributes."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for mobile textarea attributes
    assert 'autocomplete="off"' in response.text
    assert 'autocorrect="on"' in response.text
    assert 'autocapitalize="sentences"' in response.text
    assert 'spellcheck="true"' in response.text


def test_scroll_snap_suggestions(client):
    """Test that suggestions have scroll snap on mobile."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for scroll snap
    assert "scroll-snap-type: x mandatory" in response.text
    assert "scroll-snap-align: start" in response.text


def test_mobile_chat_container_height(client):
    """Test that chat container height accounts for safe areas."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for safe area calculations
    assert "calc(100vh - 12rem - var(--safe-area-top) - var(--safe-area-bottom))" in response.text
    assert "calc(100vh - 10rem - var(--safe-area-top) - var(--safe-area-bottom))" in response.text


def test_floating_input_safe_areas(client):
    """Test that floating input respects safe areas."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for safe area padding
    assert "padding-bottom: max(1rem, var(--safe-area-bottom))" in response.text
    assert "padding-bottom: max(1.5rem, calc(var(--safe-area-bottom) + 0.5rem))" in response.text


def test_delayed_focus_mobile(client):
    """Test that input focus is delayed on mobile to prevent keyboard popup."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for delayed focus
    assert "setTimeout(() => {" in response.text
    assert "window.innerWidth > 640" in response.text
    assert "queryInput.focus()" in response.text
    assert "}, 500)" in response.text

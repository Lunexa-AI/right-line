"""Unit tests for Phase 2 UI improvements."""

import pytest
from fastapi.testclient import TestClient
from services.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_progressive_disclosure_elements(client):
    """Test that progressive disclosure elements are present."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for expandable details section
    assert "details-section" in response.text
    assert "View Details" in response.text
    assert "toggleDetails" in response.text
    assert "expanded" in response.text
    

def test_copy_functionality(client):
    """Test that copy to clipboard functionality is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for copy button and functionality
    assert "copyToClipboard" in response.text
    assert "📋 Copy" in response.text
    assert "navigator.clipboard.writeText" in response.text
    assert "copyToast" in response.text
    assert "Copied to clipboard" in response.text


def test_trust_indicators(client):
    """Test that trust indicators are present."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for source badges
    assert "source-badge" in response.text
    assert "official" in response.text
    assert "veritas" in response.text
    assert "interpreted" in response.text
    assert "OFFICIAL" in response.text
    assert "VERITAS" in response.text
    assert "INTERPRETED" in response.text


def test_confidence_bar_enhanced(client):
    """Test enhanced confidence bar display."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for confidence bar components
    assert "confidence-bar" in response.text
    assert "confidence-fill" in response.text
    assert "confidence-high" in response.text
    assert "confidence-medium" in response.text
    assert "confidence-low" in response.text
    assert "confidencePercent" in response.text


def test_source_count_display(client):
    """Test that source count is displayed."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for source count
    assert "sources" in response.text
    assert "data.citations.length" in response.text


def test_last_updated_timestamp(client):
    """Test that last updated timestamp is shown."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for version/timestamp display
    assert "Last updated" in response.text
    assert "section_ref.version" in response.text


def test_dark_mode_implementation(client):
    """Test that dark mode is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for dark mode CSS variables
    assert "[data-theme=\"dark\"]" in response.text
    assert "--bg-primary: #111827" in response.text
    assert "--text-primary: #F9FAFB" in response.text
    
    # Check for system preference detection
    assert "prefers-color-scheme: dark" in response.text
    assert "@media (prefers-color-scheme: dark)" in response.text


def test_theme_toggle_button(client):
    """Test that theme toggle button exists."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for theme toggle
    assert "themeToggle" in response.text
    assert "sunIcon" in response.text
    assert "moonIcon" in response.text
    assert "Toggle theme" in response.text


def test_theme_persistence(client):
    """Test that theme preference is persisted."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for localStorage usage
    assert "localStorage.getItem('theme')" in response.text
    assert "localStorage.setItem('theme'" in response.text


def test_contextual_suggestions(client):
    """Test that contextual suggestions are implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for suggestions bar
    assert "suggestionsBar" in response.text
    assert "suggestionPills" in response.text
    assert "suggestion-pill" in response.text
    assert "updateSuggestions" in response.text


def test_related_sections_suggestions(client):
    """Test that related sections generate suggestions."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for related sections handling
    assert "related_sections" in response.text
    assert "relatedSections" in response.text
    assert "Tell me about section" in response.text


def test_seed_suggestions(client):
    """Test that seed suggestions are provided."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for seed suggestions
    assert "SEED_SUGGESTIONS" in response.text
    assert "Working hours limits" in response.text
    assert "Overtime pay rates" in response.text
    assert "Dismissal procedures" in response.text
    assert "Medical leave requirements" in response.text


def test_suggestion_pill_interaction(client):
    """Test that suggestion pills are interactive."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for pill interaction
    assert "handleSuggestionClick" in response.text
    assert "pill.onclick" in response.text


def test_fade_in_animations(client):
    """Test that fade-in animations are implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for fade-in animation
    assert "@keyframes fadeIn" in response.text
    assert "fade-in" in response.text
    assert "animation: fadeIn" in response.text


def test_expand_collapse_animation(client):
    """Test that expand/collapse animation is smooth."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for expand animation
    assert "@keyframes expandDown" in response.text
    assert "max-height: 0" in response.text
    assert "max-height: 500px" in response.text
    assert "--transition-slow" in response.text


def test_css_custom_properties(client):
    """Test that CSS custom properties are used for theming."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for CSS variables
    assert ":root {" in response.text
    assert "--primary:" in response.text
    assert "--bg-primary:" in response.text
    assert "--text-primary:" in response.text
    assert "var(--primary)" in response.text
    assert "var(--bg-primary)" in response.text


def test_proper_contrast_ratios(client):
    """Test that proper contrast is maintained."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for contrast considerations
    assert "--text-primary: #111827" in response.text  # Dark text on light
    assert "--text-primary: #F9FAFB" in response.text  # Light text on dark


def test_responsive_suggestions(client):
    """Test that suggestions are responsive."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for responsive suggestions
    assert "suggestion-pills-container" in response.text
    assert "overflow-x: auto" in response.text
    assert "-webkit-overflow-scrolling: touch" in response.text


def test_maximum_suggestions_limit(client):
    """Test that suggestions are limited to 4."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for suggestion limit
    assert "slice(0, 4)" in response.text


def test_toast_notification(client):
    """Test that toast notification is implemented."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Check for toast
    assert "toast" in response.text
    assert "showToast" in response.text
    assert "setTimeout" in response.text
    assert "2000" in response.text  # 2 second display

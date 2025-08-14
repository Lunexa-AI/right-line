"""
Unit tests for Phase 3.3 and 3.4 UI features - Accessibility and Copy/Share functionality.
Tests focus on ARIA attributes, semantic HTML, copy buttons, and share features.
"""

import pytest
from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)


class TestAccessibilityEnhancements:
    """Test Phase 3.3: Accessibility Enhancements"""
    
    def test_skip_navigation_link(self):
        """Test skip to main content link is present"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for skip navigation link
        assert 'href="#main-content"' in html
        assert 'Skip to main content' in html
        assert 'sr-only focus:not-sr-only' in html
    
    def test_semantic_html_structure(self):
        """Test proper semantic HTML elements"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for semantic landmarks
        assert 'role="banner"' in html  # Header
        assert 'role="main"' in html  # Main content
        assert 'role="log"' in html  # Messages container
        assert 'aria-live="polite"' in html  # Live region
    
    def test_aria_labels_present(self):
        """Test ARIA labels on interactive elements"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for ARIA labels
        assert 'aria-label="Toggle theme"' in html
        assert 'aria-label="Clear conversation"' in html
        assert 'aria-label="Legal question input"' in html
        assert 'aria-label="Send message"' in html
        assert 'aria-label="Conversation"' in html
    
    def test_icons_have_aria_hidden(self):
        """Test decorative icons have aria-hidden"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for aria-hidden on SVG icons
        assert 'aria-hidden="true"' in html
        assert 'focusable="false"' in html
    
    def test_heading_hierarchy(self):
        """Test proper heading hierarchy"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check heading structure
        assert '<h1' in html  # Main title
        assert '<h2' in html  # Welcome heading
        assert '<h3' in html  # Subheadings
    
    def test_focus_visible_styles(self):
        """Test focus visible styles are defined"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for focus styles
        assert '*:focus-visible' in html
        assert 'outline: 2px solid var(--primary)' in html
        assert 'outline-offset' in html
        assert 'box-shadow: 0 0 0 4px' in html
    
    def test_screen_reader_utility_class(self):
        """Test screen reader only utility class"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for sr-only class definition
        assert '.sr-only' in html
        assert 'position: absolute' in html
        assert 'clip: rect(0, 0, 1px, 1px)' in html
    
    def test_form_labels_and_descriptions(self):
        """Test form elements have proper labels"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check textarea attributes
        assert 'placeholder="Ask a legal question..."' in html
        assert 'aria-label="Legal question input"' in html
        assert 'autocomplete="off"' in html
        assert 'spellcheck="true"' in html
    
    def test_button_titles_for_tooltips(self):
        """Test buttons have title attributes for tooltips"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for title attributes
        assert 'title="Toggle theme"' in html
        assert 'title="Clear conversation"' in html
    
    def test_live_region_attributes(self):
        """Test ARIA live region configuration"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check live region attributes
        assert 'aria-live="polite"' in html
        assert 'aria-relevant="additions"' in html
        assert 'aria-atomic="true"' in html
    
    def test_role_attributes(self):
        """Test appropriate role attributes"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check role attributes
        assert 'role="status"' in html  # Toast
        assert 'role="group"' in html  # Question buttons
        assert 'role="banner"' in html  # Header
        assert 'role="main"' in html  # Main content


class TestCopyShareFunctionality:
    """Test Phase 3.4: Copy Actions & Share functionality"""
    
    def test_copy_buttons_present(self):
        """Test copy buttons are present in response"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for copy functionality
        assert 'copyToClipboard' in html
        assert '📋 Copy' in html
        assert 'aria-label="Copy summary"' in html
    
    def test_share_button_present(self):
        """Test share button is present"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for share functionality
        assert 'shareResponse' in html
        assert '🔗 Share' in html
        assert 'aria-label="Share response"' in html
    
    def test_enhanced_clipboard_fallback(self):
        """Test enhanced clipboard API fallback"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for fallback implementation
        assert 'navigator.clipboard' in html
        assert 'window.isSecureContext' in html
        assert 'document.execCommand(\'copy\')' in html
        assert 'navigator.userAgent.match(/ipad|iphone/i)' in html
    
    def test_web_share_api_implementation(self):
        """Test Web Share API implementation"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for Web Share API
        assert 'navigator.share' in html
        assert 'navigator.canShare' in html
        assert 'shareData' in html
        assert 'title: \'RightLine Legal Information\'' in html
    
    def test_toast_notification_system(self):
        """Test toast notification system"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check toast implementation
        assert 'showToast' in html
        assert 'copyToast' in html
        assert '✓ Copied to clipboard' in html
        assert 'toast.classList.add(\'show\')' in html
    
    def test_toast_error_handling(self):
        """Test toast supports error messages"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check error handling in toast
        assert 'type === \'error\'' in html
        assert '❌' in html
        assert 'Copy failed' in html
    
    def test_copy_legal_reference_button(self):
        """Test copy button for legal references"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check for legal reference copy
        assert 'aria-label="Copy legal reference"' in html
        assert 'title="Copy legal reference"' in html
    
    def test_share_fallback_to_copy(self):
        """Test share falls back to copy when unavailable"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check fallback logic
        assert 'Link copied to clipboard' in html
        assert 'From RightLine:' in html
        assert 'window.location.href' in html
    
    def test_ios_clipboard_compatibility(self):
        """Test iOS-specific clipboard handling"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check iOS handling
        assert 'document.createRange()' in html
        assert 'window.getSelection()' in html
        assert 'setSelectionRange(0, 999999)' in html
    
    def test_success_flash_animation(self):
        """Test success flash animation on copy"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check success animation
        assert 'success-flash' in html
        assert 'buttonElement.classList.add(\'success-flash\')' in html
        assert '@keyframes successFlash' in html


class TestComprehensiveAccessibility:
    """Test comprehensive accessibility features"""
    
    def test_color_contrast_variables(self):
        """Test color variables for proper contrast"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check color variables are defined
        assert '--text-primary' in html
        assert '--text-secondary' in html
        assert '--bg-primary' in html
        assert '--bg-secondary' in html
    
    def test_keyboard_navigation_support(self):
        """Test keyboard navigation features"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check keyboard support (updated for new format)
        assert '↵' in html  # Enter symbol
        assert '⇧↵' in html  # Shift+Enter symbols
        assert 'e.key === \'Enter\'' in html
        assert '!e.shiftKey' in html
    
    def test_mobile_accessibility_features(self):
        """Test mobile-specific accessibility"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check mobile accessibility
        assert 'min-height: 44px' in html  # Touch targets
        assert 'min-width: 44px' in html
        assert 'touch-target' in html
    
    def test_error_message_accessibility(self):
        """Test error messages are accessible"""
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        
        # Check error handling
        assert 'isError' in html
        assert 'border-red-300' in html
        assert 'Sorry, I couldn\'t process your request' in html

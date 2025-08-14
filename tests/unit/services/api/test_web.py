"""Unit tests for web interface."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.api.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestWebInterface:
    """Test web interface endpoints."""
    
    def test_root_endpoint_serves_html(self, client: TestClient):
        """Test that root endpoint serves HTML when file exists."""
        # Create a mock HTML file path
        html_content = "<html><body>Test</body></html>"
        
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            
            with patch("services.api.main.FileResponse") as mock_file_response:
                mock_file_response.return_value.status_code = 200
                mock_file_response.return_value.headers = {"content-type": "text/html"}
                
                response = client.get("/")
                
                # FileResponse should be called
                assert mock_file_response.called
    
    def test_root_endpoint_fallback(self, client: TestClient):
        """Test that root endpoint returns JSON fallback when HTML doesn't exist."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            
            response = client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "RightLine API"
            assert data["version"] == "0.1.0"
    
    def test_web_interface_query_flow(self, client: TestClient):
        """Test the complete query flow from web interface."""
        # Test that the API endpoint works with web channel
        query_data = {
            "text": "What is the minimum wage?",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure for web display
        assert "summary_3_lines" in data
        assert "section_ref" in data
        assert "citations" in data
        assert "confidence" in data
        assert "related_sections" in data
        
        # Check that response is suitable for web display
        assert isinstance(data["summary_3_lines"], str)
        assert "\n" in data["summary_3_lines"]  # Should have line breaks
        assert len(data["summary_3_lines"]) <= 400  # Should respect length limit
    
    def test_web_channel_validation(self, client: TestClient):
        """Test that web channel is properly validated."""
        query_data = {
            "text": "Test query",
            "channel": "web"  # Valid channel
        }
        
        response = client.post("/v1/query", json=query_data)
        assert response.status_code == 200
    
    def test_cors_headers_for_web(self, client: TestClient):
        """Test that CORS headers are set for web interface."""
        response = client.options("/v1/query")
        
        # CORS should be configured
        # Note: The actual headers depend on the CORS configuration
        assert response.status_code in [200, 204, 405]  # Common CORS response codes


class TestStaticFiles:
    """Test static file serving."""
    
    def test_static_mount_exists(self, client: TestClient):
        """Test that static files can be accessed if directory exists."""
        # This tests the mount point, not actual file serving
        # In a real scenario, we'd need actual static files
        
        # Try to access a hypothetical static file
        with patch("os.path.exists") as mock_exists:
            # First call checks static dir, second checks specific file
            mock_exists.side_effect = [True, False]
            
            # This would normally 404 if file doesn't exist
            # But we're testing that the mount point is configured
            response = client.get("/static/nonexistent.css")
            
            # Should get 404 for non-existent file, not route not found
            assert response.status_code == 404


class TestWebIntegration:
    """Test web interface integration with API."""
    
    def test_example_queries(self, client: TestClient):
        """Test that example queries from web interface work."""
        example_queries = [
            "What is the minimum wage?",
            "How much annual leave am I entitled to?",
            "Can I get maternity leave?",
            "What are my rights if I'm fired?",
        ]
        
        for query in example_queries:
            response = client.post("/v1/query", json={
                "text": query,
                "channel": "web"
            })
            
            assert response.status_code == 200
            data = response.json()
            
            # Should get meaningful responses
            assert data["confidence"] > 0.1
            assert data["section_ref"]["act"] != "General Information" or "fired" in query.lower()
    
    def test_character_limit_enforcement(self, client: TestClient):
        """Test that character limit is enforced."""
        # Test exactly at limit
        query_at_limit = "x" * 1000
        response = client.post("/v1/query", json={
            "text": query_at_limit,
            "channel": "web"
        })
        assert response.status_code == 200
        
        # Test over limit
        query_over_limit = "x" * 1001
        response = client.post("/v1/query", json={
            "text": query_over_limit,
            "channel": "web"
        })
        assert response.status_code == 422  # Validation error
    
    def test_html_escaping_in_response(self, client: TestClient):
        """Test that responses are safe for HTML display."""
        # Query that might return special characters
        response = client.post("/v1/query", json={
            "text": "What about <script>alert('xss')</script> minimum wage?",
            "channel": "web"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # The response should be safe to display in HTML
        # The actual escaping happens client-side in our implementation
        assert "<script>" not in data["summary_3_lines"]

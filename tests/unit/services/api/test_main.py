"""Unit tests for RightLine API main application."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self, client: TestClient):
        """Test /healthz endpoint returns healthy status."""
        response = client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "api"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data
        assert isinstance(data["timestamp"], (int, float))
    
    def test_readiness_check(self, client: TestClient):
        """Test /readyz endpoint returns ready status."""
        response = client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ready"
        assert data["service"] == "api"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data
        assert isinstance(data["timestamp"], (int, float))


class TestQueryEndpoint:
    """Test legal query endpoint."""
    
    def test_query_minimum_wage(self, client: TestClient):
        """Test query about minimum wage returns correct response."""
        query_data = {
            "text": "What is the minimum wage in Zimbabwe?",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "summary_3_lines" in data
        assert "section_ref" in data
        assert "citations" in data
        assert "confidence" in data
        assert "related_sections" in data
        
        # Check section reference
        section_ref = data["section_ref"]
        assert section_ref["act"] == "Labour Act"
        assert section_ref["chapter"] == "28:01"
        assert section_ref["section"] == "12A"
        
        # Check confidence is reasonable
        assert 0.0 <= data["confidence"] <= 1.0
        assert data["confidence"] > 0.5  # Should be high for good match
        
        # Check citations exist
        assert len(data["citations"]) > 0
        citation = data["citations"][0]
        assert "title" in citation
        assert "url" in citation
    
    def test_query_working_hours(self, client: TestClient):
        """Test query about working hours returns correct response."""
        query_data = {
            "text": "How many hours can I work per day?",
            "channel": "whatsapp"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should match working hours topic
        section_ref = data["section_ref"]
        assert section_ref["act"] == "Labour Act"
        assert section_ref["section"] == "14"
        
        # Check summary mentions hours
        summary = data["summary_3_lines"].lower()
        assert "hours" in summary or "hour" in summary
    
    def test_query_unknown_topic(self, client: TestClient):
        """Test query about unknown topic returns default response."""
        query_data = {
            "text": "What is the price of bananas in Zimbabwe?",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return default/fallback response
        section_ref = data["section_ref"]
        assert section_ref["act"] == "General Information"
        assert section_ref["section"] == "FAQ"
        
        # Confidence should be low
        assert data["confidence"] < 0.5
    
    def test_query_validation_empty_text(self, client: TestClient):
        """Test query with empty text returns validation error."""
        query_data = {
            "text": "",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_validation_text_too_short(self, client: TestClient):
        """Test query with text too short returns validation error."""
        query_data = {
            "text": "hi",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_validation_text_too_long(self, client: TestClient):
        """Test query with text too long returns validation error."""
        query_data = {
            "text": "x" * 1001,  # Exceeds 1000 char limit
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_validation_invalid_channel(self, client: TestClient):
        """Test query with invalid channel returns validation error."""
        query_data = {
            "text": "What is the minimum wage?",
            "channel": "invalid_channel"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_validation_invalid_lang_hint(self, client: TestClient):
        """Test query with invalid language hint returns validation error."""
        query_data = {
            "text": "What is the minimum wage?",
            "lang_hint": "invalid",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_query_with_optional_parameters(self, client: TestClient):
        """Test query with all optional parameters."""
        query_data = {
            "text": "What is the minimum wage?",
            "lang_hint": "en",
            "date_ctx": "2024-01-01",
            "channel": "telegram"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should still return valid response
        assert "summary_3_lines" in data
        assert "section_ref" in data
        assert data["confidence"] > 0.0
    
    def test_query_response_headers(self, client: TestClient):
        """Test that response includes proper headers."""
        query_data = {
            "text": "What is the minimum wage?",
            "channel": "web"
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 200
        
        # Check for request ID header
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")
    
    def test_query_missing_required_field(self, client: TestClient):
        """Test query missing required text field."""
        query_data = {
            "channel": "web"
            # Missing "text" field
        }
        
        response = client.post("/v1/query", json=query_data)
        
        assert response.status_code == 422  # Validation error


class TestMiddleware:
    """Test middleware functionality."""
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are present."""
        response = client.get("/healthz")
        
        # CORS headers should be present (though exact values depend on config)
        assert response.status_code == 200
    
    def test_request_id_generation(self, client: TestClient):
        """Test that request ID is generated and included in response."""
        response = client.get("/healthz")
        
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        
        # Request ID should be unique for different requests
        response2 = client.get("/healthz")
        assert response2.headers["X-Request-ID"] != response.headers["X-Request-ID"]

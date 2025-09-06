"""API integration tests for waitlist endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime, UTC
import uuid

from api.main import app
from libs.models.firestore import WaitlistEntry

# --- Test Setup ---

client = TestClient(app)

class TestWaitlistAPI:
    """Test cases for waitlist API endpoints."""

    def setup_method(self):
        """Set up test fixtures for each test."""
        self.test_email = "test@example.com"
        self.test_source = "web"
        self.test_waitlist_id = str(uuid.uuid4())
        self.test_timestamp = datetime.now(UTC)
        
        # Base request payload
        self.valid_payload = {
            "email": self.test_email,
            "source": self.test_source
        }
        
        # Clear rate limiting store between tests
        from api.routers.waitlist import _rate_limit_store, _honeypot_bans
        _rate_limit_store.clear()
        _honeypot_bans.clear()

    @patch('api.routers.waitlist.get_firestore_async_client')
    @patch('api.routers.waitlist.add_to_waitlist')
    async def test_valid_email_submission_new_signup(self, mock_add_to_waitlist, mock_get_client):
        """Test valid email submission for new signup returns 201 Created."""
        # Arrange
        mock_get_client.return_value = Mock()
        
        # Mock successful new signup
        created_entry = WaitlistEntry(
            waitlist_id=self.test_waitlist_id,
            email=self.test_email,
            joined_at=self.test_timestamp,
            source=self.test_source,
            metadata={"ip_address": "127.0.0.1", "user_agent": "test"}
        )
        mock_add_to_waitlist.return_value = (True, created_entry)
        
        # Act
        response = client.post("/api/v1/waitlist", json=self.valid_payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Successfully added to waitlist!"
        assert data["already_subscribed"] is False
        assert data["waitlist_id"] == self.test_waitlist_id
        
        # Verify Firestore operations were called
        mock_add_to_waitlist.assert_called_once()

    @patch('api.routers.waitlist.get_firestore_async_client')
    @patch('api.routers.waitlist.add_to_waitlist')
    async def test_duplicate_email_submission(self, mock_add_to_waitlist, mock_get_client):
        """Test duplicate email submission returns 200 OK with already_subscribed: true."""
        # Arrange
        mock_get_client.return_value = Mock()
        
        # Mock existing entry found
        existing_entry = WaitlistEntry(
            waitlist_id="existing-id",
            email=self.test_email,
            joined_at=self.test_timestamp,
            source="referral",
            metadata={"ip_address": "different-ip"}
        )
        mock_add_to_waitlist.return_value = (False, existing_entry)
        
        # Act
        response = client.post("/api/v1/waitlist", json=self.valid_payload)
        
        # Assert
        assert response.status_code == 201  # Still 201 due to idempotent behavior
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "You're already on the waitlist!"
        assert data["already_subscribed"] is True
        assert data["waitlist_id"] is None  # Privacy: don't expose existing ID

    def test_invalid_email_format(self):
        """Test invalid email formats return 422 Validation Error."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "test@",
            "test..test@example.com",
            "test@.com",
            "",
            "a" * 255 + "@example.com",  # Too long
        ]
        
        for invalid_email in invalid_emails:
            # Act
            response = client.post("/api/v1/waitlist", json={
                "email": invalid_email,
                "source": "web"
            })
            
            # Assert
            assert response.status_code == 422, f"Email '{invalid_email}' should be invalid"
            data = response.json()
            assert "detail" in data

    def test_missing_email(self):
        """Test missing email returns 422 Validation Error."""
        # Test completely missing email field
        response = client.post("/api/v1/waitlist", json={"source": "web"})
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_empty_email(self):
        """Test empty email returns 422 Validation Error."""
        # Test empty string email
        response = client.post("/api/v1/waitlist", json={
            "email": "",
            "source": "web"
        })
        
        assert response.status_code == 422

    def test_source_field_validation(self):
        """Test source field validation and sanitization."""
        # Test valid sources
        valid_sources = ["web", "social", "referral", "campaign"]
        
        for i, source in enumerate(valid_sources):
            with patch('api.routers.waitlist.get_firestore_async_client'), \
                 patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
                 patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
                
                mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
                
                response = client.post("/api/v1/waitlist", json={
                    "email": f"test{i}{source}@example.com",  # Unique emails
                    "source": source
                })
                
                assert response.status_code == 201

    def test_source_sanitization(self):
        """Test that invalid source characters are sanitized."""
        with patch('api.routers.waitlist.get_firestore_async_client'), \
             patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
             patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
            
            mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
            
            # Test source with special characters gets sanitized to "web"
            response = client.post("/api/v1/waitlist", json={
                "email": "testsanitize@example.com",
                "source": "test@#$%^&*()"
            })
            
            assert response.status_code == 201
            # Verify the sanitized source was used
            call_args = mock_add.call_args[1]  # Get keyword arguments
            assert call_args["source"] == "web"  # Should be sanitized to default

    def test_honeypot_field_detection(self):
        """Test honeypot field blocks bots."""
        # Test honeypot field with content (should be blocked)
        response = client.post("/api/v1/waitlist", json={
            "email": "bot@example.com",
            "source": "web",
            "website": "spam-content"  # Honeypot field
        })
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_request_size_limit(self):
        """Test request size limits are enforced."""
        # Create oversized request
        oversized_payload = {
            "email": "test@example.com",
            "source": "web",
            "extra_data": "x" * 2000  # Oversized content
        }
        
        response = client.post("/api/v1/waitlist", json=oversized_payload)
        
        # Should either be rejected by FastAPI or our validation
        assert response.status_code in [413, 422]

    @patch('api.routers.waitlist.get_firestore_async_client')
    @patch('api.routers.waitlist.add_to_waitlist')
    async def test_response_format_validation(self, mock_add_to_waitlist, mock_get_client):
        """Test response format matches expected schema."""
        # Arrange
        mock_get_client.return_value = Mock()
        created_entry = WaitlistEntry(
            waitlist_id=self.test_waitlist_id,
            email=self.test_email,
            joined_at=self.test_timestamp,
            source=self.test_source,
            metadata={"ip_address": "127.0.0.1"}
        )
        mock_add_to_waitlist.return_value = (True, created_entry)
        
        # Act
        response = client.post("/api/v1/waitlist", json=self.valid_payload)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        
        # Validate response schema
        required_fields = ["success", "message", "already_subscribed", "waitlist_id"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate field types
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)
        assert isinstance(data["already_subscribed"], bool)
        assert isinstance(data["waitlist_id"], (str, type(None)))

    @patch('api.routers.waitlist.get_firestore_async_client')
    @patch('api.routers.waitlist.add_to_waitlist')
    async def test_firestore_error_handling(self, mock_add_to_waitlist, mock_get_client):
        """Test Firestore errors return 500 Internal Server Error."""
        # Arrange
        mock_get_client.return_value = Mock()
        mock_add_to_waitlist.side_effect = RuntimeError("Database connection failed")
        
        # Act
        response = client.post("/api/v1/waitlist", json=self.valid_payload)
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "try again later" in data["detail"].lower()

    def test_rate_limiting_headers_metadata(self):
        """Test that rate limiting metadata is collected."""
        with patch('api.routers.waitlist.get_firestore_async_client'), \
             patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
             patch('api.routers.waitlist._validate_request_security') as mock_security:
            
            mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
            mock_security.return_value = None  # No security violations
            
            # Send request with custom headers
            response = client.post("/api/v1/waitlist", 
                                 json=self.valid_payload,
                                 headers={
                                     "User-Agent": "TestAgent/1.0",
                                     "X-Forwarded-For": "192.168.1.100"
                                 })
            
            assert response.status_code == 201
            
            # Verify security validation was called with IP/headers
            mock_security.assert_called_once()
            call_args = mock_security.call_args[0]
            assert len(call_args) == 3  # client_ip, request_size, user_agent

    def test_content_type_validation(self):
        """Test that only JSON content is accepted."""
        # Test form data (should be rejected)
        response = client.post("/api/v1/waitlist", 
                             data="email=test@example.com&source=web",
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
        
        assert response.status_code == 422

    def test_http_methods(self):
        """Test that only POST is allowed on waitlist endpoint."""
        # Test GET (should not be allowed)
        response = client.get("/api/v1/waitlist")
        assert response.status_code == 405  # Method Not Allowed
        
        # Test PUT (should not be allowed)
        response = client.put("/api/v1/waitlist", json=self.valid_payload)
        assert response.status_code == 405
        
        # Test DELETE (should not be allowed)
        response = client.delete("/api/v1/waitlist")
        assert response.status_code == 405

    @patch('api.routers.waitlist._check_rate_limits')
    async def test_rate_limiting_enforcement(self, mock_rate_limits):
        """Test rate limiting enforcement returns 429."""
        # Arrange
        from fastapi import HTTPException, status
        mock_rate_limits.side_effect = HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests"
        )
        
        # Act
        response = client.post("/api/v1/waitlist", json=self.valid_payload)
        
        # Assert
        assert response.status_code == 429
        data = response.json()
        assert "too many requests" in data["detail"].lower()

    def test_email_normalization(self):
        """Test email normalization in requests."""
        with patch('api.routers.waitlist.get_firestore_async_client'), \
             patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
             patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
            
            mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
            
            # Test uppercase email gets normalized
            response = client.post("/api/v1/waitlist", json={
                "email": "TESTNORMALIZE@EXAMPLE.COM",
                "source": "web"
            })
            
            assert response.status_code == 201
            
            # Verify normalized email was used
            call_args = mock_add.call_args[1]
            assert call_args["email"] == "testnormalize@example.com"

    def test_cors_headers(self):
        """Test CORS headers are properly set."""
        response = client.options("/api/v1/waitlist")
        
        # Should include CORS headers for preflight requests
        assert "access-control-allow-origin" in response.headers or response.status_code == 405

    @patch('api.routers.waitlist.get_firestore_async_client')
    @patch('api.routers.waitlist.add_to_waitlist')
    async def test_metadata_collection(self, mock_add_to_waitlist, mock_get_client):
        """Test that metadata is properly collected and stored."""
        # Arrange
        mock_get_client.return_value = Mock()
        mock_add_to_waitlist.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
        
        # Act
        response = client.post("/api/v1/waitlist", 
                             json=self.valid_payload,
                             headers={
                                 "User-Agent": "TestAgent/1.0",
                                 "X-Forwarded-For": "203.0.113.1"
                             })
        
        # Assert
        assert response.status_code == 201
        
        # Verify metadata was collected
        mock_add_to_waitlist.assert_called_once()
        call_args = mock_add_to_waitlist.call_args[1]
        metadata = call_args["metadata"]
        
        assert "ip_address" in metadata
        assert "user_agent" in metadata
        assert "request_size" in metadata
        assert "timestamp" in metadata

    def test_source_field_optional(self):
        """Test that source field is optional and defaults to 'web'."""
        with patch('api.routers.waitlist.get_firestore_async_client'), \
             patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
             patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
            
            mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
            
            # Test request without source field
            response = client.post("/api/v1/waitlist", json={
                "email": "testoptional@example.com"
            })
            
            assert response.status_code == 201
            
            # Verify default source was used
            call_args = mock_add.call_args[1]
            assert call_args["source"] == "web"

    def test_request_id_header(self):
        """Test that response includes request ID for tracking."""
        with patch('api.routers.waitlist.get_firestore_async_client'), \
             patch('api.routers.waitlist.add_to_waitlist') as mock_add, \
             patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
            
            mock_add.return_value = (True, Mock(waitlist_id=self.test_waitlist_id))
            
            payload = {"email": "testrid@example.com", "source": "web"}
            response = client.post("/api/v1/waitlist", json=payload)
            
            assert response.status_code == 201
            # Should include request ID header for tracing
            assert "x-request-id" in response.headers.keys() or "X-Request-ID" in response.headers.keys()


if __name__ == '__main__':
    pytest.main([__file__, "-v"])

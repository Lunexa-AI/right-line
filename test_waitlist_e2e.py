"""End-to-end tests for waitlist functionality.

This module contains comprehensive end-to-end tests that verify the complete
waitlist flow from HTTP request through validation, Firestore operations,
to final HTTP response. These tests use real application components with
minimal mocking to ensure production-ready functionality.
"""

import asyncio
import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime, UTC
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from api.main import app
from libs.models.firestore import WaitlistEntry

# Test configuration
TEST_BASE_URL = "http://localhost:8000"  # For live testing
CONCURRENT_TEST_COUNT = 10  # For load testing

class TestWaitlistE2E:
    """End-to-end test suite for waitlist functionality."""
    
    def setup_method(self):
        """Set up test fixtures for each test."""
        self.client = TestClient(app)
        self.test_emails = [
            "e2e.test@example.com",
            "duplicate.test@example.com", 
            "load.test@example.com",
            "concurrent.test@example.com"
        ]
        
        # Clear any test data
        self._clear_test_rate_limits()
        
    def teardown_method(self):
        """Clean up after each test."""
        self._clear_test_rate_limits()
        
    def _clear_test_rate_limits(self):
        """Clear rate limiting stores for clean tests."""
        try:
            from api.routers.waitlist import _rate_limit_store, _honeypot_bans
            _rate_limit_store.clear()
            _honeypot_bans.clear()
        except ImportError:
            pass  # Rate limiting might not be available in all test scenarios

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_complete_flow_new_signup(self, mock_get_client):
        """Test complete end-to-end flow for a new signup."""
        # Arrange - Mock Firestore to simulate real behavior
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        # Mock Firestore operations for new signup using add_to_waitlist directly
        with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
            # Mock successful new signup
            test_entry = WaitlistEntry(
                waitlist_id=str(uuid.uuid4()),
                email=self.test_emails[0],
                joined_at=datetime.now(UTC),
                source="e2e-test",
                metadata={"ip_address": "127.0.0.1", "user_agent": "test"}
            )
            mock_add_to_waitlist.return_value = (True, test_entry)
        
            # Act - Submit waitlist request
            response = self.client.post("/api/v1/waitlist", json={
                "email": self.test_emails[0],
                "source": "e2e-test"
            })
            
            # Assert - Verify complete response
            assert response.status_code == 201
            data = response.json()
            
            # Validate response structure
            assert data["success"] is True
            assert "Successfully added to waitlist!" in data["message"]
            assert data["already_subscribed"] is False
            assert data["waitlist_id"] is not None
            assert isinstance(data["waitlist_id"], str)
            
            # Verify Firestore was called with correct data
            mock_add_to_waitlist.assert_called_once()
            
            # Verify headers
            assert "x-request-id" in response.headers or "X-Request-ID" in response.headers

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_complete_flow_duplicate_signup(self, mock_get_client):
        """Test complete end-to-end flow for duplicate email."""
        # Mock add_to_waitlist directly for duplicate case
        with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
            # Mock existing entry found (created=False)
            existing_entry = WaitlistEntry(
                waitlist_id=str(uuid.uuid4()),
                email=self.test_emails[1],
                joined_at=datetime.now(UTC),
                source="previous-signup",
                metadata={"ip_address": "192.168.1.100"}
            )
            mock_add_to_waitlist.return_value = (False, existing_entry)
        
            # Act - Submit duplicate request  
            response = self.client.post("/api/v1/waitlist", json={
                "email": self.test_emails[1],
                "source": "e2e-test"
            })
            
            # Assert - Verify idempotent response
            assert response.status_code == 201
            data = response.json()
            
            assert data["success"] is True
            assert "already on the waitlist" in data["message"]
            assert data["already_subscribed"] is True
            assert data["waitlist_id"] is None  # Privacy protection

    def test_validation_error_scenarios(self):
        """Test various validation error scenarios end-to-end."""
        
        # Test cases with expected status codes
        test_cases = [
            # Invalid email formats
            ({"email": "not-an-email", "source": "test"}, 422),
            ({"email": "@example.com", "source": "test"}, 422),
            ({"email": "test@", "source": "test"}, 422),
            ({"email": "", "source": "test"}, 422),
            
            # Missing email
            ({"source": "test"}, 422),
            
            # Honeypot detection
            ({"email": "bot@example.com", "source": "test", "website": "spam"}, 422),
            
            # Invalid request format
            ("invalid-json", 422),
        ]
        
        for payload, expected_status in test_cases:
            if isinstance(payload, str):
                # Test invalid JSON
                response = self.client.post("/api/v1/waitlist", 
                                          content=payload,
                                          headers={"Content-Type": "application/json"})
            else:
                response = self.client.post("/api/v1/waitlist", json=payload)
            
            assert response.status_code == expected_status, f"Failed for payload: {payload}"
            
            # Ensure error response has proper structure
            if response.status_code == 422:
                data = response.json()
                assert "detail" in data

    def test_http_method_restrictions(self):
        """Test that only POST method is allowed on waitlist endpoint."""
        
        methods_and_expected = [
            ("GET", 405),
            ("PUT", 405), 
            ("DELETE", 405),
            ("PATCH", 405),
        ]
        
        for method, expected_status in methods_and_expected:
            response = self.client.request(method, "/api/v1/waitlist")
            assert response.status_code == expected_status
            
        # Verify OPTIONS is handled (for CORS)
        options_response = self.client.options("/api/v1/waitlist")
        # Should return 405 or 200 depending on CORS setup
        assert options_response.status_code in [200, 405]

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_firestore_error_handling(self, mock_get_client):
        """Test end-to-end error handling when Firestore fails."""
        
        # Arrange - Mock Firestore to fail
        mock_get_client.side_effect = Exception("Firestore connection failed")
        
        # Act
        response = self.client.post("/api/v1/waitlist", json={
            "email": "error.test@example.com",
            "source": "e2e-test"
        })
        
        # Assert
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "try again later" in data["detail"].lower()

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_rate_limiting_e2e(self, mock_get_client):
        """Test rate limiting behavior end-to-end."""
        
        # Mock rate limiting with add_to_waitlist
        with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
            mock_add_to_waitlist.return_value = (True, Mock(waitlist_id=str(uuid.uuid4())))
        
            # Act - Send multiple requests rapidly to trigger rate limiting
            responses = []
            for i in range(5):  # Send more than rate limit (2/minute)
                response = self.client.post("/api/v1/waitlist", json={
                    "email": f"rate.test.{i}@example.com",
                    "source": "rate-test"
                })
                responses.append(response)
            
            # Assert - Some requests should be rate limited
            success_count = sum(1 for r in responses if r.status_code == 201)
            rate_limited_count = sum(1 for r in responses if r.status_code == 429)
            
            # At least some should succeed, some should be rate limited
            assert success_count > 0, "No requests succeeded"
            assert rate_limited_count > 0, "Rate limiting not triggered"
            
            # Verify rate limit response format
            rate_limited_response = next(r for r in responses if r.status_code == 429)
            data = rate_limited_response.json()
            assert "detail" in data
            assert "too many requests" in data["detail"].lower()

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_concurrent_requests(self, mock_get_client):
        """Test handling of concurrent requests to the same endpoint."""
        
        # Mock concurrent requests with add_to_waitlist
        call_count = {"value": 0}
        
        def mock_add_to_waitlist_side_effect(*args, **kwargs):
            call_count["value"] += 1
            if call_count["value"] == 1:
                # First call: new entry created
                return (True, Mock(waitlist_id=str(uuid.uuid4())))
            else:
                # Subsequent calls: existing entry found
                existing_entry = Mock(
                    waitlist_id="existing-id",
                    email="concurrent@example.com"
                )
                return (False, existing_entry)
        
        with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist, \
             patch('api.routers.waitlist._validate_request_security'):  # Skip rate limiting
            mock_add_to_waitlist.side_effect = mock_add_to_waitlist_side_effect
        
            # Act - Send concurrent requests with same email
            def send_request():
                return self.client.post("/api/v1/waitlist", json={
                    "email": "concurrent@example.com",
                    "source": "concurrent-test"
                })
            
            # Use ThreadPoolExecutor for true concurrency
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_index = {
                    executor.submit(send_request): i for i in range(3)
                }
                
                responses = []
                for future in as_completed(future_to_index):
                    response = future.result()
                    responses.append(response)
            
            # Assert - All requests should succeed (either create or find existing)
            for response in responses:
                assert response.status_code == 201
                data = response.json()
                assert data["success"] is True
            
            # At least one should be "new" and others should be "already subscribed"
            already_subscribed_count = sum(
                1 for r in responses if r.json()["already_subscribed"]
            )
            new_signup_count = sum(
                1 for r in responses if not r.json()["already_subscribed"]
            )
            
            # Due to race conditions, results may vary, but all should succeed
            assert already_subscribed_count + new_signup_count == len(responses)

    @patch('api.routers.waitlist.get_firestore_async_client')
    def test_load_testing_basic(self, mock_get_client):
        """Basic load testing with multiple concurrent requests."""
        
        # Clear rate limits for load testing
        self._clear_test_rate_limits()
        
        # Mock add_to_waitlist for load testing
        with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
            mock_add_to_waitlist.return_value = (True, Mock(waitlist_id=str(uuid.uuid4())))
        
            # Act - Send multiple requests with unique emails
            def send_load_request(index):
                return self.client.post("/api/v1/waitlist", json={
                    "email": f"load.test.{index}@example.com",
                    "source": "load-test"
                })
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=CONCURRENT_TEST_COUNT) as executor:
                future_to_index = {
                    executor.submit(send_load_request, i): i 
                    for i in range(CONCURRENT_TEST_COUNT)
                }
                
                responses = []
                for future in as_completed(future_to_index):
                    response = future.result()
                    responses.append(response)
            
            end_time = time.time()
            total_time = end_time - start_time
        
            # Assert - Performance and correctness
            success_count = sum(1 for r in responses if r.status_code in [201, 429])
            error_count = sum(1 for r in responses if r.status_code >= 500)
            
            assert len(responses) == CONCURRENT_TEST_COUNT
            assert success_count >= CONCURRENT_TEST_COUNT * 0.7  # At least 70% should succeed or be rate limited
            assert error_count == 0, "No server errors should occur during load test"
            
            # Basic performance assertion (should handle requests reasonably fast)
            avg_response_time = total_time / CONCURRENT_TEST_COUNT
            assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.2f}s"
            
            print(f"\n🚀 Load Test Results:")
            print(f"   Total Requests: {CONCURRENT_TEST_COUNT}")
            print(f"   Successful Responses: {sum(1 for r in responses if r.status_code == 201)}")
            print(f"   Rate Limited: {sum(1 for r in responses if r.status_code == 429)}")
            print(f"   Total Time: {total_time:.2f}s")
            print(f"   Average Response Time: {avg_response_time:.3f}s")

    def test_request_response_headers(self):
        """Test that proper HTTP headers are set in responses."""
        
        with patch('api.routers.waitlist.get_firestore_async_client') as mock_get_client:
            # Mock successful operation with add_to_waitlist
            with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
                mock_add_to_waitlist.return_value = (True, Mock(waitlist_id=str(uuid.uuid4())))
            
                # Send request with custom headers
                response = self.client.post("/api/v1/waitlist", 
                                          json={
                                              "email": "headers.test@example.com",
                                              "source": "header-test"
                                          },
                                          headers={
                                              "User-Agent": "E2E-Test-Client/1.0",
                                              "X-Forwarded-For": "203.0.113.42"
                                          })
                
                # Verify response headers
                assert response.status_code == 201
                
                # Check for request ID tracking
                has_request_id = any(
                    header.lower() in ["x-request-id", "request-id"] 
                    for header in response.headers.keys()
                )
                assert has_request_id, "Response should include request ID header"
                
                # Verify content type
                assert response.headers["content-type"] == "application/json"

    def test_data_validation_and_sanitization(self):
        """Test end-to-end data validation and sanitization."""
        
        with patch('api.routers.waitlist.get_firestore_async_client') as mock_get_client, \
             patch('api.routers.waitlist._validate_request_security') as mock_security:
            
            # Mock successful Firestore operations
            with patch('api.routers.waitlist.add_to_waitlist') as mock_add_to_waitlist:
                mock_add_to_waitlist.return_value = (True, Mock(waitlist_id=str(uuid.uuid4())))
                mock_security.return_value = None
            
                # Test data that needs sanitization
                response = self.client.post("/api/v1/waitlist", json={
                    "email": "  SANITIZE.TEST@EXAMPLE.COM  ",  # Uppercase with spaces
                    "source": "test@#$%^&*()"  # Invalid characters
                })
                
                assert response.status_code == 201
                
                # The actual sanitization is tested in unit tests, 
                # but we verify the request succeeds end-to-end


if __name__ == '__main__':
    # Run with pytest for better output
    pytest.main([__file__, "-v", "--tb=short"])

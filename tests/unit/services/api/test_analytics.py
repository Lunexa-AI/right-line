"""Unit tests for analytics and feedback functionality."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from libs.common.settings import Settings
from services.api.analytics import (
    AnalyticsSummary,
    FeedbackEntry,
    QueryLog,
    get_analytics_summary,
    get_common_queries,
    hash_user_id,
    init_database,
    log_query,
    save_feedback,
)
from services.api.main import app
from services.api.models import FeedbackRequest, FeedbackResponse


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        app_name="RightLine Test",
        app_env="development",
        secret_key="test_secret_key_that_is_at_least_32_characters_long",
        database_url="postgresql://test",
        redis_url="redis://test",
        debug=True,
    )


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestAnalytics:
    """Test analytics functionality."""
    
    def test_hash_user_id(self, test_settings):
        """Test user ID hashing."""
        user_id = "+263771234567"
        hashed = hash_user_id(user_id, test_settings.secret_key)
        
        # Should produce consistent hash
        assert hashed == hash_user_id(user_id, test_settings.secret_key)
        
        # Should not be the original ID
        assert hashed != user_id
        
        # Should be hex string
        assert all(c in "0123456789abcdef" for c in hashed)
    
    @pytest.mark.asyncio
    async def test_log_query(self, test_settings, tmp_path):
        """Test query logging."""
        # Mock database path
        with patch("services.api.analytics.DB_PATH", tmp_path / "test.db"):
            await init_database()
            
            # Log a query
            await log_query(
                request_id="test_123",
                user_id="user_1",
                channel="web",
                query_text="What is minimum wage?",
                response_topic="minimum_wage",
                confidence=0.95,
                response_time_ms=150,
                status="success",
                session_id="session_1",
                settings=test_settings
            )
            
            # Verify it was logged (would need to query DB to fully verify)
            # For now, just ensure no errors
            assert True
    
    @pytest.mark.asyncio
    async def test_save_feedback(self, test_settings, tmp_path):
        """Test feedback saving."""
        with patch("services.api.analytics.DB_PATH", tmp_path / "test.db"):
            await init_database()
            
            # First log a query
            await log_query(
                request_id="test_456",
                user_id="user_1",
                channel="web",
                query_text="Test query",
                response_topic="test",
                confidence=0.9,
                response_time_ms=100,
                status="success",
                session_id=None,
                settings=test_settings
            )
            
            # Save feedback
            success = await save_feedback(
                request_id="test_456",
                user_id="user_1",
                rating=1,
                comment="Very helpful!",
                settings=test_settings
            )
            
            assert success is True
    
    @pytest.mark.asyncio
    async def test_get_analytics_summary(self, test_settings, tmp_path):
        """Test analytics summary generation."""
        with patch("services.api.analytics.DB_PATH", tmp_path / "test.db"):
            await init_database()
            
            # Log some queries
            for i in range(5):
                await log_query(
                    request_id=f"test_{i}",
                    user_id=f"user_{i % 2}",  # 2 unique users
                    channel="web",
                    query_text=f"Query {i}",
                    response_topic="minimum_wage" if i < 3 else "leave_entitlement",
                    confidence=0.8 + (i * 0.02),
                    response_time_ms=100 + (i * 10),
                    status="success",
                    session_id=None,
                    settings=test_settings
                )
            
            # Get summary
            summary = await get_analytics_summary(hours=24, settings=test_settings)
            
            assert summary.total_queries == 5
            assert summary.unique_users == 2
            assert summary.avg_response_time_ms > 0
            assert summary.success_rate == 100.0
            assert len(summary.top_topics) > 0
    
    @pytest.mark.asyncio
    async def test_get_common_queries(self, tmp_path):
        """Test getting common unmatched queries."""
        with patch("services.api.analytics.DB_PATH", tmp_path / "test.db"):
            await init_database()
            
            # Would need to add unmatched queries to test
            queries = await get_common_queries(limit=10)
            
            # Should return empty list for new DB
            assert queries == []


class TestFeedbackEndpoint:
    """Test feedback API endpoint."""
    
    def test_submit_feedback_success(self, client):
        """Test successful feedback submission."""
        with patch("services.api.main.save_feedback", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = True
            
            response = client.post(
                "/v1/feedback",
                json={
                    "request_id": "req_123",
                    "rating": 1,
                    "comment": "Very helpful!"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "successfully" in data["message"]
    
    def test_submit_feedback_failure(self, client):
        """Test failed feedback submission."""
        with patch("services.api.main.save_feedback", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = False
            
            response = client.post(
                "/v1/feedback",
                json={
                    "request_id": "invalid_req",
                    "rating": -1,
                    "comment": "Not helpful"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "Failed" in data["message"]
    
    def test_feedback_validation(self, client):
        """Test feedback request validation."""
        # Invalid rating
        response = client.post(
            "/v1/feedback",
            json={
                "request_id": "req_123",
                "rating": 5,  # Out of range
                "comment": "Test"
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestAnalyticsEndpoint:
    """Test analytics API endpoints."""
    
    def test_get_analytics_unauthorized(self, client):
        """Test analytics endpoint requires auth in production."""
        with patch("services.api.main.get_settings") as mock_settings:
            mock_settings.return_value.app_env = "production"
            mock_settings.return_value.secret_key = "secret123456789012345678901234567890"
            
            response = client.get("/v1/analytics")
            assert response.status_code == 401
    
    def test_get_analytics_success(self, client):
        """Test successful analytics retrieval."""
        mock_summary = AnalyticsSummary(
            total_queries=100,
            unique_users=25,
            avg_response_time_ms=150.5,
            success_rate=95.0,
            top_topics=[("minimum_wage", 30), ("leave_entitlement", 20)],
            feedback_stats={"positive": 80, "neutral": 15, "negative": 5},
            time_period="Last 24 hours"
        )
        
        with patch("services.api.main.get_analytics_summary", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_summary
            
            response = client.get("/v1/analytics?hours=24")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_queries"] == 100
            assert data["unique_users"] == 25
            assert data["success_rate"] == 95.0
    
    def test_get_common_queries(self, client):
        """Test getting common unmatched queries."""
        with patch("services.api.main.get_common_queries", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                ("pension calculation", 5),
                ("overtime rules", 3)
            ]
            
            response = client.get("/v1/analytics/common-queries?limit=10")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["queries"]) == 2
            assert data["queries"][0][0] == "pension calculation"

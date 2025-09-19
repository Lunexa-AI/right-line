"""Tests for streaming query endpoint (Task 4.4)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import User


class TestStreamingQuery:
    """Test the SSE streaming query endpoint."""
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return User(
            uid="test-user-123",
            email="test@example.com"
        )
    
    @pytest.fixture
    def mock_retrieval_results(self):
        """Mock retrieval results."""
        return [
            MagicMock(
                chunk_id="chunk-1",
                doc_id="doc-1",
                chunk_text="Art unions are legal entities...",
                score=0.85,
                source="vector",
                metadata={"title": "Art Unions Act", "chapter": "25:01"}
            )
        ], 0.85
    
    @pytest.fixture
    def mock_composed_answer(self):
        """Mock composed answer."""
        return MagicMock(
            tldr="Art unions for promoting fine arts are lawful and exempt from lottery laws.",
            key_points=[
                "Art unions aimed at fine arts promotion are legal",
                "They are exempt from lottery laws",
                "Must comply with specific requirements"
            ],
            citations=[
                {"title": "Art Unions Act", "source_url": "https://example.com/doc1"}
            ]
        )
    
    @patch('api.routers.query.get_current_user')
    @patch('api.routers.query.search_legal_documents')
    @patch('api.routers.query.compose_legal_answer')
    @patch('api.routers.query.log_query')
    def test_streaming_query_success(
        self,
        mock_log_query,
        mock_compose_answer,
        mock_search_docs,
        mock_get_user,
        mock_user,
        mock_retrieval_results,
        mock_composed_answer
    ):
        """Test successful streaming query with all events."""
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_search_docs.return_value = mock_retrieval_results
        mock_compose_answer.return_value = mock_composed_answer
        mock_log_query.return_value = AsyncMock()
        
        client = TestClient(app)
        
        # Make streaming request
        with client.stream(
            "GET", 
            "/api/v1/query/stream?query=What are the requirements for art unions?"
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            events = []
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = json.loads(line.split(":", 1)[1].strip())
                    events.append((event_type, data))
        
        # Verify event sequence
        event_types = [event[0] for event in events]
        assert "meta" in event_types
        assert "retrieval" in event_types
        assert "token" in event_types
        assert "citation" in event_types
        assert "final" in event_types
        
        # Verify final event contains expected data
        final_events = [event[1] for event in events if event[0] == "final"]
        assert len(final_events) == 1
        final_data = final_events[0]
        
        assert "request_id" in final_data
        assert final_data["tldr"] == mock_composed_answer.tldr
        assert final_data["key_points"] == mock_composed_answer.key_points
        assert final_data["confidence"] == 0.85
        assert final_data["status"] == "completed"
    
    @patch('api.routers.query.get_current_user')
    @patch('api.routers.query.search_legal_documents')
    def test_streaming_query_no_results(
        self,
        mock_search_docs,
        mock_get_user,
        mock_user
    ):
        """Test streaming query when no documents are found."""
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_search_docs.return_value = ([], 0.0)  # No results
        
        client = TestClient(app)
        
        # Make streaming request
        with client.stream(
            "GET", 
            "/api/v1/query/stream?query=nonexistent legal topic"
        ) as response:
            assert response.status_code == 200
            
            events = []
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = json.loads(line.split(":", 1)[1].strip())
                    events.append((event_type, data))
        
        # Verify warning and final events are present
        event_types = [event[0] for event in events]
        assert "warning" in event_types
        assert "final" in event_types
        
        # Verify warning event
        warning_events = [event[1] for event in events if event[0] == "warning"]
        assert len(warning_events) == 1
        assert warning_events[0]["type"] == "no_results"
        
        # Verify final event shows no results
        final_events = [event[1] for event in events if event[0] == "final"]
        assert len(final_events) == 1
        assert final_events[0]["confidence"] == 0.1
        assert "No specific legal information found" in final_events[0]["tldr"]
    
    @patch('api.routers.query.get_current_user')
    @patch('api.routers.query.search_legal_documents')
    def test_streaming_query_error_handling(
        self,
        mock_search_docs,
        mock_get_user,
        mock_user
    ):
        """Test streaming query error handling."""
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_search_docs.side_effect = Exception("Database connection failed")
        
        client = TestClient(app)
        
        # Make streaming request
        with client.stream(
            "GET", 
            "/api/v1/query/stream?query=test query"
        ) as response:
            assert response.status_code == 200
            
            events = []
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = json.loads(line.split(":", 1)[1].strip())
                    events.append((event_type, data))
        
        # Verify error event is present
        event_types = [event[0] for event in events]
        assert "error" in event_types
        
        # Verify error event content
        error_events = [event[1] for event in events if event[0] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["error"] == "Query processing failed"
        assert "request_id" in error_events[0]
    
    def test_streaming_query_authentication_required(self):
        """Test that streaming endpoint requires authentication."""
        
        client = TestClient(app)
        
        # Make request without authentication
        response = client.get("/api/v1/query/stream?query=test")
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
    
    @patch('api.routers.query.get_current_user')
    def test_streaming_query_missing_query_param(self, mock_get_user, mock_user):
        """Test streaming endpoint with missing query parameter."""
        
        mock_get_user.return_value = mock_user
        client = TestClient(app)
        
        # Make request without query parameter
        response = client.get("/api/v1/query/stream")
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

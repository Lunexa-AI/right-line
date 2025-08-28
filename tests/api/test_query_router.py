import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_query_legal_information_end_to_end_success():
    """
    Tests the /api/v1/query endpoint for a successful response in an end-to-end scenario.
    """
    # Act
    response = client.post("/api/v1/query", json={"text": "What is the minimum wage?"})
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "tldr" in data
    assert "key_points" in data
    assert "citations" in data
    assert data["confidence"] > 0

def test_query_legal_information_end_to_end_fallback():
    """
    Tests the fallback mechanism in an end-to-end scenario with a nonsensical query.
    """
    # Act
    response = client.post("/api/v1/query", json={"text": "a nonsensical query that should not match anything"})
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "I'm having trouble" in data["tldr"]
    assert data["source"] == "fallback"

def test_submit_feedback_end_to_end_success():
    """
    Tests the /v1/feedback endpoint for a successful submission in an end-to-end scenario.
    """
    # Act
    response = client.post("/api/v1/feedback", json={
        "request_id": "req_end_to_end",
        "rating": 1,
        "comment": "End-to-end test feedback"
    })
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.auth import User, get_current_user

# --- Test Setup ---

# Create a dummy user for testing purposes
dummy_user = User(uid="test-user-uid", email="test@example.com")

# Define an override for the get_current_user dependency
def override_get_current_user():
    return dummy_user

# Apply the override to the FastAPI app for all tests in this module
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


# --- Test Cases ---

@patch('api.routers.query.search_legal_documents', new_callable=AsyncMock)
@patch('api.routers.query.compose_legal_answer', new_callable=AsyncMock)
def test_query_legal_information_success(mock_compose, mock_search):
    """
    Tests the /api/v1/query endpoint for a successful response.
    Dependencies for retrieval and composition are mocked.
    """
    # Arrange
    mock_search.return_value = (["chunk1"], 0.9)
    mock_compose.return_value = MagicMock(
        tldr="This is a summary.",
        key_points=["Point 1"],
        citations=[{"title": "Doc 1", "source_url": "http://example.com"}],
        suggestions=["Ask another question"],
        confidence=0.95,
        source="mock_rag"
    )
    
    # Act
    response = client.post(
        "/api/v1/query", 
        json={"text": "What is the minimum wage?"},
        headers={"Authorization": "Bearer fake-token"}
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["tldr"] == "This is a summary."
    assert data["confidence"] > 0
    mock_search.assert_awaited_once()
    mock_compose.assert_awaited_once()

def test_query_legal_information_no_auth_header_fails():
    """
    Tests that the endpoint is protected.
    """
    # Temporarily remove the override to test the real dependency behavior
    app.dependency_overrides = {}
    
    response = client.post("/api/v1/query", json={"text": "any"})
    assert response.status_code == 401
    
    # Restore the override for other tests
    app.dependency_overrides[get_current_user] = override_get_current_user

@patch('api.routers.query.save_feedback', new_callable=AsyncMock)
def test_submit_feedback_success(mock_save_feedback):
    """
    Tests the /api/v1/feedback endpoint for a successful submission.
    The save_feedback dependency is mocked.
    """
    # Arrange
    mock_save_feedback.return_value = True

    # Act
    response = client.post(
        "/api/v1/feedback", 
        json={
            "request_id": "req_test",
            "rating": 1,
            "comment": "Test feedback"
        },
        headers={"Authorization": "Bearer fake-token"}
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    mock_save_feedback.assert_awaited_once()

# --- Teardown ---

# Clean up the dependency override after tests are finished
def teardown_module(module):
    app.dependency_overrides = {}

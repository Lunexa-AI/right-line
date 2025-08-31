import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from api.main import app
from api.auth import User, get_current_user
from libs.models.firestore import FirestoreUser

# --- Test Setup ---

dummy_user = User(uid="new-user-uid", email="new-user@example.com")

def override_get_current_user():
    return dummy_user

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

# --- Test Cases ---

@pytest.mark.asyncio
@patch('api.routers.users.get_firestore_async_client')
@patch('api.routers.users.create_user_profile', new_callable=AsyncMock)
@patch('api.routers.users.get_user_profile', new_callable=AsyncMock)
async def test_create_user_profile_new_user(mock_get_user, mock_create_user, mock_get_client):
    """
    Tests successfully creating a user profile for a new user.
    """
    # Arrange
    mock_get_client.return_value = MagicMock()
    mock_get_user.return_value = None  # Simulate user not found
    
    # The create function should return the newly created user data
    created_user_data = FirestoreUser(
        uid=dummy_user.uid, 
        email=dummy_user.email,
        name="Test User"
    )
    mock_create_user.return_value = created_user_data

    # Act
    response = client.post(
        "/api/v1/users/me",
        json={"name": "Test User"},
        headers={"Authorization": "Bearer fake-token"}
    )

    # Assert
    assert response.status_code == 201 # 201 Created for a new resource
    assert response.json()["uid"] == dummy_user.uid
    assert response.json()["email"] == dummy_user.email
    mock_get_user.assert_awaited_once()
    mock_create_user.assert_awaited_once()

@pytest.mark.asyncio
@patch('api.routers.users.get_firestore_async_client')
@patch('api.routers.users.get_user_profile', new_callable=AsyncMock)
async def test_create_user_profile_existing_user(mock_get_user, mock_get_client):
    """
    Tests calling the endpoint when a user profile already exists.
    It should return the existing profile with a 200 OK status.
    """
    # Arrange
    mock_get_client.return_value = MagicMock()
    existing_user_data = FirestoreUser(
        uid=dummy_user.uid, 
        email=dummy_user.email,
        name="Existing User"
    )
    mock_get_user.return_value = existing_user_data

    # Act
    response = client.post(
        "/api/v1/users/me",
        json={"name": "Does not matter"},
        headers={"Authorization": "Bearer fake-token"}
    )

    # Assert
    assert response.status_code == 200 # 200 OK for an existing resource
    assert response.json()["name"] == "Existing User"
    mock_get_user.assert_awaited_once()

# Teardown
def teardown_module(module):
    app.dependency_overrides = {}

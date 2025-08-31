import pytest
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from unittest.mock import patch

# Now that the file exists, this import should work
from api.auth import get_current_user, User

app = FastAPI()

@app.get("/test-secure", response_model=User)
def secure_endpoint(current_user: User = Depends(get_current_user)):
    return current_user

client = TestClient(app)

# The correct path to patch is where 'auth' is USED, which is in 'api.auth'
AUTH_MODULE_PATH = 'api.auth.auth'

@patch(f'{AUTH_MODULE_PATH}.verify_id_token')
def test_get_current_user_valid_token(mock_verify_id_token):
    # Arrange
    mock_decoded_token = {'uid': 'test_uid', 'email': 'test@example.com'}
    mock_verify_id_token.return_value = mock_decoded_token
    
    headers = {"Authorization": "Bearer fake-token"}

    # Act
    response = client.get("/test-secure", headers=headers)

    # Assert
    assert response.status_code == 200
    assert response.json() == {"uid": "test_uid", "email": "test@example.com"}
    mock_verify_id_token.assert_called_once_with("fake-token")

def test_get_current_user_no_authorization_header():
    # Act
    response = client.get("/test-secure")

    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()['detail'] == "Not authenticated"

def test_get_current_user_invalid_bearer_scheme():
    # Arrange
    headers = {"Authorization": "NotBearer fake-token"}

    # Act
    response = client.get("/test-secure", headers=headers)

    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    # The detail comes from the OAuth2PasswordBearer dependency itself when auto_error=True
    # Since we set auto_error=False, our custom message should appear.
    assert response.json()['detail'] == "Not authenticated"


@patch(f'{AUTH_MODULE_PATH}.verify_id_token')
def test_get_current_user_firebase_auth_error(mock_verify_id_token):
    # Arrange
    from firebase_admin import auth
    mock_verify_id_token.side_effect = auth.InvalidIdTokenError("Invalid token")
    headers = {"Authorization": "Bearer fake-token"}

    # Act
    response = client.get("/test-secure", headers=headers)

    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid authentication credentials" in response.json()['detail']

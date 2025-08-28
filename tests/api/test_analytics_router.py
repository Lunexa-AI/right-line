import pytest
from fastapi.testclient import TestClient
from api.main import app
from libs.common.settings import get_settings

@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()

client = TestClient(app)

def test_get_analytics_end_to_end_success():
    """
    Tests the /api/v1/analytics endpoint for a successful response in an end-to-end scenario.
    """
    # Arrange
    settings = get_settings()
    api_key = settings.secret_key[:16]
    
    # Act
    response = client.get(f"/api/v1/analytics?api_key={api_key}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "total_queries" in data
    assert "unique_users" in data

def test_get_analytics_end_to_end_unauthorized():
    """
    Tests the /api/v1/analytics endpoint for a 401 error with an invalid API key.
    """
    # Act
    response = client.get("/api/v1/analytics?api_key=invalid_key")
    
    # Assert
    assert response.status_code == 401

def test_get_common_queries_end_to_end_success():
    """
    Tests the /api/v1/analytics/common-queries endpoint for a successful response.
    """
    # Arrange
    settings = get_settings()
    api_key = settings.secret_key[:16]

    # Act
    response = client.get(f"/api/v1/analytics/common-queries?api_key={api_key}")
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "queries" in data

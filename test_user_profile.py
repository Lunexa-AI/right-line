#!/usr/bin/env python3
"""
Test script to verify the GET /api/v1/users/me endpoint works.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from api.main import app
from api.auth import User, get_current_user


def override_get_current_user():
    """Override authentication for testing."""
    return User(uid="2ijv2UP4zZdXeTj4QqfHOTlkL5Y2", email="test.credentials@example.com")


def test_get_user_profile():
    """Test the GET user profile endpoint."""
    
    # Override authentication
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Create test client
    client = TestClient(app)
    
    print("Testing GET /api/v1/users/me...")
    print("-" * 50)
    
    try:
        # Make the API call
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer test-token"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ User profile retrieved successfully!")
            print(f"UID: {data.get('uid', 'N/A')}")
            print(f"Email: {data.get('email', 'N/A')}")
            print(f"Name: {data.get('name', 'N/A')}")
            print(f"Created At: {data.get('created_at', 'N/A')}")
            
        elif response.status_code == 404:
            print(f"❌ User profile not found (expected for new users)")
            print(f"Response: {response.text}")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error making request: {e}")
    
    finally:
        # Clean up the override
        app.dependency_overrides = {}
        print("\n" + "=" * 50)
        print("Test completed.")


if __name__ == "__main__":
    test_get_user_profile()

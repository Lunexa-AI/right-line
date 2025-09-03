#!/usr/bin/env python3
"""
Test script to check if the Firestore profile was created for the test user.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from api.main import app
from api.auth import User, get_current_user


def override_get_current_user():
    """Override authentication for testing with the created user."""
    return User(uid="Zvf2K4jIPiT0815CSxRFwaAxeXz1", email="atomic.test@example.com")


def test_profile_exists():
    """Test if the Firestore profile was created."""
    
    # Override authentication
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    client = TestClient(app)
    
    print("🔍 Checking if Firestore profile exists...")
    print("-" * 50)
    
    try:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer test-token"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Profile EXISTS! Atomic signup worked!")
            print(f"UID: {data.get('uid')}")
            print(f"Email: {data.get('email')}")
            print(f"Name: {data.get('name')}")
            print(f"Created At: {data.get('created_at')}")
            
        elif response.status_code == 404:
            print("❌ Profile NOT FOUND! Rollback might have occurred or Firestore creation failed")
            print(f"Response: {response.text}")
            
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        # Clean up the override
        app.dependency_overrides = {}
        print("\n" + "=" * 50)
        print("Profile check completed.")


if __name__ == "__main__":
    test_profile_exists()

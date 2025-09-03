#!/usr/bin/env python3
"""
Comprehensive test script to debug the atomic signup process.
This will test each component and the integration.
"""

import sys
import json
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from api.main import app

def test_signup_with_detailed_logging():
    """Test signup with detailed logging to see exactly what's happening."""
    
    client = TestClient(app)
    
    print("🧪 Testing Atomic Signup Process")
    print("=" * 60)
    
    # Test 1: Email signup
    print("\n📧 Testing Email Signup...")
    email_payload = {
        "method": "email",
        "name": "Atomic Test User",
        "email": "atomic.test@example.com", 
        "password": "testpass123"
    }
    
    print(f"Request payload: {json.dumps(email_payload, indent=2)}")
    
    try:
        response = client.post(
            "/api/v1/signup",
            json=email_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 201:
            data = response.json()
            print("✅ Email signup SUCCESS!")
            print(f"User ID: {data.get('user_id')}")
            print(f"Email: {data.get('email')}")
            
            # Test if profile exists
            print("\n🔍 Testing if Firestore profile was created...")
            # We can't test this directly without auth, but we can check logs
            
        elif response.status_code == 422:
            print("❌ Validation Error (422)")
            error_data = response.json()
            print(f"Validation errors: {json.dumps(error_data, indent=2)}")
            
        elif response.status_code == 400:
            print("❌ Bad Request (400)")
            error_data = response.json()
            print(f"Error: {error_data.get('detail', 'Unknown error')}")
            
        else:
            print(f"❌ Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
    
    # Test 2: Validation errors
    print("\n🚫 Testing Validation Errors...")
    invalid_payload = {
        "method": "email",
        "name": "Test User"
        # Missing email and password
    }
    
    try:
        response = client.post(
            "/api/v1/signup",
            json=invalid_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Invalid request status: {response.status_code}")
        if response.status_code == 422:
            print("✅ Validation correctly rejected invalid request")
            error_data = response.json()
            print(f"Validation errors: {json.dumps(error_data, indent=2)}")
        else:
            print(f"❌ Expected 422, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed. Check server logs for detailed execution flow.")


if __name__ == "__main__":
    test_signup_with_detailed_logging()

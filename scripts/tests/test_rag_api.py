#!/usr/bin/env python3
"""
test_rag_api.py - Test the RAG-enabled API endpoint

This script tests the /api/v1/query endpoint to ensure the RAG integration
is working correctly with real queries.

Usage:
    python scripts/test_rag_api.py [--query TEXT] [--verbose]

Author: RightLine Team
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

# Test queries to verify different scenarios
TEST_QUERIES = [
    {
        "text": "What are the rights of employees regarding working hours?",
        "channel": "web",
        "description": "Employment rights query"
    },
    {
        "text": "termination of employment",
        "channel": "web", 
        "description": "Employment termination query"
    },
    {
        "text": "minimum wage in Zimbabwe",
        "channel": "web",
        "description": "Wage information query"
    },
    {
        "text": "What happens if I don't get paid overtime?",
        "channel": "web",
        "description": "Specific employment scenario"
    }
]

async def test_api_endpoint(query_data: dict, base_url: str = "http://localhost:8000", verbose: bool = False):
    """Test a single query against the API endpoint."""
    print(f"🔍 Testing: {query_data['description']}")
    print(f"📝 Query: {query_data['text']}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/api/v1/query",
                json=query_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"✅ Success!")
                print(f"📈 Confidence: {data.get('confidence', 'N/A'):.3f}")
                print(f"🏷️  Source: {data.get('source', 'N/A')}")
                print(f"⏱️  Processing Time: {data.get('processing_time_ms', 'N/A')}ms")
                print(f"📋 TL;DR: {data.get('tldr', 'N/A')}")
                
                if verbose:
                    print(f"🔑 Key Points:")
                    for i, point in enumerate(data.get('key_points', []), 1):
                        print(f"  {i}. {point}")
                    
                    print(f"💡 Suggestions:")
                    for i, suggestion in enumerate(data.get('suggestions', []), 1):
                        print(f"  {i}. {suggestion}")
                    
                    print(f"📚 Citations: {len(data.get('citations', []))}")
                    for i, citation in enumerate(data.get('citations', []), 1):
                        print(f"  {i}. {citation.get('title', 'Unknown')}")
                
                return True
                
            else:
                print(f"❌ Failed with status {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    finally:
        print("-" * 50)

async def test_health_endpoint(base_url: str = "http://localhost:8000"):
    """Test the health endpoint to ensure the server is running."""
    print("🏥 Testing health endpoint...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/healthz")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Server is healthy: {data.get('status')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Make sure the API server is running on localhost:8000")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Test RAG-enabled API endpoint")
    parser.add_argument("--query", type=str, help="Single query to test")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", 
                        help="Base URL of the API server")
    parser.add_argument("--verbose", action="store_true", help="Print detailed responses")
    parser.add_argument("--health-only", action="store_true", help="Only test health endpoint")
    
    args = parser.parse_args()
    
    print("🚀 Testing RightLine RAG API")
    print("=" * 50)
    
    # Test health first
    health_ok = await test_health_endpoint(args.base_url)
    if not health_ok:
        print("\n❌ Server is not accessible. Please start the API server first.")
        print("Run: python api/main.py")
        sys.exit(1)
    
    if args.health_only:
        print("\n🎉 Health check completed!")
        return
    
    print()
    
    success_count = 0
    total_tests = 0
    
    if args.query:
        # Test single query
        query_data = {
            "text": args.query,
            "channel": "web",
            "description": "Custom query"
        }
        success = await test_api_endpoint(query_data, args.base_url, args.verbose)
        total_tests = 1
        success_count = 1 if success else 0
    else:
        # Test all predefined queries
        for query_data in TEST_QUERIES:
            success = await test_api_endpoint(query_data, args.base_url, args.verbose)
            total_tests += 1
            if success:
                success_count += 1
            
            # Small delay between tests
            await asyncio.sleep(1)
    
    print(f"\n📊 Test Results: {success_count}/{total_tests} passed")
    
    if success_count == total_tests:
        print("🎉 All tests passed! RAG API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

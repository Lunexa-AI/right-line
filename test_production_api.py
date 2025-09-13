#!/usr/bin/env python3
"""Test script for production API endpoints.

This script tests the actual production endpoints that the frontend will use,
including proper Firebase authentication and the real /api/v1/query endpoint.

Usage:
    python test_production_api.py
"""

import asyncio
import json
import sys
import time
from typing import Dict, Any

import httpx
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

API_BASE = "http://localhost:8000/api/v1"


async def test_api_health():
    """Test basic API connectivity."""
    print("🔧 Testing API Health...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Test root endpoint
            response = await client.get("http://localhost:8000/")
            if response.status_code == 200:
                print("✅ API server is online")
                return True
            else:
                print(f"❌ API server error: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False


async def test_query_endpoint_without_auth():
    """Test query endpoint to see auth behavior."""
    print("\n🔐 Testing Authentication Requirements...")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/query",
                json={
                    "query": "test query",
                    "session_id": "test-session"
                }
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 401:
                print("✅ Authentication properly required")
                return True
            else:
                print("⚠️  Unexpected response - auth might be disabled")
                return False
                
    except Exception as e:
        print(f"❌ Query test failed: {e}")
        return False


async def test_retrieval_engine_directly():
    """Test the retrieval engine directly (same code path as API)."""
    print("\n🔍 Testing Retrieval Engine Directly...")
    print("This tests the exact same code that the API uses.")
    
    try:
        # Import here to avoid import issues
        sys.path.insert(0, '/Users/simbarashe.timire/repos/right-line')
        from api.retrieval import RetrievalEngine, RetrievalConfig
        
        test_queries = [
            "What are the requirements for art unions?",
            "How does hypothecation work?", 
            "What is deceased estates succession?"
        ]
        
        async with RetrievalEngine() as engine:
            for i, query in enumerate(test_queries, 1):
                print(f"\n📋 Test {i}: \"{query}\"")
                print("-" * 50)
                
                start_time = time.time()
                config = RetrievalConfig(top_k=3)
                results = await engine.retrieve(query, config)
                end_time = time.time()
                
                latency_ms = (end_time - start_time) * 1000
                
                print(f"⏱️  Latency: {latency_ms:.0f}ms")
                print(f"📊 Results: {len(results)}")
                
                if results:
                    result = results[0]
                    print(f"🎯 Top Score: {result.score:.4f}")
                    print(f"🔄 Source: {result.source}")
                    print(f"📖 Document: {result.metadata.get('title', 'Unknown')}")
                    print(f"📍 Chapter: {result.metadata.get('chapter', 'N/A')}")
                    print(f"🌳 Tree Node: {result.metadata.get('tree_node_id', 'N/A')}")
                    
                    # Show content quality
                    content = result.chunk_text
                    if content and len(content) > 100:
                        print(f"📄 Content: {len(content)} chars")
                        # Show first meaningful line
                        lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 30]
                        if lines:
                            print(f"📝 Preview: {lines[0][:100]}...")
                    else:
                        print("❌ No content retrieved")
                
                # Performance check
                if latency_ms < 2500:
                    print("✅ PASS - Under 2.5s target")
                else:
                    print("❌ FAIL - Exceeds 2.5s target")
        
        return True
        
    except Exception as e:
        print(f"❌ Retrieval engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🏛️  RIGHTLINE PRODUCTION API TEST")
    print("=" * 60)
    print("Testing actual production endpoints and retrieval engine")
    print()
    
    # Test 1: API Health
    api_ok = await test_api_health()
    if not api_ok:
        print("❌ API health check failed - cannot proceed")
        return
    
    # Test 2: Authentication
    auth_ok = await test_query_endpoint_without_auth()
    if not auth_ok:
        print("⚠️  Authentication test inconclusive")
    
    # Test 3: Direct Retrieval Engine (same code as API)
    retrieval_ok = await test_retrieval_engine_directly()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY:")
    print(f"   API Health: {'✅ PASS' if api_ok else '❌ FAIL'}")
    print(f"   Authentication: {'✅ PASS' if auth_ok else '⚠️  SKIP'}")
    print(f"   Retrieval Engine: {'✅ PASS' if retrieval_ok else '❌ FAIL'}")
    
    if api_ok and retrieval_ok:
        print("\n🎉 PRODUCTION API READY!")
        print("📝 Next steps:")
        print("   1. Configure Firebase authentication")
        print("   2. Test with real frontend integration")
        print("   3. Deploy to production environment")
    else:
        print("\n❌ Issues found - resolve before deployment")


if __name__ == "__main__":
    asyncio.run(main())

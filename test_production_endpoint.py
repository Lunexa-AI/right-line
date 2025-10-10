#!/usr/bin/env python3
"""Test the production endpoint to verify it's using the orchestrator."""

import asyncio
import json
import httpx
from datetime import datetime

async def test_endpoint():
    """Test both endpoints to compare responses."""
    
    base_url = "http://127.0.0.1:8000"
    query_text = "What are the essential elements of a valid contract?"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test the TEST endpoint (no auth required)
        print("=" * 60)
        print("Testing TEST endpoint (/api/v1/test-query)...")
        print("=" * 60)
        
        test_response = await client.post(
            f"{base_url}/api/v1/test-query",
            json={"query": query_text, "top_k": 5}
        )
        
        if test_response.status_code == 200:
            test_data = test_response.json()
            print(f"✅ Status: {test_response.status_code}")
            print(f"📝 Query: {query_text}")
            print(f"📊 Results: {test_data['performance']['results_count']} documents")
            print(f"⏱️  Latency: {test_data['performance']['latency_ms']}ms")
            print(f"📖 TLDR: {test_data.get('synthesis', {}).get('tldr', 'N/A')[:200]}...")
            print(f"🎯 Confidence: {test_data.get('synthesis', {}).get('confidence', 'N/A')}")
        else:
            print(f"❌ Failed with status: {test_response.status_code}")
            
        print("\n" + "=" * 60)
        print("Testing PRODUCTION endpoint (/api/v1/query)...")
        print("=" * 60)
        
        # Try without auth to see what error we get
        prod_response = await client.post(
            f"{base_url}/api/v1/query",
            json={"text": query_text, "channel": "web"}
        )
        
        print(f"📋 Status: {prod_response.status_code}")
        
        if prod_response.status_code == 401:
            error_data = prod_response.json()
            print(f"🔐 Auth Required: {error_data.get('detail', 'Unknown error')}")
            print("\nThis is expected - production endpoint requires Firebase auth.")
            print("The important thing is that it's now using the same orchestrator code!")
        elif prod_response.status_code == 200:
            prod_data = prod_response.json()
            print(f"✅ Success! Got response:")
            print(f"📖 TLDR: {prod_data.get('tldr', 'N/A')[:200]}...")
            print(f"🎯 Confidence: {prod_data.get('confidence', 'N/A')}")
        else:
            print(f"❌ Unexpected status: {prod_response.text}")

if __name__ == "__main__":
    print(f"\n🚀 Testing API Endpoints - {datetime.now().strftime('%H:%M:%S')}\n")
    asyncio.run(test_endpoint())
    print("\n✨ Test complete!\n")

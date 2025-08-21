#!/usr/bin/env python3
"""
test_api_retrieval.py - Test the API retrieval functionality

This script tests the api/retrieval.py module to ensure it's properly
connected to our Milvus collection and can retrieve relevant chunks.

Usage:
    python scripts/test_api_retrieval.py [--query TEXT] [--top-k INT] [--verbose]

Author: RightLine Team
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import structlog
from dotenv import load_dotenv

# Add the project root to Python path so we can import from api/
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from api.retrieval import search_legal_documents, RetrievalConfig, RetrievalEngine
except ImportError as e:
    print(f"❌ Error importing API modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

# Load environment variables
load_dotenv(".env.local")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

async def test_retrieval_engine(query: str, top_k: int = 5, verbose: bool = False):
    """Test the RetrievalEngine directly."""
    print(f"🔍 Testing RetrievalEngine with query: '{query}'")
    print(f"📊 Requesting top {top_k} results\n")
    
    try:
        async with RetrievalEngine() as engine:
            # Test retrieval
            config = RetrievalConfig(top_k=top_k, min_score=0.1)
            results = await engine.retrieve(query, config)
            confidence = engine.calculate_confidence(results)
            
            print(f"✅ Retrieval completed successfully!")
            print(f"📈 Confidence: {confidence:.3f}")
            print(f"📋 Results: {len(results)}\n")
            
            # Display results
            for i, result in enumerate(results, 1):
                print(f"Result {i}:")
                print(f"  🎯 Score: {result.score:.4f}")
                print(f"  📄 Doc ID: {result.doc_id}")
                print(f"  🔗 Chunk ID: {result.chunk_id}")
                print(f"  🏷️  Source: {result.source}")
                
                # Show metadata if verbose
                if verbose and result.metadata:
                    metadata = result.metadata
                    if 'title' in metadata:
                        print(f"  📖 Title: {metadata['title']}")
                    if 'section_path' in metadata:
                        print(f"  📍 Section: {metadata['section_path']}")
                
                # Show chunk text (truncated)
                chunk_text = result.chunk_text.strip()
                if len(chunk_text) > 300:
                    chunk_text = chunk_text[:300] + "..."
                print(f"  📝 Text: {chunk_text}")
                print()
            
            return results, confidence
            
    except Exception as e:
        print(f"❌ Error during retrieval: {e}")
        if verbose:
            import traceback
            print(traceback.format_exc())
        return [], 0.0

async def test_convenience_function(query: str, top_k: int = 5):
    """Test the convenience search_legal_documents function."""
    print(f"🔍 Testing search_legal_documents function with query: '{query}'\n")
    
    try:
        results, confidence = await search_legal_documents(
            query=query,
            top_k=top_k,
            min_score=0.1
        )
        
        print(f"✅ Search completed successfully!")
        print(f"📈 Confidence: {confidence:.3f}")
        print(f"📋 Results: {len(results)}\n")
        
        return results, confidence
        
    except Exception as e:
        print(f"❌ Error during search: {e}")
        return [], 0.0

async def test_date_filtering(query: str, date_filter: str = "2020-01-01"):
    """Test date filtering functionality."""
    print(f"🗓️  Testing date filtering with query: '{query}' (date: {date_filter})\n")
    
    try:
        results, confidence = await search_legal_documents(
            query=query,
            top_k=5,
            date_filter=date_filter,
            min_score=0.1
        )
        
        print(f"✅ Date-filtered search completed!")
        print(f"📈 Confidence: {confidence:.3f}")
        print(f"📋 Results: {len(results)}\n")
        
        return results, confidence
        
    except Exception as e:
        print(f"❌ Error during date-filtered search: {e}")
        return [], 0.0

async def main():
    parser = argparse.ArgumentParser(description="Test API retrieval functionality")
    parser.add_argument("--query", type=str, default="What are the rights of employees regarding working hours?",
                        help="Search query text")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of results to return")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("--test-all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    # Check environment variables
    required_vars = ["MILVUS_ENDPOINT", "MILVUS_TOKEN", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Make sure to set them in .env.local or export them")
        sys.exit(1)
    
    print("🚀 Testing RightLine API Retrieval System")
    print("=" * 50)
    
    if args.test_all:
        # Test 1: RetrievalEngine
        print("TEST 1: RetrievalEngine")
        print("-" * 30)
        await test_retrieval_engine(args.query, args.top_k, args.verbose)
        
        print("\n" + "=" * 50)
        
        # Test 2: Convenience function
        print("TEST 2: Convenience Function")
        print("-" * 30)
        await test_convenience_function("termination of employment", 3)
        
        print("\n" + "=" * 50)
        
        # Test 3: Date filtering (though our current data might not have effective dates)
        print("TEST 3: Date Filtering")
        print("-" * 30)
        await test_date_filtering("employment rights", "2020-01-01")
        
    else:
        # Just test the main query
        await test_retrieval_engine(args.query, args.top_k, args.verbose)
    
    print("\n🎉 Testing completed!")

if __name__ == "__main__":
    asyncio.run(main())

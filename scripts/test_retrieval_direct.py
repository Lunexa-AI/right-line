#!/usr/bin/env python3
"""
test_retrieval_direct.py - Test the retrieval functionality directly

This script tests the retrieval functionality by directly importing
the retrieval module without going through the main API settings.

Usage:
    python scripts/test_retrieval_direct.py [--query TEXT] [--verbose]

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

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv(".env.local")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

# Now import the retrieval components directly
try:
    from api.retrieval import RetrievalEngine, RetrievalConfig
except ImportError as e:
    print(f"❌ Error importing retrieval module: {e}")
    sys.exit(1)

async def test_retrieval_direct(query: str, top_k: int = 5, verbose: bool = False):
    """Test the RetrievalEngine directly without going through main API."""
    print(f"🔍 Testing RetrievalEngine directly with query: '{query}'")
    print(f"📊 Requesting top {top_k} results\n")
    
    # Check required environment variables
    required_vars = {
        "MILVUS_ENDPOINT": os.getenv("MILVUS_ENDPOINT"),
        "MILVUS_TOKEN": os.getenv("MILVUS_TOKEN"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return
    
    print("✅ Environment variables configured:")
    for k, v in required_vars.items():
        masked_value = v[:10] + "..." + v[-5:] if v and len(v) > 15 else v
        print(f"  {k}: {masked_value}")
    print()
    
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
                if len(chunk_text) > 250:
                    chunk_text = chunk_text[:250] + "..."
                print(f"  📝 Text: {chunk_text}")
                print()
            
            return results, confidence
            
    except Exception as e:
        print(f"❌ Error during retrieval: {e}")
        if verbose:
            import traceback
            print(traceback.format_exc())
        return [], 0.0

async def main():
    parser = argparse.ArgumentParser(description="Test retrieval functionality directly")
    parser.add_argument("--query", type=str, default="What are the rights of employees regarding working hours?",
                        help="Search query text")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of results to return")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    print("🚀 Testing RightLine Retrieval Engine (Direct)")
    print("=" * 50)
    
    await test_retrieval_direct(args.query, args.top_k, args.verbose)
    
    print("\n🎉 Testing completed!")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
test_retrieval_standalone.py - Test retrieval functionality standalone

This script tests the retrieval functionality by importing the retrieval
module directly without any dependencies on the main API settings.

Usage:
    python scripts/test_retrieval_standalone.py [--query TEXT] [--verbose]

Author: RightLine Team
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog
from dotenv import load_dotenv
from pymilvus import Collection, connections

# Load environment variables
load_dotenv(".env.local")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

# Configuration from environment
MILVUS_ENDPOINT = os.environ.get("MILVUS_ENDPOINT")
MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN")
MILVUS_COLLECTION_NAME = os.environ.get("MILVUS_COLLECTION_NAME", "legal_chunks")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

class SimpleRetrievalResult:
    """Simple result from document retrieval."""
    
    def __init__(self, chunk_id: str, chunk_text: str, doc_id: str, metadata: Dict[str, Any], score: float):
        self.chunk_id = chunk_id
        self.chunk_text = chunk_text
        self.doc_id = doc_id
        self.metadata = metadata
        self.score = score
        self.source = "vector"

async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for text using OpenAI API."""
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_EMBEDDING_MODEL,
                    "input": text[:8000],  # Truncate to avoid token limits
                    "encoding_format": "float"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                
                logger.info(
                    "Embedding generated",
                    model=OPENAI_EMBEDDING_MODEL,
                    input_length=len(text),
                    embedding_dim=len(embedding)
                )
                
                return embedding
            else:
                logger.error(
                    "OpenAI embedding failed",
                    status=response.status_code,
                    response=response.text[:200]
                )
                return None
                
    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        return None

async def search_milvus(query_vector: List[float], top_k: int = 5) -> List[SimpleRetrievalResult]:
    """Search for similar chunks in Milvus."""
    if not MILVUS_ENDPOINT or not MILVUS_TOKEN:
        logger.warning("Milvus credentials not configured")
        return []
    
    try:
        # Connect to Milvus
        connections.connect(
            alias="default",
            uri=MILVUS_ENDPOINT,
            token=MILVUS_TOKEN,
            timeout=10,
        )
        
        # Get collection
        collection = Collection(MILVUS_COLLECTION_NAME)
        collection.load()
        
        logger.info("Connected to Milvus", collection=MILVUS_COLLECTION_NAME)
        
        # Build search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64}
        }
        
        # Perform search
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["doc_id", "chunk_text", "metadata"]
        )
        
        # Convert to SimpleRetrievalResult objects
        retrieval_results = []
        for hit in results[0]:
            retrieval_results.append(SimpleRetrievalResult(
                chunk_id=str(hit.id),
                chunk_text=hit.entity.get("chunk_text", ""),
                doc_id=hit.entity.get("doc_id", ""),
                metadata=hit.entity.get("metadata", {}),
                score=float(hit.score)
            ))
        
        logger.info(
            "Vector search completed", 
            results_count=len(retrieval_results),
            top_score=retrieval_results[0].score if retrieval_results else 0
        )
        
        return retrieval_results
        
    except Exception as e:
        logger.error("Vector search failed", error=str(e))
        return []
    finally:
        try:
            connections.disconnect("default")
        except:
            pass

async def test_retrieval(query: str, top_k: int = 5, verbose: bool = False):
    """Test the retrieval functionality."""
    print(f"🔍 Testing retrieval with query: '{query}'")
    print(f"📊 Requesting top {top_k} results\n")
    
    # Check required environment variables
    required_vars = {
        "MILVUS_ENDPOINT": MILVUS_ENDPOINT,
        "MILVUS_TOKEN": MILVUS_TOKEN,
        "OPENAI_API_KEY": OPENAI_API_KEY,
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        return
    
    print("✅ Environment variables configured:")
    for k, v in required_vars.items():
        if v:
            masked_value = v[:10] + "..." + v[-5:] if len(v) > 15 else v
            print(f"  {k}: {masked_value}")
    print()
    
    start_time = time.time()
    
    try:
        # Generate embedding
        print("🔄 Generating embedding...")
        embedding = await get_embedding(query)
        
        if not embedding:
            print("❌ Failed to generate embedding")
            return
        
        print(f"✅ Generated embedding with {len(embedding)} dimensions")
        
        # Search Milvus
        print("🔍 Searching Milvus...")
        results = await search_milvus(embedding, top_k)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        print(f"✅ Retrieval completed in {elapsed_ms}ms!")
        print(f"📋 Results: {len(results)}\n")
        
        # Display results
        for i, result in enumerate(results, 1):
            print(f"Result {i}:")
            print(f"  🎯 Score: {result.score:.4f}")
            print(f"  📄 Doc ID: {result.doc_id}")
            print(f"  🔗 Chunk ID: {result.chunk_id}")
            
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
        
        return results
        
    except Exception as e:
        print(f"❌ Error during retrieval: {e}")
        if verbose:
            import traceback
            print(traceback.format_exc())
        return []

async def main():
    parser = argparse.ArgumentParser(description="Test retrieval functionality standalone")
    parser.add_argument("--query", type=str, default="What are the rights of employees regarding working hours?",
                        help="Search query text")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of results to return")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    print("🚀 Testing RightLine Retrieval (Standalone)")
    print("=" * 50)
    
    await test_retrieval(args.query, args.top_k, args.verbose)
    
    print("\n🎉 Testing completed!")

if __name__ == "__main__":
    asyncio.run(main())

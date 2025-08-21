#!/usr/bin/env python3
"""
test_milvus_search.py - Test searching in Milvus collection

This script connects to Milvus, performs a simple search, and prints the results.

Usage:
    python scripts/test_milvus_search.py [--query TEXT] [--limit INT] [--verbose]

Author: RightLine Team
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict, List

import structlog
from dotenv import load_dotenv

try:
    from pymilvus import (
        connections,
        Collection,
        utility
    )
    import openai
except ImportError:
    print("❌ Error: Required libraries not installed. Run: pip install pymilvus openai")
    sys.exit(1)

# Load environment variables from .env.local
load_dotenv(".env.local")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

def get_milvus_config() -> Dict[str, Any]:
    """Get Milvus configuration from environment variables."""
    config = {
        "endpoint": os.getenv("MILVUS_ENDPOINT"),
        "token": os.getenv("MILVUS_TOKEN"),
        "collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks"),
    }
    
    if not config["endpoint"]:
        raise ValueError("MILVUS_ENDPOINT environment variable not set")
    
    if not config["token"]:
        raise ValueError("MILVUS_TOKEN environment variable not set")
    
    return config

def get_openai_config() -> Dict[str, Any]:
    """Get OpenAI configuration from environment variables."""
    config = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    }
    
    if not config["api_key"]:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    return config

def connect_to_milvus(endpoint: str, token: str) -> None:
    """Connect to Milvus Cloud."""
    connections.connect(
        alias="default",
        uri=endpoint,
        token=token
    )

def generate_query_embedding(client: openai.OpenAI, query: str, model: str) -> List[float]:
    """Generate embedding for the search query."""
    response = client.embeddings.create(
        model=model,
        input=[query]
    )
    return response.data[0].embedding

def search_milvus(collection: Collection, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
    """Search for similar chunks in Milvus."""
    search_params = {
        "metric_type": "COSINE",
        "params": {"ef": 64}
    }
    
    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=limit,
        output_fields=["doc_id", "chunk_text", "doc_type", "language", "court", "date_context", "metadata"]
    )
    
    # Convert results to list of dicts
    search_results = []
    for hit in results[0]:
        result = {
            "score": hit.score,
            "doc_id": hit.entity.get("doc_id"),
            "chunk_text": hit.entity.get("chunk_text"),
            "doc_type": hit.entity.get("doc_type"),
            "language": hit.entity.get("language"),
            "court": hit.entity.get("court"),
            "date_context": hit.entity.get("date_context"),
            "metadata": hit.entity.get("metadata"),
        }
        search_results.append(result)
    
    return search_results

def main():
    parser = argparse.ArgumentParser(description="Test searching in Milvus collection")
    parser.add_argument("--query", type=str, default="What are employee rights regarding working hours?",
                        help="Search query text")
    parser.add_argument("--limit", type=int, default=5,
                        help="Number of search results to return")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    try:
        # Get configurations
        milvus_config = get_milvus_config()
        openai_config = get_openai_config()
        
        # Connect to Milvus
        logger.info(f"Connecting to Milvus Cloud: {milvus_config['endpoint']}")
        connect_to_milvus(milvus_config["endpoint"], milvus_config["token"])
        
        # Check if collection exists
        collection_name = milvus_config["collection_name"]
        if not utility.has_collection(collection_name):
            logger.error(f"❌ Collection '{collection_name}' does not exist.")
            sys.exit(1)
        
        # Get collection
        collection = Collection(collection_name)
        collection.load()
        
        # Get collection stats
        stats = collection.num_entities
        logger.info(f"Collection '{collection_name}' has {stats} entities")
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=openai_config["api_key"])
        
        # Generate query embedding
        logger.info(f"Generating embedding for query: '{args.query}'")
        query_embedding = generate_query_embedding(
            client, 
            args.query, 
            openai_config["embedding_model"]
        )
        
        # Search Milvus
        logger.info(f"Searching for top {args.limit} similar chunks...")
        results = search_milvus(collection, query_embedding, args.limit)
        
        # Print results
        print(f"\n🔍 Search Results for: '{args.query}'")
        print(f"Found {len(results)} results:\n")
        
        for i, result in enumerate(results, 1):
            print(f"Result {i}:")
            print(f"  Score: {result['score']:.4f}")
            print(f"  Doc ID: {result['doc_id']}")
            print(f"  Doc Type: {result['doc_type']}")
            print(f"  Language: {result['language']}")
            if result['court']:
                print(f"  Court: {result['court']}")
            if result['date_context']:
                print(f"  Date: {result['date_context']}")
            
            # Print metadata if available
            if result['metadata'] and args.verbose:
                metadata = result['metadata']
                if 'title' in metadata:
                    print(f"  Title: {metadata['title']}")
                if 'section_path' in metadata:
                    print(f"  Section: {metadata['section_path']}")
            
            # Print chunk text (truncated)
            chunk_text = result['chunk_text']
            if len(chunk_text) > 200:
                chunk_text = chunk_text[:200] + "..."
            print(f"  Text: {chunk_text}")
            print()
        
        logger.info("✅ Search test completed successfully")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Disconnect from Milvus
        connections.disconnect("default")

if __name__ == "__main__":
    main()

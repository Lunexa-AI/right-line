#!/usr/bin/env python3
"""
debug_milvus_upsert.py - Debug and fix Milvus upsert issues

This script helps debug issues with upserting chunks to Milvus by:
1. Loading chunks from a JSONL file
2. Printing detailed information about the chunks
3. Attempting to upsert a single chunk to diagnose issues

Usage:
    python scripts/debug_milvus_upsert.py [--input_file PATH] [--chunk_index INT]

Author: RightLine Team
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import structlog
from dotenv import load_dotenv

try:
    from pymilvus import (
        connections,
        Collection,
        utility
    )
except ImportError:
    print("❌ Error: pymilvus not installed. Run: pip install pymilvus")
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

def connect_to_milvus(endpoint: str, token: str) -> None:
    """Connect to Milvus Cloud."""
    connections.connect(
        alias="default",
        uri=endpoint,
        token=token
    )

def debug_chunk(chunk: Dict[str, Any]) -> None:
    """Print debug information about a chunk."""
    print("\n=== Chunk Debug Information ===")
    print(f"chunk_id: {chunk.get('chunk_id')}")
    print(f"doc_id: {chunk.get('doc_id')}")
    
    # Check doc_type
    doc_type = chunk.get('doc_type')
    print(f"doc_type: {doc_type}")
    if isinstance(doc_type, str):
        print(f"  - Length: {len(doc_type)}")
    else:
        print(f"  - Type: {type(doc_type)}")
    
    # Check language
    language = chunk.get('language')
    print(f"language: {language}")
    if isinstance(language, str):
        print(f"  - Length: {len(language)}")
    
    # Check court
    court = chunk.get('court')
    print(f"court: {court}")
    if isinstance(court, str):
        print(f"  - Length: {len(court)}")
    
    # Check date_context
    date_context = chunk.get('date_context')
    print(f"date_context: {date_context}")
    if isinstance(date_context, str):
        print(f"  - Length: {len(date_context)}")
    
    # Check chunk_text
    chunk_text = chunk.get('chunk_text')
    print(f"chunk_text: {chunk_text[:50]}...")
    if isinstance(chunk_text, str):
        print(f"  - Length: {len(chunk_text)}")
    
    # Check embedding
    embedding = chunk.get('embedding')
    if embedding:
        print(f"embedding: [...]")
        print(f"  - Length: {len(embedding)}")
    
    # Check metadata
    metadata = chunk.get('metadata')
    print(f"metadata: {type(metadata)}")
    if metadata:
        print(f"  - Keys: {list(metadata.keys()) if isinstance(metadata, dict) else 'Not a dict'}")

def try_upsert_single_chunk(collection: Collection, chunk: Dict[str, Any]) -> None:
    """Try to upsert a single chunk to Milvus."""
    print("\n=== Attempting to upsert single chunk ===")
    
    try:
        # Prepare data
        doc_id = chunk.get("doc_id")
        chunk_text = chunk.get("chunk_text")
        embedding = chunk.get("embedding")
        doc_type = chunk.get("doc_type", "unknown")[:20]  # Ensure max length 20
        language = chunk.get("language", "eng")[:10]      # Ensure max length 10
        court = chunk.get("court", "unknown")[:100]       # Ensure max length 100
        date_context = chunk.get("date_context", "unknown")[:32]  # Ensure max length 32
        metadata = chunk.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        
        print(f"Prepared fields:")
        print(f"  - doc_id: {doc_id}")
        print(f"  - doc_type: {doc_type} (length: {len(doc_type)})")
        print(f"  - language: {language} (length: {len(language)})")
        print(f"  - court: {court} (length: {len(court)})")
        print(f"  - date_context: {date_context} (length: {len(date_context)})")
        print(f"  - metadata: {type(metadata)}")
        
        # Insert single chunk
        collection.insert([
            [doc_id],
            [chunk_text],
            [doc_type],
            [language],
            [court],
            [date_context],
            [embedding],
            [metadata]
        ])
        
        print("✅ Successfully upserted single chunk to Milvus")
        
    except Exception as e:
        print(f"❌ Error upserting chunk: {e}")
        import traceback
        print(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description="Debug Milvus upsert issues")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks_with_embeddings_fixed.jsonl", 
                        help="Path to input JSONL file with embeddings")
    parser.add_argument("--chunk_index", type=int, default=0,
                        help="Index of the chunk to debug (default: 0)")
    
    args = parser.parse_args()
    
    try:
        # Load chunks
        chunks = []
        with open(args.input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        logger.info(f"Loaded {len(chunks)} chunks from {args.input_file}")
        
        if args.chunk_index >= len(chunks):
            logger.error(f"Chunk index {args.chunk_index} is out of range (max: {len(chunks) - 1})")
            sys.exit(1)
        
        # Get chunk to debug
        chunk = chunks[args.chunk_index]
        debug_chunk(chunk)
        
        # Connect to Milvus
        config = get_milvus_config()
        logger.info(f"Connecting to Milvus Cloud: {config['endpoint']}")
        connect_to_milvus(config["endpoint"], config["token"])
        
        # Check if collection exists
        collection_name = config["collection_name"]
        if not utility.has_collection(collection_name):
            logger.error(f"❌ Collection '{collection_name}' does not exist. Run init-milvus.py first.")
            sys.exit(1)
        
        # Get collection
        collection = Collection(collection_name)
        
        # Load collection
        logger.info(f"Loading collection '{collection_name}'...")
        collection.load()
        
        # Try to upsert single chunk
        try_upsert_single_chunk(collection, chunk)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Disconnect from Milvus
        connections.disconnect("default")

if __name__ == "__main__":
    main()

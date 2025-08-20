#!/usr/bin/env python3
"""
milvus_upsert.py - Upload chunks with embeddings to Milvus Cloud

This script implements Task 7 from the INGESTION_AND_CHUNKING_TASKLIST.md.
It reads chunks with embeddings from chunks_with_embeddings.jsonl and 
upserts them into the Milvus collection.

Usage:
    python scripts/milvus_upsert.py [--input_file PATH] [--batch_size INT] [--verbose]

Author: RightLine Team
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from dotenv import load_dotenv
from tqdm import tqdm

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

# Default configuration
DEFAULT_BATCH_SIZE = 100

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

def upload_to_milvus(collection: Collection, data: List[Dict[str, Any]], batch_size: int = 100, verbose: bool = False) -> None:
    """
    Upload chunks with embeddings to Milvus.
    
    Args:
        collection: Milvus collection
        data: List of chunks with embeddings
        batch_size: Number of chunks to upload in each batch
        verbose: Whether to print verbose output
    """
    total_batches = (len(data) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading to Milvus", unit="batch"):
        batch = data[i:i + batch_size]
        
        # Prepare batch data
        doc_ids = []
        chunk_texts = []
        embeddings = []
        doc_types = []
        languages = []
        courts = []
        date_contexts = []
        metadatas = []
        
        for item in batch:
            doc_ids.append(item["doc_id"])
            chunk_texts.append(item["chunk_text"])
            embeddings.append(item["embedding"])
            doc_types.append(item.get("doc_type", "unknown"))
            languages.append(item.get("language", "eng"))
            courts.append(item.get("court", "unknown"))
            date_contexts.append(item.get("date_context", "unknown"))
            
            # Ensure metadata is a dict
            metadata = item.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            metadatas.append(metadata)
        
        # Insert batch
        try:
            collection.insert([
                doc_ids,
                chunk_texts,
                doc_types,
                languages, 
                courts,
                date_contexts,
                embeddings,
                metadatas
            ])
            
            if verbose:
                logger.info(f"Uploaded batch {i//batch_size + 1}/{total_batches}")
        except Exception as e:
            logger.error(f"❌ Error uploading batch {i//batch_size + 1}: {e}")
            if verbose:
                import traceback
                logger.error(traceback.format_exc())
            raise
    
    # Flush to ensure data is persisted
    collection.flush()
    logger.info(f"✅ Successfully uploaded {len(data)} chunks to Milvus")

def main():
    parser = argparse.ArgumentParser(description="Upload chunks with embeddings to Milvus Cloud")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks_with_embeddings.jsonl", 
                        help="Path to input JSONL file with embeddings")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Number of chunks to upload in each batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    try:
        # Load chunks with embeddings
        chunks = []
        with open(args.input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        logger.info(f"Loaded {len(chunks)} chunks with embeddings from {args.input_file}")
        
        # Get Milvus configuration
        config = get_milvus_config()
        
        # Connect to Milvus
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
        
        # Upload chunks to Milvus
        logger.info(f"Uploading {len(chunks)} chunks to Milvus...")
        upload_to_milvus(collection, chunks, args.batch_size, args.verbose)
        
        # Log statistics
        logger.info(f"Milvus upload statistics:")
        logger.info(f"  Total chunks: {len(chunks)}")
        logger.info(f"  Collection: {collection_name}")
        
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

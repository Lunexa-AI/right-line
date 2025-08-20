#!/usr/bin/env python3
"""
milvus_upsert.py - Upload embedded chunks to Milvus Cloud

This script implements Task 7 from the INGESTION_AND_CHUNKING_TASKLIST.md.
It reads chunks with embeddings from chunks_with_embeddings.jsonl,
and upserts them into Milvus Cloud.

Usage:
    python scripts/milvus_upsert.py [--input_file PATH] [--batch_size INT] [--verbose]

Author: RightLine Team
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from dotenv import load_dotenv
from pymilvus import Collection, connections, utility
from tqdm import tqdm

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
DEFAULT_COLLECTION_NAME = "legal_chunks"

def connect_to_milvus() -> None:
    """Connect to Milvus Cloud using environment variables."""
    endpoint = os.getenv("MILVUS_ENDPOINT")
    token = os.getenv("MILVUS_TOKEN")
    
    if not endpoint or not token:
        raise ValueError("MILVUS_ENDPOINT and MILVUS_TOKEN environment variables must be set")
    
    connections.connect(
        alias="default",
        uri=endpoint,
        token=token,
        secure=True,
    )
    logger.info(f"Connected to Milvus at {endpoint}")

def get_collection(collection_name: str = DEFAULT_COLLECTION_NAME) -> Collection:
    """Get the Milvus collection, creating it if it doesn't exist."""
    if not utility.has_collection(collection_name):
        raise ValueError(f"Collection {collection_name} does not exist. Run scripts/init-milvus.py first.")
    
    collection = Collection(collection_name)
    collection.load()
    logger.info(f"Loaded collection {collection_name}")
    
    return collection

def prepare_batch_data(batch: List[Dict[str, Any]]) -> Dict[str, List]:
    """
    Prepare batch data for Milvus upsert.
    
    Args:
        batch: List of chunk documents
        
    Returns:
        Dictionary of field names to lists of values
    """
    batch_data = {
        "doc_id": [],
        "chunk_text": [],
        "embedding": [],
        "doc_type": [],
        "language": [],
        "court": [],
        "date_context": [],
        "metadata": [],
    }
    
    for chunk in batch:
        # Required fields
        batch_data["doc_id"].append(chunk["doc_id"])
        batch_data["chunk_text"].append(chunk["chunk_text"])
        batch_data["embedding"].append(chunk.get("embedding", [0.0] * 1536))  # Default empty embedding if missing
        
        # Optional fields with defaults
        batch_data["doc_type"].append(chunk.get("doc_type", "unknown"))
        batch_data["language"].append(chunk.get("language", "eng"))
        
        # Court field - try to get from metadata or entities
        court = None
        if "metadata" in chunk and "court" in chunk["metadata"]:
            court = chunk["metadata"]["court"]
        elif "entities" in chunk and "courts" in chunk["entities"] and chunk["entities"]["courts"]:
            court = chunk["entities"]["courts"][0]
        batch_data["court"].append(court or "unknown")
        
        # Date context
        batch_data["date_context"].append(chunk.get("date_context", "unknown"))
        
        # Metadata - combine all useful fields
        metadata = {
            "section_path": chunk.get("section_path", ""),
            "source_url": chunk.get("source_url", ""),
            "title": chunk.get("metadata", {}).get("title", ""),
            "canonical_citation": chunk.get("metadata", {}).get("canonical_citation", ""),
        }
        
        # Add entities to metadata
        if "entities" in chunk:
            metadata["entities"] = chunk["entities"]
            
        batch_data["metadata"].append(metadata)
    
    return batch_data

def upsert_chunks(
    input_file: Path, 
    collection_name: str = DEFAULT_COLLECTION_NAME,
    batch_size: int = DEFAULT_BATCH_SIZE,
    verbose: bool = False
) -> None:
    """
    Upsert chunks from input file to Milvus.
    
    Args:
        input_file: Path to input JSONL file
        collection_name: Name of Milvus collection
        batch_size: Number of chunks to upsert in each batch
        verbose: Whether to print verbose output
    """
    try:
        # Connect to Milvus
        connect_to_milvus()
        collection = get_collection(collection_name)
        
        # Load chunks
        chunks = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        logger.info(f"Loaded {len(chunks)} chunks from {input_file}")
        
        # Process chunks in batches
        total_chunks = len(chunks)
        successful_chunks = 0
        failed_chunks = 0
        
        for i in tqdm(range(0, total_chunks, batch_size), desc="Upserting to Milvus"):
            batch = chunks[i:i+batch_size]
            
            try:
                # Prepare batch data
                batch_data = prepare_batch_data(batch)
                
                # Upsert batch
                insert_result = collection.insert(batch_data)
                successful_chunks += len(batch)
                
                if verbose:
                    logger.info(f"Upserted batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}")
                    logger.info(f"  Batch size: {len(batch)}")
                    logger.info(f"  Insert result: {insert_result}")
                
                # Small delay to avoid overwhelming the server
                time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error upserting batch {i//batch_size + 1}: {e}")
                if verbose:
                    import traceback
                    logger.error(traceback.format_exc())
                
                failed_chunks += len(batch)
        
        # Flush to ensure all data is written
        collection.flush()
        
        # Log statistics
        success_rate = successful_chunks / total_chunks * 100 if total_chunks else 0
        logger.info(f"Milvus upsert statistics:")
        logger.info(f"  Total chunks: {total_chunks}")
        logger.info(f"  Successful chunks: {successful_chunks} ({success_rate:.2f}%)")
        logger.info(f"  Failed chunks: {failed_chunks} ({100 - success_rate:.2f}%)")
        
        # Query to verify
        if successful_chunks > 0:
            count = collection.num_entities
            logger.info(f"Collection now contains {count} entities")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # Close connection
        connections.disconnect("default")

def main():
    parser = argparse.ArgumentParser(description="Upload embedded chunks to Milvus Cloud")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks_with_embeddings.jsonl", 
                        help="Path to input JSONL file")
    parser.add_argument("--collection_name", type=str, default=DEFAULT_COLLECTION_NAME,
                        help=f"Name of Milvus collection (default: {DEFAULT_COLLECTION_NAME})")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Number of chunks to upsert in each batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    upsert_chunks(
        args.input_file, 
        args.collection_name,
        args.batch_size,
        args.verbose
    )

if __name__ == "__main__":
    main()

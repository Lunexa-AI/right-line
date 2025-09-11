#!/usr/bin/env python3
"""
cleanup_milvus_duplicates.py - Remove duplicate entries from Milvus collection

This script identifies and removes duplicate chunk_ids from the Milvus collection,
keeping only the first occurrence of each chunk.

Usage:
    python scripts/cleanup_milvus_duplicates.py [--dry_run]

Author: RightLine Team
"""

import argparse
import os
import sys
from collections import Counter
from typing import Dict, Any, List

import structlog
from dotenv import load_dotenv

try:
    from pymilvus import connections, Collection, utility
except ImportError:
    print("❌ Error: pymilvus not installed. Run: pip install pymilvus")
    sys.exit(1)

# Load environment variables
load_dotenv(".env.local")

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger()

def get_config() -> Dict[str, Any]:
    """Get Milvus configuration from environment variables."""
    config = {
        "endpoint": os.getenv("MILVUS_ENDPOINT"),
        "token": os.getenv("MILVUS_TOKEN"),
        "collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks_v2"),
    }
    
    for key, value in config.items():
        if not value:
            raise ValueError(f"{key.upper()} environment variable not set")
    
    return config

def find_and_remove_duplicates(collection: Collection, dry_run: bool = True) -> None:
    """Find and remove duplicate chunk_ids, keeping only the first occurrence."""
    
    logger.info("🔍 Analyzing collection for duplicates...")
    
    # Query all records to find duplicates (with pagination due to 16k limit)
    try:
        all_results = []
        limit = 16000  # Stay under 16,384 limit
        offset = 0
        
        while True:
            results = collection.query(
                expr="chunk_id != ''",
                output_fields=["chunk_id"],
                limit=limit,
                offset=offset
            )
            
            if not results:
                break
                
            all_results.extend(results)
            offset += len(results)
            
            if len(results) < limit:
                break  # No more results
        
        results = all_results
        
        logger.info(f"📊 Found {len(results)} total entities")
        
        # Count occurrences of each chunk_id
        chunk_id_counts = Counter(item["chunk_id"] for item in results)
        duplicates = {chunk_id: count for chunk_id, count in chunk_id_counts.items() if count > 1}
        
        if not duplicates:
            logger.info("✅ No duplicates found!")
            return
        
        logger.info(f"🎯 Found {len(duplicates)} chunk_ids with duplicates:")
        total_duplicates = sum(count - 1 for count in duplicates.values())  # -1 because we keep one
        
        for chunk_id, count in duplicates.items():
            logger.info(f"  - {chunk_id}: {count} occurrences ({count-1} to remove)")
        
        logger.info(f"📈 Total duplicate entities to remove: {total_duplicates}")
        
        if dry_run:
            logger.info("🔍 DRY RUN - No changes made. Use --execute to actually remove duplicates.")
            return
        
        # Remove duplicates by deleting specific chunk_ids that appear multiple times
        removed_count = 0
        for chunk_id, count in duplicates.items():
            if count > 1:
                # Delete all instances of this chunk_id
                collection.delete(expr=f'chunk_id == "{chunk_id}"')
                removed_count += count
                logger.info(f"🗑️  Deleted all {count} instances of {chunk_id}")
        
        # Flush changes
        collection.flush()
        
        logger.info(f"✅ Removed {removed_count} duplicate entities")
        logger.info(f"📊 Collection now has {collection.num_entities} entities")
        
    except Exception as e:
        logger.error(f"❌ Error during deduplication: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Remove duplicate chunks from Milvus collection")
    parser.add_argument("--execute", action="store_true", 
                        help="Actually remove duplicates (default is dry run)")
    
    args = parser.parse_args()
    
    try:
        # Get configuration
        config = get_config()
        
        # Connect to Milvus
        logger.info(f"🔌 Connecting to Milvus: {config['endpoint']}")
        connections.connect(
            alias="default",
            uri=config["endpoint"],
            token=config["token"]
        )
        
        # Get collection
        collection_name = config["collection_name"]
        if not utility.has_collection(collection_name):
            logger.error(f"❌ Collection '{collection_name}' does not exist")
            sys.exit(1)
        
        collection = Collection(collection_name)
        collection.load()
        
        logger.info(f"📊 Collection '{collection_name}' has {collection.num_entities} entities")
        
        # Find and remove duplicates
        find_and_remove_duplicates(collection, dry_run=not args.execute)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)
    
    finally:
        connections.disconnect("default")

if __name__ == "__main__":
    main()

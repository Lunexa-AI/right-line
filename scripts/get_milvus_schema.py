#!/usr/bin/env python3
"""
get_milvus_schema.py - Get the schema of a Milvus collection

This script connects to Milvus and prints the schema of a collection.

Usage:
    python scripts/get_milvus_schema.py [--collection_name NAME]

Author: RightLine Team
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict

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

def main():
    parser = argparse.ArgumentParser(description="Get the schema of a Milvus collection")
    parser.add_argument("--collection_name", type=str, default=None,
                        help="Name of the collection to get schema for (default: from env)")
    
    args = parser.parse_args()
    
    try:
        # Get Milvus configuration
        config = get_milvus_config()
        
        # Override collection name if provided
        if args.collection_name:
            config["collection_name"] = args.collection_name
        
        # Connect to Milvus
        logger.info(f"Connecting to Milvus Cloud: {config['endpoint']}")
        connect_to_milvus(config["endpoint"], config["token"])
        
        # Check if collection exists
        collection_name = config["collection_name"]
        if not utility.has_collection(collection_name):
            logger.error(f"❌ Collection '{collection_name}' does not exist.")
            sys.exit(1)
        
        # Get collection
        collection = Collection(collection_name)
        
        # Get schema
        schema = collection.schema
        
        # Print schema
        print(f"\n=== Schema for collection '{collection_name}' ===")
        print(f"Description: {schema.description}")
        print(f"Auto ID: {schema.auto_id}")
        print(f"Fields:")
        
        for i, field in enumerate(schema.fields):
            print(f"  {i}. {field.name}")
            print(f"     - Type: {field.dtype}")
            print(f"     - Description: {field.description}")
            print(f"     - Is primary: {field.is_primary}")
            if hasattr(field, "max_length") and field.max_length is not None:
                print(f"     - Max length: {field.max_length}")
            if hasattr(field, "dim") and field.dim is not None:
                print(f"     - Dimensions: {field.dim}")
        
        # Get indexes
        print("\n=== Indexes ===")
        indexes = collection.indexes
        for index in indexes:
            print(f"Field: {index.field_name}")
            print(f"  - Index type: {index.params.get('index_type')}")
            print(f"  - Metric type: {index.params.get('metric_type')}")
            print(f"  - Parameters: {index.params.get('params', {})}")
        
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

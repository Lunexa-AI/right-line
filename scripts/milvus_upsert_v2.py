#!/usr/bin/env python3
"""
milvus_upsert_v2.py - Upload chunks with embeddings to Milvus Cloud v2.0 Schema

This script implements the v2.0 "Small-to-Big" architecture for Task 2.4.
It reads small chunks from R2, generates embeddings, and upserts them into 
the new Milvus collection schema optimized for retrieval.

Key features:
- Reads chunks directly from R2 (not local files)
- Generates embeddings using OpenAI API in batches
- Uses new v2.0 schema with chunk_id as primary key
- Supports parallel processing for faster embedding generation
- Only stores lightweight metadata (chunk content retrieved from R2 later)

Usage:
    python scripts/milvus_upsert_v2.py [--max_chunks INT] [--batch_size INT] [--verbose]

Author: RightLine Team
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional
from tqdm import tqdm

import boto3
import openai
import structlog
from dotenv import load_dotenv

# Import chunk model
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.models import ChunkV3 as Chunk

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
DEFAULT_MAX_CHUNKS = None
EMBEDDING_BATCH_SIZE = 50  # OpenAI API batch size for embedding generation


def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    config = {
        # Milvus
        "milvus_endpoint": os.getenv("MILVUS_ENDPOINT"),
        "milvus_token": os.getenv("MILVUS_TOKEN"),
        "milvus_collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks_v2"),
        
        # R2
        "r2_endpoint": os.getenv("R2_ENDPOINT") or os.getenv("CLOUDFLARE_R2_S3_ENDPOINT"),
        "r2_access_key": os.getenv("R2_ACCESS_KEY_ID") or os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID"),
        "r2_secret_key": os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
        "r2_bucket": os.getenv("R2_BUCKET_NAME") or os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents"),
        
        # OpenAI
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
    }
    
    # Validate required settings
    required_fields = [
        ("milvus_endpoint", "MILVUS_ENDPOINT"),
        ("milvus_token", "MILVUS_TOKEN"),
        ("r2_endpoint", "R2_ENDPOINT or CLOUDFLARE_R2_S3_ENDPOINT"),
        ("r2_access_key", "R2_ACCESS_KEY_ID or CLOUDFLARE_R2_ACCESS_KEY_ID"),
        ("r2_secret_key", "R2_SECRET_ACCESS_KEY or CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
        ("openai_api_key", "OPENAI_API_KEY"),
    ]
    
    for field_name, env_var in required_fields:
        if not config[field_name]:
            raise ValueError(f"{env_var} environment variable not set")
    
    return config


def create_r2_client(endpoint: str, access_key: str, secret_key: str):
    """Create R2 client."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",  # R2 uses 'auto' region
    )


def connect_to_milvus(endpoint: str, token: str) -> None:
    """Connect to Milvus Cloud."""
    connections.connect(
        alias="default",
        uri=endpoint,
        token=token
    )


def list_chunks_from_r2(r2_client, bucket: str, prefix: str = "corpus/chunks/") -> List[str]:
    """List all chunk object keys from R2."""
    chunk_keys = []
    paginator = r2_client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                if obj['Key'].endswith('.json'):
                    chunk_keys.append(obj['Key'])
    
    return chunk_keys


def load_chunk_from_r2(r2_client, bucket: str, chunk_key: str) -> Dict[str, Any]:
    """Load a single chunk from R2and add required fields."""
    try:
        response = r2_client.get_object(Bucket=bucket, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))  # Load as dict
        
        # Add the R2 object key to the chunk data (required by Milvus schema)
        chunk_data['chunk_object_key'] = chunk_key
        
        # Add source_document_key from metadata if available
        if 'metadata' in chunk_data and 'r2_pdf_key' in chunk_data['metadata']:
            chunk_data['source_document_key'] = chunk_data['metadata']['r2_pdf_key']
        else:
            chunk_data['source_document_key'] = chunk_data.get('source_url', '')
        
        return chunk_data  # Return dict instead of model instance
    except Exception as e:
        logger.error(f"Error loading chunk {chunk_key} from R2: {e}")
        return None


def generate_embeddings_batch(texts: List[str], model: str = "text-embedding-3-large") -> List[List[float]]:
    """Generate embeddings for a batch of texts using OpenAI API."""
    try:
        # Initialize OpenAI client with explicit API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.embeddings.create(
            input=texts,
            model=model
        )
        
        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]
        return embeddings
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise


def generate_parent_doc_id_from_chunk(chunk: Dict[str, Any]) -> str:
    """Generate parent_doc_id that matches chunk_docs.py logic."""
    try:
        # Get required fields from chunk
        doc_id = chunk.get('doc_id', '')
        section_path = chunk.get('section_path', '')
        chunk_text = chunk.get('chunk_text', '')
        
        if not all([doc_id, section_path, chunk_text]):
            # Fallback to doc_id if we can't generate proper parent_doc_id
            return doc_id
        
        # Replicate chunk_docs.py generate_chunk_id logic for parent docs
        # parent_doc_id = generate_chunk_id(doc_id, section_path, 0, len(section_content), section_content)
        import hashlib
        
        # Create deterministic ID using same algorithm as chunk_docs.py
        content_hash = hashlib.sha256(chunk_text.encode('utf-8')).hexdigest()[:8]
        id_components = f"{doc_id}_{section_path}_0_{len(chunk_text)}_{content_hash}"
        parent_doc_id = hashlib.sha256(id_components.encode('utf-8')).hexdigest()[:16]
        
        return parent_doc_id
        
    except Exception as e:
        logger.warning("Failed to generate parent_doc_id, using doc_id fallback", error=str(e))
        return chunk.get('doc_id', chunk.get('chunk_id', ''))

def transform_chunk_for_milvus_v2(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Transform chunk data to match v3.0 Milvus schema with PageIndex tree support."""
    # Extract source document key from chunk metadata
    metadata = chunk.get('metadata', {})
    source_document_key = metadata.get('source_document_key') or metadata.get('r2_pdf_key', '')
    
    # Use parent_doc_id directly from chunk (no generation needed)
    parent_doc_id = chunk.get('parent_doc_id', chunk.get('doc_id', ''))
    
    transformed = {
        "chunk_id": chunk.get('chunk_id', ''),
        "embedding": chunk.get('embedding', []),  # Will be populated by embedding generation
        "num_tokens": chunk.get('num_tokens', 0),
        "doc_type": (chunk.get('doc_type', 'unknown')[:20]),  # Truncate to max length
        "language": (chunk.get('language', 'eng')[:10]),  # Truncate to max length
        "parent_doc_id": parent_doc_id[:64],  # Truncate to max length
        "tree_node_id": chunk.get('tree_node_id', '')[:16],  # NEW: PageIndex node reference
        "chunk_object_key": chunk.get('chunk_object_key', ''),
        "source_document_key": source_document_key,
        "nature": (chunk.get('nature', '') or '')[:32],  # Truncate to max length
        "year": chunk.get('year', 0) or 0,
        "chapter": (chunk.get('chapter', '') or '')[:16],  # Truncate to max length
        "date_context": (chunk.get('date_context', '') or '')[:32],  # Truncate to max length
    }
    
    # Ensure all required fields have valid values
    if not transformed["chunk_id"]:
        raise ValueError("chunk_id is required")
    if not transformed["chunk_object_key"]:
        raise ValueError("chunk_object_key is required")
    
    return transformed


def upload_to_milvus_v2(collection: Collection, data: List[Dict[str, Any]], batch_size: int = 100, verbose: bool = False, skip_duplicates: bool = True) -> None:
    """Upload chunks with embeddings to Milvus v2.0 collection."""
    
    # Filter out existing chunks if skip_duplicates is True
    if skip_duplicates:
        logger.info("Checking for existing chunks to avoid duplicates...")
        existing_chunk_ids = set()
        
        # Get all existing chunk_ids from the collection
        try:
            # Query all chunk_ids in the collection
            results = collection.query(
                expr="chunk_id != ''",  # Get all records
                output_fields=["chunk_id"],
                limit=100000  # Adjust if you have more chunks
            )
            existing_chunk_ids = {item["chunk_id"] for item in results}
            logger.info(f"Found {len(existing_chunk_ids)} existing chunks in collection")
        except Exception as e:
            logger.warning(f"Could not check existing chunks: {e}. Proceeding with insert...")
            existing_chunk_ids = set()
        
        # Filter out chunks that already exist
        original_count = len(data)
        data = [chunk for chunk in data if chunk["chunk_id"] not in existing_chunk_ids]
        filtered_count = len(data)
        
        if original_count != filtered_count:
            logger.info(f"Filtered out {original_count - filtered_count} existing chunks. Processing {filtered_count} new chunks.")
        
        if not data:
            logger.info("No new chunks to upload.")
            return
    
    total_batches = (len(data) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading to Milvus", unit="batch"):
        batch = data[i:i + batch_size]
        
        # Prepare batch data according to v2.0 schema field order
        chunk_ids = []
        embeddings = []
        num_tokens_list = []
        doc_types = []
        languages = []
        parent_doc_ids = []
        tree_node_ids = []
        chunk_object_keys = []
        source_document_keys = []
        natures = []
        years = []
        chapters = []
        date_contexts = []
        
        for item in batch:
            chunk_ids.append(item["chunk_id"])
            embeddings.append(item["embedding"])
            num_tokens_list.append(item["num_tokens"])
            doc_types.append(item["doc_type"])
            languages.append(item["language"])
            parent_doc_ids.append(item["parent_doc_id"])
            tree_node_ids.append(item["tree_node_id"])
            chunk_object_keys.append(item["chunk_object_key"])
            source_document_keys.append(item["source_document_key"])
            natures.append(item["nature"])
            years.append(item["year"])
            chapters.append(item["chapter"])
            date_contexts.append(item["date_context"])
        
        # Insert batch with correct field order matching schema
        try:
            collection.insert([
                chunk_ids,
                embeddings,
                num_tokens_list,
                doc_types,
                languages,
                parent_doc_ids,
                tree_node_ids,
                chunk_object_keys,
                source_document_keys,
                natures,
                years,
                chapters,
                date_contexts
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
    logger.info(f"✅ Successfully uploaded {len(data)} chunks to Milvus v2.0")


def main():
    parser = argparse.ArgumentParser(description="Upload chunks with embeddings to Milvus Cloud v2.0")
    parser.add_argument("--max_chunks", type=int, default=DEFAULT_MAX_CHUNKS,
                        help="Maximum number of chunks to process (for testing)")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Number of chunks to upload in each batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("--clear_collection", action="store_true", 
                        help="Clear the collection before uploading (removes duplicates)")
    parser.add_argument("--force_duplicates", action="store_true",
                        help="Allow duplicate uploads (skip deduplication check)")
    
    args = parser.parse_args()
    
    try:
        # Get configuration
        config = get_config()
        
        # Create R2 client
        logger.info("Creating R2 client...")
        r2_client = create_r2_client(
            config["r2_endpoint"], 
            config["r2_access_key"], 
            config["r2_secret_key"]
        )
        
        # List all chunks in R2
        logger.info("Listing chunks from R2...")
        chunk_keys = list_chunks_from_r2(r2_client, config["r2_bucket"])
        logger.info(f"Found {len(chunk_keys)} chunks in R2")
        
        if args.max_chunks:
            chunk_keys = chunk_keys[:args.max_chunks]
            logger.info(f"Limited to {len(chunk_keys)} chunks for testing")
        
        # Load chunks from R2
        logger.info("Loading chunks from R2...")
        chunks: List[Dict[str, Any]] = []
        failed_chunks = 0
        
        for chunk_key in tqdm(chunk_keys, desc="Loading chunks"):
            chunk_data = load_chunk_from_r2(r2_client, config["r2_bucket"], chunk_key)
            if chunk_data:
                chunks.append(chunk_data)
            else:
                failed_chunks += 1
        
        logger.info(f"Loaded {len(chunks)} chunks successfully, {failed_chunks} failed")
        
        if not chunks:
            logger.error("No chunks loaded. Exiting.")
            sys.exit(1)
        
        # Generate embeddings in batches
        logger.info("Generating embeddings...")
        
        # Extract texts for embedding
        texts = [chunk['chunk_text'] for chunk in chunks]
        all_embeddings = []
        
        # Process in batches to avoid API limits
        for i in tqdm(range(0, len(texts), EMBEDDING_BATCH_SIZE), desc="Generating embeddings"):
            batch_texts = texts[i:i + EMBEDDING_BATCH_SIZE]
            batch_embeddings = generate_embeddings_batch(batch_texts, config["openai_embedding_model"])
            all_embeddings.extend(batch_embeddings)
        
        logger.info(f"Generated {len(all_embeddings)} embeddings")
        
        # Add embeddings to chunks and transform for Milvus
        logger.info("Transforming chunks for Milvus v2.0...")
        milvus_chunks = []
        
        for chunk_dict, embedding in zip(chunks, all_embeddings):
            try:
                # Add embedding to chunk data
                chunk_dict['embedding'] = embedding
                transformed_chunk = transform_chunk_for_milvus_v2(chunk_dict)
                milvus_chunks.append(transformed_chunk)
            except Exception as e:
                logger.error(f"Error transforming chunk {chunk_dict.get('chunk_id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Transformed {len(milvus_chunks)} chunks for Milvus")
        
        # Connect to Milvus
        logger.info(f"Connecting to Milvus Cloud: {config['milvus_endpoint']}")
        connect_to_milvus(config["milvus_endpoint"], config["milvus_token"])
        
        # Check if collection exists
        collection_name = config["milvus_collection_name"]
        if not utility.has_collection(collection_name):
            logger.error(f"❌ Collection '{collection_name}' does not exist. Run init-milvus-v2.py first.")
            sys.exit(1)
        
        # Get collection
        collection = Collection(collection_name)
        
        # Load collection into memory
        logger.info(f"Loading collection '{collection_name}'...")
        collection.load()
        
        # Clear collection if requested
        if args.clear_collection:
            logger.info("🧹 Clearing collection to remove all existing data...")
            try:
                collection.delete(expr="chunk_id != ''")  # Delete all records
                collection.flush()
                logger.info(f"✅ Collection cleared. Current entities: {collection.num_entities}")
            except Exception as e:
                logger.error(f"❌ Error clearing collection: {e}")
        
        # Upload chunks to Milvus (with deduplication unless forced)
        skip_duplicates = not args.force_duplicates
        logger.info(f"Uploading {len(milvus_chunks)} chunks to Milvus (deduplication: {skip_duplicates})...")
        upload_to_milvus_v2(collection, milvus_chunks, args.batch_size, args.verbose, skip_duplicates=skip_duplicates)
        
        # Log final statistics
        total_count = collection.num_entities
        logger.info(f"✅ Upload complete!")
        logger.info(f"   Processed chunks: {len(chunks)}")
        logger.info(f"   Generated embeddings: {len(all_embeddings)}")
        logger.info(f"   Uploaded to Milvus: {len(milvus_chunks)}")
        logger.info(f"   Total entities in collection: {total_count}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)
        
    finally:
        # Disconnect from Milvus
        try:
            connections.disconnect("default")
        except:
            pass


if __name__ == "__main__":
    main()

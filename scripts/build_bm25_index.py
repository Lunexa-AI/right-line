#!/usr/bin/env python3
"""
build_bm25_index.py - Build and save BM25 index from R2 corpus for lightning-fast sparse search

This script implements production-grade BM25 index preprocessing for Task 3.1.
It builds a highly optimized BM25 index from the corpus in R2 and saves it
for fast loading during API requests.

Key features:
- Reads all chunks from R2 corpus
- Advanced tokenization optimized for legal documents
- Builds rank-bm25 index with optimal parameters
- Saves index with pickle for fast loading
- Performance optimizations for 50K+ document corpus

Usage:
    python scripts/build_bm25_index.py [--output_file PATH] [--max_docs INT] [--verbose]

Author: RightLine Team  
"""

import argparse
import asyncio
import json
import logging
import os
import pickle
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import structlog
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
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
DEFAULT_OUTPUT_FILE = "data/processed/bm25_index.pkl"
DEFAULT_MAX_DOCS = None

# R2 configuration from environment  
R2_ENDPOINT = os.environ.get("R2_ENDPOINT") or os.environ.get("CLOUDFLARE_R2_S3_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME") or os.environ.get("CLOUDFLARE_R2_BUCKET_NAME", "gweta-prod-documents")

# BM25 configuration - optimized for legal documents
BM25_K1 = 1.5  # Term frequency saturation parameter
BM25_B = 0.75  # Length normalization parameter


def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    config = {
        "r2_endpoint": R2_ENDPOINT,
        "r2_access_key": R2_ACCESS_KEY, 
        "r2_secret_key": R2_SECRET_KEY,
        "r2_bucket": R2_BUCKET_NAME,
    }
    
    # Validate required settings
    required_fields = [
        ("r2_endpoint", "R2_ENDPOINT or CLOUDFLARE_R2_S3_ENDPOINT"),
        ("r2_access_key", "R2_ACCESS_KEY_ID or CLOUDFLARE_R2_ACCESS_KEY_ID"),
        ("r2_secret_key", "R2_SECRET_ACCESS_KEY or CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
    ]
    
    for field_name, env_var in required_fields:
        if not config[field_name]:
            raise ValueError(f"{env_var} environment variable not set")
    
    return config


def create_r2_client(endpoint: str, access_key: str, secret_key: str):
    """Create R2 client for accessing corpus."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",  # R2 uses 'auto' region
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


def load_chunk_from_r2(r2_client, bucket: str, chunk_key: str) -> Optional[Dict[str, Any]]:
    """Load a single chunk from R2."""
    try:
        response = r2_client.get_object(Bucket=bucket, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))
        return chunk_data
    except Exception as e:
        logger.error(f"Error loading chunk {chunk_key} from R2: {e}")
        return None


def optimize_tokenize_legal_text(text: str) -> List[str]:
    """
    Advanced tokenization optimized for legal document analysis.
    
    Features:
    - Preserves legal citations and references
    - Handles section numbers and legal formatting
    - Optimized for BM25 performance
    
    Args:
        text: Raw text to tokenize
        
    Returns:
        List of optimized tokens for legal document search
    """
    if not text:
        return []
    
    # Convert to lowercase for case-insensitive matching
    text = text.lower()
    
    # Preserve important legal patterns
    # Keep section references like "section 5", "s. 12", "sec 15a"
    text = re.sub(r'\bs\.?\s*(\d+[a-z]?)\b', r'section\1', text)
    text = re.sub(r'\bsec\.?\s*(\d+[a-z]?)\b', r'section\1', text)
    
    # Keep chapter references like "[chapter 28:01]"
    text = re.sub(r'\[chapter\s+([0-9:]+)\]', r'chapter\1', text)
    
    # Keep court citations and case numbers
    text = re.sub(r'\[(\d{4})\]\s*([a-z]+)\s*(\d+)', r'\1\2\3', text)
    
    # Basic tokenization - split on non-alphanumeric, keep numbers and letters
    tokens = re.findall(r'\b[a-z0-9]+\b', text)
    
    # Filter out very short tokens and common stop words
    legal_stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 
        'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
        'that', 'the', 'to', 'was', 'will', 'with'
    }
    
    filtered_tokens = [
        token for token in tokens 
        if len(token) >= 2 and token not in legal_stop_words
    ]
    
    # Limit token count for performance (BM25 works best with 50-200 tokens per doc)
    return filtered_tokens[:200]


def build_bm25_index_from_r2(
    r2_client, 
    bucket: str, 
    max_docs: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Build BM25 index from chunks stored in R2.
    
    Args:
        r2_client: Boto3 R2 client
        bucket: R2 bucket name
        max_docs: Maximum number of chunks to process (for testing)
        verbose: Enable verbose logging
        
    Returns:
        Dict containing BM25 index data and metadata
    """
    start_time = time.time()
    
    # List all chunks from R2
    logger.info("Listing chunks from R2...")
    chunk_keys = list_chunks_from_r2(r2_client, bucket)
    logger.info(f"Found {len(chunk_keys)} chunks in R2")
    
    if max_docs:
        chunk_keys = chunk_keys[:max_docs]
        logger.info(f"Limited to {max_docs} chunks for testing")
    
    # Load chunks and build corpus
    logger.info("Loading chunks and building corpus...")
    corpus_texts = []
    chunk_metadata = []
    failed_loads = 0
    
    for chunk_key in tqdm(chunk_keys, desc="Loading chunks"):
        chunk_data = load_chunk_from_r2(r2_client, bucket, chunk_key)
        
        if chunk_data:
            chunk_text = chunk_data.get("chunk_text", "")
            if chunk_text:
                # Optimize tokenization for legal text
                tokens = optimize_tokenize_legal_text(chunk_text)
                corpus_texts.append(tokens)
                
                # Store metadata for result mapping
                chunk_metadata.append({
                    "chunk_id": chunk_data.get("chunk_id", ""),
                    "doc_id": chunk_data.get("doc_id", ""),
                    "parent_doc_id": chunk_data.get("doc_id", ""),  # For small-to-big
                    "chunk_object_key": chunk_key,
                    "doc_type": chunk_data.get("doc_type", ""),
                    "metadata": chunk_data.get("metadata", {})
                })
            else:
                failed_loads += 1
        else:
            failed_loads += 1
    
    logger.info(f"Loaded {len(corpus_texts)} chunks successfully, {failed_loads} failed")
    
    if not corpus_texts:
        raise ValueError("No valid chunks loaded for BM25 index building")
    
    # Build BM25 index
    logger.info("Building BM25 index...")
    bm25_start = time.time()
    
    bm25_index = BM25Okapi(
        corpus_texts,
        k1=BM25_K1,
        b=BM25_B
    )
    
    bm25_build_time = time.time() - bm25_start
    logger.info(f"BM25 index built in {bm25_build_time:.2f} seconds")
    
    # Prepare index data for serialization
    index_data = {
        "bm25_index": bm25_index,
        "chunk_metadata": chunk_metadata,
        "corpus_size": len(corpus_texts),
        "build_timestamp": time.time(),
        "build_duration_seconds": time.time() - start_time,
        "parameters": {
            "k1": BM25_K1,
            "b": BM25_B,
            "max_docs_processed": max_docs
        }
    }
    
    # Log statistics
    total_tokens = sum(len(tokens) for tokens in corpus_texts)
    avg_tokens_per_chunk = total_tokens / len(corpus_texts) if corpus_texts else 0
    
    logger.info(f"BM25 Index Statistics:")
    logger.info(f"  Total chunks: {len(corpus_texts)}")
    logger.info(f"  Total tokens: {total_tokens:,}")
    logger.info(f"  Average tokens per chunk: {avg_tokens_per_chunk:.1f}")
    logger.info(f"  Build time: {index_data['build_duration_seconds']:.2f}s")
    logger.info(f"  Parameters: k1={BM25_K1}, b={BM25_B}")
    
    return index_data


def save_bm25_index_to_r2(
    r2_client, 
    bucket: str,
    index_data: Dict[str, Any], 
    r2_key: str = "corpus/indexes/bm25_index.pkl"
) -> None:
    """Save BM25 index to R2 for cloud-native deployment."""
    logger.info(f"Saving BM25 index to R2: {r2_key}...")
    
    # Serialize index data
    serialized_data = pickle.dumps(index_data, protocol=pickle.HIGHEST_PROTOCOL)
    
    # Upload to R2
    r2_client.put_object(
        Bucket=bucket,
        Key=r2_key,
        Body=serialized_data,
        ContentType="application/octet-stream",
        Metadata={
            "index_type": "bm25",
            "corpus_size": str(index_data['corpus_size']),
            "build_timestamp": str(index_data['build_timestamp']),
            "build_duration": str(index_data['build_duration_seconds']),
            "bm25_k1": str(index_data['parameters']['k1']),
            "bm25_b": str(index_data['parameters']['b'])
        }
    )
    
    # Log success metrics
    index_size_mb = len(serialized_data) / 1024 / 1024
    logger.info(f"✅ BM25 index uploaded to R2 successfully")
    logger.info(f"  R2 key: {r2_key}")
    logger.info(f"  Size: {index_size_mb:.2f} MB")
    logger.info(f"  Chunks: {index_data['corpus_size']:,}")
    logger.info(f"  Cloud-native: ✅ Ready for serverless deployment")

def save_bm25_index_local_backup(index_data: Dict[str, Any], output_file: str) -> None:
    """Save local backup copy for development (optional)."""
    logger.info(f"Saving local backup to {output_file}...")
    
    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save with optimized pickle protocol
    with open(output_file, 'wb') as f:
        pickle.dump(index_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    # Log file size
    file_size = os.path.getsize(output_file)
    logger.info(f"✅ Local backup saved")
    logger.info(f"  File: {output_file}")
    logger.info(f"  Size: {file_size / 1024 / 1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Build BM25 index from R2 corpus for lightning-fast sparse search")
    parser.add_argument("--output_file", type=str, default=DEFAULT_OUTPUT_FILE,
                        help=f"Output file for BM25 index (default: {DEFAULT_OUTPUT_FILE})")
    parser.add_argument("--max_docs", type=int, default=DEFAULT_MAX_DOCS,
                        help="Maximum number of chunks to process (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
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
        
        # Build BM25 index
        logger.info("🚀 Building production-grade BM25 index...")
        index_data = build_bm25_index_from_r2(
            r2_client,
            config["r2_bucket"],
            max_docs=args.max_docs,
            verbose=args.verbose
        )
        
        # Save index to R2 (cloud-native)
        logger.info("💾 Saving BM25 index to R2 (cloud-native deployment)...")
        save_bm25_index_to_r2(r2_client, config["r2_bucket"], index_data)
        
        # Save local backup for development (optional)
        if args.output_file:
            save_bm25_index_local_backup(index_data, args.output_file)
        
        # Performance summary
        build_time = index_data['build_duration_seconds']
        chunks_per_second = index_data['corpus_size'] / build_time
        
        logger.info(f"🎯 Performance Summary:")
        logger.info(f"  Chunks processed: {index_data['corpus_size']:,}")
        logger.info(f"  Build time: {build_time:.2f}s")
        logger.info(f"  Processing rate: {chunks_per_second:.1f} chunks/second")
        logger.info(f"  Index file: {args.output_file}")
        
        logger.info("✅ BM25 index build complete - ready for lightning-fast search!")
        
    except Exception as e:
        logger.error(f"❌ Error building BM25 index: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

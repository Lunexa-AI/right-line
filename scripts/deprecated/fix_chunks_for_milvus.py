#!/usr/bin/env python3
"""
fix_chunks_for_milvus.py - Fix chunks data to be compatible with Milvus schema

This script reads chunks with embeddings from chunks_with_embeddings.jsonl,
fixes field values to match Milvus schema constraints, and writes the fixed
chunks to chunks_with_embeddings_fixed.jsonl.

Usage:
    python scripts/fix_chunks_for_milvus.py [--input_file PATH] [--output_file PATH] [--verbose]

Author: RightLine Team
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import structlog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

def fix_chunk_for_milvus(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fix chunk data to be compatible with Milvus schema.
    
    Args:
        chunk: The chunk data to fix
        
    Returns:
        The fixed chunk data
    """
    fixed_chunk = chunk.copy()
    
    # Fix doc_type (max length 20)
    doc_type = fixed_chunk.get("doc_type", "unknown")
    if isinstance(doc_type, str) and len(doc_type) > 20:
        fixed_chunk["doc_type"] = doc_type[:20]
    
    # Fix language (max length 10)
    language = fixed_chunk.get("language", "eng")
    if isinstance(language, str) and len(language) > 10:
        fixed_chunk["language"] = language[:10]
    
    # Fix court (max length 100)
    court = fixed_chunk.get("court", "unknown")
    if isinstance(court, str) and len(court) > 100:
        fixed_chunk["court"] = court[:100]
    
    # Fix date_context (max length 32)
    date_context = fixed_chunk.get("date_context", "unknown")
    if isinstance(date_context, str) and len(date_context) > 32:
        fixed_chunk["date_context"] = date_context[:32]
    
    # Ensure metadata is a dict
    metadata = fixed_chunk.get("metadata", {})
    if not isinstance(metadata, dict):
        fixed_chunk["metadata"] = {}
    
    return fixed_chunk

def main():
    parser = argparse.ArgumentParser(description="Fix chunks data to be compatible with Milvus schema")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks_with_embeddings.jsonl", 
                        help="Path to input JSONL file with embeddings")
    parser.add_argument("--output_file", type=Path, default="data/processed/chunks_with_embeddings_fixed.jsonl", 
                        help="Path to output JSONL file with fixed chunks")
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
        
        # Fix chunks
        fixed_chunks = []
        for chunk in chunks:
            fixed_chunk = fix_chunk_for_milvus(chunk)
            fixed_chunks.append(fixed_chunk)
        
        logger.info(f"Fixed {len(fixed_chunks)} chunks")
        
        # Write fixed chunks
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as f:
            for chunk in fixed_chunks:
                f.write(json.dumps(chunk) + "\n")
        
        logger.info(f"Wrote {len(fixed_chunks)} fixed chunks to {args.output_file}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

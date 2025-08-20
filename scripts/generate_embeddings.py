#!/usr/bin/env python3
"""
generate_embeddings.py - Generate embeddings for chunks using OpenAI API

This script implements Task 6 from the INGESTION_AND_CHUNKING_TASKLIST.md.
It reads enriched chunks from chunks_enriched.jsonl, generates embeddings using OpenAI,
and writes chunks with embeddings to chunks_with_embeddings.jsonl.

Usage:
    python scripts/generate_embeddings.py [--input_file PATH] [--output_file PATH] [--batch_size INT] [--verbose]

Author: RightLine Team
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
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
DEFAULT_BATCH_SIZE = 64
DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_DIMENSIONS = 1536

def get_openai_client() -> OpenAI:
    """Get OpenAI client with API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    return OpenAI(api_key=api_key)

@retry(wait=wait_exponential(min=1, max=60), stop=stop_after_attempt(5))
def generate_embeddings(client: OpenAI, texts: List[str], model: str = DEFAULT_MODEL) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts using OpenAI API.
    
    Args:
        client: OpenAI client
        texts: List of texts to embed
        model: OpenAI embedding model to use
        
    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    response = client.embeddings.create(
        model=model,
        input=texts,
        # dimensions parameter is not supported in this version of the OpenAI API
    )
    
    return [data.embedding for data in response.data]

def process_chunks(
    input_file: Path, 
    output_file: Path, 
    batch_size: int = DEFAULT_BATCH_SIZE, 
    model: str = DEFAULT_MODEL,
    sample_only: bool = False,
    verbose: bool = False
) -> None:
    """
    Process chunks from input file, generate embeddings, and write to output file.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output JSONL file
        batch_size: Number of chunks to process in each batch
        model: OpenAI embedding model to use
        sample_only: If True, only process a small sample of chunks
        verbose: Whether to print verbose output
    """
    try:
        # Load chunks
        chunks = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        logger.info(f"Loaded {len(chunks)} chunks from {input_file}")
        
        # Limit to a small sample if requested
        if sample_only:
            sample_size = min(10, len(chunks))
            chunks = chunks[:sample_size]
            logger.info(f"Processing sample of {sample_size} chunks")
        
        # Initialize OpenAI client
        client = get_openai_client()
        
        # Process chunks in batches
        processed_chunks = []
        total_tokens = 0
        failed_chunks = 0
        
        for i in tqdm(range(0, len(chunks), batch_size), desc="Generating embeddings"):
            batch = chunks[i:i+batch_size]
            batch_texts = [chunk["chunk_text"] for chunk in batch]
            
            try:
                # Generate embeddings for batch
                embeddings = generate_embeddings(client, batch_texts, model)
                
                # Add embeddings to chunks
                for j, embedding in enumerate(embeddings):
                    chunk = batch[j].copy()
                    chunk["embedding"] = embedding
                    processed_chunks.append(chunk)
                    
                    # Estimate token usage for cost tracking
                    tokens = chunk["num_tokens"] if "num_tokens" in chunk else estimate_tokens(chunk["chunk_text"])
                    total_tokens += tokens
                
                if verbose:
                    logger.info(f"Processed batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {e}")
                if verbose:
                    import traceback
                    logger.error(traceback.format_exc())
                
                # Add chunks without embeddings
                for chunk in batch:
                    failed_chunks += 1
                    processed_chunks.append(chunk)
        
        # Write processed chunks to output file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # If sample_only, write to sample file
        if sample_only:
            sample_file = output_file.with_suffix(".sample.json")
            with open(sample_file, "w", encoding="utf-8") as f:
                # Write first 3 chunks as pretty JSON for inspection
                json.dump(processed_chunks[:3], f, indent=2, default=str)
            logger.info(f"Wrote {len(processed_chunks[:3])} sample chunks to {sample_file}")
        else:
            # Write all chunks as JSONL
            with open(output_file, "w", encoding="utf-8") as f:
                for chunk in processed_chunks:
                    f.write(json.dumps(chunk, default=str) + "\n")
            logger.info(f"Wrote {len(processed_chunks)} chunks to {output_file}")
        
        # Log statistics
        success_rate = (len(chunks) - failed_chunks) / len(chunks) * 100 if chunks else 0
        logger.info(f"Embedding generation statistics:")
        logger.info(f"  Total chunks: {len(chunks)}")
        logger.info(f"  Failed chunks: {failed_chunks} ({100 - success_rate:.2f}%)")
        logger.info(f"  Estimated tokens: {total_tokens}")
        logger.info(f"  Estimated cost: ${total_tokens / 1000 * 0.00002:.4f} (at $0.00002/1K tokens)")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text using character count."""
    # Simple approximation: ~4 chars per token for English text
    return len(text) // 4

def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for chunks using OpenAI API")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks_enriched.jsonl", 
                        help="Path to input JSONL file")
    parser.add_argument("--output_file", type=Path, default="data/processed/chunks_with_embeddings.jsonl", 
                        help="Path to output JSONL file")
    parser.add_argument("--batch_size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Number of chunks to process in each batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"OpenAI embedding model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--sample", action="store_true",
                        help="Only process a small sample of chunks")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    process_chunks(
        args.input_file, 
        args.output_file, 
        args.batch_size, 
        args.model,
        args.sample,
        args.verbose
    )

if __name__ == "__main__":
    main()
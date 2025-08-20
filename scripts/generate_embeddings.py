#!/usr/bin/env python3
"""Generate OpenAI embeddings for document chunks and upload to Milvus.

This script reads parsed document chunks, generates embeddings using OpenAI's
text-embedding-3-small model, and uploads them to Milvus Cloud.

Usage:
    python scripts/generate_embeddings.py [--input data/processed/chunks.json]

Environment Variables:
    OPENAI_API_KEY - OpenAI API key
    MILVUS_ENDPOINT - Milvus Cloud endpoint URL
    MILVUS_TOKEN - Milvus Cloud access token
    MILVUS_COLLECTION_NAME - Collection name (default: legal_chunks)
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import argparse

try:
    import openai
    from pymilvus import connections, Collection
    from tqdm import tqdm
except ImportError as e:
    print(f"❌ Error: Missing dependency. Run: pip install openai pymilvus tqdm")
    print(f"   Specific error: {e}")
    sys.exit(1)


def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    config = {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "milvus_endpoint": os.getenv("MILVUS_ENDPOINT"),
        "milvus_token": os.getenv("MILVUS_TOKEN"),
        "collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks"),
        "embedding_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", "100")),
    }
    
    if not config["openai_api_key"]:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    if not config["milvus_endpoint"]:
        print("❌ Error: MILVUS_ENDPOINT environment variable not set")
        sys.exit(1)
    
    if not config["milvus_token"]:
        print("❌ Error: MILVUS_TOKEN environment variable not set")
        sys.exit(1)
    
    return config


def load_chunks(input_file: Path) -> List[Dict[str, Any]]:
    """Load document chunks from JSON file."""
    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        print("   Run python scripts/parse_docs.py first to generate chunks")
        sys.exit(1)
    
    with open(input_file, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    print(f"📚 Loaded {len(chunks)} chunks from {input_file}")
    return chunks


def generate_embeddings_batch(texts: List[str], model: str, client) -> List[List[float]]:
    """Generate embeddings for a batch of texts using OpenAI API."""
    try:
        response = client.embeddings.create(
            model=model,
            input=texts,
            encoding_format="float"
        )
        return [embedding.embedding for embedding in response.data]
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        raise


def upload_to_milvus(collection: Collection, data: List[Dict[str, Any]], batch_size: int = 1000):
    """Upload data to Milvus collection in batches."""
    total_batches = (len(data) + batch_size - 1) // batch_size
    
    for i in tqdm(range(0, len(data), batch_size), desc="Uploading to Milvus", unit="batch"):
        batch = data[i:i + batch_size]
        
        # Prepare batch data
        # Order must match schema (excluding auto primary key):
        # doc_id, doc_type, language, court, date_context, chunk_text, embedding, metadata
        batch_data = [
            [item.get("doc_id", "") for item in batch],                 # doc_id
            [item.get("doc_type", item.get("metadata", {}).get("doc_type", "unknown")) for item in batch],  # doc_type
            [item.get("language", item.get("metadata", {}).get("language", "eng")) for item in batch],      # language
            [item.get("court", item.get("metadata", {}).get("court", "")) for item in batch],              # court
            [item.get("date_context", item.get("metadata", {}).get("date_context", "")) for item in batch],# date_context
            [item["chunk_text"] for item in batch],                       # chunk_text
            [item["embedding"] for item in batch],                        # embedding
            [item["metadata"] for item in batch],                         # metadata
        ]
        
        # Insert batch
        try:
            collection.insert(batch_data)
        except Exception as e:
            print(f"❌ Error uploading batch {i//batch_size + 1}: {e}")
            raise
    
    # Flush to ensure data is written
    collection.flush()


def main():
    """Main function to generate embeddings and upload to Milvus."""
    parser = argparse.ArgumentParser(description="Generate embeddings and upload to Milvus")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/chunks.json"),
        help="Input JSON file with document chunks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate embeddings but don't upload to Milvus"
    )
    
    args = parser.parse_args()
    
    print("🚀 Starting embedding generation and Milvus upload...")
    
    # Get configuration
    config = get_config()
    
    # Initialize OpenAI client
    client = openai.OpenAI(api_key=config["openai_api_key"])
    
    # Load document chunks
    chunks = load_chunks(args.input)
    
    # Connect to Milvus (if not dry run)
    collection = None
    if not args.dry_run:
        print(f"🔌 Connecting to Milvus Cloud: {config['milvus_endpoint']}")
        connections.connect(
            alias="default",
            uri=config["milvus_endpoint"],
            token=config["milvus_token"]
        )
        collection = Collection(config["collection_name"])
        print(f"✅ Connected to collection '{config['collection_name']}'")
    
    # Process chunks in batches
    batch_size = config["batch_size"]
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    processed_chunks = []
    
    print(f"🧠 Generating embeddings using {config['embedding_model']}...")
    print(f"   Batch size: {batch_size}")
    print(f"   Total batches: {total_batches}")
    
    total_tokens = 0
    
    for i in tqdm(range(0, len(chunks), batch_size), desc="Processing batches", unit="batch"):
        batch_chunks = chunks[i:i + batch_size]
        texts = [chunk["chunk_text"] for chunk in batch_chunks]
        
        # Generate embeddings for this batch
        try:
            embeddings = generate_embeddings_batch(texts, config["embedding_model"], client)
            
            # Estimate token usage (approximate)
            batch_tokens = sum(len(text.split()) for text in texts)
            total_tokens += batch_tokens
            
        except Exception as e:
            print(f"❌ Failed to generate embeddings for batch {i//batch_size + 1}: {e}")
            continue
        
        # Prepare data for Milvus
        for chunk, embedding in zip(batch_chunks, embeddings):
            processed_chunk = {
                "doc_id": chunk["doc_id"],
                "chunk_text": chunk["chunk_text"],
                "embedding": embedding,
                # Promote common scalar fields with safe defaults
                "doc_type": chunk.get("doc_type", "unknown"),
                "language": chunk.get("language", "eng"),
                "court": chunk.get("court", ""),
                "date_context": chunk.get("date_context", ""),
                "metadata": {
                    "source_url": chunk.get("source_url", ""),
                    "title": chunk.get("title", ""),
                    "section": chunk.get("section", ""),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    # Carry through additional context if present
                    "doc_type": chunk.get("doc_type"),
                    "language": chunk.get("language"),
                    "court": chunk.get("court"),
                    "date_context": chunk.get("date_context"),
                }
            }
            processed_chunks.append(processed_chunk)
        
        # Small delay to respect rate limits
        time.sleep(0.1)
    
    print(f"✅ Generated {len(processed_chunks)} embeddings")
    print(f"📊 Estimated tokens used: {total_tokens:,}")
    print(f"💰 Estimated cost: ${(total_tokens / 1_000_000) * 0.02:.4f}")
    
    # Upload to Milvus
    if not args.dry_run and processed_chunks:
        print("⬆️  Uploading to Milvus...")
        upload_to_milvus(collection, processed_chunks)
        
        # Get collection stats
        collection.load()
        num_entities = collection.num_entities
        print(f"✅ Upload complete! Collection now has {num_entities} entities")
    
    elif args.dry_run:
        print("🔍 Dry run complete - no data uploaded")
        
        # Save embeddings to file for inspection
        output_file = Path("data/processed/chunks_with_embeddings.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_chunks[:5], f, indent=2)  # Save only first 5 for inspection
        print(f"💾 Sample embeddings saved to {output_file}")
    
    # Cleanup
    if collection:
        connections.disconnect("default")
    
    print("🎉 Process completed successfully!")


if __name__ == "__main__":
    main()

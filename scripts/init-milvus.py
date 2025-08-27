#!/usr/bin/env python3
"""Initialize Milvus Cloud collection for RightLine RAG system.

This script creates the necessary collection and indexes in Milvus Cloud
for storing document chunks and their OpenAI embeddings.

Usage:
    python scripts/init-milvus.py

Environment Variables:
    MILVUS_ENDPOINT - Milvus Cloud endpoint URL
    MILVUS_TOKEN - Milvus Cloud access token
    MILVUS_COLLECTION_NAME - Collection name (default: legal_chunks)
"""

import os
import sys
from typing import Dict, Any

try:
    from pymilvus import (
        connections,
        Collection,
        CollectionSchema,
        FieldSchema,
        DataType,
        utility
    )
except ImportError:
    print("❌ Error: pymilvus not installed. Run: pip install pymilvus")
    sys.exit(1)


def get_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    config = {
        "endpoint": os.getenv("MILVUS_ENDPOINT"),
        "token": os.getenv("MILVUS_TOKEN"),
        "collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks"),
    }
    
    if not config["endpoint"]:
        print("❌ Error: MILVUS_ENDPOINT environment variable not set")
        print("   Get this from your Milvus Cloud cluster details")
        sys.exit(1)
    
    if not config["token"]:
        print("❌ Error: MILVUS_TOKEN environment variable not set")
        print("   Get this from your Milvus Cloud cluster details")
        sys.exit(1)
    
    return config


def create_collection_schema() -> CollectionSchema:
    """Create the collection schema for legal document chunks."""
    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True,
            description="Primary key"
        ),
        FieldSchema(
            name="doc_id",
            dtype=DataType.VARCHAR,
            max_length=100,
            description="Source document identifier"
        ),
        # Recommended scalar fields for filtering (see INGESTION_AND_CHUNKING.md)
        FieldSchema(
            name="doc_type",
            dtype=DataType.VARCHAR,
            max_length=20,
            description="Document type: act | judgment | constitution | si | other"
        ),
        FieldSchema(
            name="nature",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Nature label aligned to ZimLII index: Act | Ordinance | Statutory Instrument"
        ),
        FieldSchema(
            name="language",
            dtype=DataType.VARCHAR,
            max_length=10,
            description="Language code, e.g., eng"
        ),
        FieldSchema(
            name="court",
            dtype=DataType.VARCHAR,
            max_length=100,
            description="Court name for judgments (optional)"
        ),
        FieldSchema(
            name="date_context",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Date context (ISO), e.g., version_effective_date or judgment date"
        ),
        FieldSchema(
            name="year",
            dtype=DataType.INT64,
            description="Publication/effective year for filtering"
        ),
        FieldSchema(
            name="chapter",
            dtype=DataType.VARCHAR,
            max_length=16,
            description="Chapter number like 7:01 when available"
        ),
        FieldSchema(
            name="chunk_text",
            dtype=DataType.VARCHAR,
            max_length=5000,
            description="Text content of the chunk"
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=3072,  # Using OpenAI text-embedding-3-large dimension to match generated embeddings
            description="OpenAI embedding vector"
        ),
        FieldSchema(
            name="metadata",
            dtype=DataType.JSON,
            description="Additional metadata (source_url, title, section, etc.)"
        ),
    ]
    
    schema = CollectionSchema(
        fields=fields,
        description="Legal document chunks with OpenAI embeddings",
        enable_dynamic_field=False
    )
    
    return schema


def main():
    """Initialize Milvus collection."""
    print("🚀 Initializing Milvus Cloud collection for RightLine...")
    
    # Get configuration
    config = get_config()
    
    try:
        # Connect to Milvus Cloud
        print(f"🔌 Connecting to Milvus Cloud: {config['endpoint']}")
        connections.connect(
            alias="default",
            uri=config["endpoint"],
            token=config["token"]
        )
        print("✅ Connected to Milvus Cloud successfully")
        
        # Check if collection already exists
        collection_name = config["collection_name"]
        if utility.has_collection(collection_name):
            print(f"⚠️  Collection '{collection_name}' already exists")
            
            # Ask user if they want to recreate
            response = input("Do you want to recreate it? (y/N): ").lower().strip()
            if response == 'y':
                print(f"🗑️  Dropping existing collection '{collection_name}'...")
                utility.drop_collection(collection_name)
            else:
                print("ℹ️  Keeping existing collection")
                return
        
        # Create collection schema
        print("📋 Creating collection schema...")
        schema = create_collection_schema()
        
        # Create collection
        print(f"🏗️  Creating collection '{collection_name}'...")
        collection = Collection(
            name=collection_name,
            schema=schema,
            using='default'
        )
        
        # Create HNSW index on embedding field
        print("🔍 Creating HNSW index on embedding field...")
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 256}
        }
        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )

        # Create inverted indexes for scalar filter fields (optional but recommended)
        try:
            print("🧭 Creating INVERTED indexes for scalar fields (doc_type, nature, language, court, date_context, year, chapter)...")
            for scalar_field in ["doc_type", "nature", "language", "court", "date_context", "year", "chapter"]:
                collection.create_index(
                    field_name=scalar_field,
                    index_params={"index_type": "INVERTED", "params": {}}
                )
        except Exception as e:
            print(f"⚠️  Skipped creating scalar indexes: {e}")
        
        # Load collection into memory
        print("💾 Loading collection into memory...")
        collection.load()
        
        # Display collection info
        print("\n✅ Collection created successfully!")
        print(f"   Name: {collection_name}")
        print(f"   Schema: {len(schema.fields)} fields")
        print(f"   Primary key: id (auto-generated)")
        print(f"   Vector field: embedding (1536 dimensions)")
        print(f"   Index: HNSW with COSINE similarity")
        print(f"   Scalar filter fields: doc_type, nature, language, court, date_context, year, chapter")
        
        # Display next steps
        print("\n📝 Next steps:")
        print("1. Run document ingestion: python scripts/crawl_zimlii.py")
        print("2. Parse documents: python scripts/parse_docs.py") 
        print("3. Generate embeddings: python scripts/generate_embeddings.py")
        print("4. Test search: python scripts/test_search.py")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
    
    finally:
        # Disconnect
        connections.disconnect("default")


if __name__ == "__main__":
    main()

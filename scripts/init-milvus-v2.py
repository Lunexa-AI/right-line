#!/usr/bin/env python3
"""Initialize Milvus Cloud collection for RightLine v2.0 (Small-to-Big Architecture).

This script creates the NEW v2.0 collection schema optimized for small-to-big retrieval,
where small chunks are indexed for search but full parent documents are retrieved for context.

Key changes from v1:
- chunk_id as primary key (not auto-generated int)  
- chunk_object_key to reference R2 storage location
- parent_doc_id for expanding to full parent documents
- Only lightweight metadata stored (text content retrieved from R2)

Usage:
    python scripts/init-milvus-v2.py

Environment Variables:
    MILVUS_ENDPOINT - Milvus Cloud endpoint URL
    MILVUS_TOKEN - Milvus Cloud access token  
    MILVUS_COLLECTION_NAME - Collection name (default: legal_chunks_v2)
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
        "collection_name": os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks_v2"),
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


def create_collection_schema_v2() -> CollectionSchema:
    """Create the v2.0 collection schema for small-to-big retrieval."""
    fields = [
        # Primary key - chunk_id (deterministic, stable)
        FieldSchema(
            name="chunk_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            auto_id=False,  # We provide our own IDs
            description="Stable chunk identifier (sha256 hash)"
        ),
        
        # Vector field for embedding search
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=3072,  # OpenAI text-embedding-3-large dimension
            description="OpenAI embedding vector for semantic search"
        ),
        
        # Core chunk metadata
        FieldSchema(
            name="num_tokens",
            dtype=DataType.INT64,
            description="Estimated token count for the chunk"
        ),
        FieldSchema(
            name="doc_type",
            dtype=DataType.VARCHAR,
            max_length=20,
            description="Document type: act | judgment | constitution | si | other"
        ),
        FieldSchema(
            name="language",
            dtype=DataType.VARCHAR,
            max_length=10,
            description="Language code, e.g., eng"
        ),
        
        # Small-to-big retrieval fields
        FieldSchema(
            name="parent_doc_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="Parent document ID for expanding to full context"
        ),
        FieldSchema(
            name="chunk_object_key",
            dtype=DataType.VARCHAR,
            max_length=200,
            description="R2 object key for retrieving chunk content"
        ),
        FieldSchema(
            name="source_document_key",
            dtype=DataType.VARCHAR,
            max_length=200,
            description="R2 object key for original source document"
        ),
        
        # Additional lightweight filtering metadata
        FieldSchema(
            name="nature",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Nature label: Act | Ordinance | Statutory Instrument"
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
            name="date_context",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="Date context (YYYY-MM-DD) for filtering"
        ),
    ]
    
    schema = CollectionSchema(
        fields=fields,
        description="Legal document chunks v2.0 - Small-to-Big architecture with R2 storage",
        enable_dynamic_field=False
    )
    
    return schema


def main():
    """Initialize Milvus v2.0 collection."""
    print("🚀 Initializing Milvus Cloud collection for RightLine v2.0...")
    
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
        print("📋 Creating v2.0 collection schema...")
        schema = create_collection_schema_v2()
        
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

        # Create inverted indexes for scalar filter fields
        try:
            print("🧭 Creating INVERTED indexes for scalar fields...")
            scalar_fields = ["doc_type", "language", "nature", "year", "chapter", "date_context"]
            for field_name in scalar_fields:
                collection.create_index(
                    field_name=field_name,
                    index_params={"index_type": "INVERTED", "params": {}}
                )
        except Exception as e:
            print(f"⚠️  Skipped creating scalar indexes: {e}")
        
        # Load collection into memory
        print("💾 Loading collection into memory...")
        collection.load()
        
        # Display collection info
        print("\n✅ v2.0 Collection created successfully!")
        print(f"   Name: {collection_name}")
        print(f"   Schema: {len(schema.fields)} fields")
        print(f"   Primary key: chunk_id (user-provided)")
        print(f"   Vector field: embedding (3072 dimensions)")
        print(f"   Index: HNSW with COSINE similarity")
        print(f"   Architecture: Small-to-Big with R2 content retrieval")
        
        # Display schema details
        print("\n📋 Schema fields:")
        for field in schema.fields:
            field_info = f"   - {field.name} ({field.dtype})"
            if hasattr(field, 'max_length') and field.max_length:
                field_info += f" max_length={field.max_length}"
            if field.is_primary:
                field_info += " [PRIMARY KEY]"
            print(field_info)
        
        # Display next steps
        print("\n📝 Next steps:")
        print("1. Generate embeddings: python scripts/generate_embeddings.py")
        print("2. Upsert to Milvus: python scripts/milvus_upsert_v2.py")
        print("3. Verify collection: python scripts/get_milvus_schema.py")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
    
    finally:
        # Disconnect
        connections.disconnect("default")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Propagate enhanced metadata from source documents to their corresponding chunks.

After enhancing SI/Ordinance source documents with year/date/nature metadata,
this script updates all chunks to inherit that metadata from their parent documents.

Usage:
    python scripts/propagate_metadata_to_chunks.py [--dry-run] [--doc-types si,ordinance]
"""

import argparse
import json
import os
import sys
from typing import Dict, Any, List, Set

import boto3
from botocore.client import Config
from dotenv import load_dotenv
from tqdm import tqdm
import structlog

logger = structlog.get_logger("propagate_metadata")

def get_r2_client():
    """Get R2 client."""
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )

def load_document_metadata_map(r2_client, bucket: str, doc_type: str) -> Dict[str, Dict[str, Any]]:
    """Load all source documents and create a map of doc_id -> metadata."""
    
    metadata_map = {}
    
    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        
        print(f"📄 Loading {doc_type.upper()} source document metadata...")
        
        doc_keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/docs/{doc_type}/'):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.json'):
                    doc_keys.append(obj['Key'])
        
        for doc_key in tqdm(doc_keys, desc=f"Loading {doc_type} docs"):
            try:
                response = r2_client.get_object(Bucket=bucket, Key=doc_key)
                doc_data = json.loads(response['Body'].read().decode('utf-8'))
                
                doc_id = doc_data.get('doc_id')
                if doc_id:
                    # Extract relevant metadata that chunks should inherit
                    metadata_map[doc_id] = {
                        'year': doc_data.get('year'),
                        'act_year': doc_data.get('act_year'), 
                        'date_context': doc_data.get('date_context'),
                        'version_date': doc_data.get('version_date'),
                        'nature': doc_data.get('nature'),
                        'title': doc_data.get('title'),
                        'canonical_citation': doc_data.get('canonical_citation'),
                        'akn_uri': doc_data.get('akn_uri'),
                        'pageindex_doc_id': doc_data.get('pageindex_doc_id')
                    }
                    
            except Exception as e:
                logger.error("doc_load_error", doc_key=doc_key, error=str(e))
                
    except Exception as e:
        logger.error("doc_type_load_error", doc_type=doc_type, error=str(e))
    
    logger.info("metadata_map_loaded", doc_type=doc_type, docs=len(metadata_map))
    return metadata_map

def propagate_metadata_to_chunk(chunk_data: Dict[str, Any], source_metadata: Dict[str, Any]) -> bool:
    """Update chunk with metadata from source document. Returns True if modified."""
    
    modified = False
    
    # Fields to propagate from source to chunk
    propagation_map = {
        'year': 'year',
        'act_year': 'year',  # act_year from source becomes year in chunk
        'date_context': 'date_context', 
        'version_date': 'date_context',  # version_date from source becomes date_context in chunk
        'nature': 'nature'
    }
    
    for source_field, chunk_field in propagation_map.items():
        source_value = source_metadata.get(source_field)
        current_value = chunk_data.get(chunk_field)
        
        # Update if source has value and chunk doesn't
        if source_value and not current_value:
            chunk_data[chunk_field] = source_value
            modified = True
    
    # Update metadata section for discoverability
    if not chunk_data.get('metadata'):
        chunk_data['metadata'] = {}
    
    metadata_updates = {
        'title': source_metadata.get('title'),
        'canonical_citation': source_metadata.get('canonical_citation'),
        'akn_uri': source_metadata.get('akn_uri'),
        'pageindex_doc_id': source_metadata.get('pageindex_doc_id')
    }
    
    for field, value in metadata_updates.items():
        if value and not chunk_data['metadata'].get(field):
            chunk_data['metadata'][field] = value
            modified = True
    
    return modified

def propagate_metadata_for_doc_type(r2_client, bucket: str, doc_type: str, dry_run: bool = False) -> int:
    """Propagate metadata for all chunks of a specific doc_type."""
    
    # Load source document metadata
    source_metadata_map = load_document_metadata_map(r2_client, bucket, doc_type)
    
    if not source_metadata_map:
        logger.warning("no_source_metadata", doc_type=doc_type)
        return 0
    
    # Process all chunks of this doc_type
    print(f"🧩 Updating {doc_type.upper()} chunks with enhanced metadata...")
    
    chunks_updated = 0
    
    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        chunk_keys = []
        
        for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/chunks/{doc_type}/'):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.json'):
                    chunk_keys.append(obj['Key'])
        
        for chunk_key in tqdm(chunk_keys, desc=f"Updating {doc_type}"):
            try:
                response = r2_client.get_object(Bucket=bucket, Key=chunk_key)
                chunk_data = json.loads(response['Body'].read().decode('utf-8'))
                
                # Find source metadata for this chunk
                chunk_doc_id = chunk_data.get('doc_id')
                source_metadata = source_metadata_map.get(chunk_doc_id)
                
                if source_metadata:
                    if propagate_metadata_to_chunk(chunk_data, source_metadata):
                        chunks_updated += 1
                        
                        if not dry_run:
                            # Update R2 metadata headers
                            r2_metadata = response.get('Metadata', {})
                            
                            # Add enhanced fields to R2 metadata
                            if chunk_data.get('year'):
                                r2_metadata['year'] = str(chunk_data['year'])
                            if chunk_data.get('date_context'):
                                r2_metadata['date_context'] = str(chunk_data['date_context'])
                            if chunk_data.get('nature'):
                                r2_metadata['nature'] = str(chunk_data['nature'])
                            
                            # Upload enhanced chunk
                            r2_client.put_object(
                                Bucket=bucket,
                                Key=chunk_key,
                                Body=json.dumps(chunk_data, default=str).encode('utf-8'),
                                ContentType='application/json',
                                Metadata=r2_metadata
                            )
                else:
                    logger.warning("no_source_metadata_for_chunk", chunk_doc_id=chunk_doc_id)
                    
            except Exception as e:
                logger.error("chunk_update_error", chunk_key=chunk_key, error=str(e))
                
    except Exception as e:
        logger.error("chunk_processing_error", doc_type=doc_type, error=str(e))
    
    logger.info("doc_type_propagation_complete", doc_type=doc_type, updated=chunks_updated)
    return chunks_updated

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Propagate enhanced metadata to chunks")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading changes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output") 
    parser.add_argument("--doc-types", default="si,ordinance", help="Comma-separated doc types to process")
    args = parser.parse_args()
    
    # Load environment
    load_dotenv(".env.local")
    
    try:
        # Get R2 client
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Parse doc types
        doc_types = [dt.strip() for dt in args.doc_types.split(',')]
        
        total_updated = 0
        
        for doc_type in doc_types:
            updated = propagate_metadata_for_doc_type(r2_client, bucket, doc_type, dry_run=args.dry_run)
            total_updated += updated
        
        print(f"\n🎉 METADATA PROPAGATION COMPLETE!")
        print(f"   🧩 Total chunks updated: {total_updated:,}")
        
        if args.dry_run:
            print(f"   ℹ️ DRY RUN - No changes were uploaded")
        else:
            print(f"   ✅ Enhanced metadata propagated to chunks")
            print(f"   📅 SI/Ordinance chunks now have year, date, and nature!")
            print(f"   🚀 Ready for comprehensive legal AI with temporal awareness")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

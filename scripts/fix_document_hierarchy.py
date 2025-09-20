#!/usr/bin/env python3
"""
Fix hierarchy metadata for all source documents.

This script adds constitutional hierarchy metadata to all parsed documents
based on their doc_type, ensuring proper authority ranking in the legal AI.
"""

import json
import os
import sys
from typing import Dict, Any

try:
    import boto3
    from botocore.client import Config
    from dotenv import load_dotenv
    from tqdm import tqdm
except ImportError as e:
    print(f"❌ Error: Missing dependency: {e}")
    sys.exit(1)

# Load environment
load_dotenv(".env.local")

def get_r2_client():
    """Get R2 client."""
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )

def get_hierarchy_metadata(doc_type: str) -> Dict[str, Any]:
    """Get hierarchy metadata based on document type."""
    
    hierarchy_map = {
        "constitution": {
            "authority_level": "supreme",
            "hierarchy_rank": 1,
            "binding_scope": "all_courts",
            "subject_category": "constitutional_law"
        },
        "act": {
            "authority_level": "high", 
            "hierarchy_rank": 2,
            "binding_scope": "national",
            "subject_category": "legislation"
        },
        "ordinance": {
            "authority_level": "medium",
            "hierarchy_rank": 3, 
            "binding_scope": "specific",
            "subject_category": "legislation"
        },
        "si": {
            "authority_level": "medium",
            "hierarchy_rank": 3,
            "binding_scope": "specific", 
            "subject_category": "legislation"
        }
    }
    
    return hierarchy_map.get(doc_type, {
        "authority_level": "unknown",
        "hierarchy_rank": 99,
        "binding_scope": "unknown",
        "subject_category": "unknown"
    })

def fix_documents_hierarchy(r2_client, bucket: str):
    """Add hierarchy metadata to all documents."""
    
    doc_types = ["constitution", "act", "ordinance", "si"]
    total_fixed = 0
    
    for doc_type in doc_types:
        print(f"\n📋 FIXING {doc_type.upper()} DOCUMENTS...")
        
        # Get hierarchy metadata for this doc type
        hierarchy = get_hierarchy_metadata(doc_type)
        
        try:
            # List all documents of this type
            paginator = r2_client.get_paginator('list_objects_v2')
            doc_keys = []
            
            for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/docs/{doc_type}/'):
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        doc_keys.append(obj['Key'])
            
            print(f"   Found {len(doc_keys)} {doc_type} documents")
            
            # Process each document
            fixed_count = 0
            for doc_key in tqdm(doc_keys, desc=f"Fixing {doc_type}"):
                try:
                    # Download document
                    response = r2_client.get_object(Bucket=bucket, Key=doc_key)
                    doc_data = json.loads(response['Body'].read().decode('utf-8'))
                    
                    # Check if already has hierarchy
                    has_hierarchy = all([
                        doc_data.get('authority_level'),
                        doc_data.get('hierarchy_rank'),
                        doc_data.get('binding_scope'),
                        doc_data.get('subject_category')
                    ])
                    
                    if not has_hierarchy:
                        # Add hierarchy metadata
                        doc_data.update(hierarchy)
                        
                        # Upload back to R2
                        r2_client.put_object(
                            Bucket=bucket,
                            Key=doc_key,
                            Body=json.dumps(doc_data, default=str).encode('utf-8'),
                            ContentType='application/json',
                            Metadata=response.get('Metadata', {})
                        )
                        
                        fixed_count += 1
                    
                except Exception as e:
                    print(f"   ❌ Error fixing {doc_key}: {e}")
                    continue
            
            print(f"   ✅ Fixed {fixed_count} {doc_type} documents")
            total_fixed += fixed_count
            
        except Exception as e:
            print(f"   ❌ Error processing {doc_type}: {e}")
            continue
    
    print(f"\n🎯 HIERARCHY FIX SUMMARY:")
    print(f"   📊 Total documents updated: {total_fixed}")
    print(f"   🏛️ Constitutional hierarchy now complete!")
    
    return total_fixed

def main():
    """Main function."""
    print("=== FIXING DOCUMENT HIERARCHY METADATA ===")
    
    try:
        # Get R2 client
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Fix all documents
        fixed_count = fix_documents_hierarchy(r2_client, bucket)
        
        if fixed_count > 0:
            print(f"\n🎉 SUCCESS! Fixed {fixed_count} documents")
            print(f"   ✅ All documents now have constitutional hierarchy metadata")
            print(f"   🚀 Ready to re-chunk with proper authority ranking")
            print(f"\nNEXT STEPS:")
            print(f"   1. Re-run chunking: python scripts/chunk_docs.py --force --verbose")
            print(f"   2. Upload to Milvus with hierarchy awareness")
            print(f"   3. Test legal AI with constitutional authority ranking")
        else:
            print(f"\n✅ All documents already have hierarchy metadata")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

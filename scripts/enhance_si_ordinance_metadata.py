#!/usr/bin/env python3
"""
Enhance SI and Ordinance metadata by extracting year, date, and nature from filenames and content.

Usage:
    python scripts/enhance_si_ordinance_metadata.py [--dry-run] [--verbose]
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, Any, Optional

import boto3
from botocore.client import Config
from dotenv import load_dotenv
from tqdm import tqdm
import structlog

logger = structlog.get_logger("enhance_metadata")

def get_r2_client():
    """Get R2 client."""
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )

def extract_si_metadata(filename: str, title: str) -> Dict[str, Any]:
    """Extract metadata from SI filename and title."""
    metadata = {}
    
    # SI pattern: akn_zw_act_si_2024_181_eng_2024-11-15.pdf
    si_match = re.search(r'si_(\d{4})_(\d+)_eng_(\d{4}-\d{2}-\d{2})', filename)
    if si_match:
        metadata['year'] = int(si_match.group(1))
        metadata['si_number'] = int(si_match.group(2))
        metadata['date_context'] = si_match.group(3)
        metadata['nature'] = 'Statutory Instrument'
    else:
        # Fallback: extract any years and dates
        years = re.findall(r'(20\d{2})', filename)
        dates = re.findall(r'(20\d{2}-\d{2}-\d{2})', filename)
        
        if years:
            metadata['year'] = int(years[0])  # Use first year found
        if dates:
            metadata['date_context'] = dates[-1]  # Use last (most recent) date
        
        metadata['nature'] = 'Statutory Instrument'
    
    # Extract nature from title if more specific
    title_lower = title.lower()
    if 'rules' in title_lower:
        metadata['nature'] = 'Rules'
    elif 'regulations' in title_lower:
        metadata['nature'] = 'Regulations'
    elif 'notice' in title_lower:
        metadata['nature'] = 'Notice'
    elif 'order' in title_lower:
        metadata['nature'] = 'Order'
    
    return metadata

def extract_ordinance_metadata(filename: str, title: str) -> Dict[str, Any]:
    """Extract metadata from Ordinance filename and title."""
    metadata = {}
    
    # Ordinance pattern: akn_zw_act_ord_1900_4_eng_2016-12-31.pdf
    ord_match = re.search(r'ord_(\d{4})_(\d+)_eng_(\d{4}-\d{2}-\d{2})', filename)
    if ord_match:
        metadata['year'] = int(ord_match.group(1))  # Original year
        metadata['ordinance_number'] = int(ord_match.group(2))
        metadata['date_context'] = ord_match.group(3)  # Revision date
        metadata['nature'] = 'Ordinance'
    else:
        # Fallback extraction
        years = re.findall(r'(\d{4})', filename)
        dates = re.findall(r'(\d{4}-\d{2}-\d{2})', filename)
        
        if years:
            # For ordinances, use earliest year (original) if multiple found
            year_ints = [int(y) for y in years if int(y) >= 1800]
            if year_ints:
                metadata['year'] = min(year_ints)
                
        if dates:
            metadata['date_context'] = dates[-1]  # Use last date (revision)
            
        metadata['nature'] = 'Ordinance'
    
    return metadata

def enhance_document_metadata(doc_data: Dict[str, Any], doc_type: str) -> bool:
    """Enhance document metadata. Returns True if modified."""
    
    r2_pdf_key = doc_data.get('extra', {}).get('r2_pdf_key', '')
    title = doc_data.get('title', '')
    
    if not r2_pdf_key:
        return False
    
    filename = os.path.basename(r2_pdf_key)
    modified = False
    
    # Extract metadata based on doc_type
    if doc_type == 'si':
        extracted = extract_si_metadata(filename, title)
    elif doc_type == 'ordinance':
        extracted = extract_ordinance_metadata(filename, title)
    else:
        return False
    
    # Update document with extracted metadata (only if missing)
    for field, value in extracted.items():
        if not doc_data.get(field) and value:
            doc_data[field] = value
            modified = True
    
    # Special handling for act_year (used by chunking script)
    if not doc_data.get('act_year') and extracted.get('year'):
        doc_data['act_year'] = extracted['year']
        modified = True
    
    # Add version_date if missing (for consistency with Acts)
    if not doc_data.get('version_date') and extracted.get('date_context'):
        doc_data['version_date'] = extracted['date_context']
        modified = True
    
    return modified

def enhance_chunk_metadata(chunk_data: Dict[str, Any], doc_type: str) -> bool:
    """Enhance chunk metadata with extracted info. Returns True if modified."""
    
    # Get source metadata from chunk's metadata field or doc fields
    metadata = chunk_data.get('metadata', {})
    title = metadata.get('title', chunk_data.get('title', ''))
    
    # Check if chunk already has complete metadata
    has_year = chunk_data.get('year') or chunk_data.get('act_year')
    has_date = chunk_data.get('date_context') or chunk_data.get('version_date') 
    has_nature = chunk_data.get('nature')
    
    if has_year and has_date and has_nature:
        return False  # Already complete
    
    # Try to extract from chunk metadata or other sources
    modified = False
    
    # Extract nature from doc_type
    if not has_nature:
        if doc_type == 'si':
            chunk_data['nature'] = 'Statutory Instrument'
            modified = True
        elif doc_type == 'ordinance':
            chunk_data['nature'] = 'Ordinance'
            modified = True
    
    # Try to extract year/date from title or other fields
    if title and not has_year:
        # Look for year patterns in title
        year_matches = re.findall(r'(19\d{2}|20\d{2})', title)
        if year_matches:
            chunk_data['year'] = int(year_matches[0])
            modified = True
    
    return modified

def enhance_documents_and_chunks(r2_client, bucket: str, dry_run: bool = False, verbose: bool = False):
    """Enhance metadata for SI and Ordinance documents and chunks."""
    
    doc_types = ['si', 'ordinance']
    total_docs_enhanced = 0
    total_chunks_enhanced = 0
    
    for doc_type in doc_types:
        logger.info("enhancing_doc_type", doc_type=doc_type)
        
        docs_enhanced = 0
        chunks_enhanced = 0
        
        # Step 1: Enhance source documents
        print(f"📄 Enhancing {doc_type.upper()} source documents...")
        
        try:
            paginator = r2_client.get_paginator('list_objects_v2')
            doc_keys = []
            
            for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/docs/{doc_type}/'):
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        doc_keys.append(obj['Key'])
            
            for doc_key in tqdm(doc_keys, desc=f"Docs {doc_type}"):
                try:
                    response = r2_client.get_object(Bucket=bucket, Key=doc_key)
                    doc_data = json.loads(response['Body'].read().decode('utf-8'))
                    
                    if enhance_document_metadata(doc_data, doc_type):
                        docs_enhanced += 1
                        total_docs_enhanced += 1
                        
                        if not dry_run:
                            # Upload enhanced document back
                            r2_client.put_object(
                                Bucket=bucket,
                                Key=doc_key,
                                Body=json.dumps(doc_data, default=str).encode('utf-8'),
                                ContentType='application/json',
                                Metadata=response.get('Metadata', {})
                            )
                            
                        if verbose and docs_enhanced <= 3:
                            print(f"   Enhanced {doc_key}: year={doc_data.get('year')}, date={doc_data.get('date_context')}")
                    
                except Exception as e:
                    logger.error("doc_enhancement_error", doc_key=doc_key, error=str(e))
                    
        except Exception as e:
            logger.error("doc_type_error", doc_type=doc_type, error=str(e))
        
        # Step 2: Enhance chunks
        print(f"🧩 Enhancing {doc_type.upper()} chunks...")
        
        try:
            chunk_keys = []
            for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/chunks/{doc_type}/'):
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        chunk_keys.append(obj['Key'])
            
            for chunk_key in tqdm(chunk_keys, desc=f"Chunks {doc_type}"):
                try:
                    response = r2_client.get_object(Bucket=bucket, Key=chunk_key)
                    chunk_data = json.loads(response['Body'].read().decode('utf-8'))
                    
                    if enhance_chunk_metadata(chunk_data, doc_type):
                        chunks_enhanced += 1
                        total_chunks_enhanced += 1
                        
                        if not dry_run:
                            # Update chunk metadata for R2
                            r2_metadata = response.get('Metadata', {})
                            if chunk_data.get('year'):
                                r2_metadata['year'] = str(chunk_data['year'])
                            if chunk_data.get('date_context'):
                                r2_metadata['date_context'] = str(chunk_data['date_context'])
                            if chunk_data.get('nature'):
                                r2_metadata['nature'] = str(chunk_data['nature'])
                            
                            # Upload enhanced chunk back
                            r2_client.put_object(
                                Bucket=bucket,
                                Key=chunk_key,
                                Body=json.dumps(chunk_data, default=str).encode('utf-8'),
                                ContentType='application/json',
                                Metadata=r2_metadata
                            )
                    
                except Exception as e:
                    logger.error("chunk_enhancement_error", chunk_key=chunk_key, error=str(e))
                    
        except Exception as e:
            logger.error("chunks_error", doc_type=doc_type, error=str(e))
        
        logger.info("doc_type_complete", doc_type=doc_type, docs_enhanced=docs_enhanced, chunks_enhanced=chunks_enhanced)
    
    logger.info("enhancement_complete", total_docs=total_docs_enhanced, total_chunks=total_chunks_enhanced)
    return total_docs_enhanced, total_chunks_enhanced

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Enhance SI and Ordinance metadata")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading changes")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    # Load environment
    load_dotenv(".env.local")
    
    try:
        # Get R2 client
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Run enhancement
        docs_enhanced, chunks_enhanced = enhance_documents_and_chunks(
            r2_client, bucket, dry_run=args.dry_run, verbose=args.verbose
        )
        
        print(f"\n🎉 METADATA ENHANCEMENT COMPLETE!")
        print(f"   📄 Enhanced documents: {docs_enhanced}")
        print(f"   🧩 Enhanced chunks: {chunks_enhanced}")
        
        if args.dry_run:
            print(f"   ℹ️ DRY RUN - No changes were uploaded")
            print(f"   💡 Run without --dry-run to apply changes")
        else:
            print(f"   ✅ Changes uploaded to R2")
            print(f"   🚀 SI/Ordinance metadata now complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

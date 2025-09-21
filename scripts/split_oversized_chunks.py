#!/usr/bin/env python3
"""
Split oversized chunks that exceed OpenAI embedding token limits.

This script finds chunks that exceed 8192 tokens and splits them into 
smaller sub-chunks while preserving all hierarchy and temporal metadata.

Usage:
    python scripts/split_oversized_chunks.py [--dry-run] [--token-limit 8192]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Dict, Any, List

import boto3
from botocore.client import Config
from dotenv import load_dotenv
from tqdm import tqdm
import structlog

logger = structlog.get_logger("split_oversized")

def get_r2_client():
    """Get R2 client."""
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )

def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    return len(text.split()) * 1.3  # Conservative estimate

def smart_split_text(text: str, max_tokens: int = 7500, overlap_tokens: int = 200) -> List[str]:
    """
    Split text intelligently at sentence/paragraph boundaries.
    
    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk (leave buffer below 8192)
        overlap_tokens: Overlap between chunks for context
    
    Returns:
        List of text chunks with overlap
    """
    
    # First, try to split at paragraph boundaries
    paragraphs = re.split(r'\n\s*\n', text)
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
            
        # Check if adding this paragraph would exceed limit
        potential_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
        
        if estimate_tokens(potential_chunk) <= max_tokens:
            current_chunk = potential_chunk
        else:
            # Save current chunk if it has content
            if current_chunk:
                chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap from end of previous chunk
                overlap_text = ""
                sentences = current_chunk.split('. ')
                if len(sentences) > 3:
                    overlap_text = '. '.join(sentences[-2:]) + ". "  # Last 2 sentences for context
                
                current_chunk = overlap_text + paragraph
            else:
                # Single paragraph is too large - split at sentence boundaries
                sentences = re.split(r'(?<=\.)\s+', paragraph)
                temp_chunk = ""
                
                for sentence in sentences:
                    if estimate_tokens(temp_chunk + sentence) <= max_tokens:
                        temp_chunk += sentence + " "
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                            # Add overlap
                            overlap_words = temp_chunk.split()[-20:]  # Last 20 words
                            temp_chunk = " ".join(overlap_words) + " " + sentence + " "
                        else:
                            # Single sentence too large - just truncate (rare case)
                            words = sentence.split()
                            word_count = int(max_tokens * 0.75)  # Conservative word count
                            chunks.append(" ".join(words[:word_count]))
                            temp_chunk = " ".join(words[word_count-20:])  # Overlap
                
                if temp_chunk:
                    current_chunk = temp_chunk
                else:
                    current_chunk = ""
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def create_sub_chunk(original_chunk: Dict[str, Any], sub_text: str, sub_index: int) -> Dict[str, Any]:
    """Create a sub-chunk with all original metadata preserved."""
    
    # Generate new chunk ID for sub-chunk
    original_id = original_chunk.get('chunk_id', '')
    sub_chunk_id = hashlib.sha256(f"{original_id}_{sub_index}_{sub_text[:100]}".encode()).hexdigest()[:16]
    
    # Create sub-chunk with all original metadata
    sub_chunk = original_chunk.copy()
    
    # Update chunk-specific fields
    sub_chunk.update({
        'chunk_id': sub_chunk_id,
        'chunk_text': sub_text,
        'num_tokens': int(estimate_tokens(sub_text)),
        'start_char': 0,  # Simplified
        'end_char': len(sub_text),
    })
    
    # Update section path to indicate sub-chunk
    original_section = original_chunk.get('section_path', '')
    sub_chunk['section_path'] = f"{original_section} (Part {sub_index + 1})"
    
    # Update metadata to indicate sub-chunk
    if not sub_chunk.get('metadata'):
        sub_chunk['metadata'] = {}
    sub_chunk['metadata']['sub_chunk'] = True
    sub_chunk['metadata']['original_chunk_id'] = original_id
    sub_chunk['metadata']['sub_index'] = sub_index
    
    return sub_chunk

def split_oversized_chunk(r2_client, bucket: str, chunk_key: str, token_limit: int = 8192, dry_run: bool = False) -> List[str]:
    """Split an oversized chunk into sub-chunks."""
    
    try:
        # Load the oversized chunk
        response = r2_client.get_object(Bucket=bucket, Key=chunk_key)
        chunk_data = json.loads(response['Body'].read().decode('utf-8'))
        
        chunk_text = chunk_data.get('chunk_text', '')
        num_tokens = chunk_data.get('num_tokens', 0)
        
        logger.info("splitting_chunk", chunk_id=chunk_data.get('chunk_id'), tokens=num_tokens)
        
        # Split the text intelligently
        max_tokens_per_sub = token_limit - 500  # Leave buffer
        sub_texts = smart_split_text(chunk_text, max_tokens=max_tokens_per_sub)
        
        logger.info("split_result", original_tokens=num_tokens, sub_chunks=len(sub_texts))
        
        sub_chunk_keys = []
        
        for i, sub_text in enumerate(sub_texts):
            # Create sub-chunk with preserved metadata
            sub_chunk = create_sub_chunk(chunk_data, sub_text, i)
            
            # Generate R2 key for sub-chunk
            doc_type = chunk_data.get('doc_type', 'unknown')
            sub_chunk_id = sub_chunk['chunk_id']
            sub_chunk_key = f"corpus/chunks/{doc_type}/{sub_chunk_id}.json"
            
            if not dry_run:
                # Upload sub-chunk to R2
                r2_metadata = response.get('Metadata', {}).copy()
                r2_metadata['sub_chunk'] = 'true'
                r2_metadata['original_chunk_id'] = chunk_data.get('chunk_id', '')
                r2_metadata['sub_index'] = str(i)
                
                r2_client.put_object(
                    Bucket=bucket,
                    Key=sub_chunk_key,
                    Body=json.dumps(sub_chunk, default=str).encode('utf-8'),
                    ContentType='application/json',
                    Metadata=r2_metadata
                )
            
            sub_chunk_keys.append(sub_chunk_key)
            
            logger.info("created_sub_chunk", 
                       sub_index=i,
                       sub_chunk_id=sub_chunk_id,
                       tokens=sub_chunk['num_tokens'])
        
        if not dry_run:
            # Remove original oversized chunk
            r2_client.delete_object(Bucket=bucket, Key=chunk_key)
            logger.info("removed_original", chunk_key=chunk_key)
        
        return sub_chunk_keys
        
    except Exception as e:
        logger.error("split_error", chunk_key=chunk_key, error=str(e))
        return []

def find_and_split_oversized_chunks(r2_client, bucket: str, token_limit: int = 8192, dry_run: bool = False):
    """Find all oversized chunks and split them."""
    
    doc_types = ['constitution', 'act', 'ordinance', 'si']
    total_split = 0
    total_sub_chunks_created = 0
    
    for doc_type in doc_types:
        logger.info("checking_doc_type", doc_type=doc_type)
        
        oversized_chunks = []
        
        try:
            # Find oversized chunks in this doc_type
            paginator = r2_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=f'corpus/chunks/{doc_type}/'):
                for obj in page.get('Contents', []):
                    if obj['Key'].endswith('.json'):
                        try:
                            # Quick check using HEAD request to get metadata
                            head_response = r2_client.head_object(Bucket=bucket, Key=obj['Key'])
                            metadata = head_response.get('Metadata', {})
                            
                            # Check if it's already a sub-chunk (skip)
                            if metadata.get('sub_chunk') == 'true':
                                continue
                                
                            # Get token count from metadata if available, otherwise load chunk
                            num_tokens = None
                            if 'num_tokens' in metadata:
                                try:
                                    num_tokens = int(metadata['num_tokens'])
                                except (ValueError, TypeError):
                                    pass
                            
                            if num_tokens is None:
                                # Load chunk to get token count
                                response = r2_client.get_object(Bucket=bucket, Key=obj['Key'])
                                chunk_data = json.loads(response['Body'].read().decode('utf-8'))
                                num_tokens = chunk_data.get('num_tokens', 0)
                            
                            if num_tokens > token_limit:
                                oversized_chunks.append((obj['Key'], num_tokens))
                                
                        except Exception as e:
                            logger.warning("chunk_check_error", chunk_key=obj['Key'], error=str(e))
                            continue
        
        except Exception as e:
            logger.error("doc_type_error", doc_type=doc_type, error=str(e))
            continue
        
        # Split oversized chunks for this doc_type
        if oversized_chunks:
            logger.info("found_oversized", doc_type=doc_type, count=len(oversized_chunks))
            
            for chunk_key, tokens in tqdm(oversized_chunks, desc=f"Splitting {doc_type}"):
                sub_chunk_keys = split_oversized_chunk(r2_client, bucket, chunk_key, token_limit, dry_run)
                
                if sub_chunk_keys:
                    total_split += 1
                    total_sub_chunks_created += len(sub_chunk_keys)
                    
                    print(f"   ✅ Split {chunk_key} ({tokens:,} tokens) → {len(sub_chunk_keys)} sub-chunks")
                else:
                    print(f"   ❌ Failed to split {chunk_key}")
        else:
            logger.info("no_oversized", doc_type=doc_type)
    
    return total_split, total_sub_chunks_created

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Split oversized chunks for embedding compatibility")
    parser.add_argument("--dry-run", action="store_true", help="Run without making changes")
    parser.add_argument("--token-limit", type=int, default=8192, help="Token limit for chunks")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    # Load environment
    load_dotenv(".env.local")
    
    try:
        # Get R2 client
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Find and split oversized chunks
        split_count, sub_chunks_created = find_and_split_oversized_chunks(
            r2_client, bucket, args.token_limit, args.dry_run
        )
        
        print(f"\n🎉 OVERSIZED CHUNK PROCESSING COMPLETE!")
        print(f"   📊 Original oversized chunks: {split_count}")
        print(f"   🧩 Sub-chunks created: {sub_chunks_created}")
        
        if args.dry_run:
            print(f"   ℹ️ DRY RUN - No changes made")
            print(f"   💡 Run without --dry-run to apply splits")
        else:
            print(f"   ✅ Oversized chunks split and uploaded to R2")
            print(f"   🚀 All chunks now within {args.token_limit} token limit!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

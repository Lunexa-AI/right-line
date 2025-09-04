#!/usr/bin/env python3
"""Parse PDFs from Cloudflare R2 into normalized document objects.

This script processes PDF files stored in Cloudflare R2, extracts text content,
and creates normalized document objects. It uploads the parsed documents
back to R2 as a consolidated metadata catalog.

Usage:
    python scripts/parse_docs.py [--max-docs N] [--verbose]

Environment Variables:
    CLOUDFLARE_R2_S3_ENDPOINT, CLOUDFLARE_R2_ACCESS_KEY_ID, 
    CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import boto3
    import fitz  # PyMuPDF
    from botocore.client import Config
except ImportError as e:
    print(f"❌ Error: Missing dependency. Run: poetry add boto3 pymupdf")
    print(f"   Specific error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_r2_client():
    """Initialize and return a boto3 client for Cloudflare R2."""
    try:
        return boto3.client(
            service_name="s3",
            endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
            aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
        )
    except KeyError as e:
        raise RuntimeError(f"Missing required environment variable for R2: {e}")


def extract_text_from_pdf(pdf_content: bytes) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract text from PDF content using PyMuPDF.
    
    Returns:
        Tuple of (full_text, page_info_list)
    """
    try:
        # Create PDF document from bytes
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        full_text = ""
        page_info = []
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            
            if page_text.strip():
                full_text += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"
                page_info.append({
                    "page_number": page_num + 1,
                    "text_length": len(page_text),
                    "has_text": bool(page_text.strip())
                })
        
        doc.close()
        return full_text.strip(), page_info
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return "", []


def sha256_16(text: str) -> str:
    """Generate a 16-character SHA256 hash of the input text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace, quotes, dashes, etc."""
    if not text:
        return ""
    
    # Replace multiple spaces, tabs, newlines with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace("'", "'").replace("'", "'")
    
    # Normalize dashes
    text = text.replace('–', '-').replace('—', '-')
    
    # Trim leading/trailing whitespace
    return text.strip()


def list_pdfs_from_r2(r2_client, bucket: str) -> List[Dict[str, Any]]:
    """List all PDF files from R2 legislation folders with their metadata."""
    pdf_files = []
    
    # List files from all legislation subfolders
    legislation_prefixes = [
        "corpus/sources/legislation/acts/",
        "corpus/sources/legislation/ordinances/", 
        "corpus/sources/legislation/statutory_instruments/"
    ]
    
    for prefix in legislation_prefixes:
        try:
            paginator = r2_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].endswith('.pdf'):
                            # Get object metadata
                            try:
                                head_response = r2_client.head_object(Bucket=bucket, Key=obj['Key'])
                                obj_metadata = head_response.get('Metadata', {})
                                
                                pdf_files.append({
                                    'key': obj['Key'],
                                    'size': obj['Size'],
                                    'last_modified': obj['LastModified'],
                                    'metadata': obj_metadata
                                })
                            except Exception as e:
                                logger.warning(f"Could not get metadata for {obj['Key']}: {e}")
                                
        except Exception as e:
            logger.error(f"Error listing files from {prefix}: {e}")
    
    logger.info(f"Found {len(pdf_files)} PDFs in R2 legislation folders")
    return pdf_files


def parse_pdf_from_r2(r2_client, bucket: str, pdf_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse a PDF from R2 into a normalized document object.
    
    Args:
        r2_client: boto3 client for R2
        bucket: R2 bucket name  
        pdf_info: PDF info dict with key and metadata
        
    Returns:
        Normalized document object or None if parsing fails
    """
    key = pdf_info['key']
    r2_metadata = pdf_info['metadata']
    
    try:
        # Download PDF content from R2
        logger.info(f"Processing PDF: {key}")
        response = r2_client.get_object(Bucket=bucket, Key=key)
        pdf_content = response['Body'].read()
        
        # Extract text from PDF
        full_text, page_info = extract_text_from_pdf(pdf_content)
        
        if not full_text.strip():
            logger.warning(f"No text extracted from PDF: {key}")
            return None
        
        # Get metadata from R2 object metadata
        title = r2_metadata.get('title', 'Untitled Document')
        nature = r2_metadata.get('nature', 'Act')
        doc_type_folder = r2_metadata.get('document_type', 'acts')
        akn_uri = r2_metadata.get('akn_uri', '')
        source_url = r2_metadata.get('source_url', '')
        year = int(r2_metadata.get('year', '0')) if r2_metadata.get('year', '').isdigit() else None
        chapter = r2_metadata.get('chapter')
        effective_date = r2_metadata.get('effective_date')
        work_frbr_uri = r2_metadata.get('work_frbr_uri')
        expression_frbr_uri = r2_metadata.get('expression_frbr_uri')
        
        # Generate stable doc_id from key and content
        doc_id = sha256_16(f"{key}_{akn_uri}_{title}")
        
        # Map document type
        if nature == "Statutory Instrument":
            doc_type = "si"
        elif nature == "Ordinance":
            doc_type = "ordinance"
        else:
            doc_type = "act"
        
        # Create simplified content structure for PDFs
        # Since PDF text extraction is linear, we'll create sections based on page breaks
        sections = []
        
        # Split content by page markers and create sections
        pages = full_text.split("--- Page")
        for i, page_content in enumerate(pages[1:], 1):  # Skip first empty split
            page_text = page_content.strip()
            if page_text and len(page_text) > 100:  # Skip very short pages
                # Remove the page number from the beginning
                page_text = re.sub(r'^\d+\s*---\s*', '', page_text)
                page_text = normalize_whitespace(page_text)
                
                sections.append({
                    "id": f"page-{i}",
                    "title": f"Page {i}",
                    "anchor": f"#page-{i}",
                    "paragraphs": [page_text]
                })
        
        # If no page-based sections found, create a single section
        if not sections:
            normalized_text = normalize_whitespace(full_text)
            sections.append({
                "id": "document-content",
                "title": "Document Content", 
                "anchor": "#content",
                "paragraphs": [normalized_text]
            })
        
        content_tree = {
            "parts": [{
                "title": "Main Content",
                "id": "main",
                "sections": sections
            }]
        }
        
        # Build extra metadata
        extra = {
            "chapter": chapter,
            "expression_uri": expression_frbr_uri,
            "work_uri": work_frbr_uri,
            "akn_uri": akn_uri,
            "nature": nature,
            "year": year,
            "r2_pdf_key": key,
            "page_count": len(page_info),
            "pdf_size_bytes": len(pdf_content),
            "section_ids": [s["id"] for s in sections],
            "part_map": {"Main Content": [s["id"] for s in sections]}
        }
        
        if effective_date:
            extra["effective_start"] = effective_date
        
        # Create document object
        now = datetime.datetime.utcnow().isoformat() + "Z"
        document = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "title": title,
            "source_url": source_url,
            "language": "eng",  # Assume English for ZimLII documents
            "jurisdiction": "ZW",
            "version_effective_date": effective_date,
            "canonical_citation": None,
            "created_at": now,
            "updated_at": now,
            "extra": extra,
            "content_tree": content_tree,
        }
        
        return document
        
    except Exception as e:
        logger.error(f"Error parsing PDF {key}: {e}")
        return None


def process_pdfs_from_r2(r2_client, bucket: str, max_docs: Optional[int] = None) -> None:
    """
    Process all PDF files from R2, parse them, and upload the results back to R2.
    
    Args:
        r2_client: boto3 client for R2
        bucket: R2 bucket name
        max_docs: Maximum number of documents to process (for testing)
    """
    # List all PDFs from R2
    pdf_files = list_pdfs_from_r2(r2_client, bucket)
    
    if max_docs:
        pdf_files = pdf_files[:max_docs]
        logger.info(f"Limited processing to {max_docs} documents for testing")
    
    if not pdf_files:
        logger.warning("No PDF files found in R2")
        return
    
    # Process each PDF
    parsed_documents = []
    failed_count = 0
    
    for pdf_info in pdf_files:
        try:
            document = parse_pdf_from_r2(r2_client, bucket, pdf_info)
            if document:
                parsed_documents.append(document)
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Failed to process {pdf_info['key']}: {e}")
            failed_count += 1
    
    logger.info(f"Successfully parsed {len(parsed_documents)} documents, {failed_count} failed")
    
    if not parsed_documents:
        logger.warning("No documents were successfully parsed")
        return
    
    # Upload parsed documents catalog to R2
    catalog_content = "\n".join([
        json.dumps(doc, default=str) for doc in parsed_documents
    ])
    
    catalog_metadata = {
        "content_type": "application/jsonl",
        "description": "Parsed legislation documents catalog",
        "document_count": str(len(parsed_documents)),
        "processing_timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # Upload to R2
    try:
        put_params = {
            "Bucket": bucket,
            "Key": "corpus/processed/legislation_docs.jsonl",
            "Body": catalog_content.encode("utf-8"),
            "ContentType": "application/json"
        }
        
        if catalog_metadata:
            put_params["Metadata"] = catalog_metadata
        
        r2_client.put_object(**put_params)
        logger.info(f"Uploaded parsed documents catalog to R2")
        
    except Exception as e:
        logger.error(f"Failed to upload catalog to R2: {e}")
    
    logger.info(f"Processing complete. Uploaded {len(parsed_documents)} parsed documents to R2")


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Parse PDFs from R2 into normalized document objects")
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Maximum number of documents to process (for testing)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Get R2 client and bucket
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Process PDFs
        process_pdfs_from_r2(r2_client, bucket, args.max_docs)
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
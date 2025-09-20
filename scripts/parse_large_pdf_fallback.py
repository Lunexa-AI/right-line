#!/usr/bin/env python3
"""
Fallback PDF processor for documents that fail PageIndex processing.

Uses PyMuPDF (fitz) for direct PDF text extraction when PageIndex fails.
Designed specifically for critical documents like Supreme Court Rules.

Usage:
    python scripts/parse_large_pdf_fallback.py --pdf-key "corpus/sources/..." --doc-type si
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List

import boto3
import structlog
from botocore.client import Config
from dotenv import load_dotenv

try:
    import fitz  # PyMuPDF
except ImportError:
    print("❌ Error: PyMuPDF not installed. Run: poetry add pymupdf")
    sys.exit(1)

logger = structlog.get_logger("fallback_processor")

def get_r2_client():
    """Get R2 client."""
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )


def extract_text_with_structure(pdf_bytes: bytes) -> Dict[str, Any]:
    """Extract text and basic structure from PDF using PyMuPDF."""
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        pages = []
        full_text = ""
        page_count = len(doc)
        
        logger.info("Extracting text from PDF", total_pages=page_count)
        
        for page_num in range(page_count):
            page = doc.load_page(page_num)
            
            # Extract text
            text = page.get_text()
            
            # Clean text
            text = re.sub(r'\n+', '\n', text)  # Normalize line breaks
            text = re.sub(r'\s+', ' ', text)   # Normalize spaces
            text = text.strip()
            
            if text:
                pages.append({
                    "page_index": page_num + 1,
                    "text": text,
                    "markdown": f"## Page {page_num + 1}\n\n{text}"
                })
                full_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"
        
        doc.close()
        
        # Create simple structure based on text patterns
        tree_nodes = create_simple_structure(full_text, pages)
        
        return {
            "markdown": full_text.strip(),
            "tree": tree_nodes,
            "page_count": page_count,
            "extraction_method": "pymupdf_fallback"
        }
        
    except Exception as e:
        logger.error("PyMuPDF extraction failed", error=str(e))
        raise


def create_simple_structure(full_text: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create simple document structure from text patterns."""
    
    # For Supreme Court Rules, look for rule numbers and sections
    tree_nodes = []
    
    # Extract major sections/rules
    sections = []
    
    # Look for rule patterns: "Rule 1", "Order 1", "Part I", etc.
    rule_patterns = [
        r'^(Rule\s+\d+[A-Za-z]?[.-].*?)$',
        r'^(Order\s+\d+[.-].*?)$', 
        r'^(Part\s+[IVX]+[.-].*?)$',
        r'^(Section\s+\d+[.-].*?)$',
        r'^(Chapter\s+\d+[.-].*?)$'
    ]
    
    lines = full_text.split('\n')
    current_section = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line starts a new section
        is_section_header = False
        for pattern in rule_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                # Save previous section if it exists
                if current_section and current_text:
                    sections.append({
                        "title": current_section,
                        "text": "\n".join(current_text),
                        "node_id": f"{len(sections):04d}",
                        "page_index": 1  # Simplified
                    })
                
                # Start new section
                current_section = line
                current_text = []
                is_section_header = True
                break
        
        if not is_section_header and current_section:
            current_text.append(line)
    
    # Don't forget the last section
    if current_section and current_text:
        sections.append({
            "title": current_section,
            "text": "\n".join(current_text),
            "node_id": f"{len(sections):04d}",
            "page_index": 1
        })
    
    # If no structured sections found, create simple page-based structure
    if not sections:
        for i, page in enumerate(pages[:10]):  # Limit to first 10 pages for structure
            sections.append({
                "title": f"Page {page['page_index']}",
                "text": page["text"][:2000],  # Limit text length
                "node_id": f"{i:04d}",
                "page_index": page["page_index"]
            })
    
    logger.info("Created document structure", sections=len(sections))
    return sections


def process_pdf_fallback(pdf_key: str, doc_type: str, r2_client, bucket: str) -> Dict[str, Any]:
    """Process PDF using fallback method."""
    
    try:
        logger.info("Starting fallback PDF processing", pdf_key=pdf_key)
        
        # Download PDF from R2
        obj = r2_client.get_object(Bucket=bucket, Key=pdf_key)
        pdf_bytes = obj["Body"].read()
        
        logger.info("PDF downloaded", size_mb=len(pdf_bytes)/(1024*1024))
        
        # Extract with PyMuPDF
        extraction_result = extract_text_with_structure(pdf_bytes)
        
        # Generate document metadata
        filename = os.path.basename(pdf_key)
        doc_id = hashlib.sha256(pdf_key.encode('utf-8')).hexdigest()[:16]
        
        # Extract title from content
        title = extract_title_from_text(extraction_result["markdown"])
        
        # Build parent document
        parent_doc = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "title": title,
            "language": "eng",
            "jurisdiction": "ZW",
            "subject_category": "legislation" if doc_type == "si" else "unknown",
            "authority_level": "medium" if doc_type == "si" else "unknown",
            "hierarchy_rank": 3 if doc_type == "si" else 99,
            "binding_scope": "specific" if doc_type == "si" else "unknown",
            "canonical_citation": title,
            "pageindex_doc_id": f"fallback_{doc_id}",
            "content_tree": extraction_result["tree"],
            "pageindex_markdown": extraction_result["markdown"],
            "extra": {
                "r2_pdf_key": pdf_key,
                "tree_nodes_count": len(extraction_result["tree"]),
                "markdown_length": len(extraction_result["markdown"]),
                "page_count": extraction_result["page_count"],
                "extraction_method": extraction_result["extraction_method"],
                "processed_at": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        logger.info("Fallback processing completed",
                   doc_id=doc_id,
                   title=title[:50],
                   tree_nodes=len(extraction_result["tree"]),
                   pages=extraction_result["page_count"])
        
        return parent_doc
        
    except Exception as e:
        logger.error("Fallback processing failed", pdf_key=pdf_key, error=str(e))
        raise


def extract_title_from_text(text: str) -> str:
    """Extract document title from text content."""
    
    lines = text.split('\n')[:20]  # Check first 20 lines
    
    # Look for common title patterns
    title_patterns = [
        r'^(Supreme Court Rules.*?)$',
        r'^(High Court Rules.*?)$',
        r'^([A-Z][A-Za-z\s]+Rules.*?)$',
        r'^(Statutory Instrument.*?)$',
        r'^([A-Z][A-Za-z\s]+Act.*?)$'
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        for pattern in title_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    
    # Fallback title
    return "Supreme Court Rules, 2025"


def upload_document(r2_client, bucket: str, doc: Dict[str, Any]):
    """Upload processed document to R2."""
    
    obj_key = f"corpus/docs/{doc['doc_type']}/{doc['doc_id']}.json"
    
    # Prepare metadata
    r2_metadata = {
        "doc_id": doc["doc_id"],
        "doc_type": doc["doc_type"],
        "title": doc["title"][:900],  # Truncate for R2 limits
        "jurisdiction": doc["jurisdiction"],
        "language": doc["language"],
        "subject_category": doc["subject_category"],
        "authority_level": doc["authority_level"],
        "hierarchy_rank": str(doc["hierarchy_rank"]),
        "extraction_method": doc["extra"]["extraction_method"],
        "processed_at": doc["extra"]["processed_at"]
    }
    
    r2_client.put_object(
        Bucket=bucket,
        Key=obj_key,
        Body=json.dumps(doc, default=str).encode("utf-8"),
        ContentType="application/json",
        Metadata=r2_metadata
    )
    
    logger.info("Document uploaded to R2", obj_key=obj_key)


def main():
    """Main processing function."""
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-key", required=True, help="R2 key of PDF to process")
    parser.add_argument("--doc-type", required=True, help="Document type (si, act, etc.)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load environment
    load_dotenv(".env.local")
    bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    r2_client = get_r2_client()
    
    try:
        # Process PDF with fallback method
        doc = process_pdf_fallback(args.pdf_key, args.doc_type, r2_client, bucket)
        
        # Upload to R2
        upload_document(r2_client, bucket, doc)
        
        print(f"✅ Successfully processed with fallback method:")
        print(f"   Title: {doc['title']}")
        print(f"   Doc Type: {doc['doc_type']}")
        print(f"   Tree Nodes: {len(doc['content_tree'])}")
        print(f"   Pages: {doc['extra']['page_count']}")
        print(f"   Text Length: {len(doc['pageindex_markdown']):,} characters")
        
        # Now we need to manually add to manifest since we're bypassing the main script
        print(f"\n📋 MANUAL MANIFEST UPDATE REQUIRED:")
        print(f"   The document was processed outside the main script")
        print(f"   Need to add to manifest manually or re-run manifest recreation")
        
    except Exception as e:
        print(f"❌ Fallback processing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

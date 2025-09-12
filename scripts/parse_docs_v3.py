#!/usr/bin/env python3
"""Parse PDFs from R2 using PageIndex OCR + Tree.

This script supersedes `parse_docs.py`. It requires the environment variable
`PAGEINDEX_API_KEY`.  Text extraction and hierarchical structure are provided
by the PageIndex Cloud API (not SDK).

Output:
* Parent-document JSON objects uploaded to `corpus/docs/{doc_type}/{doc_id}.json`.
* Master manifest `corpus/processed/legislation_docs.jsonl`.

Usage:
    python scripts/parse_docs_v3.py [--max-docs 5] [--poll-interval 8] [--verbose]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

import boto3
import requests
from botocore.client import Config
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("parse_docs_v3")

# cloud base URL
PAGEINDEX_API_URL = os.getenv("PAGEINDEX_API_URL", "https://api.pageindex.ai")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def get_r2_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )


LEGISLATION_PREFIXES = [
    "corpus/sources/legislation/acts/",
    "corpus/sources/legislation/ordinances/",
    "corpus/sources/legislation/statutory_instruments/",
]


def list_pdfs(r2, bucket: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    paginator = r2.get_paginator("list_objects_v2")
    for prefix in LEGISLATION_PREFIXES:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".pdf"):
                    out.append({"key": obj["Key"], "size": obj["Size"], "last_modified": obj["LastModified"]})
    logger.info("Found %d PDFs across legislation prefixes", len(out))
    return out


# ---------------------------------------------------------------------------
# PageIndex API
# ---------------------------------------------------------------------------

def _tree_to_markdown(tree_nodes: List[Dict[str, Any]], level: int = 0) -> str:
    """Convert PageIndex tree structure to markdown."""
    markdown_parts = []
    for node in tree_nodes:
        title = node.get("title", "Untitled")
        text = node.get("text", "")
        
        # Add heading
        heading_prefix = "#" * (level + 1)
        markdown_parts.append(f"{heading_prefix} {title}\n\n")
        
        # Add node text if available
        if text:
            markdown_parts.append(f"{text}\n\n")
        
        # Process child nodes recursively
        child_nodes = node.get("nodes", [])
        if child_nodes:
            child_markdown = _tree_to_markdown(child_nodes, level + 1)
            markdown_parts.append(child_markdown)
    
    return "".join(markdown_parts)

def extract_akn_metadata(filename: str, tree_nodes: List[Dict[str, Any]], full_markdown: str = "", ocr_pages: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract comprehensive metadata from filename and PageIndex tree."""
    metadata = {
        "title": os.path.basename(filename).replace(".pdf", ""),
        "jurisdiction": "ZW",
        "language": "eng",
        "doc_type": None,
        "chapter": None,
        "act_number": None,
        "act_year": None,
        "version_date": None,
        "akn_uri": None,
        "canonical_citation": None,
        "subject_category": None
    }
    
    # Determine doc_type from R2 path structure first
    if "/acts/" in filename:
        metadata["doc_type"] = "act"
        metadata["subject_category"] = "legislation"
    elif "/ordinances/" in filename:
        metadata["doc_type"] = "ordinance"  
        metadata["subject_category"] = "legislation"
    elif "/statutory_instruments/" in filename:
        metadata["doc_type"] = "si"
        metadata["subject_category"] = "legislation"
    elif "/judgments/" in filename:
        metadata["doc_type"] = "judgment"
        metadata["subject_category"] = "case_law"
    elif "/case_law/" in filename:
        metadata["doc_type"] = "case"
        metadata["subject_category"] = "case_law"
    else:
        metadata["doc_type"] = "unknown"
        metadata["subject_category"] = "unknown"
    
    # Parse AKN URI from filename: akn_zw_act_1860_28_eng_2016-12-31.pdf
    akn_pattern = r"akn_([a-z]{2})_([a-z]+)_(\d{4})_(\d+)_([a-z]{3})_(\d{4}-\d{2}-\d{2})"
    match = re.search(akn_pattern, filename)
    if match:
        jurisdiction, akn_doc_type, year, number, lang, version = match.groups()
        metadata.update({
            "jurisdiction": jurisdiction.upper(),
            "doc_type": akn_doc_type,  # Override with AKN type if available
            "act_year": year,
            "act_number": number,
            "language": lang,
            "version_date": version,
            "akn_uri": f"/akn/{jurisdiction}/{akn_doc_type}/{year}/{number}/{lang}@{version}"
        })
        
        # Update subject category based on AKN doc type
        if akn_doc_type in ["act", "ordinance", "si"]:
            metadata["subject_category"] = "legislation"
        elif akn_doc_type in ["judgment", "case"]:
            metadata["subject_category"] = "case_law"
    
    # Extract title and chapter from OCR pages first (more reliable)
    if ocr_pages:
        # Look in first few pages for document title and chapter
        for page in ocr_pages[:3]:  # Check first 3 pages
            page_text = page.get("markdown", "")
            
            # Look for document title patterns
            title_patterns = [
                r"^([A-Z][A-Za-z\s]+Act)\s*$",  # "Some Act"
                r"([A-Z][A-Za-z\s]+Act)\s*Chapter",  # "Some Act Chapter"
                r"([A-Z][A-Za-z\s]+Act)\s*\n",  # "Some Act" followed by newline
            ]
            
            for pattern in title_patterns:
                title_match = re.search(pattern, page_text, re.MULTILINE)
                if title_match:
                    potential_title = title_match.group(1).strip()
                    if len(potential_title) > 5:  # Reasonable title length
                        metadata["title"] = potential_title
                        break
            
            # Look for chapter pattern
            chapter_match = re.search(r"Chapter\s+(\d+:\d+)", page_text, re.IGNORECASE)
            if chapter_match:
                metadata["chapter"] = chapter_match.group(1)
    
    # Fallback: Extract from full markdown
    if not metadata["title"] or not metadata["chapter"]:
        if full_markdown:
            # Look for document title
            if not metadata["title"]:
                title_match = re.search(r"([A-Z][A-Za-z\s]+Act)", full_markdown)
                if title_match:
                    metadata["title"] = title_match.group(1).strip()
            
            # Look for chapter
            if not metadata["chapter"]:
                chapter_match = re.search(r"Chapter\s+(\d+:\d+)", full_markdown, re.IGNORECASE)
                if chapter_match:
                    metadata["chapter"] = chapter_match.group(1)
    
    # Final fallback: Extract from PageIndex tree
    if not metadata["title"] and tree_nodes:
        root_node = tree_nodes[0]
        title = root_node.get("title", "")
        if title and title != "Untitled" and not title.startswith("1."):
            metadata["title"] = title
    
    # Build canonical citation
    if metadata["title"] and metadata["chapter"]:
        metadata["canonical_citation"] = f"{metadata['title']} [Chapter {metadata['chapter']}]"
    
    return metadata

def submit_to_pageindex(pdf_bytes: bytes, filename: str, api_key: str) -> str:
    """Upload PDF; return remote `doc_id`."""
    url = f"{PAGEINDEX_API_URL}/doc/"
    headers = {"api_key": api_key}
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    resp = requests.post(url, headers=headers, files=files, timeout=120)
    resp.raise_for_status()
    return resp.json()["doc_id"]


def poll_pageindex(doc_id: str, api_key: str, poll_interval: int = 8) -> Dict[str, Any]:
    """Wait until OCR + Tree is finished; return combined result."""
    headers = {"api_key": api_key}
    status_url = f"{PAGEINDEX_API_URL}/doc/{doc_id}/"

    # wait until processing completed
    while True:
        resp = requests.get(status_url, headers=headers, timeout=30)
        resp.raise_for_status()
        logger.debug("Status response: %s", resp.text[:500])
        data = resp.json()
        st = data.get("status")
        logger.info("Current status: %s", st)
        if st == "completed":
            break
        elif st == "failed":
            raise RuntimeError(f"PageIndex processing failed for {doc_id}: {resp.text}")
        time.sleep(poll_interval)

    # Fetch tree structure for hierarchical info
    tree_url = f"{status_url}?type=tree"
    tree_resp = requests.get(tree_url, headers=headers, timeout=60)
    tree_resp.raise_for_status()
    tree_data = tree_resp.json()
    tree = tree_data.get("result", [])
    logger.info("Got tree with %d root nodes", len(tree))
    
    # Fetch OCR in page format for full content and metadata
    ocr_page_url = f"{status_url}?type=ocr&format=page"
    ocr_resp = requests.get(ocr_page_url, headers=headers, timeout=60)
    ocr_resp.raise_for_status()
    ocr_data = ocr_resp.json()
    pages = ocr_data.get("result", [])
    logger.info("Got OCR with %d pages", len(pages))
    
    # Combine all page markdown
    full_markdown = ""
    for page in pages:
        page_markdown = page.get("markdown", "")
        if page_markdown:
            full_markdown += f"\n\n--- Page {page.get('page_index', '?')} ---\n\n{page_markdown}"
    
    # Also try OCR node format for structured content
    ocr_node_url = f"{status_url}?type=ocr&format=node"
    try:
        node_resp = requests.get(ocr_node_url, headers=headers, timeout=60)
        node_resp.raise_for_status()
        node_data = node_resp.json()
        ocr_nodes = node_data.get("result", [])
        logger.info("Got OCR nodes: %d", len(ocr_nodes))
    except Exception as e:
        logger.warning("Failed to get OCR nodes: %s", e)
        ocr_nodes = []

    return {
        "markdown": full_markdown.strip(), 
        "tree": tree, 
        "ocr_pages": pages,
        "ocr_nodes": ocr_nodes,
        "pageindex_doc_id": doc_id
    }

# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_pdf(r2, bucket: str, pdf_info: Dict[str, Any], api_key: str, poll_interval: int) -> Optional[Dict[str, Any]]:
    key = pdf_info["key"]
    obj = r2.get_object(Bucket=bucket, Key=key)
    pdf_bytes = obj["Body"].read()

    # Submit to PageIndex
    remote_doc_id = submit_to_pageindex(pdf_bytes, os.path.basename(key), api_key)
    logger.info("Submitted %s → PageIndex doc_id %s", key, remote_doc_id)

    result = poll_pageindex(remote_doc_id, api_key, poll_interval)

    # Extract comprehensive metadata with OCR data
    metadata = extract_akn_metadata(key, result["tree"], result["markdown"], result.get("ocr_pages", []))
    canonical_id = sha256_16(f"{key}_{remote_doc_id}")

    # Count nodes
    def count_nodes(nodes):
        total = len(nodes)
        for node in nodes:
            if 'nodes' in node:
                total += count_nodes(node['nodes'])
        return total
    
    total_nodes = count_nodes(result["tree"])
    
    parent_doc = {
        "doc_id": canonical_id,
        "doc_type": metadata["doc_type"],
        "title": metadata["title"],
        "language": metadata["language"],
        "jurisdiction": metadata["jurisdiction"],
        "chapter": metadata["chapter"],
        "act_number": metadata["act_number"],
        "act_year": metadata["act_year"],
        "version_date": metadata["version_date"],
        "akn_uri": metadata["akn_uri"],
        "canonical_citation": metadata["canonical_citation"],
        "subject_category": metadata["subject_category"],
        "pageindex_doc_id": remote_doc_id,
        "content_tree": result["tree"],
        "pageindex_markdown": result["markdown"],
        "extra": {
            "r2_pdf_key": key,
            "tree_nodes_count": total_nodes,
            "markdown_length": len(result["markdown"]),
            "processed_at": datetime.datetime.utcnow().isoformat() + "Z"
        },
    }
    return parent_doc


def upload_parent_doc(r2, bucket: str, doc: Dict[str, Any]):
    obj_key = f"corpus/docs/{doc['doc_type']}/{doc['doc_id']}.json"
    
    # Build R2 metadata (string values only, sanitized)
    def sanitize_metadata_value(value):
        """Remove newlines and limit length for R2 metadata."""
        if not value:
            return ""
        return str(value).replace('\n', ' ').replace('\r', ' ').strip()[:1000]
    
    r2_metadata = {
        "doc_id": doc["doc_id"],
        "doc_type": doc["doc_type"], 
        "title": sanitize_metadata_value(doc["title"]),
        "jurisdiction": doc["jurisdiction"],
        "language": doc["language"],
        "subject_category": doc["subject_category"],
        "pageindex_doc_id": doc["pageindex_doc_id"],
        "tree_nodes_count": str(doc["extra"]["tree_nodes_count"]),
        "markdown_length": str(doc["extra"]["markdown_length"]),
        "processed_at": doc["extra"]["processed_at"]
    }
    
    # Add optional fields if present
    if doc.get("chapter"):
        r2_metadata["chapter"] = doc["chapter"]
    if doc.get("act_number"):
        r2_metadata["act_number"] = doc["act_number"]
    if doc.get("act_year"):
        r2_metadata["act_year"] = doc["act_year"]
    if doc.get("version_date"):
        r2_metadata["version_date"] = doc["version_date"]
    if doc.get("akn_uri"):
        r2_metadata["akn_uri"] = sanitize_metadata_value(doc["akn_uri"])
    
    r2.put_object(
        Bucket=bucket, 
        Key=obj_key, 
        Body=json.dumps(doc).encode("utf-8"), 
        ContentType="application/json",
        Metadata=r2_metadata
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=8, help="Seconds between PageIndex status checks")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    load_dotenv(".env.local")
    api_key = os.getenv("PAGEINDEX_API_KEY")
    if not api_key:
        logger.error("PAGEINDEX_API_KEY not set")
        sys.exit(1)

    bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    r2 = get_r2_client()

    pdfs = list_pdfs(r2, bucket)
    if args.max_docs:
        pdfs = pdfs[: args.max_docs]

    parsed: List[Dict[str, Any]] = []
    for pdf in pdfs:
        try:
            doc = process_pdf(r2, bucket, pdf, api_key, args.poll_interval)
            if doc:
                parsed.append(doc)
                upload_parent_doc(r2, bucket, doc)
        except Exception as e:
            logger.error("Failed to process %s: %s", pdf["key"], e)

    if not parsed:
        logger.warning("No documents parsed successfully.")
        return

    # Build manifest with R2 metadata
    manifest_key = "corpus/processed/legislation_docs.jsonl"
    content = "\n".join(json.dumps(d) for d in parsed)
    
    # Aggregate statistics for manifest metadata
    doc_types = {}
    jurisdictions = set()
    total_nodes = 0
    total_markdown_chars = 0
    
    for doc in parsed:
        doc_type = doc.get("doc_type", "unknown")
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        jurisdictions.add(doc.get("jurisdiction", "unknown"))
        total_nodes += doc["extra"]["tree_nodes_count"]
        total_markdown_chars += doc["extra"]["markdown_length"]
    
    manifest_metadata = {
        "content_type": "application/jsonl",
        "description": "Parsed legislation documents manifest",
        "document_count": str(len(parsed)),
        "total_tree_nodes": str(total_nodes),
        "total_markdown_chars": str(total_markdown_chars),
        "doc_types": ",".join(f"{k}:{v}" for k, v in doc_types.items()),
        "jurisdictions": ",".join(jurisdictions),
        "processing_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "pageindex_integration": "enabled"
    }
    
    r2.put_object(
        Bucket=bucket, 
        Key=manifest_key, 
        Body=content.encode("utf-8"), 
        ContentType="application/json",
        Metadata=manifest_metadata
    )
    logger.info("Uploaded manifest with %d documents", len(parsed))


if __name__ == "__main__":
    main()

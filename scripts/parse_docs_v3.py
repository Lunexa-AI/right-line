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
import hashlib
import json
import logging
import os
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

def submit_to_pageindex(pdf_bytes: bytes, filename: str, api_key: str) -> str:
    """Upload PDF; return remote `doc_id`."""
    url = f"{PAGEINDEX_API_URL}/doc/"
    headers = {"api_key": api_key}
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    resp = requests.post(url, headers=headers, files=files, timeout=120)
    resp.raise_for_status()
    return resp.json()["doc_id"]


def poll_pageindex(doc_id: str, api_key: str, poll_interval: int = 8) -> Dict[str, Any]:
    """Wait until OCR + Tree is finished; return result."""
    headers = {"api_key": api_key}
    status_url = f"{PAGEINDEX_API_URL}/doc/{doc_id}/"

    # wait until processing completed
    completed_response = None
    while True:
        resp = requests.get(status_url, headers=headers, timeout=30)
        resp.raise_for_status()
        logger.debug("Status response: %s", resp.text[:500])
        data = resp.json()
        st = data.get("status")
        logger.info("Current status: %s", st)
        if st == "completed":
            completed_response = data
            break
        elif st == "failed":
            raise RuntimeError(f"PageIndex processing failed for {doc_id}: {resp.text}")
        time.sleep(poll_interval)

    # Extract tree from completed status response
    tree = completed_response.get("result", [])
    logger.info("Got tree with %d root nodes", len(tree))
    
    # Generate markdown from tree structure (simplified)
    markdown = _tree_to_markdown(tree)

    return {"markdown": markdown, "tree": tree, "pageindex_doc_id": doc_id}

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

    # metadata placeholders (could call head_object to retrieve details later)
    doc_type = "act" if "acts/" in key else "ordinance" if "ordinances/" in key else "si"
    canonical_id = sha256_16(f"{key}_{remote_doc_id}")

    parent_doc = {
        "doc_id": canonical_id,
        "doc_type": doc_type,
        "title": os.path.basename(key),
        "language": "eng",
        "pageindex_doc_id": remote_doc_id,
        "content_tree": result["tree"],
        "pageindex_markdown": result["markdown"],
        "extra": {
            "r2_pdf_key": key,
            "page_count": len(result["markdown"].split("\n")),
        },
    }
    return parent_doc


def upload_parent_doc(r2, bucket: str, doc: Dict[str, Any]):
    obj_key = f"corpus/docs/{doc['doc_type']}/{doc['doc_id']}.json"
    r2.put_object(Bucket=bucket, Key=obj_key, Body=json.dumps(doc).encode("utf-8"), ContentType="application/json")


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

    manifest_key = "corpus/processed/legislation_docs.jsonl"
    content = "\n".join(json.dumps(d) for d in parsed)
    r2.put_object(Bucket=bucket, Key=manifest_key, Body=content.encode("utf-8"), ContentType="application/json")
    logger.info("Uploaded manifest with %d documents", len(parsed))


if __name__ == "__main__":
    main()

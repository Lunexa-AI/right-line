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
from typing import Any, Dict, List, Optional, Tuple

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


def _sanitize_text(text: str, node_title: Optional[str] = None) -> str:
    """Remove OCR artifacts and boilerplate from node text.
    - Strip physical markers and image references
    - Drop boilerplate (About this collection, FRBR URI, license, contact)
    - Remove duplicate intra-text heading matching node title
    - Normalize LaTeX-ish tokens and whitespace
    """
    if not text:
        return ""

    cleaned = text
    # Remove physical markers
    cleaned = re.sub(r"<physical_index_\d+>\n?", "", cleaned)
    # Remove images
    cleaned = re.sub(r"!\[[^\]]*\]\([^\)]*\)\n?", "", cleaned)
    # Remove boilerplate lines
    boilerplate_patterns = [
        r"^About this collection.*$",
        r"^FRBR URI.*$",
        r"^This PDF copy is licensed.*$",
        r"^There (?:is no copyright|may have been updates).*$",
        r"^www\.[^\s]+$",
        r"^info@[^\s]+$",
    ]
    for pat in boilerplate_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.MULTILINE)

    # Remove duplicate heading matching node title
    if node_title:
        heading_patterns = [
            rf"^\#{{1,6}}\s+{re.escape(node_title)}\s*$",
            rf"^\#{{1,6}}\s+{re.escape(node_title)}\b.*$",
        ]
        for pat in heading_patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.MULTILINE)

    # Normalize LaTeX-ish tokens
    cleaned = cleaned.replace("$\\quad$", " ")
    cleaned = re.sub(r"\$\s*([\d]+)\s*/\s*([\d]+)\s*/\s*([\d]+)\s*\$", r"\1/\2/\3", cleaned)
    # Collapse blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_tree(tree_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitize tree structure:
    - Remove banner nodes like 'Zimbabwe'
    - Remove 'Chapter X:Y' nodes (captured as metadata elsewhere)
    - Hoist meaningful children when removing a wrapper
    - Sanitize text for each node
    - Deduplicate nodes by normalized title within the same parent, keeping the longest text
    """
    if not tree_nodes:
        return tree_nodes

    def is_banner(title: str) -> bool:
        t = (title or "").strip()
        return t in {"Zimbabwe", "About this collection", "Contents"}

    def is_chapter(title: str) -> bool:
        return bool(re.match(r"^Chapter\s+\d+:\d+\b", (title or "").strip(), flags=re.IGNORECASE))

    sanitized_children: List[Dict[str, Any]] = []

    for node in tree_nodes:
        title = node.get("title", "")
        if is_banner(title) or is_chapter(title):
            # Hoist grandchildren if present
            for child in node.get("nodes", []) or []:
                # Sanitize each hoisted child recursively
                sanitized_children.extend(_sanitize_tree([child]))
            continue

        new_node = node.copy()
        # Sanitize text
        if new_node.get("text"):
            new_node["text"] = _sanitize_text(new_node["text"], node_title=title)

        # Recurse for children
        if new_node.get("nodes"):
            new_node["nodes"] = _sanitize_tree(new_node["nodes"])

        sanitized_children.append(new_node)

    # Deduplicate by normalized title within this level
    normalized_map: Dict[str, Dict[str, Any]] = {}
    for n in sanitized_children:
        key = re.sub(r"\s+", " ", (n.get("title") or "").strip()).lower()
        if key in normalized_map:
            # Keep the node with more text content
            existing = normalized_map[key]
            existing_len = len(existing.get("text", ""))
            new_len = len(n.get("text", ""))
            if new_len > existing_len:
                normalized_map[key] = n
        else:
            normalized_map[key] = n

    return list(normalized_map.values())

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
    
    # Helper to normalize a heading string into a clean title
    def _clean_title(raw_title: str) -> str:
        t = (raw_title or "").strip()
        # Remove leading numbering like '1. '
        t = re.sub(r"^\d+\.\s+", "", t)
        # Remove trailing Chapter suffix
        t = re.sub(r"\s*Chapter\s+\d+:\d+\s*$", "", t, flags=re.IGNORECASE)
        return t.strip()

    # Prefer titles from the structural tree that look like legislation headings
    def _pick_title_from_tree(nodes: List[Dict[str, Any]]) -> Optional[str]:
        for node in nodes:
            title = (node.get("title") or "").strip()
            if not title:
                continue
            # Accept if contains key legal doc keywords
            if re.search(r"\b(Act|Ordinance|Constitution)\b", title) or title.startswith("Statutory Instrument"):
                return _clean_title(title)
        return None

    tree_title = _pick_title_from_tree(tree_nodes) if tree_nodes else None
    if tree_title:
        metadata["title"] = tree_title

    # Extract title and chapter from OCR pages
    if ocr_pages and (not metadata["title"] or not metadata["chapter"]):
        for page in ocr_pages[:3]:
            page_text = page.get("markdown", "") or page.get("text", "")
            # Prefer line-anchored detection
            for line in page_text.splitlines():
                line_clean = line.strip()
                if not line_clean:
                    continue
                if not metadata["title"]:
                    m_line = re.match(r"^([A-Z][A-Za-z'\- ]+?(?:Act|Ordinance|Constitution))\b", line_clean)
                    if m_line:
                        metadata["title"] = _clean_title(m_line.group(1))
                        # no break; still look for chapter
                if not metadata["chapter"]:
                    m_ch = re.search(r"Chapter\s+(\d+:\d+)", line_clean, flags=re.IGNORECASE)
                    if m_ch:
                        metadata["chapter"] = m_ch.group(1)
    
    # Fallback: Extract from full markdown (and override filename placeholder if detected)
    def _is_placeholder_title(title_value: Optional[str]) -> bool:
        if not title_value:
            return True
        lower = title_value.lower()
        if lower.startswith("akn_"):
            return True
        if "_" in title_value:
            return True
        return False

    if full_markdown:
        # Prefer line-anchored detection to avoid cross-line matches (e.g., leading 'Zimbabwe')
        extracted_title: Optional[str] = None
        for line in full_markdown.splitlines():
            line_clean = line.strip()
            if not line_clean:
                continue
            # Acts / Ordinances / Constitutions
            m_line = re.match(r"^([A-Z][A-Za-z'\- ]+?(?:Act|Ordinance|Constitution))\b", line_clean)
            if m_line:
                extracted_title = m_line.group(1).strip()
                break
            # Statutory Instrument
            m_si = re.match(r"^(Statutory\s+Instrument\s+No\.?\s*\d+\s*of\s*\d{4})\b", line_clean)
            if m_si:
                extracted_title = m_si.group(1).strip()
                break

        # If still not found, try broader search (may span whitespace but we'll post-trim to last 'Act' word)
        if not extracted_title:
            title_patterns = [
                r"([A-Z][A-Za-z'\-\s]+Act)\b",
                r"([A-Z][A-Za-z'\-\s]+Ordinance)\b",
                r"(Statutory\s+Instrument\s+No\.?\s*\d+\s*of\s*\d{4})\b",
                r"([A-Z][A-Za-z'\-\s]+Constitution)\b",
            ]
            for pattern in title_patterns:
                m = re.search(pattern, full_markdown)
                if m:
                    candidate = m.group(1).strip()
                    # If candidate spans multiple words including newlines (e.g., 'Zimbabwe ... Act'),
                    # reduce to the shortest suffix ending with the key word
                    parts = re.split(r"\s+", candidate)
                    if "Act" in parts:
                        # Take from the last capitalized word before 'Act'
                        act_idx = len(parts) - 1 - parts[::-1].index("Act")
                        reduced = " ".join(parts[: act_idx + 1])
                        candidate = reduced
                    if len(candidate) >= 6:
                        extracted_title = candidate
                        break

        if extracted_title and (_is_placeholder_title(metadata["title"]) or extracted_title != metadata["title"]):
            metadata["title"] = extracted_title

        # Extract chapter if missing
        if not metadata["chapter"]:
            chapter_match = re.search(r"Chapter\s+(\d+:\d+)", full_markdown, re.IGNORECASE)
            if chapter_match:
                metadata["chapter"] = chapter_match.group(1)

        # As a final robust fallback, parse the Short title clause
        if (not metadata["title"]) or metadata["title"].lower() in {"this act", "this ordinance", "this constitution"}:
            # Typical phrasing: "This Act may be cited as the X Act [Chapter Y:Z]."
            m_short = re.search(r"This\s+(Act|Ordinance|Constitution)\s+may\s+be\s+cited\s+as\s+the\s+(.+?)\s+(Act|Ordinance|Constitution)\b", full_markdown, flags=re.IGNORECASE)
            if m_short:
                candidate = m_short.group(2).strip() + " " + m_short.group(3).capitalize()
                metadata["title"] = _clean_title(candidate)
    
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

def _enhance_tree_with_ocr_content(tree_nodes: List[Dict[str, Any]], ocr_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enhance tree structure by mapping OCR node content to tree nodes."""
    if not ocr_nodes:
        logger.warning("No OCR nodes available for tree enhancement")
        return tree_nodes
    
    # Create a mapping from a normalized title to OCR text content
    ocr_content_map = {}
    for ocr_node in ocr_nodes:
        title = ocr_node.get("title", "").strip()
        text = ocr_node.get("text", "").strip()
        if title and text:
            # Normalize title for better matching
            normalized_title = re.sub(r'\s+', ' ', title).lower()
            ocr_content_map[normalized_title] = text
    
    logger.info(f"Created OCR content map with {len(ocr_content_map)} nodes")
    
    def enhance_node(node: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively enhance tree nodes with OCR content."""
        enhanced_node = node.copy()
        title = node.get("title", "").strip()
        normalized_title = re.sub(r'\s+', ' ', title).lower()
        
        # Add OCR text content if available
        if normalized_title in ocr_content_map:
            enhanced_node["text"] = ocr_content_map[normalized_title]
            logger.debug(f"Enhanced node '{title}' with {len(ocr_content_map[normalized_title])} chars")
        
        # Recursively enhance child nodes
        if "nodes" in node:
            enhanced_node["nodes"] = [enhance_node(child) for child in node["nodes"]]
        
        return enhanced_node
    
    # Enhance all root nodes
    enhanced_tree = [enhance_node(node) for node in tree_nodes]
    
    # Count nodes with text after enhancement
    def count_nodes_with_text(nodes):
        count = 0
        for node in nodes:
            if node.get("text") and len(node.get("text", "").strip()) > 50:
                count += 1
            if "nodes" in node:
                count += count_nodes_with_text(node["nodes"])
        return count
    
    nodes_with_text = count_nodes_with_text(enhanced_tree)
    logger.info(f"Enhanced tree: {nodes_with_text} nodes now have text content")
    
    return enhanced_tree

def _merge_tree_and_ocr_nodes(tree_nodes: List[Dict[str, Any]], ocr_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge OCR node text content into a structural tree from PageIndex.

    This is the core fix for documents where the `type=tree` response lacks text.
    It maps text from `type=ocr&format=node` based on title and page index.
    """
    if not ocr_nodes:
        logger.warning("No OCR nodes available for merging.")
        return tree_nodes

    # Create a lookup map from OCR nodes: (normalized_title, page_index) -> text
    ocr_map: Dict[Tuple[str, int], str] = {}
    for ocr_node in ocr_nodes:
        title = ocr_node.get("title", "").strip()
        text = ocr_node.get("text", "").strip()
        page_index = ocr_node.get("page_index")
        if title and text and page_index is not None:
            # Normalize title for robust matching
            normalized_title = re.sub(r'\s+', ' ', title).lower()
            ocr_map[(normalized_title, page_index)] = text

    logger.info(f"Built OCR content map with {len(ocr_map)} entries.")

    def merge_recursively(structural_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Recursively walk the structural tree and inject text."""
        enhanced_nodes = []
        for node in structural_nodes:
            enhanced_node = node.copy()
            title = node.get("title", "").strip()
            page_index = node.get("page_index")
            
            # If node has no text, try to find it in the OCR map
            if not enhanced_node.get("text") and title and page_index is not None:
                normalized_title = re.sub(r'\s+', ' ', title).lower()
                if (normalized_title, page_index) in ocr_map:
                    enhanced_node["text"] = ocr_map[(normalized_title, page_index)]
                    logger.debug(f"Merged text into node '{title}' (page {page_index})")

            # Recurse for children
            if "nodes" in enhanced_node:
                enhanced_node["nodes"] = merge_recursively(enhanced_node["nodes"])
            
            enhanced_nodes.append(enhanced_node)
        return enhanced_nodes

    merged_tree = merge_recursively(tree_nodes)

    # Final count for verification
    def count_nodes_with_text(nodes):
        count = 0
        for node in nodes:
            if node.get("text"):
                count += 1
            if "nodes" in node:
                count += count_nodes_with_text(node["nodes"])
        return count

    final_count = count_nodes_with_text(merged_tree)
    logger.info(f"After merging, {final_count} nodes have text content.")
    
    return merged_tree


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

    # Fetch tree structure (may lack text)
    tree_url = f"{status_url}?type=tree"
    tree_resp = requests.get(tree_url, headers=headers, timeout=60)
    tree_resp.raise_for_status()
    tree_data = tree_resp.json()
    tree = tree_data.get("result", [])
    logger.info("Got structural tree with %d root nodes", len(tree))
    
    # Fetch OCR nodes (has text)
    ocr_node_url = f"{status_url}?type=ocr&format=node"
    ocr_node_resp = requests.get(ocr_node_url, headers=headers, timeout=60)
    ocr_node_resp.raise_for_status()
    ocr_node_data = ocr_node_resp.json()
    ocr_nodes = ocr_node_data.get("result", [])
    logger.info("Got OCR nodes for content mapping: %d", len(ocr_nodes))
    
    # Fetch raw markdown; if it fails, fallback to page-format concatenation
    full_markdown = ""
    ocr_pages: List[Dict[str, Any]] = []
    try:
        ocr_raw_url = f"{status_url}?type=ocr&format=raw"
        ocr_raw_resp = requests.get(ocr_raw_url, headers=headers, timeout=60)
        ocr_raw_resp.raise_for_status()
        ocr_raw_data = ocr_raw_resp.json()
        full_markdown = (ocr_raw_data.get("result", "") or "").strip()
        logger.info("Got raw markdown with %d characters", len(full_markdown))
    except Exception as e:
        logger.warning("Raw OCR failed, falling back to page format: %s", e)
        ocr_page_url = f"{status_url}?type=ocr&format=page"
        ocr_page_resp = requests.get(ocr_page_url, headers=headers, timeout=60)
        ocr_page_resp.raise_for_status()
        ocr_pages_data = ocr_page_resp.json()
        ocr_pages = ocr_pages_data.get("result", []) or []
        # Concatenate pages into a single markdown string
        page_parts: List[str] = []
        for page in sorted(ocr_pages, key=lambda p: p.get("page_index", 0)):
            idx = page.get("page_index")
            page_md = page.get("markdown") or page.get("text") or ""
            page_parts.append(f"--- Page {idx} ---\n\n{page_md}\n")
        full_markdown = "\n".join(page_parts).strip()
        logger.info("Built markdown from %d pages with %d characters", len(ocr_pages), len(full_markdown))
    
    # Merge the tree and OCR nodes to get a content-rich tree
    enhanced_tree = _merge_tree_and_ocr_nodes(tree, ocr_nodes)
    # Sanitize structure and text
    enhanced_tree = _sanitize_tree(enhanced_tree)

    return {
        "markdown": full_markdown.strip(),
        "tree": enhanced_tree,
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
    metadata = extract_akn_metadata(key, result["tree"], result["markdown"])
    # Use a stable document ID derived solely from the R2 PDF key so re-parses don't duplicate
    canonical_id = sha256_16(key)

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


def check_document_already_parsed(r2_client, bucket: str, doc_id: str, doc_type: str) -> bool:
    """Check if a document has already been parsed and stored in R2."""
    try:
        # Check if parent document exists in R2
        parent_doc_key = f"corpus/docs/{doc_type}/{doc_id}.json"
        r2_client.head_object(Bucket=bucket, Key=parent_doc_key)
        logger.info(f"Document {doc_id} already parsed, skipping")
        return True
    except r2_client.exceptions.NoSuchKey:
        return False
    except Exception as e:
        logger.warning(f"Error checking if document {doc_id} exists: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=8, help="Seconds between PageIndex status checks")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--force", action="store_true", help="Force reprocessing of already parsed documents")
    parser.add_argument("--pdf-keys", type=str, help="Comma-separated list of PDF keys to process")
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

    if args.pdf_keys:
        pdf_keys = [k.strip() for k in args.pdf_keys.split(',')]
        pdfs = [{"key": k} for k in pdf_keys]
        logger.info(f"Processing {len(pdfs)} specific PDFs from --pdf-keys")
    else:
        pdfs = list_pdfs(r2, bucket)
        if args.max_docs:
            pdfs = pdfs[: args.max_docs]

    parsed: List[Dict[str, Any]] = []
    skipped_count = 0
    
    for pdf in pdfs:
        try:
            # For duplicate detection, we need to generate doc_id using the same logic as process_pdf
            # Extract from the PDF key path (simplified approach)
            pdf_key = pdf["key"]
            pdf_name = os.path.basename(pdf_key).replace('.pdf', '')
            
            # Extract doc_type from path
            if "/acts/" in pdf_key:
                doc_type = "act"
            elif "/statutory_instruments/" in pdf_key:
                doc_type = "si"
            elif "/ordinances/" in pdf_key:
                doc_type = "ordinance"
            else:
                doc_type = "unknown"
            
            # Generate doc_id using same hash logic as process_pdf
            import hashlib
            doc_id = hashlib.sha256(pdf_key.encode('utf-8')).hexdigest()[:16]
            
            # Skip if already parsed (unless forced)
            if not args.force and check_document_already_parsed(r2, bucket, doc_id, doc_type):
                skipped_count += 1
                continue
            
            doc = process_pdf(r2, bucket, pdf, api_key, args.poll_interval)
            if doc:
                parsed.append(doc)
                upload_parent_doc(r2, bucket, doc)
        except Exception as e:
            logger.error("Failed to process %s: %s", pdf["key"], e)

    if not parsed:
        if skipped_count > 0:
            logger.info(f"No new documents to parse. Skipped {skipped_count} already parsed documents.")
        else:
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

#!/usr/bin/env python3
"""
chunk_docs.py - Chunk normalized documents into optimal segments for embedding

This script reads parsed documents from Cloudflare R2, chunks them into 
optimally-sized overlapping segments, and uploads individual chunk files
back to R2 for retrieval by the API.

Usage:
    python scripts/chunk_docs.py [--max-docs N] [--verbose]

Environment Variables:
    CLOUDFLARE_R2_S3_ENDPOINT, CLOUDFLARE_R2_ACCESS_KEY_ID, 
    CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import boto3
    from botocore.client import Config
    from pydantic import BaseModel, Field, field_validator
    from tqdm import tqdm
except ImportError as e:
    print(f"❌ Error: Missing dependency. Run: poetry add boto3 pydantic tqdm")
    print(f"   Specific error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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

# ---------------------------------------------------------------------------
# Chunking constants
# ---------------------------------------------------------------------------

# "Big" parent doc granularity – we use sections/pages which can be >512 tokens
PARENT_MAX_TOKENS = 2048  # upper bound for big chunk sanity check

# "Small" chunk target size (for embeddings)
SMALL_TARGET_TOKENS = 256

# Old constant kept for legacy functions that still use it (judgments path)
TARGET_TOKENS = 512  # will be phased out for legislation path
MAX_CHARS = 5000  # Maximum characters per chunk (Milvus varchar limit)
MIN_TOKENS = 100  # Minimum tokens per chunk

# We keep a slight overlap so embeddings capture context
OVERLAP_RATIO = 0.15  # 15 %
CHARS_PER_TOKEN = 4  # Approximate characters per token for English text

# Entity extraction patterns (enhanced from enrich_chunks.py)
PATTERNS = {
    # Date patterns: match various formats and normalize to ISO
    "dates": r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
    
    # Section references: standardize format
    "statute_refs": r"\bs\.?\s*(\d+[A-Z]?)(?:\s*\(\d+\))?(?:\s*\([a-z]\))?|\bsection\s+(\d+[A-Z]?)(?:\s*\(\d+\))?(?:\s*\([a-z]\))?|\b([A-Za-z\s]+)\s+Act\s+\[Chapter\s+(\d+:\d+)\]|\b([A-Za-z\s]+)\s+Act\b",
    
    # Case citations: standardize format
    "case_refs": r"\[(\d{4})\]\s+([A-Z]{2,5})\s+(\d+)|(\d{4})\s*\((\d+)\)\s*([A-Z]{2,5})\s*(\d+)|S\s+v\s+([A-Z][a-z]+)\s+([A-Z]{2,5})\s+(\d+)/(\d+)",
    
    # Court names: standardize format
    "courts": r"\b(?:High Court|Supreme Court|Constitutional Court|Magistrates Court|Labour Court)\b",
    
    # Judge names: extract judge names
    "judges": r"\b([A-Z]{2,})\s+J\b|\b([A-Z]{2,})\s+JA\b|\bJustice\s+([A-Z][A-Za-z]+)\b",
    
    # Party names: extract party names from case names
    "parties": r"\b([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\b"
}

# Court name lookup for entity extraction
COURTS = [
    "High Court of Zimbabwe",
    "Supreme Court of Zimbabwe",
    "Constitutional Court of Zimbabwe",
    "Magistrates Court",
    "Labour Court",
]


class Chunk(BaseModel):
    """Pydantic model for a document chunk (v3.0 - PageIndex tree-aware)."""
    
    chunk_id: str = Field(description="Stable, deterministic ID")
    doc_id: str = Field(description="Parent document ID")
    parent_doc_id: str = Field(description="Parent document ID (same as doc_id)")
    tree_node_id: Optional[str] = Field(description="PageIndex tree node ID", max_length=16)
    chunk_text: str = Field(description="Clean text content (max ~5000 chars)")
    section_path: str = Field(description="Hierarchical path in document")
    start_char: int = Field(description="Start character offset in original document")
    end_char: int = Field(description="End character offset in original document")
    num_tokens: int = Field(description="Estimated token count")
    language: str = Field(description="Document language (e.g., eng)", max_length=10)
    doc_type: str = Field(description="Document type (act, judgment, etc.)", max_length=20)
    date_context: Optional[str] = Field(description="Date context (YYYY-MM-DD)", max_length=32)
    entities: Dict[str, List[str]] = Field(default_factory=dict, description="Extracted entities")
    source_url: Optional[str] = Field(None, description="Source URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    nature: Optional[str] = Field(default=None, description="Act | Ordinance | Statutory Instrument", max_length=32)
    year: Optional[int] = Field(default=None, description="Publication/effective year")
    chapter: Optional[str] = Field(default=None, description="Chapter number like 7:01", max_length=16)
    
    @field_validator("chunk_text")
    def validate_chunk_text(cls, v):
        """Validate chunk text length."""
        if len(v) > MAX_CHARS:
            raise ValueError(f"Chunk text exceeds maximum length of {MAX_CHARS} characters")
        return v
    
    @field_validator("num_tokens")
    def validate_num_tokens(cls, v):
        """Validate token count."""
        if v < 1:
            raise ValueError("Number of tokens must be >= 1")
        return v
    
    @field_validator("doc_type")
    def validate_doc_type(cls, v):
        """Validate and fix doc_type field."""
        if v is None:
            return "unknown"
        if len(v) > 20:
            return v[:20]
        return v
    
    @field_validator("language")
    def validate_language(cls, v):
        """Validate and fix language field."""
        if v is None:
            return "eng"
        if len(v) > 10:
            return v[:10]
        return v
    
    @field_validator("date_context")
    def validate_date_context(cls, v):
        """Validate and fix date_context field."""
        if v is None:
            return None
        if len(v) > 32:
            return v[:32]
        return v


def load_documents_from_r2(r2_client, bucket: str) -> List[Dict[str, Any]]:
    """Load parsed documents from R2."""
    try:
        # Download the parsed documents catalog from R2
        response = r2_client.get_object(Bucket=bucket, Key="corpus/processed/legislation_docs.jsonl")
        content = response['Body'].read().decode('utf-8')
        
        # Parse JSONL content
        documents = []
        for line in content.strip().split('\n'):
            if line.strip():
                documents.append(json.loads(line))
        
        logger.info(f"Loaded {len(documents)} documents from R2")
        return documents
        
    except Exception as e:
        logger.error(f"Error loading documents from R2: {e}")
        raise


def upload_chunk_to_r2(r2_client, bucket: str, chunk: Dict[str, Any]) -> None:
    """Upload a single chunk to R2 as an individual object."""
    try:
        chunk_id = chunk.get("chunk_id")
        doc_type = chunk.get("doc_type", "unknown")
        
        # Create R2 key for this chunk
        r2_key = f"corpus/chunks/{doc_type}/{chunk_id}.json"
        
        # Prepare chunk metadata for R2
        chunk_metadata = {
            "doc_id": str(chunk.get("doc_id", "")),
            "doc_type": str(chunk.get("doc_type", "")),
            "section_path": str(chunk.get("section_path", "")),
            "num_tokens": str(chunk.get("num_tokens", 0)),
            "nature": str(chunk.get("nature", "")),
            "year": str(chunk.get("year", "")),
            "chapter": str(chunk.get("chapter", ""))
        }
        
        # Sanitize metadata values for ASCII compatibility
        sanitized_metadata = {}
        for k, v in chunk_metadata.items():
            if v and isinstance(v, str):
                # Replace non-ASCII characters
                sanitized_v = v.replace("'", "'").replace(""", '"').replace(""", '"')
                sanitized_v = "".join(char for char in sanitized_v if ord(char) < 128)
                sanitized_metadata[k] = sanitized_v
            else:
                sanitized_metadata[k] = str(v) if v else ""
        
        # Upload chunk to R2
        r2_client.put_object(
            Bucket=bucket,
            Key=r2_key,
            Body=json.dumps(chunk, default=str).encode('utf-8'),
            ContentType="application/json",
            Metadata=sanitized_metadata
        )
        
    except Exception as e:
        logger.error(f"Error uploading chunk {chunk.get('chunk_id')} to R2: {e}")


def upload_parent_doc_to_r2(r2_client, bucket: str, parent_doc: Dict[str, Any]) -> str:
    """Upload a *big* parent document JSON object and return its R2 key."""

    parent_id = parent_doc["parent_doc_id"]
    doc_type = parent_doc.get("doc_type", "unknown")

    r2_key = f"corpus/docs/{doc_type}/{parent_id}.json"

    # Minimal metadata for discoverability
    meta = {
        "doc_id": str(parent_doc.get("doc_id", "")),
        "doc_type": doc_type,
        "section_path": parent_doc.get("section_path", ""),
        "num_tokens": str(parent_doc.get("num_tokens", 0)),
    }

    # Sanitize values
    meta = {k: ("".join(c for c in v if ord(c) < 128) if isinstance(v, str) else str(v)) for k, v in meta.items()}

    r2_client.put_object(
        Bucket=bucket,
        Key=r2_key,
        Body=json.dumps(parent_doc, default=str).encode("utf-8"),
        ContentType="application/json",
        Metadata=meta,
    )

    return r2_key


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text using character count."""
    # Simple approximation: ~4 chars per token for English text
    return len(text) // CHARS_PER_TOKEN


def normalize_text(text: str) -> str:
    """Normalize text for consistent processing."""
    # Replace multiple whitespace with a single space
    text = re.sub(r'\s+', ' ', text)
    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    # Normalize dashes
    text = text.replace('—', '-').replace('–', '-')
    # Strip leading/trailing whitespace
    return text.strip()


def find_sentence_boundary(text: str, position: int) -> int:
    """Find the nearest sentence boundary to the given position."""
    # Look for sentence-ending punctuation followed by space or newline
    sentence_end_pattern = r'[.!?]\s+'
    
    # Search forward for the next sentence boundary
    forward_match = re.search(sentence_end_pattern, text[position:])
    forward_pos = position + forward_match.end() if forward_match else len(text)
    
    # Search backward for the previous sentence boundary
    text_before = text[:position]
    backward_matches = list(re.finditer(sentence_end_pattern, text_before))
    backward_pos = backward_matches[-1].end() if backward_matches and backward_matches else 0
    
    # If no sentence boundaries found, just find word boundaries
    if forward_pos == len(text) and backward_pos == 0:
        # Try to find a space near the position
        if position < len(text) and text[position] == ' ':
            return position
        
        # Look for the nearest space
        space_before = text[:position].rfind(' ')
        space_after = text[position:].find(' ')
        
        if space_before == -1:
            space_before = 0
        if space_after == -1:
            space_after = len(text) - position
            
        # Return the closest space
        if position - space_before <= space_after:
            return space_before
        else:
            return position + space_after
    
    # Return the closest sentence boundary
    if position - backward_pos <= forward_pos - position:
        return backward_pos
    else:
        return forward_pos


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract entities from text using regex patterns and normalize them."""
    entities = {}
    
    # Extract dates and normalize them
    dates = re.findall(PATTERNS["dates"], text)
    normalized_dates = []
    for date in dates:
        # Try to normalize to ISO format (YYYY-MM-DD)
        try:
            # Handle common formats
            if re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', date):
                # DD/MM/YYYY or MM/DD/YYYY
                parts = re.split(r'[-/]', date)
                if len(parts[2]) == 2:  # Convert 2-digit year to 4-digit
                    parts[2] = '20' + parts[2] if int(parts[2]) < 50 else '19' + parts[2]
                # Assume DD/MM/YYYY format
                normalized_date = f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}"
                normalized_dates.append(normalized_date)
            else:
                # Just add as-is if we can't normalize
                normalized_dates.append(date)
        except Exception:
            # If normalization fails, keep original
            normalized_dates.append(date)
    
    if normalized_dates:
        entities["dates"] = list(set(normalized_dates))
    
    # Extract statute references
    statute_refs = re.findall(PATTERNS["statute_refs"], text)
    if statute_refs:
        # Flatten tuples and filter out empty strings
        flattened_refs = []
        for ref in statute_refs:
            if isinstance(ref, tuple):
                # Join non-empty parts of the tuple
                ref_text = " ".join([part for part in ref if part.strip()])
                if ref_text.strip():
                    flattened_refs.append(ref_text.strip())
            elif isinstance(ref, str) and ref.strip():
                flattened_refs.append(ref.strip())
        entities["statute_refs"] = list(set(flattened_refs))
    
    # Extract case citations
    case_refs = re.findall(PATTERNS["case_refs"], text)
    if case_refs:
        # Flatten tuples and filter out empty strings
        flattened_refs = []
        for ref in case_refs:
            if isinstance(ref, tuple):
                # Join non-empty parts of the tuple
                ref_text = " ".join([part for part in ref if part.strip()])
                if ref_text.strip():
                    flattened_refs.append(ref_text.strip())
            elif isinstance(ref, str) and ref.strip():
                flattened_refs.append(ref.strip())
        entities["case_refs"] = list(set(flattened_refs))
    
    # Extract courts
    courts = []
    for court in COURTS:
        if court in text:
            courts.append(court)
    if courts:
        entities["courts"] = courts
    
    # Extract judges (SURNAME J, SURNAME JA, Justice SURNAME)
    judge_pattern = r'\b([A-Z]{2,})\s+J\b|\b([A-Z]{2,})\s+JA\b|\bJustice\s+([A-Z][A-Za-z]+)\b'
    judges = re.findall(judge_pattern, text)
    if judges:
        # Flatten and filter non-empty groups
        judge_names = []
        for match in judges:
            for group in match:
                if group:
                    if 'J' not in group and 'JA' not in group:
                        judge_names.append(f"Justice {group}")
                    else:
                        judge_names.append(group)
        if judge_names:
            entities["judges"] = list(set(judge_names))
    
    # Extract party names (X v Y)
    party_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\b'
    parties = re.findall(party_pattern, text)
    if parties:
        party_strings = []
        for applicant, respondent in parties:
            if applicant.strip() and respondent.strip():
                party_strings.append(f"{applicant.strip()} v {respondent.strip()}")
        if party_strings:
            entities["parties"] = party_strings
    
    return entities


def generate_chunk_id(doc_id: str, section_path: str, start_char: int, end_char: int, chunk_text: str) -> str:
    """Generate a stable, deterministic chunk ID."""
    # Normalize whitespace before hashing to ensure stability
    normalized_text = re.sub(r'\s+', ' ', chunk_text).strip()
    text_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:8]
    
    components = f"{doc_id}|{section_path}|{start_char}|{end_char}|{text_hash}"
    return hashlib.sha256(components.encode("utf-8")).hexdigest()[:16]


def chunk_text(
    text: str,
    section_path: str,
    doc_id: str,
    start_offset: int = 0,
    target_tokens: int = SMALL_TARGET_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Chunk text into overlapping segments using sliding window.
    
    Args:
        text: The text to chunk
        section_path: Hierarchical path in the document
        doc_id: Parent document ID
        start_offset: Character offset in the original document
        
    Returns:
        List of chunk dictionaries
    """
    if not text.strip():
        return []
    
    chunks = []
    text = normalize_text(text)
    text_length = len(text)
    
    # If text is shorter than target, return as single chunk
    if estimate_tokens(text) <= target_tokens:
        start_char = start_offset
        end_char = start_offset + text_length
        num_tokens = estimate_tokens(text)
        
        chunk = {
            "chunk_text": text,
            "section_path": section_path,
            "start_char": start_char,
            "end_char": end_char,
            "num_tokens": num_tokens,
        }
        return [chunk]
    
    # Calculate sliding window parameters
    overlap_tokens = int(target_tokens * OVERLAP_RATIO)
    stride_tokens = target_tokens - overlap_tokens
    stride_chars = stride_tokens * CHARS_PER_TOKEN
    
    # Initialize window
    pos = 0
    chunk_index = 0
    
    while pos < text_length:
        # Calculate end position for current chunk
        target_chars = target_tokens * CHARS_PER_TOKEN
        end_pos = min(pos + target_chars, text_length)
        
        # Adjust to sentence boundary if not at end of text
        if end_pos < text_length:
            end_pos = find_sentence_boundary(text, end_pos)
        
        # Extract chunk text
        chunk_text = text[pos:end_pos]
        num_tokens = estimate_tokens(chunk_text)
        
        # Skip if chunk is too small (except at end of text)
        if num_tokens < MIN_TOKENS and end_pos < text_length:
            pos += stride_chars
            continue
        
        # Create chunk
        start_char = start_offset + pos
        end_char = start_offset + end_pos
        
        chunk = {
            "chunk_text": chunk_text,
            "section_path": section_path,
            "start_char": start_char,
            "end_char": end_char,
            "num_tokens": num_tokens,
        }
        
        chunks.append(chunk)
        chunk_index += 1
        
        # Move window
        pos += stride_chars
        
        # Break if we've reached the end
        if pos >= text_length:
            break
    
    return chunks


def chunk_from_pageindex_tree(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk a document using PageIndex tree structure for semantic boundaries.
    
    Args:
        doc: Document with PageIndex content_tree
        
    Returns:
        List of chunk dictionaries
    """
    doc_id = doc["doc_id"]
    doc_type = doc.get("doc_type", "act")
    language = doc.get("language", "eng")
    nature = doc.get("nature", "Act")
    year = doc.get("act_year")
    chapter = doc.get("chapter")
    version_date = doc.get("version_date")
    source_url = doc.get("source_url", "")
    
    # Get PageIndex tree
    content_tree = doc.get("content_tree", [])
    if not content_tree:
        logger.warning(f"Document {doc_id} has no PageIndex tree structure")
        return []
    
    all_chunks = []
    
    def process_tree_node(node: Dict[str, Any], parent_path: str = "") -> None:
        """Recursively process tree nodes into chunks."""
        node_title = node.get("title", "")
        node_id = node.get("node_id", "")
        node_text = node.get("text", "")
        
        # Build section path
        section_path = f"{parent_path} > {node_title}" if parent_path else node_title
        
        # Create chunk if node has text content
        if node_text and len(node_text.strip()) > 0:
            # Estimate tokens
            token_count = estimate_tokens(node_text)
            
            # Only create chunks that meet minimum requirements
            if token_count >= MIN_TOKENS:
                # Generate chunk ID
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    section_path=section_path,
                    start_char=0,  # PageIndex doesn't provide char offsets
                    end_char=len(node_text),
                    chunk_text=node_text
                )
                
                # Extract entities
                entities = extract_entities(node_text)
                
                # Create chunk
                chunk = Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    parent_doc_id=doc_id,  # Always same as doc_id
                    tree_node_id=node_id,
                    chunk_text=node_text.strip(),
                    section_path=section_path,
                    start_char=0,
                    end_char=len(node_text),
                    num_tokens=token_count,
                    language=language,
                    doc_type=doc_type,
                    date_context=version_date,
                    entities=entities,
                    source_url=source_url,
                    nature=nature,
                    year=int(year) if year and str(year).isdigit() else None,
                    chapter=chapter,
                    metadata={
                        "title": doc.get("title", ""),
                        "jurisdiction": doc.get("jurisdiction", "ZW"),
                        "akn_uri": doc.get("akn_uri", ""),
                        "canonical_citation": doc.get("canonical_citation", ""),
                        "pageindex_doc_id": doc.get("pageindex_doc_id", ""),
                        "tree_node_id": node_id,
                        "page_index": node.get("page_index")
                    }
                )
                
                all_chunks.append(chunk.model_dump())
                logger.debug(f"Created chunk {chunk_id} from node {node_id}: {token_count} tokens")
        
        # Process child nodes recursively
        child_nodes = node.get("nodes", [])
        for child_node in child_nodes:
            process_tree_node(child_node, section_path)
    
    # Process all root nodes
    for root_node in content_tree:
        process_tree_node(root_node)
    
    logger.info(f"Generated {len(all_chunks)} chunks from PageIndex tree for doc {doc_id}")
    return all_chunks, []  # Return empty parent_docs list since we don't create them anymore

def chunk_legislation(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Legacy chunking function - replaced by chunk_from_pageindex_tree.
    
    Args:
        doc: The document to chunk
        
    Returns:
        List of chunk dictionaries
    """
    # Check if document has PageIndex tree
    if doc.get("content_tree") and doc.get("pageindex_doc_id"):
        logger.info(f"Using PageIndex tree-aware chunking for doc {doc['doc_id']}")
        return chunk_from_pageindex_tree(doc)
    else:
        logger.warning(f"Document {doc['doc_id']} missing PageIndex tree, using legacy chunking")
        # Fall back to legacy logic (existing code below)
        all_chunks = []
    doc_id = doc["doc_id"]
    language = doc["language"]
    date_context = doc.get("version_effective_date")
    source_url = doc.get("source_url")
    title = doc.get("title", "")
    extra = doc.get("extra", {})
    nature = extra.get("nature")
    year = extra.get("year")
    chapter = extra.get("chapter")

    # Normalize doc_type for legislation based on nature and existing value
    doc_type_raw = (doc.get("doc_type") or "").lower()
    nature_lower = (nature or "").lower()
    if doc_type_raw in {"act", "si", "ordinance"}:
        doc_type = doc_type_raw
    elif doc_type_raw == "legislation":
        doc_type = "act"
    else:
        # Fallback to nature
        if nature_lower == "statutory instrument":
            doc_type = "si"
        elif "ordinance" in nature_lower:
            doc_type = "ordinance"
        else:
            doc_type = "act"
    
    # Process content tree
    content_tree = doc.get("content_tree", {})
    parts = content_tree.get("parts", [])
    
    # If content_tree is empty or has no parts, return empty list
    if not parts:
        logger.warning(f"Document {doc_id} has no content to chunk")
        return []
    
    parent_docs: List[Dict[str, Any]] = []

    # Process each part
    for part_idx, part in enumerate(parts):
        part_title = part.get("title", f"Part {part_idx + 1}")
        sections = part.get("sections", [])
        
        # Process each section
        for section_idx, section in enumerate(sections):
            section_title = section.get("title", f"Section {section_idx + 1}")
            
            # Get section content from paragraphs
            section_paragraphs = section.get("paragraphs", [])
            if not section_paragraphs:
                # Fallback to legacy "content" field
                section_content = section.get("content", "")
            else:
                # Join all paragraphs in the section
                section_content = " ".join(section_paragraphs)
            
            # Skip empty sections
            if not section_content.strip():
                continue
            
            # Create section path (parent doc path)
            section_path = f"{part_title} > {section_title}"

            # ------------------------------------------------------------------
            # Build BIG parent document record for this section
            # ------------------------------------------------------------------

            parent_doc_id = generate_chunk_id(doc_id, section_path, 0, len(section_content), section_content)

            parent_doc = {
                "parent_doc_id": parent_doc_id,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "section_path": section_path,
                "text": section_content,
                "num_tokens": estimate_tokens(section_content),
                "language": language,
                "nature": nature,
                "year": year,
                "chapter": chapter,
            }

            parent_docs.append(parent_doc)

            parent_object_key = f"corpus/docs/{doc_type}/{parent_doc_id}.json"

            # ------------------------------------------------------------------
            # SMALL chunk generation
            # ------------------------------------------------------------------

            # For legislation, if section is too short, merge with adjacent sections
            if estimate_tokens(section_content) < MIN_TOKENS:
                # Try to merge with next sections in the same part
                merged_content = section_content
                merged_sections = [section_title]
                
                for next_idx in range(section_idx + 1, len(sections)):
                    next_section = sections[next_idx]
                    next_paragraphs = next_section.get("paragraphs", [])
                    if next_paragraphs:
                        next_content = " ".join(next_paragraphs)
                        if estimate_tokens(merged_content + " " + next_content) <= SMALL_TARGET_TOKENS * 2:
                            merged_content += " " + next_content
                            merged_sections.append(next_section.get("title", f"Section {next_idx + 1}"))
                        else:
                            break
                
                # If still too short, keep as a single minimal chunk for legal completeness
                if estimate_tokens(merged_content) < MIN_TOKENS:
                    entities = extract_entities(merged_content)
                    chunk_id = generate_chunk_id(
                        doc_id=doc_id,
                        section_path=section_path,
                        start_char=0,
                        end_char=len(merged_content),
                        chunk_text=merged_content,
                    )
                    try:
                        full_chunk = Chunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            chunk_text=merged_content,
                            section_path=section_path,
                            start_char=0,
                            end_char=len(merged_content),
                            num_tokens=max(1, estimate_tokens(merged_content)),
                            language=language,
                            doc_type=doc_type,
                            date_context=date_context,
                            entities=entities,
                            source_url=source_url,
                            nature=nature,
                            year=year,
                            chapter=chapter,
                            metadata={
                                "title": title,
                                "sections": merged_sections,
                                "chunk_index": 0,
                                "nature": nature,
                                "year": year,
                                "chapter": chapter,
                            },
                        )
                        all_chunks.append(full_chunk.model_dump(exclude_none=True))
                    except Exception as e:
                        logger.warning(f"Skipping minimal chunk for document {doc_id}: {e}")
                    continue
                
                # Create a single chunk for the merged sections
                section_path = f"{part_title} > {' + '.join(merged_sections)}"
                
                # Extract entities
                entities = extract_entities(merged_content)
                
                # Generate chunk ID
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    section_path=section_path,
                    start_char=0,
                    end_char=len(merged_content),
                    chunk_text=merged_content,
                )
                
                try:
                    # Create full chunk object
                    full_chunk = Chunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        chunk_text=merged_content,
                        section_path=section_path,
                        start_char=0,
                        end_char=len(merged_content),
                        num_tokens=estimate_tokens(merged_content),
                        language=language,
                        doc_type=doc_type,
                        date_context=date_context,
                        entities=entities,
                        source_url=source_url,
                        nature=nature,
                        year=year,
                        chapter=chapter,
                        metadata={
                            "title": title,
                            "sections": merged_sections,
                            "chunk_index": 0,
                            "nature": nature,
                            "year": year,
                            "chapter": chapter,
                        },
                    )
                    
                    all_chunks.append(full_chunk.model_dump(exclude_none=True))
                except Exception as e:
                    logger.warning(f"Skipping invalid merged chunk for document {doc_id}: {e}")
            else:
                # Section is long enough, chunk normally
                # Generate *small* chunks with new target size
                section_chunks = chunk_text(
                    text=section_content,
                    section_path=section_path,
                    doc_id=doc_id,
                    target_tokens=SMALL_TARGET_TOKENS,
                )
                
                # Add metadata to chunks
                for i, chunk in enumerate(section_chunks):
                    # Add header to first chunk if multiple chunks
                    if i == 0 and len(section_chunks) > 1 and section_title:
                        chunk["chunk_text"] = f"{section_title}: {chunk['chunk_text']}"
                    
                    # Extract entities
                    entities = extract_entities(chunk["chunk_text"])
                    
                    # Generate chunk ID
                    chunk_id = generate_chunk_id(
                        doc_id=doc_id,
                        section_path=chunk["section_path"],
                        start_char=chunk["start_char"],
                        end_char=chunk["end_char"],
                        chunk_text=chunk["chunk_text"],
                    )
                    
                    try:
                        # Create full chunk object
                        full_chunk = Chunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            chunk_text=chunk["chunk_text"],
                            section_path=chunk["section_path"],
                            start_char=chunk["start_char"],
                            end_char=chunk["end_char"],
                            num_tokens=chunk["num_tokens"],
                            language=language,
                            doc_type=doc_type,
                            date_context=date_context,
                            entities=entities,
                            source_url=source_url,
                            nature=nature,
                            year=year,
                            chapter=chapter,
                            metadata={
                                "title": title,
                                "section": section_title,
                                "chunk_index": i,
                                "nature": nature,
                                "year": year,
                                "chapter": chapter,
                            },
                        )
                        
                        all_chunks.append(full_chunk.model_dump(exclude_none=True))
                    except Exception as e:
                        logger.warning(f"Skipping invalid chunk for document {doc_id}: {e}")
    
    return all_chunks, parent_docs


def chunk_judgment(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk a judgment document into optimal segments.
    
    Args:
        doc: The document to chunk
        
    Returns:
        List of chunk dictionaries
    """
    all_chunks = []
    doc_id = doc["doc_id"]
    doc_type = doc["doc_type"]
    language = doc["language"]
    date_context = doc.get("version_effective_date")
    source_url = doc.get("source_url")
    title = doc.get("title", "")
    
    # Extract metadata from extra field
    extra = doc.get("extra", {})
    court = extra.get("court", "")
    canonical_citation = doc.get("canonical_citation")
    
    # Process content tree
    content_tree = doc.get("content_tree", {})
    headnote = content_tree.get("headnote", [])
    body = content_tree.get("body", [])
    
    # Process headnote
    if headnote:
        headnote_text = " ".join(headnote)
        
        # Skip "Download PDF" and other boilerplate headnotes
        if len(headnote_text) < 50 or headnote_text.strip() in ["Download PDF"]:
            logger.warning(f"Skipping short or boilerplate headnote for document {doc_id}")
        else:
            headnote_chunks = chunk_text(
                text=headnote_text,
                section_path="Headnote",
                doc_id=doc_id,
            )
            
            # Add metadata to chunks
            for i, chunk in enumerate(headnote_chunks):
                # Allow short chunks for completeness
                    
                # Extract entities
                entities = extract_entities(chunk["chunk_text"])
                
                # Generate chunk ID
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    section_path=chunk["section_path"],
                    start_char=chunk["start_char"],
                    end_char=chunk["end_char"],
                    chunk_text=chunk["chunk_text"],
                )
                
                try:
                    # Create full chunk object
                    full_chunk = Chunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        chunk_text=chunk["chunk_text"],
                        section_path=chunk["section_path"],
                        start_char=chunk["start_char"],
                        end_char=chunk["end_char"],
                        num_tokens=chunk["num_tokens"],
                        language=language,
                        doc_type=doc_type,
                        date_context=date_context,
                        entities=entities,
                        source_url=source_url,
                        metadata={
                            "title": title,
                            "court": court,
                            "canonical_citation": canonical_citation,
                            "chunk_index": i,
                        },
                    )
                    
                    all_chunks.append(full_chunk.model_dump(exclude_none=True))
                except Exception as e:
                    logger.warning(f"Skipping invalid headnote chunk for document {doc_id}: {e}")
    
    # Process body
    if body:
        # Filter out boilerplate content
        filtered_body = []
        boilerplate_patterns = [
            "Download PDF", "Download DOCX", "Share", "Report a problem", 
            "Document detail", "Related documents", "Sign up or Log in",
            "https://", "www.", ".html", ".pdf", "accessed on", "cite_note",
            "contents of #navigation", "data-offcanvas", "navigation-column"
        ]
        
        # Track paragraph numbers for better section paths
        para_number = 0
        
        for para in body:
            is_boilerplate = False
            
            # Check for boilerplate patterns
            for pattern in boilerplate_patterns:
                if pattern in para:
                    is_boilerplate = True
                    break
            
            # Skip navigation content
            if "navigation-content" in para or "navigation-column" in para or "#" in para:
                is_boilerplate = True
                
            # Skip very short paragraphs (likely navigation elements)
            if len(para.strip()) < 10:
                is_boilerplate = True
                
            if not is_boilerplate:
                para_number += 1
                # Add paragraph number as metadata
                filtered_body.append((para_number, para))
        
        # Skip if body is too short after filtering
        if not filtered_body:
            logger.warning(f"Body text too short after filtering for document {doc_id}")
            return all_chunks
        
        # Improved chunking with paragraph awareness
        chunk_size = TARGET_TOKENS * CHARS_PER_TOKEN
        overlap_size = int(chunk_size * OVERLAP_RATIO)
        
        current_chunk_text = ""
        current_chunk_paras = []
        chunk_index = 0
        
        # Process paragraphs to create chunks
        for i, (para_num, para) in enumerate(filtered_body):
            # Normalize paragraph text
            para_text = normalize_text(para)
            
            # If adding this paragraph would exceed target size and we already have content
            if current_chunk_text and len(current_chunk_text + " " + para_text) > chunk_size:
                # Create a chunk from accumulated paragraphs
                start_para = current_chunk_paras[0]
                end_para = current_chunk_paras[-1]
                section_path = f"Body > Paras {start_para}-{end_para}"
                
                # Extract entities
                entities = extract_entities(current_chunk_text)
                
                # Generate chunk ID
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    section_path=section_path,
                    start_char=0,  # We don't track exact character positions in this version
                    end_char=len(current_chunk_text),
                    chunk_text=current_chunk_text,
                )
                
                try:
                    # Create full chunk object
                    full_chunk = Chunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        chunk_text=current_chunk_text,
                        section_path=section_path,
                        start_char=0,  # Simplified
                        end_char=len(current_chunk_text),
                        num_tokens=estimate_tokens(current_chunk_text),
                        language=language,
                        doc_type=doc_type,
                        date_context=date_context,
                        entities=entities,
                        source_url=source_url,
                        metadata={
                            "title": title,
                            "court": court,
                            "canonical_citation": canonical_citation,
                            "chunk_index": chunk_index,
                            "paragraph_range": f"{start_para}-{end_para}"
                        },
                    )
                    
                    all_chunks.append(full_chunk.model_dump(exclude_none=True))
                    chunk_index += 1
                except Exception as e:
                    logger.warning(f"Skipping invalid body chunk for document {doc_id}: {e}")
                
                # Calculate how many paragraphs to keep for overlap
                # We want to keep approximately OVERLAP_RATIO of the text
                overlap_paras = []
                overlap_text = ""
                
                # Start from the end and work backwards
                # Always include at least one paragraph for overlap
                min_overlap_paras = 1
                
                for para_idx in reversed(current_chunk_paras):
                    para_content = next((p for n, p in filtered_body if n == para_idx), "")
                    para_content = normalize_text(para_content)
                    
                    if len(overlap_text + " " + para_content) <= overlap_size or len(overlap_paras) < min_overlap_paras:
                        overlap_paras.insert(0, para_idx)
                        overlap_text = para_content + " " + overlap_text if overlap_text else para_content
                    else:
                        break
                
                # Reset for next chunk, keeping overlap paragraphs
                current_chunk_paras = overlap_paras
                current_chunk_text = overlap_text
            
            # Add current paragraph to the chunk
            if current_chunk_text:
                current_chunk_text += " " + para_text
            else:
                current_chunk_text = para_text
            
            current_chunk_paras.append(para_num)
        
        # Don't forget the last chunk if there's content left
        if current_chunk_text and estimate_tokens(current_chunk_text) >= MIN_TOKENS:
            start_para = current_chunk_paras[0]
            end_para = current_chunk_paras[-1]
            section_path = f"Body > Paras {start_para}-{end_para}"
            
            # Extract entities
            entities = extract_entities(current_chunk_text)
            
            # Generate chunk ID
            chunk_id = generate_chunk_id(
                doc_id=doc_id,
                section_path=section_path,
                start_char=0,
                end_char=len(current_chunk_text),
                chunk_text=current_chunk_text,
            )
            
            try:
                # Create full chunk object
                full_chunk = Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    chunk_text=current_chunk_text,
                    section_path=section_path,
                    start_char=0,
                    end_char=len(current_chunk_text),
                    num_tokens=estimate_tokens(current_chunk_text),
                    language=language,
                    doc_type=doc_type,
                    date_context=date_context,
                    entities=entities,
                    source_url=source_url,
                    metadata={
                        "title": title,
                        "court": court,
                        "canonical_citation": canonical_citation,
                        "chunk_index": chunk_index,
                        "paragraph_range": f"{start_para}-{end_para}"
                    },
                )
                
                all_chunks.append(full_chunk.model_dump(exclude_none=True))
            except Exception as e:
                logger.warning(f"Skipping invalid body chunk for document {doc_id}: {e}")
    
    return all_chunks


def enrich_chunks(chunks: List[Dict[str, Any]], verbose: bool = False) -> List[Dict[str, Any]]:
    """
    Enrich chunks with additional entity extraction and normalization.
    
    Args:
        chunks: List of chunks to enrich
        verbose: Whether to print verbose output
        
    Returns:
        List of enriched chunks
    """
    enriched_chunks = []
    
    for chunk in tqdm(chunks, desc="Enriching chunks"):
        try:
            # Extract text for processing
            chunk_text = chunk.get("chunk_text", "")
            
            # Extract and normalize entities with improved extraction
            entities = extract_entities(chunk_text)
            
            # Merge with existing entities if present
            if "entities" in chunk and isinstance(chunk["entities"], dict):
                for entity_type, values in entities.items():
                    if entity_type in chunk["entities"]:
                        # Combine and deduplicate
                        if entity_type == "parties":
                            # Special handling for parties
                            chunk["entities"][entity_type] = values
                        else:
                            existing = set(chunk["entities"][entity_type])
                            existing.update(values)
                            chunk["entities"][entity_type] = list(existing)
                    else:
                        chunk["entities"][entity_type] = values
            else:
                chunk["entities"] = entities
            
            # Extract date context if available
            if "dates" in entities and entities["dates"] and not chunk.get("date_context"):
                # Use the first date as date_context if not already set
                chunk["date_context"] = entities["dates"][0]
            
            # Add court to metadata if available
            if "courts" in entities and entities["courts"]:
                if "metadata" not in chunk:
                    chunk["metadata"] = {}
                if "court" not in chunk["metadata"] or not chunk["metadata"]["court"]:
                    chunk["metadata"]["court"] = entities["courts"][0]
            
            enriched_chunks.append(chunk)
            
            if verbose:
                logger.info(f"Enriched chunk {chunk.get('chunk_id')}")
                
        except Exception as e:
            logger.error(f"Error enriching chunk {chunk.get('chunk_id')}: {e}")
            if verbose:
                import traceback
                logger.error(traceback.format_exc())
            # Keep the original chunk
            enriched_chunks.append(chunk)
    
    # Log statistics
    entity_counts = {}
    for chunk in enriched_chunks:
        if "entities" in chunk:
            for entity_type, values in chunk["entities"].items():
                if entity_type not in entity_counts:
                    entity_counts[entity_type] = 0
                entity_counts[entity_type] += len(values) if isinstance(values, list) else 1
    
    logger.info("Entity extraction statistics:")
    for entity_type, count in entity_counts.items():
        logger.info(f"  {entity_type}: {count}")
    
    return enriched_chunks


def process_documents_from_r2(
    r2_client,
    bucket: str,
    max_docs: Optional[int] = None,
    verbose: bool = False,
    enrich: bool = True,
    doc_ids: Optional[Set[str]] = None,
) -> None:
    """
    Process documents from R2, chunk them, and upload chunks back to R2.
    
    Args:
        r2_client: boto3 client for R2
        bucket: R2 bucket name
        max_docs: Maximum number of documents to process (for testing)
        verbose: Whether to print verbose output
        enrich: Whether to apply advanced entity enrichment
    """
    # Load documents from R2
    documents = load_documents_from_r2(r2_client, bucket)

    # If specific doc_ids provided, filter
    if doc_ids:
        before = len(documents)
        documents = [doc for doc in documents if doc.get("doc_id") in doc_ids]
        logger.info(f"Filtered documents list from {before} to {len(documents)} based on --doc-ids filter")
    
    if max_docs:
        documents = documents[:max_docs]
        logger.info(f"Limited processing to {max_docs} documents for testing")
    
    all_chunks = []
    all_parent_docs = []
    
    # Process each document
    for doc in tqdm(documents, desc="Chunking documents"):
        try:
            # Determine document type and apply appropriate chunking strategy
            doc_type_value = (doc.get("doc_type") or "").lower()
            nature_value = (doc.get("extra", {}).get("nature") or "").lower()
            is_legislation = (
                doc_type_value in {"act", "si", "ordinance", "constitution", "legislation"}
                or nature_value in {"act", "statutory instrument", "ordinance"}
            )

            if is_legislation:
                chunks, parent_docs = chunk_legislation(doc)
                all_chunks.extend(chunks)
                all_parent_docs.extend(parent_docs)
            else:
                chunks = chunk_judgment(doc)
                all_chunks.extend(chunks)
            
            if verbose:
                logger.info(f"Generated {len(chunks)} chunks for document {doc.get('doc_id')}")
        
        except Exception as e:
            logger.error(f"Error processing document {doc.get('doc_id')}: {e}")
            if verbose:
                import traceback
                logger.error(traceback.format_exc())
    
    # Apply advanced entity enrichment if requested
    if enrich and all_chunks:
        logger.info("Applying advanced entity enrichment...")
        all_chunks = enrich_chunks(all_chunks, verbose)
    
    # ------------------------------------------------------------------
    # Upload parent docs first (big chunks)
    # ------------------------------------------------------------------
    logger.info(f"Uploading {len(all_parent_docs)} parent docs to R2 ...")
    for pd in tqdm(all_parent_docs, desc="Uploading parents"):
        try:
            upload_parent_doc_to_r2(r2_client, bucket, pd)
        except Exception as e:
            logger.error(f"Failed to upload parent doc {pd.get('parent_doc_id')}: {e}")

    # Also upload docs.jsonl manifest
    if all_parent_docs:
        manifest_content = "\n".join([json.dumps(p, default=str) for p in all_parent_docs])
        r2_client.put_object(
            Bucket=bucket,
            Key="corpus/docs/docs.jsonl",
            Body=manifest_content.encode("utf-8"),
            ContentType="application/json",
        )

    # ------------------------------------------------------------------
    # Upload individual *small* chunks
    # ------------------------------------------------------------------
    logger.info(f"Uploading {len(all_chunks)} chunks to R2...")
    successful_uploads = 0
    failed_uploads = 0
    
    for chunk in tqdm(all_chunks, desc="Uploading chunks"):
        try:
            upload_chunk_to_r2(r2_client, bucket, chunk)
            successful_uploads += 1
        except Exception as e:
            logger.error(f"Failed to upload chunk {chunk.get('chunk_id')}: {e}")
            failed_uploads += 1
    
    # Log statistics
    avg_tokens = sum(chunk["num_tokens"] for chunk in all_chunks) / len(all_chunks) if all_chunks else 0
    avg_chars = sum(len(chunk["chunk_text"]) for chunk in all_chunks) / len(all_chunks) if all_chunks else 0
    
    logger.info(f"Generated {len(all_chunks)} chunks from {len(documents)} documents")
    logger.info(f"Successfully uploaded: {successful_uploads}, Failed: {failed_uploads}")
    logger.info(f"Average chunk size: {avg_tokens:.1f} tokens, {avg_chars:.1f} characters")


def fix_chunks_for_milvus(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fix chunks data to be compatible with Milvus schema constraints.
    
    Args:
        chunks: List of chunks to fix
        
    Returns:
        List of fixed chunks
    """
    fixed_chunks = []
    
    for chunk in chunks:
        fixed_chunk = chunk.copy()
        
        # Fix doc_type (max length 20)
        doc_type = fixed_chunk.get("doc_type", "unknown")
        if isinstance(doc_type, str) and len(doc_type) > 20:
            fixed_chunk["doc_type"] = doc_type[:20]
        elif doc_type is None:
            fixed_chunk["doc_type"] = "unknown"
        
        # Fix language (max length 10)
        language = fixed_chunk.get("language", "eng")
        if isinstance(language, str) and len(language) > 10:
            fixed_chunk["language"] = language[:10]
        elif language is None:
            fixed_chunk["language"] = "eng"
        
        # Fix court (max length 100)
        court = fixed_chunk.get("court", "unknown")
        if isinstance(court, str) and len(court) > 100:
            fixed_chunk["court"] = court[:100]
        elif court is None:
            fixed_chunk["court"] = "unknown"
        
        # Fix date_context (max length 32)
        date_context = fixed_chunk.get("date_context", "unknown")
        if isinstance(date_context, str) and len(date_context) > 32:
            fixed_chunk["date_context"] = date_context[:32]
        
        # Ensure metadata is a dict
        metadata = fixed_chunk.get("metadata", {})
        if not isinstance(metadata, dict):
            fixed_chunk["metadata"] = {}
        
        fixed_chunks.append(fixed_chunk)
    
    return fixed_chunks


def main():
    parser = argparse.ArgumentParser(description="Chunk documents from R2 and upload chunks back to R2")
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Maximum number of documents to process (for testing)"
    )
    parser.add_argument(
        "--doc-ids",
        type=str,
        default=None,
        help="Comma-separated list of doc_id values to process only those documents"
    )
    parser.add_argument("--no-enrich", action="store_true", 
                        help="Skip advanced entity enrichment")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Get R2 client and bucket
        r2_client = get_r2_client()
        bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
        
        # Process documents from R2 into chunks and upload back to R2
        process_documents_from_r2(
            r2_client, 
            bucket, 
            max_docs=args.max_docs,
            verbose=args.verbose,
            enrich=not args.no_enrich,
            doc_ids=set(args.doc_ids.split(",")) if args.doc_ids else None
        )
            
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

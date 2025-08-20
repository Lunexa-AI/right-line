#!/usr/bin/env python3
"""
test_chunking.py - Test the chunking script on a single document

This script loads a single document from docs.jsonl and processes it through
the chunking algorithm to verify it works correctly.
"""

import json
import logging
import sys
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional

import structlog

# Constants for chunking
TARGET_TOKENS = 512  # Target number of tokens per chunk
MAX_CHARS = 5000  # Maximum characters per chunk (Milvus varchar limit)
MIN_TOKENS = 100  # Minimum tokens per chunk
OVERLAP_RATIO = 0.15  # Overlap between chunks (15%)
CHARS_PER_TOKEN = 4  # Approximate characters per token for English text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

# Entity extraction patterns
PATTERNS = {
    "dates": r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    "statute_refs": r"\bs(?:ection)?\s*\d+[A-Z]?(?:\s*\(\d+\))?(?:\s*\([a-z]\))?|\b[A-Za-z]+\s+Act\s+\[Chapter\s+\d+:\d+\]|\b[A-Za-z]+\s+Act\b",
    "case_refs": r"\[\d{4}\]\s+[A-Z]{2,5}\s+\d+|\d{4}\s*\(\d+\)\s*[A-Z]{2,5}\s*\d+|S\s+v\s+[A-Z][a-z]+\s+[A-Z]{2,5}\s+\d+/\d+",
    "courts": r"\b(?:High Court|Supreme Court|Constitutional Court|Magistrates Court|Labour Court)\b"
}

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

def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extract entities from text using regex patterns."""
    entities = {}
    
    # Extract dates
    dates = re.findall(PATTERNS["dates"], text)
    if dates:
        entities["dates"] = list(set(dates))
    
    # Extract statute references
    statute_refs = re.findall(PATTERNS["statute_refs"], text)
    if statute_refs:
        entities["statute_refs"] = list(set(statute_refs))
    
    # Extract case citations
    case_refs = re.findall(PATTERNS["case_refs"], text)
    if case_refs:
        entities["case_refs"] = list(set(case_refs))
    
    # Extract courts
    courts = []
    court_matches = re.findall(PATTERNS["courts"], text)
    if court_matches:
        entities["courts"] = list(set(court_matches))
    
    return entities

def generate_chunk_id(doc_id: str, section_path: str, start_char: int, end_char: int, chunk_text: str) -> str:
    """Generate a stable, deterministic chunk ID."""
    # Normalize whitespace before hashing to ensure stability
    normalized_text = re.sub(r'\s+', ' ', chunk_text).strip()
    text_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()[:8]
    
    components = f"{doc_id}|{section_path}|{start_char}|{end_char}|{text_hash}"
    return hashlib.sha256(components.encode("utf-8")).hexdigest()[:16]

def find_sentence_boundary(text: str, position: int) -> int:
    """Find the nearest sentence boundary to the given position."""
    # Look for sentence-ending punctuation followed by space or newline
    sentence_end_pattern = r'[.!?]\s+'
    
    # If we're at the end of the text, return that position
    if position >= len(text):
        return len(text)
    
    # If we're at a space, that's a good boundary
    if text[position] == ' ':
        return position
    
    # Search forward for the next sentence boundary
    text_after = text[position:]
    forward_match = re.search(sentence_end_pattern, text_after)
    forward_pos = position + forward_match.end() if forward_match else len(text)
    
    # Search backward for the previous sentence boundary or start of a sentence
    text_before = text[:position]
    backward_matches = list(re.finditer(sentence_end_pattern, text_before))
    
    if backward_matches:
        backward_pos = backward_matches[-1].end()
    else:
        # If no sentence boundary found, look for start of paragraph or start of text
        last_newline = text_before.rfind('\n')
        if last_newline != -1:
            backward_pos = last_newline + 1  # Start of line after newline
        else:
            backward_pos = 0  # Start of text
    
    # If we're closer to the end of a sentence than the start of the next one, go to the end
    if forward_pos - position <= position - backward_pos:
        return forward_pos
    else:
        return backward_pos

def process_judgment(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a judgment document and create chunks."""
    chunks = []
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
    body = content_tree.get("body", [])
    
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
        return chunks
    
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
                start_char=0,  # We don't track exact character positions in this simplified version
                end_char=len(current_chunk_text),
                chunk_text=current_chunk_text,
            )
            
            # Create chunk object
            chunk = {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "chunk_text": current_chunk_text,
                "section_path": section_path,
                "start_char": 0,  # Simplified
                "end_char": len(current_chunk_text),
                "num_tokens": estimate_tokens(current_chunk_text),
                "language": language,
                "doc_type": doc_type,
                "date_context": date_context,
                "entities": entities,
                "source_url": source_url,
                "metadata": {
                    "title": title,
                    "court": court,
                    "canonical_citation": canonical_citation,
                    "chunk_index": chunk_index,
                    "paragraph_range": f"{start_para}-{end_para}"
                },
            }
            
            chunks.append(chunk)
            chunk_index += 1
            
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
        
        # Create chunk object
        chunk = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "chunk_text": current_chunk_text,
            "section_path": section_path,
            "start_char": 0,
            "end_char": len(current_chunk_text),
            "num_tokens": estimate_tokens(current_chunk_text),
            "language": language,
            "doc_type": doc_type,
            "date_context": date_context,
            "entities": entities,
            "source_url": source_url,
            "metadata": {
                "title": title,
                "court": court,
                "canonical_citation": canonical_citation,
                "chunk_index": chunk_index,
                "paragraph_range": f"{start_para}-{end_para}"
            },
        }
        
        chunks.append(chunk)
    
    return chunks

def main():
    # Path to docs.jsonl
    docs_path = Path("data/processed/docs.jsonl")
    
    # Output path for test chunks
    output_path = Path("data/processed/test_chunks.jsonl")
    
    # Load a single document (the second one, which is a judgment with actual content)
    with open(docs_path, "r", encoding="utf-8") as f:
        docs = [json.loads(line) for line in f]
        
    # Find a judgment with substantive content
    test_doc = None
    for doc in docs:
        if doc["doc_type"] == "judgment":
            content_tree = doc.get("content_tree", {})
            body = content_tree.get("body", [])
            # Find a document with a substantial body
            if len(" ".join(body)) > 1000:
                test_doc = doc
                break
    
    if not test_doc:
        logger.error("No suitable test document found")
        sys.exit(1)
    
    logger.info(f"Testing chunking on document: {test_doc.get('doc_id')} - {test_doc.get('title')}")
    
    # Process the document
    chunks = process_judgment(test_doc)
    
    # Write chunks to output file
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, default=str) + "\n")
    
    logger.info(f"Generated {len(chunks)} chunks from test document")
    
    # Print some stats about the chunks
    if chunks:
        avg_tokens = sum(chunk["num_tokens"] for chunk in chunks) / len(chunks)
        avg_chars = sum(len(chunk["chunk_text"]) for chunk in chunks) / len(chunks)
        
        logger.info(f"Average chunk size: {avg_tokens:.1f} tokens, {avg_chars:.1f} characters")
        
        # Print a sample chunk
        logger.info("Sample chunk:")
        sample = chunks[0]
        logger.info(f"  ID: {sample.get('chunk_id')}")
        logger.info(f"  Section: {sample.get('section_path')}")
        logger.info(f"  Tokens: {sample.get('num_tokens')}")
        logger.info(f"  Text: {sample.get('chunk_text')[:100]}...")
        
        if len(chunks) > 1:
            logger.info("Overlap between first two chunks:")
            chunk1 = chunks[0]["chunk_text"]
            chunk2 = chunks[1]["chunk_text"]
            
            # Find the overlap
            overlap_start = 0
            for i in range(min(len(chunk1), 100)):
                if chunk2.startswith(chunk1[-i:]):
                    overlap_start = len(chunk1) - i
                    break
            
            if overlap_start > 0:
                overlap_text = chunk1[overlap_start:]
                logger.info(f"  Overlap: {len(overlap_text)} chars")
                logger.info(f"  Text: {overlap_text[:50]}...")
            else:
                logger.info("  No direct text overlap found")

if __name__ == "__main__":
    main()
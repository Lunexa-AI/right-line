#!/usr/bin/env python3
"""
enrich_chunks.py - Enrich chunks with additional entity extraction and normalization

This script implements Task 5 from the INGESTION_AND_CHUNKING_TASKLIST.md.
It reads chunks from chunks.jsonl, performs advanced entity extraction and normalization,
and writes the enriched chunks back to the same file.

Usage:
    python scripts/enrich_chunks.py [--input_file PATH] [--output_file PATH] [--verbose]

Author: RightLine Team
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import structlog
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = structlog.get_logger()

# Entity extraction patterns (enhanced from chunk_docs.py)
PATTERNS = {
    # Date patterns: match various formats and normalize to ISO
    "dates": [
        # DD/MM/YYYY or DD-MM-YYYY
        (r'\b(\d{1,2})[-/](\d{1,2})[-/]((?:19|20)\d{2})\b', lambda m: f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"),
        # MM/DD/YYYY or MM-DD-YYYY (US format)
        (r'\b(\d{1,2})[-/](\d{1,2})[-/]((?:19|20)\d{2})\b', lambda m: f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"),
        # DD Month YYYY
        (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+((?:19|20)\d{2})\b', 
         lambda m: f"{m.group(3)}-{month_to_number(m.group(2)):02d}-{int(m.group(1)):02d}"),
        # Month DD, YYYY
        (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+((?:19|20)\d{2})\b',
         lambda m: f"{m.group(3)}-{month_to_number(m.group(1)):02d}-{int(m.group(2)):02d}"),
        # YYYY-MM-DD (already ISO)
        (r'\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b', lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
    ],
    
    # Section references: standardize format
    "statute_refs": [
        # s 12A, s. 12A, s.12A -> Section 12A
        (r'\bs\.?\s*(\d+[A-Z]?)(?:\s*\(\d+\))?(?:\s*\([a-z]\))?', lambda m: f"Section {m.group(1)}"),
        # section 12A -> Section 12A
        (r'\bsection\s+(\d+[A-Z]?)(?:\s*\(\d+\))?(?:\s*\([a-z]\))?', lambda m: f"Section {m.group(1)}"),
        # Act [Chapter X:Y]
        (r'\b([A-Za-z\s]+)\s+Act\s+\[Chapter\s+(\d+:\d+)\]', lambda m: f"{m.group(1)} Act [Chapter {m.group(2)}]"),
        # Simple Act names
        (r'\b([A-Za-z\s]+)\s+Act\b', lambda m: f"{m.group(1)} Act"),
    ],
    
    # Case citations: standardize format
    "case_refs": [
        # [YYYY] COURT NNN
        (r'\[(\d{4})\]\s+([A-Z]{2,5})\s+(\d+)', lambda m: f"[{m.group(1)}] {m.group(2)} {m.group(3)}"),
        # YYYY (N) COURT NNN
        (r'(\d{4})\s*\((\d+)\)\s*([A-Z]{2,5})\s*(\d+)', lambda m: f"{m.group(1)} ({m.group(2)}) {m.group(3)} {m.group(4)}"),
        # S v Name COURT NNN/YY
        (r'S\s+v\s+([A-Z][a-z]+)\s+([A-Z]{2,5})\s+(\d+)/(\d+)', lambda m: f"S v {m.group(1)} {m.group(2)} {m.group(3)}/{m.group(4)}"),
    ],
    
    # Court names: standardize format
    "courts": [
        # High Court
        (r'\bHigh Court\b', lambda m: "High Court of Zimbabwe"),
        # Supreme Court
        (r'\bSupreme Court\b', lambda m: "Supreme Court of Zimbabwe"),
        # Constitutional Court
        (r'\bConstitutional Court\b', lambda m: "Constitutional Court of Zimbabwe"),
        # Magistrates Court
        (r'\bMagistrates Court\b', lambda m: "Magistrates Court of Zimbabwe"),
        # Labour Court
        (r'\bLabour Court\b', lambda m: "Labour Court of Zimbabwe"),
    ],
    
    # Judge names: extract judge names
    "judges": [
        # SURNAME J
        (r'\b([A-Z]{2,})\s+J\b', lambda m: f"{m.group(1)} J"),
        # SURNAME JA
        (r'\b([A-Z]{2,})\s+JA\b', lambda m: f"{m.group(1)} JA"),
        # Justice SURNAME
        (r'\bJustice\s+([A-Z][A-Za-z]+)\b', lambda m: f"Justice {m.group(1)}"),
    ],
    
    # Party names: extract party names from case names
    "parties": [
        # X v Y
        (r'\b([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)\b', 
         lambda m: {"applicant": m.group(1), "respondent": m.group(2)}),
    ],
}

# List of known courts for verification
KNOWN_COURTS = [
    "High Court of Zimbabwe",
    "Supreme Court of Zimbabwe",
    "Constitutional Court of Zimbabwe",
    "Magistrates Court of Zimbabwe",
    "Labour Court of Zimbabwe",
]

def month_to_number(month_name: str) -> int:
    """Convert month name to month number."""
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }
    return months.get(month_name, 1)  # Default to January if not found

def extract_and_normalize_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract and normalize entities from text using regex patterns.
    
    Args:
        text: The text to process
        
    Returns:
        Dictionary of entity types and their normalized values
    """
    entities = {}
    
    # Process each entity type
    for entity_type, patterns in PATTERNS.items():
        if entity_type == "parties":
            # Special handling for parties which returns a dict
            for pattern, formatter in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    party_dict = formatter(match)
                    if "parties" not in entities:
                        entities["parties"] = []
                    entities["parties"].append(party_dict)
        else:
            # Standard entity extraction with normalization
            extracted = []
            for pattern, formatter in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    normalized = formatter(match)
                    if normalized not in extracted:
                        extracted.append(normalized)
            
            if extracted:
                entities[entity_type] = extracted
    
    return entities

def enrich_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a chunk with additional entity extraction and normalization.
    
    Args:
        chunk: The chunk to enrich
        
    Returns:
        Enriched chunk
    """
    # Extract text for processing
    chunk_text = chunk.get("chunk_text", "")
    
    # Extract and normalize entities
    entities = extract_and_normalize_entities(chunk_text)
    
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
    if "dates" in entities and entities["dates"]:
        # Use the first date as date_context if not already set
        if not chunk.get("date_context"):
            chunk["date_context"] = entities["dates"][0]
    
    # Add court to metadata if available
    if "courts" in entities and entities["courts"]:
        if "metadata" not in chunk:
            chunk["metadata"] = {}
        if "court" not in chunk["metadata"] or not chunk["metadata"]["court"]:
            chunk["metadata"]["court"] = entities["courts"][0]
    
    return chunk

def process_chunks(input_file: Path, output_file: Path, verbose: bool = False) -> None:
    """
    Process chunks from input file and write enriched chunks to output file.
    
    Args:
        input_file: Path to input JSONL file
        output_file: Path to output JSONL file
        verbose: Whether to print verbose output
    """
    try:
        # Load chunks
        chunks = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        logger.info(f"Loaded {len(chunks)} chunks from {input_file}")
        
        # Process each chunk
        enriched_chunks = []
        for chunk in tqdm(chunks, desc="Enriching chunks"):
            try:
                enriched_chunk = enrich_chunk(chunk)
                enriched_chunks.append(enriched_chunk)
                
                if verbose:
                    logger.info(f"Enriched chunk {chunk.get('chunk_id')}")
            except Exception as e:
                logger.error(f"Error enriching chunk {chunk.get('chunk_id')}: {e}")
                if verbose:
                    import traceback
                    logger.error(traceback.format_exc())
                # Keep the original chunk
                enriched_chunks.append(chunk)
        
        # Write enriched chunks to output file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for chunk in enriched_chunks:
                f.write(json.dumps(chunk, default=str) + "\n")
        
        logger.info(f"Wrote {len(enriched_chunks)} enriched chunks to {output_file}")
        
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
    
    except Exception as e:
        logger.error(f"Error: {e}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Enrich chunks with additional entity extraction and normalization")
    parser.add_argument("--input_file", type=Path, default="data/processed/chunks.jsonl", 
                        help="Path to input JSONL file")
    parser.add_argument("--output_file", type=Path, default="data/processed/chunks_enriched.jsonl", 
                        help="Path to output JSONL file")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    
    args = parser.parse_args()
    
    process_chunks(args.input_file, args.output_file, args.verbose)

if __name__ == "__main__":
    main()

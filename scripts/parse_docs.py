#!/usr/bin/env python3
"""Parse ZimLII HTML into normalized document objects.

This script parses raw HTML files from ZimLII (legislation and judgments)
into normalized document objects according to the schema defined in
PARSING_AND_NORMALIZATION.md, and outputs them as JSON lines in
data/processed/docs.jsonl.

Usage:
    python scripts/parse_docs.py [--input-dir data/raw] [--output data/processed/docs.jsonl]

Environment Variables:
    None required
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from bs4 import BeautifulSoup, Tag
    import orjson
except ImportError as e:
    print(f"❌ Error: Missing dependency. Run: pip install beautifulsoup4 lxml orjson")
    print(f"   Specific error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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


def extract_json_script(soup: BeautifulSoup, script_id: str) -> Dict[str, Any]:
    """Extract JSON data from a script tag with the given ID."""
    script_tag = soup.find("script", id=script_id)
    if not script_tag or not script_tag.string:
        return {}
    
    try:
        return json.loads(script_tag.string)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON from script tag with id '{script_id}'")
        return {}


def extract_metadata_from_head(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract metadata from HTML head tags."""
    metadata = {}
    
    # Extract title
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()
        # Remove "- ZimLII" suffix if present
        if "- ZimLII" in title:
            title = title.replace("- ZimLII", "").strip()
        metadata["title"] = title
    
    # Extract publication date
    pub_date_meta = soup.find("meta", property="article:published_time")
    if pub_date_meta and pub_date_meta.get("content"):
        metadata["publication_date"] = pub_date_meta["content"]
    
    # Extract FRBR URI data from track-page-properties
    frbr_data = extract_json_script(soup, "track-page-properties")
    if frbr_data:
        metadata.update({
            "work_frbr_uri": frbr_data.get("work_frbr_uri"),
            "expression_frbr_uri": frbr_data.get("expression_frbr_uri"),
            "frbr_uri_doctype": frbr_data.get("frbr_uri_doctype"),
            "frbr_uri_language": frbr_data.get("frbr_uri_language"),
            "frbr_uri_date": frbr_data.get("frbr_uri_date"),
            "frbr_uri_number": frbr_data.get("frbr_uri_number"),
            "frbr_uri_actor": frbr_data.get("frbr_uri_actor"),
        })
    
    return metadata


def find_main_content(soup: BeautifulSoup) -> Optional[Tag]:
    """Find the main content container in the HTML."""
    # Try different selectors to find the main content
    selectors = [
        "main",
        "article",
        "div.akoma-ntoso",
        "div.document-content",
        "div.judgment",
        "div[role='main']",
        "div.main-content",
    ]
    
    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            return content
    
    # Fallback: look for a div with id or class containing content-related terms
    content_terms = ["content", "document", "main", "judgment", "legislation"]
    for term in content_terms:
        # Try id
        content = soup.find("div", id=lambda x: x and term in x.lower())
        if content:
            return content
        
        # Try class
        content = soup.find("div", class_=lambda x: x and term in x.lower())
        if content:
            return content
    
    logger.warning("Could not find main content container")
    return None


def clean_html_content(content: Tag) -> Tag:
    """Remove unnecessary elements from the content."""
    if not content:
        return content
    
    # Clone to avoid modifying the original
    content = content.__copy__()
    
    # Remove script, style, nav, footer, etc.
    for tag_name in ["script", "style", "nav", "footer", "header", "aside"]:
        for tag in content.find_all(tag_name):
            tag.decompose()
    
    # Remove social/share blocks
    for tag in content.find_all(class_=lambda x: x and any(term in x.lower() for term in ["social", "share", "cookie", "banner"])):
        tag.decompose()
    
    return content


def infer_nature_from_frbr(work_uri: Optional[str], expression_uri: Optional[str]) -> str:
    """Infer document nature from FRBR URIs.
    - /act/si/ -> Statutory Instrument
    - /act/ord/ -> Ordinance
    - otherwise -> Act
    """
    uri = expression_uri or work_uri or ""
    if "/act/si/" in uri:
        return "Statutory Instrument"
    if "/act/ord/" in uri:
        return "Ordinance"
    return "Act"


def parse_effective_date(expression_uri: Optional[str], fallback_pub: Optional[str]) -> Optional[str]:
    if expression_uri:
        date_match = re.search(r'@(\d{4}-\d{2}-\d{2})', expression_uri)
        if date_match:
            return date_match.group(1)
    return fallback_pub


def parse_year_from_uris(number: Optional[str], expression_uri: Optional[str]) -> Optional[int]:
    if expression_uri:
        m = re.search(r'/(\d{4})/', expression_uri)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
    if number and number.isdigit() and len(number) == 4:
        try:
            return int(number)
        except Exception:
            return None
    return None


def extract_text_with_structure(element: Tag) -> List[Dict[str, Any]]:
    """Extract text while preserving some structure (headings, paragraphs)."""
    result = []
    
    for child in element.children:
        if isinstance(child, Tag):
            if child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                # Extract heading
                text = normalize_whitespace(child.get_text())
                if text:
                    result.append({
                        "type": "heading",
                        "level": int(child.name[1]),
                        "text": text,
                        "id": child.get("id", ""),
                    })
            elif child.name == "p":
                # Extract paragraph
                text = normalize_whitespace(child.get_text())
                if text:
                    result.append({
                        "type": "paragraph",
                        "text": text,
                    })
            elif child.name in ["div", "section"]:
                # Recursively process div/section
                result.extend(extract_text_with_structure(child))
            elif child.name in ["ul", "ol"]:
                # Process lists
                for li in child.find_all("li", recursive=False):
                    text = normalize_whitespace(li.get_text())
                    if text:
                        result.append({
                            "type": "list_item",
                            "text": text,
                        })
            elif child.name == "table":
                # For tables, just extract as text for now
                text = normalize_whitespace(child.get_text())
                if text:
                    result.append({
                        "type": "table",
                        "text": text,
                    })
        elif child.string and child.string.strip():
            # Direct text node
            text = normalize_whitespace(child.string)
            if text:
                result.append({
                    "type": "text",
                    "text": text,
                })
    
    return result


def extract_akn_legislation(content: Tag) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract Akoma Ntoso legislation structure."""
    parts = []
    section_ids = []
    part_map = {}
    
    # Find all parts in the legislation
    akn_parts = content.find_all("section", class_="akn-part")
    
    for part_elem in akn_parts:
        part_id = part_elem.get("id", "")
        
        # Extract part title from h2
        part_title_elem = part_elem.find("h2")
        part_title = normalize_whitespace(part_title_elem.get_text()) if part_title_elem else f"Part {part_id}"
        
        # Find all sections within this part
        sections = []
        part_section_ids = []
        akn_sections = part_elem.find_all("section", class_="akn-section", recursive=False)
        
        for section_elem in akn_sections:
            section_id = section_elem.get("id", "")
            
            # Extract section title from h3
            section_title_elem = section_elem.find("h3")
            section_title = normalize_whitespace(section_title_elem.get_text()) if section_title_elem else f"Section {section_id}"
            
            # Extract all paragraphs within this section
            paragraphs = []
            
            # Get all akn-p elements within this section (content paragraphs)
            akn_paragraphs = section_elem.find_all("span", class_="akn-p")
            
            for para_elem in akn_paragraphs:
                para_text = normalize_whitespace(para_elem.get_text())
                if para_text and len(para_text.strip()) > 10:  # Skip very short paragraphs
                    paragraphs.append(para_text)
            
            if paragraphs:  # Only add sections that have content
                section_ids.append(section_id)
                part_section_ids.append(section_id)
                
                sections.append({
                    "id": section_id,
                    "title": section_title,
                    "anchor": f"#{section_id}",
                    "paragraphs": paragraphs
                })
        
        if sections:  # Only add parts that have sections
            part_map[part_title] = part_section_ids
            parts.append({
                "title": part_title,
                "id": part_id,
                "sections": sections
            })
    
    content_tree = {"parts": parts}
    extra = {
        "section_ids": section_ids,
        "part_map": part_map
    }
    
    return content_tree, extra


def extract_sections_legislation(content: Tag) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract sections from legislation content."""
    # First try AKN structure
    if content.find("section", class_="akn-part"):
        return extract_akn_legislation(content)
    
    # Fallback to generic HTML parsing
    sections = []
    section_ids = []
    part_map = {}
    current_part = None
    current_chapter = None
    
    # Extract structured content
    elements = extract_text_with_structure(content)
    
    # Process elements to identify parts, chapters, sections
    i = 0
    while i < len(elements):
        element = elements[i]
        
        if element["type"] == "heading":
            heading_text = element["text"].lower()
            
            # Check if it's a part heading
            if "part" in heading_text and (element["level"] <= 2 or "part" in heading_text[:10]):
                current_part = element["text"]
                part_map[current_part] = []
                i += 1
                continue
            
            # Check if it's a chapter heading
            if "chapter" in heading_text and (element["level"] <= 3 or "chapter" in heading_text[:15]):
                current_chapter = element["text"]
                i += 1
                continue
            
            # Check if it's a section heading
            if "section" in heading_text or re.search(r'^\d+\.', heading_text):
                section_id = element.get("id", f"s-{len(sections)}")
                section_ids.append(section_id)
                
                # Collect paragraphs for this section
                section_paragraphs = []
                j = i + 1
                while j < len(elements) and (
                    elements[j]["type"] != "heading" or 
                    elements[j]["level"] >= element["level"]
                ):
                    if elements[j]["type"] in ["paragraph", "list_item", "text", "table"]:
                        section_paragraphs.append(elements[j]["text"])
                    j += 1
                
                # Create section object
                section = {
                    "id": section_id,
                    "title": element["text"],
                    "anchor": f"#{section_id}",
                    "paragraphs": section_paragraphs
                }
                
                sections.append(section)
                
                # Update part_map
                if current_part:
                    part_map[current_part].append(section_id)
                
                i = j
                continue
        
        i += 1
    
    # Create content tree
    content_tree = {
        "parts": []
    }
    
    # Organize sections into parts/chapters
    current_part = None
    current_part_obj = None
    
    for section in sections:
        if not current_part_obj or section["id"] not in part_map.get(current_part, []):
            # Find which part this section belongs to
            for part_name, part_sections in part_map.items():
                if section["id"] in part_sections:
                    current_part = part_name
                    current_part_obj = {
                        "title": part_name,
                        "chapters": [],
                        "sections": []
                    }
                    content_tree["parts"].append(current_part_obj)
                    break
            
            # If no part found, create a default one
            if not current_part_obj:
                current_part = "General Provisions"
                current_part_obj = {
                    "title": current_part,
                    "chapters": [],
                    "sections": []
                }
                content_tree["parts"].append(current_part_obj)
        
        # Add section to current part
        current_part_obj["sections"].append(section)
    
    extra = {
        "section_ids": section_ids,
        "part_map": part_map
    }
    
    return content_tree, extra


def extract_case_details(content: Tag) -> Dict[str, Any]:
    """Extract case details from a judgment."""
    details = {}
    
    # Look for case number, court, date, judges
    case_number_pattern = r'(?:case|application|criminal|civil)\s+(?:no\.?|number)\s*:?\s*([A-Z]{1,5}\s*\d+\/\d+)'
    court_pattern = r'(?:in the|before the)\s+(.*?court.*?)(?:$|,|\n)'
    date_pattern = r'(?:date delivered|date of delivery|delivered on)[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+,?\s+\d{4})'
    judges_pattern = r'(?:before|judge|judges)[:\s]+(.*?)(?:$|,|\n)'
    
    # Extract text from the first few elements
    text = " ".join([normalize_whitespace(element.get_text()) for element in content.find_all(["h1", "h2", "h3", "p"], limit=10)])
    
    # Case number
    case_number_match = re.search(case_number_pattern, text, re.IGNORECASE)
    if case_number_match:
        details["case_number"] = case_number_match.group(1).strip()
    
    # Court
    court_match = re.search(court_pattern, text, re.IGNORECASE)
    if court_match:
        details["court"] = court_match.group(1).strip()
    elif "HIGH COURT" in text.upper():
        details["court"] = "High Court of Zimbabwe"
    elif "SUPREME COURT" in text.upper():
        details["court"] = "Supreme Court of Zimbabwe"
    
    # Date
    date_match = re.search(date_pattern, text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1).strip()
        # Try to parse and standardize the date
        try:
            # Remove ordinal suffixes
            date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            date_obj = datetime.datetime.strptime(date_str, "%d %B %Y")
            details["date_decided"] = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            details["date_decided"] = date_str
    
    # Judges
    judges_match = re.search(judges_pattern, text, re.IGNORECASE)
    if judges_match:
        judges_text = judges_match.group(1).strip()
        judges = [j.strip() for j in re.split(r'(?:,|and)', judges_text) if j.strip()]
        if judges:
            details["judges"] = judges
    
    # Extract parties (applicant/respondent or appellant/respondent)
    parties = {}
    
    # Look for "v" or "vs" pattern
    v_pattern = r'([^v]+)\s+v\.?\s+([^,\n]+)'
    v_match = re.search(v_pattern, text)
    if v_match:
        parties["applicant"] = normalize_whitespace(v_match.group(1))
        parties["respondent"] = normalize_whitespace(v_match.group(2))
    
    if parties:
        details["parties"] = parties
    
    return details


def extract_sections_judgment(content: Tag) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract sections from judgment content."""
    # Extract case details
    extra = extract_case_details(content)
    
    # Extract structured content
    elements = extract_text_with_structure(content)
    
    # Identify headnote and body
    headnote = []
    body = []
    
    # Simple heuristic: first few paragraphs before a major heading are likely the headnote
    in_headnote = True
    for element in elements:
        if in_headnote and element["type"] == "heading" and element["level"] <= 2:
            in_headnote = False
        
        if element["type"] in ["paragraph", "text", "list_item", "table"]:
            if in_headnote:
                headnote.append(element["text"])
            else:
                body.append(element["text"])
    
    # If no clear headnote was found, assume first paragraph is headnote
    if not headnote and body:
        headnote = [body.pop(0)]
    
    # Store raw headnote in extra
    if headnote:
        extra["headnote"] = "\n\n".join(headnote)
    
    # Create content tree
    content_tree = {
        "headnote": headnote,
        "body": body
    }
    
    return content_tree, extra


def extract_references(content: Tag) -> List[str]:
    """Extract references to legislation and cases."""
    references = []
    
    # Look for common reference patterns
    text = content.get_text()
    
    # Acts
    act_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act(?:\s+\[[^\]]+\])?'
    for match in re.finditer(act_pattern, text):
        references.append(match.group(0).strip())
    
    # Cases with neutral citations
    case_pattern = r'[A-Z][a-z]+\s+v\s+[A-Z][a-z]+\s+\[\d{4}\]\s+[A-Z]{2,5}\s+\d+'
    for match in re.finditer(case_pattern, text):
        references.append(match.group(0).strip())
    
    # Deduplicate
    return list(set(references))


def parse_legislation(html_content: str, source_url: str) -> Dict[str, Any]:
    """Parse legislation HTML into a normalized document object."""
    soup = BeautifulSoup(html_content, "lxml")
    
    # Extract metadata from head
    metadata = extract_metadata_from_head(soup)
    
    # Find main content
    content = find_main_content(soup)
    if not content:
        logger.warning(f"Could not find main content in {source_url}")
        content = soup.find("body")
    
    # Clean content
    content = clean_html_content(content)
    
    # Extract sections and extra metadata
    content_tree, extra_data = extract_sections_legislation(content)
    
    # Extract references
    references = extract_references(content)
    if references:
        extra_data["references"] = references
    
    # Get FRBR data
    work_uri = metadata.get("work_frbr_uri", "")
    expression_uri = metadata.get("expression_frbr_uri", "")
    
    # Effective date and year
    effective_date = parse_effective_date(expression_uri, metadata.get("publication_date"))
    year = parse_year_from_uris(metadata.get("frbr_uri_number"), expression_uri)
    
    # Infer nature and chapter
    nature = infer_nature_from_frbr(work_uri, expression_uri)
    chapter = None
    # Scan title and page text for a Chapter pattern if not already found in structured sections
    page_text = soup.get_text(" ")
    chapter_pattern = r'Chapter\s+(\d+(?::\d+)?)'
    m_ch = re.search(chapter_pattern, page_text, flags=re.I)
    if m_ch:
        chapter = m_ch.group(1)
    
    # Build extra object
    extra = {
        "chapter": chapter,
        "act_number": metadata.get("frbr_uri_number"),
        "expression_uri": expression_uri,
        "work_uri": work_uri,
        "akn_uri": work_uri or expression_uri,
        "nature": nature,
        "year": year,
        "section_ids": extra_data.get("section_ids", []),
        "part_map": extra_data.get("part_map", {}),
    }
    
    if effective_date:
        extra["effective_start"] = effective_date
    
    # Add references if found
    if "references" in extra_data:
        extra["references"] = extra_data["references"]
    
    # Generate stable doc_id
    id_input = f"{source_url}{expression_uri}{metadata.get('title', '')}"
    doc_id = sha256_16(id_input)
    
    # Decide document type for downstream filtering
    if nature == "Statutory Instrument":
        doc_type = "si"
    elif nature == "Ordinance":
        doc_type = "ordinance"
    else:
        doc_type = "act"

    # Create document object
    now = datetime.datetime.utcnow().isoformat() + "Z"
    document = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "title": metadata.get("title", "Untitled Act"),
        "source_url": source_url,
        "language": metadata.get("frbr_uri_language", "eng"),
        "jurisdiction": "ZW",
        "version_effective_date": effective_date,
        "canonical_citation": None,  # Not typically available for legislation
        "created_at": now,
        "updated_at": now,
        "extra": extra,
        "content_tree": content_tree,
    }
    
    return document


def parse_judgment(html_content: str, source_url: str) -> Dict[str, Any]:
    """Parse judgment HTML into a normalized document object."""
    soup = BeautifulSoup(html_content, "lxml")
    
    # Extract metadata from head
    metadata = extract_metadata_from_head(soup)
    
    # Find main content
    content = find_main_content(soup)
    if not content:
        logger.warning(f"Could not find main content in {source_url}")
        content = soup.find("body")
    
    # Clean content
    content = clean_html_content(content)
    
    # Extract sections and case details
    content_tree, extra_data = extract_sections_judgment(content)
    
    # Extract references
    references = extract_references(content)
    if references:
        extra_data["references"] = references
    
    # Extract neutral citation from title
    neutral_citation = None
    citation_pattern = r'\[\d{4}\]\s+[A-Z]{2,5}\s+\d+'
    title = metadata.get("title", "")
    citation_match = re.search(citation_pattern, title)
    if citation_match:
        neutral_citation = citation_match.group(0)
    
    # Extract date decided
    date_decided = extra_data.get("date_decided")
    if not date_decided and "publication_date" in metadata:
        date_decided = metadata["publication_date"]
    
    # Generate stable doc_id
    expression_uri = metadata.get("expression_frbr_uri", "")
    id_input = f"{source_url}{expression_uri}{metadata.get('title', '')}"
    doc_id = sha256_16(id_input)
    
    # Create document object
    now = datetime.datetime.utcnow().isoformat() + "Z"
    document = {
        "doc_id": doc_id,
        "doc_type": "judgment",
        "title": metadata.get("title", "Untitled Judgment"),
        "source_url": source_url,
        "language": metadata.get("frbr_uri_language", "eng"),
        "jurisdiction": "ZW",
        "version_effective_date": None,  # Not applicable for judgments
        "canonical_citation": neutral_citation,
        "created_at": now,
        "updated_at": now,
        "extra": extra_data,
        "content_tree": content_tree,
    }
    
    return document


def detect_document_type(file_path: Path) -> str:
    """Detect document type from file path or content."""
    # Check path first
    path_str = str(file_path).lower()
    if "legislation" in path_str:
        return "act"
    elif "judgment" in path_str:
        return "judgment"
    
    # If path doesn't give a clear indication, check content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(4096)  # Read just the beginning
            soup = BeautifulSoup(content, "lxml")
            
            # Check for FRBR data
            frbr_data = extract_json_script(soup, "track-page-properties")
            if frbr_data:
                doctype = frbr_data.get("frbr_uri_doctype")
                if doctype == "act":
                    return "act"
                elif doctype == "judgment":
                    return "judgment"
            
            # Check title
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                title = title_tag.string.lower()
                if "act" in title and "v" not in title:
                    return "act"
                elif "v" in title or "case" in title:
                    return "judgment"
    
    except Exception as e:
        logger.warning(f"Error detecting document type for {file_path}: {e}")
    
    # Default to judgment if we can't determine
    return "judgment"


def parse_html_file(file_path: Path) -> Dict[str, Any]:
    """Parse an HTML file into a normalized document object."""
    # Determine document type
    doc_type = detect_document_type(file_path)
    
    # Read file
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Try to reconstruct canonical AKN URL from FRBR data in the HTML
    try:
        soup = BeautifulSoup(html_content, "lxml")
        frbr = extract_json_script(soup, "track-page-properties")
        src = frbr.get("expression_frbr_uri") or frbr.get("work_frbr_uri")
        if src and src.startswith("/"):
            source_url = f"https://zimlii.org{src}"
        else:
            source_url = src or f"https://zimlii.org/content/{file_path.name}"
    except Exception:
        source_url = f"https://zimlii.org/content/{file_path.name}"
    
    # Parse based on document type
    if doc_type == "act":
        return parse_legislation(html_content, source_url)
    else:
        return parse_judgment(html_content, source_url)


def process_directory(input_dir: Path, output_file: Path) -> None:
    """Process all HTML files in the input directory and write to output file."""
    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Find all HTML files
    html_files = []
    for subdir in ["legislation", "judgments"]:
        subdir_path = input_dir / subdir
        if subdir_path.exists():
            html_files.extend(list(subdir_path.glob("*.html")))
    
    if not html_files:
        logger.warning(f"No HTML files found in {input_dir}/legislation or {input_dir}/judgments")
        return
    
    logger.info(f"Found {len(html_files)} HTML files to process")
    
    # Process each file
    documents = []
    for file_path in html_files:
        try:
            logger.info(f"Processing {file_path}")
            document = parse_html_file(file_path)
            documents.append(document)
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
    
    logger.info(f"Processed {len(documents)} documents successfully")
    
    # Write output
    with open(output_file, "wb") as f:
        for doc in documents:
            # Use orjson for better performance and UTF-8 handling
            f.write(orjson.dumps(doc))
            f.write(b"\n")
    
    logger.info(f"Wrote {len(documents)} documents to {output_file}")


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Parse ZimLII HTML into normalized document objects")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw"),
        help="Input directory containing HTML files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/docs.jsonl"),
        help="Output JSONL file"
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
    
    # Process files
    process_directory(args.input_dir, args.output)


if __name__ == "__main__":
    main()

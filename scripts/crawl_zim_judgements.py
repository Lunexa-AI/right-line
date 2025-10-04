#!/usr/bin/env python3
"""
crawl_zim_judgements.py - Crawl ZimLII judgments with rich metadata, uploading PDFs to Cloudflare R2.

Goals:
- Enumerate all judgments from ZimLII (8,539+ judgments across all courts)
- Extract rich metadata (case name, court, citation, date, parties, judges)
- Download PDF files for each judgment
- Upload PDFs to R2 under `corpus/sources/judgements/`
- Persist consolidated metadata catalog to R2 as `corpus/metadata/judgements_catalog.jsonl`

Courts Covered:
- Constitutional Court of Zimbabwe
- Supreme Court of Zimbabwe
- High Courts (Bulawayo, Chinhoyi, Harare, Masvingo, Mutare)
- Labour Court

Usage:
  # Ensure R2 env vars are set before running
  python scripts/crawl_zim_judgements.py --max-pages 0 --delay 0.8 --concurrency 8
  
  # Crawl specific court only
  python scripts/crawl_zim_judgements.py --court supreme --max-pages 10
  
  # Crawl specific year range
  python scripts/crawl_zim_judgements.py --start-year 2020 --end-year 2025
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import boto3
import httpx
from botocore.client import Config
from bs4 import BeautifulSoup

BASE = "https://zimlii.org"
INDEX_URL = f"{BASE}/judgments/all/"
UA = "RightLineCrawler/1.0 (+https://rightline.zw)"
DEFAULT_TIMEOUT = 30.0
RETRIES = 3

# Years that need month-level filtering to bypass pagination limits
YEARS_NEEDING_MONTH_FILTER = [2024, 2023, 2017, 2016, 2015]

# Court mappings from ZimLII URL patterns to readable names
COURT_MAPPINGS = {
    "zwcc": "Constitutional Court of Zimbabwe",
    "zwsc": "Supreme Court of Zimbabwe",
    "zwbhc": "High Court of Zimbabwe (Bulawayo)",
    "zwchhc": "High Court of Zimbabwe (Chinhoyi)",
    "zwhc": "High Court of Zimbabwe (Harare)",
    "zwmsvhc": "High Court of Zimbabwe (Masvingo)",
    "zwmthc": "High Court of Zimbabwe (Mutare)",
    "zwlc": "Labour Court of Zimbabwe",
    "zwhhc": "High Court of Zimbabwe (Harare)",  # Alternative code
}


@dataclass
class JudgmentCatalogRow:
    """Metadata for a single judgment."""
    akn_uri: str
    case_name: str
    citation: str
    court: str
    court_code: str
    judgment_date: str
    year: int
    case_number: str
    parties: Dict[str, List[str]]  # plaintiff, defendant, appellant, respondent
    judges: Optional[List[str]]
    topics: Optional[List[str]]
    media_neutral_citation: Optional[str]
    citation_full: Optional[str]
    language: Optional[str]
    work_frbr_uri: Optional[str]
    expression_frbr_uri: Optional[str]
    source_url: str
    r2_pdf_key: str
    crawled_at: str


def get_r2_client(dry_run: bool = False):
    """Initialize and return boto3 client for Cloudflare R2."""
    if dry_run:
        return None  # No R2 client in dry-run mode
    
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


def abs_url(href: str) -> str:
    """Convert relative URL to absolute."""
    if href.startswith("http"):
        return href
    return urljoin(BASE, href)


def unique_pdf_filename_from_akn(akn_uri: str) -> str:
    """Create a unique and safe PDF filename from the AKN URI."""
    path = akn_uri
    if path.startswith("http"):
        try:
            path = re.sub(r"^https?://[^/]+", "", path)
        except Exception:
            pass
    if path.startswith("/"):
        path = path[1:]
    
    # Convert to safe filename
    name = path.replace("/", "_").replace("@", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    
    if not name.endswith(".pdf"):
        name += ".pdf"
    
    return name


def _slugify_ascii(value: str, max_len: int = 80) -> str:
    """Create a lowercase ASCII slug with underscores, limited length."""
    if not value:
        return "unknown"
    # Normalize whitespace
    value = re.sub(r"\s+", " ", value).strip()
    # Replace separators with underscores
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = value.strip("_").lower()
    if len(value) > max_len:
        value = value[:max_len].rstrip("_")
    return value or "unknown"


def _parse_language_from_expr(expr_uri: Optional[str]) -> Optional[str]:
    """Extract language code from expression FRBR URI and map to name."""
    if not expr_uri:
        return None
    # Example: /akn/zw/judgment/zwsc/2025/67/eng@2025-07-30
    m = re.search(r"/([a-z]{2,3})@", expr_uri)
    if not m:
        return None
    code = m.group(1).lower()
    return {
        "eng": "English",
        "en": "English",
        "sna": "Shona",
        "ndc": "Ndebele",
    }.get(code, code)


def _parse_case_number(title: str, akn_uri: str, year: Optional[int]) -> str:
    """Best-effort parse of a human-friendly case number like '67 of 2025'."""
    # Try from title: "(67 of 2025)"
    m = re.search(r"\((\d+\s+of\s+\d{4})\)", title)
    if m:
        return m.group(1)
    # Fallback from AKN URI segments /{year}/{number}/
    num_m = re.search(r"/(\d{4})/(\d+)/", akn_uri)
    if num_m:
        yr = int(num_m.group(1))
        num = num_m.group(2)
        return f"{num} of {yr}"
    if year:
        # Last resort: just year
        return f"unknown of {year}"
    return "unknown"


def build_unique_pdf_filename(
    akn_uri: str,
    expr_uri: Optional[str],
    case_name: str
) -> str:
    """Construct a robust unique filename using AKN parts + case slug + hash."""
    # Extract components
    court_code_match = re.search(r"/judgment/([a-z]+)/", akn_uri)
    court_code = court_code_match.group(1) if court_code_match else "unknown"
    year_match = re.search(r"/(\d{4})/", akn_uri)
    year = year_match.group(1) if year_match else "0000"
    number_match = re.search(r"/\d{4}/(\d+)(?:/|$)", akn_uri)
    number = number_match.group(1) if number_match else "0"
    date_match = re.search(r"@(\d{4}-\d{2}-\d{2})", expr_uri or "")
    date = date_match.group(1) if date_match else year
    lang_match = re.search(r"/([a-z]{2,3})@", expr_uri or "")
    lang = (lang_match.group(1) if lang_match else "eng").lower()
    case_slug = _slugify_ascii(case_name, max_len=80)
    # Add short hash for absolute uniqueness
    import hashlib
    base_for_hash = (expr_uri or akn_uri or case_name).encode("utf-8", errors="ignore")
    hash8 = hashlib.sha1(base_for_hash).hexdigest()[:8]
    filename = f"{court_code}_{year}_{number}_{lang}_{date}_{case_slug}_{hash8}.pdf"
    # Safety cleanup
    filename = re.sub(r"[^a-z0-9._-]", "_", filename)
    return filename


async def get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """HTTP GET with retries."""
    last_exc = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = await client.get(url, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            await asyncio.sleep(0.7 * attempt)
    raise RuntimeError(f"GET failed for {url}: {last_exc}")


async def upload_to_r2(
    r2_client,
    bucket: str,
    key: str,
    content: bytes | str,
    metadata: Optional[Dict[str, str]] = None
):
    """Upload content to R2 with optional metadata."""
    print(f"  -> Uploading to R2: s3://{bucket}/{key}")
    body = content.encode("utf-8") if isinstance(content, str) else content
    
    put_params = {
        "Bucket": bucket,
        "Key": key,
        "Body": body
    }
    
    if metadata:
        # Ensure all metadata values are strings and ASCII-safe
        sanitized_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, str):
                # Remove non-ASCII characters
                v = "".join(char for char in v if ord(char) < 128)
            sanitized_metadata[k] = str(v)
        put_params["Metadata"] = sanitized_metadata
        debug_court = sanitized_metadata.get('court_full') or sanitized_metadata.get('court')
        debug_judges = sanitized_metadata.get('judges')
        print(f"     with metadata: court={debug_court}, year={sanitized_metadata.get('year')}, judges={debug_judges}")
    
    try:
        r2_client.put_object(**put_params)
    except Exception as e:
        print(f"  !! R2 upload failed for key {key}: {e}")


def extract_head_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract metadata from page head."""
    meta: Dict[str, Any] = {}
    
    # Look for track-page-properties script tag
    script = soup.find("script", id="track-page-properties")
    if script and script.string:
        try:
            meta.update(json.loads(script.string))
        except Exception:
            pass
    
    # Extract title
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.replace("- ZimLII", "").strip()
        meta.setdefault("title", title)
    
    return meta


def extract_topics_from_page(soup: BeautifulSoup) -> Optional[List[str]]:
    """Best-effort extraction of topics/keywords from the judgment page.
    ZimLII often has no explicit tags, so we try:
      - meta[name="keywords"]
      - badges/labels within the page (e.g., spans with label classes)
      - common sections like 'Subject:' or 'Category:'
    """
    topics: List[str] = []
    # Meta keywords
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    if meta_kw and meta_kw.get("content"):
        topics.extend([t.strip() for t in meta_kw["content"].split(",") if t.strip()])

    # Look for badge-like elements
    for span in soup.find_all(["span", "a"], class_=re.compile(r"(badge|label)", re.I)):
        txt = span.get_text(" ", strip=True)
        if txt:
            topics.append(txt)

    # Heuristic: lines starting with 'Subject:' or 'Category:'
    text = soup.get_text("\n")
    for m in re.finditer(r"^(Subject|Category)\s*:\s*(.+)$", text, re.I | re.M):
        topics.extend([t.strip() for t in m.group(2).split(",") if t.strip()])

    # Deduplicate and cap
    topics = list(dict.fromkeys([t for t in topics if t]))
    return topics[:10] if topics else None


def parse_court_from_akn(akn_uri: str) -> Tuple[str, str]:
    """
    Parse court name and code from AKN URI.
    
    Args:
        akn_uri: e.g., "/akn/zw/judgment/zwbhc/2025/49/eng@2025-08-01"
        
    Returns:
        (court_code, court_name) e.g., ("zwbhc", "Bulawayo High Court")
    """
    # Extract court code from AKN URI
    match = re.search(r"/judgment/([a-z]+)/", akn_uri)
    if match:
        court_code = match.group(1)
        court_name = COURT_MAPPINGS.get(court_code, court_code.upper())
        return court_code, court_name
    
    return "unknown", "Unknown Court"


def parse_citation_from_title(title: str) -> Optional[str]:
    """
    Extract citation from judgment title.
    
    Examples:
        "Case Name [2025] ZWBHC 49 (1 August 2025)" -> "[2025] ZWBHC 49"
        "Smith v Jones (67 of 2025) [2025] ZWSC 67" -> "[2025] ZWSC 67"
    """
    # Pattern: [YYYY] COURT_CODE NUMBER
    match = re.search(r"\[(\d{4})\]\s+([A-Z]+)\s+(\d+)", title)
    if match:
        return f"[{match.group(1)}] {match.group(2)} {match.group(3)}"
    
    return None


def parse_case_name_from_title(title: str) -> str:
    """
    Extract clean case name from title.
    
    Examples:
        "Lepar v Matabeleland Hauliers & Anor [2025] ZWBHC 49 (1 August 2025)" 
        -> "Lepar v Matabeleland Hauliers & Anor"
    """
    # Remove citation and date parts
    name = re.sub(r"\s*\[?\d{4}\]?\s+[A-Z]+\s+\d+.*$", "", title)
    name = re.sub(r"\s*\(\d+\s+\w+\s+\d{4}\)\s*$", "", name)
    return name.strip()


def extract_parties(case_name: str) -> Dict[str, List[str]]:
    """
    Extract parties from case name.
    
    Examples:
        "Smith v Jones" -> {"plaintiff": ["Smith"], "defendant": ["Jones"]}
        "State v Accused" -> {"plaintiff": ["State"], "defendant": ["Accused"]}
        "Appellant v Respondent" -> {"appellant": ["Appellant"], "respondent": ["Respondent"]}
    """
    parties = {
        "plaintiff": [],
        "defendant": [],
        "appellant": [],
        "respondent": []
    }
    
    # Handle different case name patterns
    if " v " in case_name or " v. " in case_name:
        parts = re.split(r"\s+v\.?\s+", case_name, maxsplit=1)
        if len(parts) == 2:
            # Determine if criminal, civil, or appeal
            if parts[0].lower() in ["state", "the state", "s"]:
                parties["plaintiff"] = [parts[0].strip()]
                parties["defendant"] = [parts[1].strip()]
            elif "appellant" in parts[0].lower() or "respondent" in parts[1].lower():
                parties["appellant"] = [parts[0].strip()]
                parties["respondent"] = [parts[1].strip()]
            else:
                parties["plaintiff"] = [parts[0].strip()]
                parties["defendant"] = [parts[1].strip()]
    
    return parties


def _parse_judge_names(text: str) -> List[str]:
    """Parse a string into a list of judge names (with suffixes like J/JA/CJ)."""
    text = (text or "").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # Direct pattern: match names ending with judicial suffixes
    pattern = r"[A-Z][A-Za-z\-\.'\s]+\s(?:CJ|DCJ|JA|AJA|JP|J)\b"
    matches = re.findall(pattern, text)
    if not matches:
        # Fallback: split on separators and keep those with suffixes
        parts = re.split(r",|;|\band\b|&", text)
        matches = [p.strip() for p in parts if re.search(r"\b(CJ|DCJ|JA|AJA|JP|J)\b", p)]
    cleaned: List[str] = []
    for m in matches:
        name = re.sub(r"\s+", " ", m).strip(" ,;")
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


def extract_judges_from_page(soup: BeautifulSoup) -> Optional[List[str]]:
    """Extract judge names from judgment page robustly.
    Prefers structured "Document detail" (dt/dd or table rows) and falls back to
    constrained text heuristics.
    """
    # 1) Look for definition lists dt/dd
    for dt in soup.find_all("dt"):
        label = dt.get_text(" ", strip=True).strip(":").lower()
        if label in ("judge", "judges"):
            dd = dt.find_next_sibling("dd")
            if dd:
                names = _parse_judge_names(dd.get_text(" ", strip=True))
                if names:
                    return names
    
    # 2) Look for table rows with Judges label
    for tr in soup.find_all("tr"):
        # Try th then first td as label
        header = tr.find("th") or (tr.find_all("td")[0] if tr.find_all("td") else None)
        if not header:
            continue
        label = header.get_text(" ", strip=True).strip(":").lower()
        if label in ("judge", "judges"):
            tds = tr.find_all("td")
            value_cell = None
            if header.name == "th" and tds:
                value_cell = tds[0]
            elif len(tds) > 1:
                value_cell = tds[1]
            if value_cell:
                names = _parse_judge_names(value_cell.get_text(" ", strip=True))
                if names:
                    return names
    
    # 3) Meta tags that might include judges
    meta = soup.find("meta", attrs={"name": "judges"}) or soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content"):
        names = _parse_judge_names(meta["content"])
        if names:
            return names
    
    # 4) Fallback: a narrow "Before:" capture near the top of the page
    # Limit to the first ~1,500 characters to avoid grabbing the entire judgment
    text_head = soup.get_text(" ", strip=True)[:1500]
    m = re.search(r"Before\s*:\s*([^\n]{1,160})", text_head, re.IGNORECASE)
    if m:
        names = _parse_judge_names(m.group(1))
        if names:
            return names
    
    return None


async def fetch_and_process_judgment(
    http_client: httpx.AsyncClient,
    r2_client,
    bucket: str,
    href: str,
    delay: float,
) -> Optional[JudgmentCatalogRow]:
    """
    Fetch a judgment page, extract metadata, download PDF, and upload to R2.
    
    Args:
        http_client: HTTP client for requests
        r2_client: boto3 R2 client
        bucket: R2 bucket name
        href: Judgment page URL (relative or absolute)
        delay: Delay after processing
        
    Returns:
        JudgmentCatalogRow with metadata, or None if failed
    """
    url = abs_url(href)
    
    try:
        r = await get(http_client, url)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 1. Extract metadata from page
        head_meta = extract_head_metadata(soup)
        work_uri = head_meta.get("work_frbr_uri")
        expr_uri = head_meta.get("expression_frbr_uri")
        title = head_meta.get("title", "Untitled Judgment")
        
        # Parse AKN URI
        akn_uri = work_uri or expr_uri or href
        
        # Extract court information
        court_code, court_name = parse_court_from_akn(akn_uri)
        
        # Extract citation
        citation = parse_citation_from_title(title)
        if not citation:
            # Try to construct from AKN URI
            match = re.search(r"/([a-z]+)/(\d{4})/(\d+)/", akn_uri)
            if match:
                court_abbr = match.group(1).upper()
                year = match.group(2)
                number = match.group(3)
                citation = f"[{year}] {court_abbr} {number}"
        
        # Extract case name
        case_name = parse_case_name_from_title(title)
        
        # Extract year and case number
        year_match = re.search(r"/(\d{4})/", akn_uri)
        year = int(year_match.group(1)) if year_match else None
        
        number_match = re.search(r"/(\d+)/", akn_uri)
        case_number = _parse_case_number(title, akn_uri, year)
        
        # Extract judgment date from expression URI or title
        judgment_date = None
        date_match = re.search(r"@(\d{4}-\d{2}-\d{2})", expr_uri or "")
        if date_match:
            judgment_date = date_match.group(1)
        else:
            # Try to extract from title: "(1 August 2025)"
            date_match = re.search(r"\((\d+\s+\w+\s+\d{4})\)", title)
            if date_match:
                try:
                    parsed_date = datetime.strptime(date_match.group(1), "%d %B %Y")
                    judgment_date = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    pass
        
        if not judgment_date and year:
            judgment_date = f"{year}-01-01"  # Fallback
        
        # Extract parties
        parties = extract_parties(case_name)
        
        # Extract judges (if available)
        judges = extract_judges_from_page(soup)

        # Extract topics (if available)
        topics = extract_topics_from_page(soup)

        # Determine language
        language = _parse_language_from_expr(expr_uri) or "English"

        # Build full citation string like
        # "{case_name} ({case_number}) {citation} ({day Month YYYY})"
        human_date = None
        try:
            if judgment_date:
                dt = datetime.strptime(judgment_date, "%Y-%m-%d")
                human_date = dt.strftime("%d %B %Y")
        except Exception:
            human_date = None
        citation_full = None
        if case_name or citation or human_date:
            pieces = [
                piece for piece in [
                    case_name or "",
                    f"({case_number})" if case_number else "",
                    citation or "",
                    f"({human_date})" if human_date else ""
                ] if piece is not None
            ]
            citation_full = " ".join(p for p in pieces if p).strip()
        
        # 2. Find and download PDF
        pdf_anchor = None
        for a in soup.find_all("a", href=True):
            if "Download PDF" in a.get_text() or ".pdf" in a.get("href", "").lower():
                pdf_anchor = a
                break
        
        if not pdf_anchor:
            print(f"  -- No PDF download link found for {url}")
            return None
        
        pdf_url = abs_url(pdf_anchor["href"])
        pdf_filename = build_unique_pdf_filename(akn_uri, expr_uri, case_name)
        
        # Flat structure under judgements/; full court name is in metadata
        r2_key = f"corpus/sources/judgements/{pdf_filename}"
        
        # Create rich but bounded metadata for R2 (<=2KB total)
        media_neutral_citation = citation  # For ZimLII this equals citation
        judges_str = ", ".join(judges[:5]) if judges else ""
        def _trunc(s: Optional[str], n: int) -> str:
            return (s or "")[:n]
        pdf_metadata = {
            "doc_type": "judgment",
            "case_name": _trunc(case_name, 150),
            "citation": _trunc(citation or "", 120),
            "media_neutral_citation": _trunc(media_neutral_citation or "", 120),
            "court_full": _trunc(court_name, 120),
            "case_number": _trunc(case_number, 64),
            "year": _trunc(str(year or ""), 8),
            "judges": _trunc(judges_str, 200),
            "judgment_date": _trunc(judgment_date or "", 32),
            "language": _trunc(language, 32),
            "citation_full": _trunc(citation_full or "", 200),
            "topics": _trunc(", ".join(topics) if topics else "", 200),
        }
        
        print(f"  - Found PDF: {pdf_url}")
        print(f"    Citation: {citation}, Court: {court_name}, Date: {judgment_date}")
        
        pdf_response = await get(http_client, pdf_url)
        
        # Upload PDF to R2
        await upload_to_r2(r2_client, bucket, r2_key, pdf_response.content, pdf_metadata)
        await asyncio.sleep(delay)
        
        # 3. Return catalog row
        return JudgmentCatalogRow(
            akn_uri=akn_uri,
            case_name=case_name,
            citation=citation or "Unknown",
            court=court_name,
            court_code=court_code,
            judgment_date=judgment_date or "unknown",
            year=year or 0,
            case_number=case_number,
            parties=parties,
            judges=judges,
            topics=topics,
            media_neutral_citation=media_neutral_citation,
            citation_full=citation_full,
            language=language,
            work_frbr_uri=work_uri,
            expression_frbr_uri=expr_uri,
            source_url=url,
            r2_pdf_key=r2_key,
            crawled_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        print(f"  !! Failed to process {url}: {e}")
        return None


async def get_available_years(client: httpx.AsyncClient) -> List[int]:
    """
    Get list of available years from the judgments page.
    
    Returns:
        List of years (integers) sorted descending
    """
    try:
        resp = await get(client, INDEX_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        years = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text.isdigit() and len(text) == 4 and 1980 <= int(text) <= 2030:
                years.append(int(text))
        
        return sorted(set(years), reverse=True)
    except Exception as e:
        print(f"  !! Failed to fetch years: {e}")
        return []


async def crawl_year_month_page(
    client: httpx.AsyncClient,
    year: int,
    month: Optional[int] = None,
    page: int = 1
) -> List[str]:
    """
    Crawl a single page for a year or year-month combination.
    
    Args:
        client: HTTP client
        year: Year to crawl
        month: Optional month (1-12)
        page: Page number
        
    Returns:
        List of judgment URLs
    """
    # Build URL
    if month:
        if page == 1:
            url = f"{INDEX_URL}{year}/{month}/"
        else:
            url = f"{INDEX_URL}{year}/{month}/?page={page}"
    else:
        if page == 1:
            url = f"{INDEX_URL}{year}/"
        else:
            url = f"{INDEX_URL}{year}/?page={page}"
    
    try:
        resp = await get(client, url)
        if resp.status_code != 200:
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract judgment links
        judgment_urls = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/akn/zw/judgment/" in href and f"/{year}/" in href:
                judgment_urls.append(href)
        
        return list(set(judgment_urls))
    except Exception as e:
        return []


async def crawl_zim_judgements(
    bucket: str,
    max_pages: int,
    delay: float,
    concurrency: int,
    court_filter: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Main crawler function to fetch all ZimLII judgments.
    
    Args:
        bucket: R2 bucket name
        max_pages: Max pages per year/month to crawl (0 = all)
        delay: Delay between requests per worker
        concurrency: Max concurrent downloads
        court_filter: Optional court code filter (e.g., "zwsc", "zwbhc")
        start_year: Optional start year filter
        end_year: Optional end year filter
        limit: Optional limit on number of judgments to process
        
    Returns:
        Number of judgments successfully processed
    """
    r2_client = get_r2_client()
    headers = {"User-Agent": UA}
    sem = asyncio.Semaphore(concurrency)
    catalog_rows: List[JudgmentCatalogRow] = []
    
    print(f"Starting ZimLII judgments crawler...")
    print(f"Target: {INDEX_URL}")
    print(f"Concurrency: {concurrency}, Delay: {delay}s")
    if court_filter:
        print(f"Court filter: {court_filter}")
    if start_year or end_year:
        print(f"Year range: {start_year or 'any'} - {end_year or 'any'}")
    if limit:
        print(f"Limit: {limit} judgments")
    
    async with httpx.AsyncClient(headers=headers) as client:
        # Get available years
        print(f"\nFetching available years...")
        years = await get_available_years(client)
        
        # Apply year filters
        if start_year:
            years = [y for y in years if y >= start_year]
        if end_year:
            years = [y for y in years if y <= end_year]
        
        print(f"Crawling {len(years)} years: {years}")
        print(f"{'='*80}\n")
        
        # Collect all judgment URLs by year
        all_judgment_urls: set = set()
        
        for year in years:
            year_urls: set = set()
            
            if year in YEARS_NEEDING_MONTH_FILTER:
                # Use month-level filtering for years with many judgments
                print(f"Crawling {year} (month-by-month)...")
                
                for month in range(1, 13):
                    month_urls: set = set()
                    page = 1
                    consecutive_empty = 0
                    
                    while True:
                        if max_pages > 0 and page > max_pages:
                            break
                        
                        page_urls = await crawl_year_month_page(client, year, month, page)
                        
                        if not page_urls:
                            consecutive_empty += 1
                            if consecutive_empty >= 2:
                                break
                        else:
                            new_urls = set(page_urls) - month_urls
                            if not new_urls:
                                consecutive_empty += 1
                                if consecutive_empty >= 2:
                                    break
                            else:
                                month_urls.update(new_urls)
                                consecutive_empty = 0
                        
                        page += 1
                        await asyncio.sleep(0.05)
                    
                    if month_urls:
                        year_urls.update(month_urls)
                        print(f"  Month {month:2d}: {len(month_urls):3d} judgments, total: {len(year_urls)}")
            else:
                # Crawl by year only
                print(f"Crawling {year}...")
                page = 1
                consecutive_empty = 0
                
                while True:
                    if max_pages > 0 and page > max_pages:
                        break
                    
                    page_urls = await crawl_year_month_page(client, year, None, page)
                    
                    if not page_urls:
                        consecutive_empty += 1
                        if consecutive_empty >= 2:
                            break
                    else:
                        new_urls = set(page_urls) - year_urls
                        if not new_urls:
                            consecutive_empty += 1
                            if consecutive_empty >= 2:
                                break
                        else:
                            year_urls.update(new_urls)
                            consecutive_empty = 0
                    
                    page += 1
                    await asyncio.sleep(0.05)
            
            print(f"{year}: {len(year_urls)} judgments\n")
            all_judgment_urls.update(year_urls)
        
        print(f"{'='*80}")
        print(f"Total unique judgments found: {len(all_judgment_urls)}")
        print(f"{'='*80}\n")
        
        # Process each judgment
        processed_counter = 0
        unique_urls = list(all_judgment_urls)

        async def worker(judgment_url: str):
            async with sem:
                try:
                    print(f"Processing {judgment_url} ...")
                    row = await fetch_and_process_judgment(
                        client, r2_client, bucket, judgment_url, delay
                    )
                    
                    if not row:
                        return
                    
                    nonlocal processed_counter
                    if limit is not None and processed_counter >= limit:
                        return
                    
                    # Apply filters
                    if court_filter and row.court_code != court_filter:
                        return
                    
                    catalog_rows.append(row)
                    processed_counter += 1
                    
                except Exception as e:
                    print(f"⚠️  Failed {judgment_url}: {e}")
        
        # Process all judgments concurrently
        await asyncio.gather(*(worker(url) for url in unique_urls))
    
    # Upload metadata catalog
    if catalog_rows:
        print(f"\n{'='*80}")
        print(f"Uploading metadata catalog for {len(catalog_rows)} judgments")
        print(f"{'='*80}")
        
        # Sort by year and case number for easier browsing
        catalog_rows.sort(key=lambda r: (r.year, r.court_code, r.case_number), reverse=True)
        
        catalog_content = "\n".join(
            [json.dumps(asdict(row), ensure_ascii=False) for row in catalog_rows]
        )
        
        catalog_metadata = {
            "content_type": "application/jsonl",
            "description": "ZimLII judgments metadata catalog",
            "total_judgments": str(len(catalog_rows)),
            "crawled_at": datetime.utcnow().isoformat()
        }
        
        await upload_to_r2(
            r2_client,
            bucket,
            "corpus/metadata/judgements_catalog.jsonl",
            catalog_content,
            catalog_metadata
        )
        
        # Also create a summary by court
        court_stats = {}
        for row in catalog_rows:
            court_stats[row.court] = court_stats.get(row.court, 0) + 1
        
        print(f"\n{'='*80}")
        print("Judgments by Court:")
        for court, count in sorted(court_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {court:30s}: {count:5d}")
        print(f"{'='*80}\n")
    
    return len(catalog_rows)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    p = argparse.ArgumentParser(
        description="Crawl ZimLII judgments, uploading PDFs and metadata to R2."
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Max index pages to crawl (0=all, default=0 for complete crawl).",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay between requests per worker (default: 0.8s)."
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Max concurrent downloads (default: 8)."
    )
    p.add_argument(
        "--court",
        type=str,
        default=None,
        help="Filter by court code (e.g., zwsc, zwbhc, zwcc)."
    )
    p.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="Filter judgments from this year onwards."
    )
    p.add_argument(
        "--end-year",
        type=int,
        default=None,
        help="Filter judgments up to this year."
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N valid judgments (after filtering)."
    )
    return p.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    # Try to load .env.local file if exists
    try:
        from dotenv import load_dotenv
        load_dotenv(".env.local")
    except ImportError:
        pass  # dotenv not available, use existing env vars
    
    try:
        bucket_name = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    except KeyError:
        raise RuntimeError("CLOUDFLARE_R2_BUCKET_NAME environment variable not set.")
    
    print(f"\n{'='*80}")
    print("ZimLII Judgments Crawler")
    print(f"{'='*80}\n")
    
    count = asyncio.run(
        crawl_zim_judgements(
            bucket=bucket_name,
            max_pages=args.max_pages,
            delay=args.delay,
            concurrency=args.concurrency,
            court_filter=args.court,
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit,
        )
    )
    
    print(f"\n{'='*80}")
    print(f"✅ Successfully processed {count} judgments")
    print(f"   PDFs uploaded to: corpus/sources/judgements/")
    print(f"   Catalog saved to: corpus/metadata/judgements_catalog.jsonl")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()


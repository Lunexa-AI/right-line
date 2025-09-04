#!/usr/bin/env python3
"""
crawl_current_legislation.py - Crawl ZimLII "Current legislation" with rich metadata, uploading PDFs and a metadata catalog directly to Cloudflare R2.

Goals
- Enumerate the current-legislation index.
- For each document page, find the canonical PDF link.
- Upload the PDF to R2 under `corpus/sources/legislation/`.
- Extract rich metadata (title, year, chapter, etc.).
- Persist a consolidated metadata catalog to R2 as `corpus/metadata/legislation_catalog.jsonl`.

Usage
  # Ensure R2 env vars are set before running: CLOUDFLARE_R2_S3_ENDPOINT, CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME
  python scripts/crawl_current_legislation.py --max-pages 0 --delay 0.8 --concurrency 8
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import boto3
import httpx
from botocore.client import Config
from bs4 import BeautifulSoup

BASE = "https://zimlii.org"
INDEX_URL = f"{BASE}/legislation/"
UA = "RightLineCrawler/1.0 (+https://rightline.zw)"
DEFAULT_TIMEOUT = 30.0
RETRIES = 3


@dataclass
class CatalogRow:
    akn_uri: str
    nature: str
    title: str
    chapter: Optional[str]
    work_frbr_uri: Optional[str]
    expression_frbr_uri: Optional[str]
    effective_date: Optional[str]
    year: Optional[int]
    source_url: str
    r2_pdf_key: str


def get_r2_client():
    """Initializes and returns a boto3 client for Cloudflare R2."""
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
    if href.startswith("http"):
        return href
    return f"{BASE}{href}"


def unique_pdf_filename_from_href(href: str) -> str:
    """Create a unique and safe PDF filename from the AKN path."""
    path = href
    if path.startswith("http"):
        try:
            path = re.sub(r"^https?://[^/]+", "", path)
        except Exception:
            pass
    if path.startswith("/"):
        path = path[1:]
    name = path.replace("/", "_").replace("@", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.endswith(".pdf"):
        name += ".pdf"
    return name


async def get(client: httpx.AsyncClient, url: str) -> httpx.Response:
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


async def upload_to_r2(r2_client, bucket: str, key: str, content: bytes | str, metadata: Optional[Dict[str, str]] = None):
    """Uploads binary or text content to an R2 bucket with optional metadata."""
    print(f"  -> Uploading to R2: s3://{bucket}/{key}")
    body = content.encode("utf-8") if isinstance(content, str) else content
    
    # Prepare the put_object parameters
    put_params = {
        "Bucket": bucket,
        "Key": key,
        "Body": body
    }
    
    # Add metadata if provided
    if metadata:
        put_params["Metadata"] = metadata
        print(f"     with metadata: {metadata}")
    
    try:
        r2_client.put_object(**put_params)
    except Exception as e:
        print(f"  !! R2 upload failed for key {key}: {e}")


def parse_effective_date(expression_frbr_uri: Optional[str]) -> Optional[str]:
    if not expression_frbr_uri:
        return None
    m = re.search(r"@(\d{4}-\d{2}-\d{2})", expression_frbr_uri)
    return m.group(1) if m else None


def parse_year_from_frbr(
    number: Optional[str], expression_frbr_uri: Optional[str]
) -> Optional[int]:
    if expression_frbr_uri:
        m = re.search(r"/(\d{4})/", expression_frbr_uri)
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


def extract_head_metadata(soup: BeautifulSoup) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    script = soup.find("script", id="track-page-properties")
    if script and script.string:
        try:
            meta.update(json.loads(script.string))
        except Exception:
            pass
    t = soup.find("title")
    if t and t.string:
        title = t.string.replace("- ZimLII", "").strip()
        meta.setdefault("title", title)
    return meta


def infer_nature_from_path(path: str) -> str:
    if "/act/si/" in path:
        return "Statutory Instrument"
    if "/act/ord/" in path:
        return "Ordinance"
    return "Act"


def get_document_type_folder(nature: str) -> str:
    """Convert document nature to R2 folder name."""
    if nature == "Statutory Instrument":
        return "statutory_instruments"
    elif nature == "Ordinance":
        return "ordinances"
    else:  # Act
        return "acts"


def sanitize_metadata_for_r2(metadata: Dict[str, str]) -> Dict[str, str]:
    """Sanitize metadata values to contain only ASCII characters for R2 compatibility."""
    sanitized = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            # Replace common non-ASCII characters with ASCII equivalents
            sanitized_value = (
                value.replace("'", "'")
                .replace(""", '"')
                .replace(""", '"')
                .replace("–", "-")
                .replace("—", "-")
            )
            # Keep only ASCII characters
            sanitized_value = "".join(char for char in sanitized_value if ord(char) < 128)
            sanitized[key] = sanitized_value
        else:
            sanitized[key] = value
    return sanitized


def extract_chapter_from_row(cell_text: str) -> Optional[str]:
    m = re.search(r"Chapter\s+([0-9]+:[0-9]+)", cell_text, flags=re.I)
    return m.group(1) if m else None


async def fetch_and_process_doc(
    http_client: httpx.AsyncClient,
    r2_client,
    bucket: str,
    href: str,
    delay: float,
) -> Optional[CatalogRow]:
    """
    Fetches a document page, extracts metadata, finds the PDF,
    uploads the PDF to R2, and returns the metadata row.
    """
    url = abs_url(href)
    r = await get(http_client, url)
    soup = BeautifulSoup(r.text, "html.parser")

    # 1. Extract metadata from the HTML page
    head_meta = extract_head_metadata(soup)
    work = head_meta.get("work_frbr_uri")
    expr = head_meta.get("expression_frbr_uri")
    number = head_meta.get("frbr_uri_number")

    akn_uri = work or expr or href
    title = head_meta.get("title") or "Untitled"
    effective_date = parse_effective_date(expr)
    year = parse_year_from_frbr(number, expr)
    nature = infer_nature_from_path(akn_uri)

    try:
        chapter = extract_chapter_from_row(soup.get_text(" "))
    except Exception:
        chapter = None

    # 2. Find and upload the PDF
    # Look for links containing "Download PDF" text
    pdf_anchor = None
    for a in soup.find_all("a", href=True):
        if "Download PDF" in a.get_text():
            pdf_anchor = a
            break
    
    if not pdf_anchor:
        print(f"  -- No PDF download link found for {url}")
        return None

    pdf_url = abs_url(pdf_anchor["href"])
    pdf_filename = unique_pdf_filename_from_href(href)
    
    # Organize by document type folder
    doc_type_folder = get_document_type_folder(nature)
    r2_key = f"corpus/sources/legislation/{doc_type_folder}/{pdf_filename}"
    
    # Create rich metadata for R2
    pdf_metadata = {
        "document_type": doc_type_folder,
        "nature": nature,
        "title": title,
        "akn_uri": akn_uri,
        "source_url": url,
    }
    
    # Add optional metadata fields if available
    if year:
        pdf_metadata["year"] = str(year)
    if chapter:
        pdf_metadata["chapter"] = chapter
    if effective_date:
        pdf_metadata["effective_date"] = effective_date
    if work:
        pdf_metadata["work_frbr_uri"] = work
    if expr:
        pdf_metadata["expression_frbr_uri"] = expr

    print(f"  - Found PDF: {pdf_url}")
    pdf_response = await get(http_client, pdf_url)
    
    # Sanitize metadata for R2 ASCII compatibility
    sanitized_metadata = sanitize_metadata_for_r2(pdf_metadata)
    await upload_to_r2(r2_client, bucket, r2_key, pdf_response.content, sanitized_metadata)
    await asyncio.sleep(delay)

    # 3. Return CatalogRow
    return CatalogRow(
        akn_uri=akn_uri,
        nature=nature,
        title=title,
        chapter=chapter,
        work_frbr_uri=work,
        expression_frbr_uri=expr,
        effective_date=effective_date,
        year=year,
        source_url=url,
        r2_pdf_key=r2_key,
    )


async def crawl_index_page(
    client: httpx.AsyncClient, url: str
) -> List[Tuple[str, Optional[str]]]:
    try:
        resp = await get(client, url)
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")

    results: List[Tuple[str, Optional[str]]] = []
    
    # Look for the specific table structure used by ZimLII
    table_div = soup.find("div", class_="table-responsive")
    if not table_div:
        return results
        
    table = table_div.find("table", class_="doc-table")
    if not table:
        return results
        
    # Look at ALL rows in the table, not just tbody
    # The documents are stored directly in table rows
    all_rows = table.find_all("tr")
    for tr in all_rows:
        # Look for ANY cell that might contain a document link
        found_link = False
        chapter_text = None
        
        for cell in tr.find_all(["td", "th"]):
            a = cell.find("a", href=True)
            if a and a.get("href", "").startswith("/akn/zw/act/"):
                href = a["href"]
                
                # Try to find chapter information in other cells in this row
                other_cells = tr.find_all("td")
                for other_cell in other_cells:
                    if other_cell != cell:  # Skip the cell with the link
                        cell_text = other_cell.get_text(" ").strip()
                        if cell_text:
                            chapter_text = extract_chapter_from_row(cell_text)
                            if chapter_text:
                                break
                
                results.append((href, chapter_text))
                found_link = True
                break
        
        if found_link:
            continue
    return results


async def crawl_current_legislation(
    bucket: str,
    max_pages: int,
    delay: float,
    concurrency: int,
    years: Optional[List[int]] = None,
    natures: Optional[List[str]] = None,
) -> int:
    r2_client = get_r2_client()
    headers = {"User-Agent": UA}
    sem = asyncio.Semaphore(concurrency)
    catalog_rows: List[CatalogRow] = []

    async with httpx.AsyncClient(headers=headers) as client:

        async def collect_hrefs_for_nature(
            nature_param: Optional[str],
        ) -> List[Tuple[str, Optional[str]]]:
            page = 1
            hrefs: List[Tuple[str, Optional[str]]] = []
            while True:
                if max_pages > 0 and page > max_pages:
                    break
                if nature_param:
                    base = f"{INDEX_URL}?natures={nature_param}&sort=title"
                    index_url = base if page == 1 else f"{base}&page={page}"
                else:
                    index_url = INDEX_URL if page == 1 else f"{INDEX_URL}?page={page}"
                rows = await crawl_index_page(client, index_url)
                if not rows:
                    break

                filtered_rows = []
                for href, chap in rows:
                    # Include all document types for now (Acts, SIs, Ordinances)
                    filtered_rows.append((href, chap))
                hrefs.extend(filtered_rows)
                page += 1
            return hrefs

        all_hrefs: List[Tuple[str, Optional[str]]] = await collect_hrefs_for_nature(None)
        seen = {href for href, _ in all_hrefs}
        unique_rows = list(dict.fromkeys(all_hrefs))
        print(f"Found {len(unique_rows)} unique document pages to crawl.")

        async def worker(href: str, chap_hint: Optional[str]):
            async with sem:
                try:
                    print(f"Processing {href} ...")
                    row = await fetch_and_process_doc(client, r2_client, bucket, href, delay)
                    if not row:
                        return
                    if chap_hint and not row.chapter:
                        row.chapter = chap_hint
                    if years and row.year and row.year not in years:
                        return
                    catalog_rows.append(row)
                except Exception as e:
                    print(f"⚠️  Failed {href}: {e}")

        await asyncio.gather(*(worker(h, c) for h, c in unique_rows))

    if catalog_rows:
        print(f"\n--- Uploading metadata catalog for {len(catalog_rows)} documents ---")
        catalog_content = "\n".join(
            [json.dumps(asdict(row), ensure_ascii=False) for row in catalog_rows]
        )
        catalog_metadata = sanitize_metadata_for_r2({
            "content_type": "application/jsonl", 
            "description": "Legislation metadata catalog"
        })
        await upload_to_r2(
            r2_client,
            bucket,
            "corpus/metadata/legislation_catalog.jsonl",
            catalog_content,
            catalog_metadata
        )

    return len(catalog_rows)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Crawl ZimLII current legislation, uploading PDFs and metadata to R2."
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=9,
        help="Max index pages to crawl (0=all, default=9 for full current legislation).",
    )
    p.add_argument(
        "--delay", type=float, default=0.8, help="Delay between requests per worker."
    )
    p.add_argument("--concurrency", type=int, default=8, help="Max concurrent downloads.")
    p.add_argument(
        "--years",
        type=str,
        default="",
        help="Comma-separated list of years to filter by.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    try:
        bucket_name = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    except KeyError:
        raise RuntimeError("CLOUDFLARE_R2_BUCKET_NAME environment variable not set.")

    years = (
        [int(y) for y in args.years.split(",") if y.strip().isdigit()]
        if args.years
        else None
    )

    count = asyncio.run(
        crawl_current_legislation(
            bucket=bucket_name,
            max_pages=args.max_pages,
            delay=args.delay,
            concurrency=args.concurrency,
            years=years,
        )
    )
    print(
        f"\nSuccessfully processed and uploaded {count} legislation documents and their metadata catalog to R2."
    )


if __name__ == "__main__":
    main()




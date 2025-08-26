#!/usr/bin/env python3
"""
crawl_current_legislation.py - Crawl ZimLII "Current legislation" with rich metadata

Goals
- Enumerate the current-legislation index (405+ docs) with optional filters
- Extract per-item metadata directly from the index and the document page:
  - nature (Act | Ordinance | Statutory Instrument)
  - title, chapter (if shown), work/expression FRBR URIs
  - effective date (from expression URI @YYYY-MM-DD)
  - year (from FRBR number or expression date)
  - akn_uri (canonical /akn path)
  - version status (implicitly current)
- Persist raw HTML in data/raw/legislation/ and a catalog JSONL in data/processed/leg_catalog.jsonl

Usage
  python scripts/crawl_current_legislation.py --out data/raw --max-pages 0 --delay 0.8 --concurrency 8 --catalog data/processed/leg_catalog.jsonl

Notes
- Polite crawling: configurable delay and limited concurrency.
- Only targets /legislation/ index tabs and underlying /akn/zw/act/... pages.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
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


def abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return f"{BASE}{href}"


def unique_filename_from_href(href: str) -> str:
    """Create a collision-resistant filename from the entire AKN path.
    Example: /akn/zw/act/1971/6/eng@2024-12-31 -> akn_zw_act_1971_6_eng_2024-12-31.html
    """
    path = href
    if path.startswith("http"):
        # Convert full URL to path
        try:
            path = re.sub(r"^https?://[^/]+", "", path)
        except Exception:
            pass
    if path.startswith("/"):
        path = path[1:]
    # Replace separators and reserved characters
    name = path.replace("/", "_").replace("@", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.endswith(".html"):
        name += ".html"
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


def slugify_title(title: str, max_len: int = 80) -> str:
    """Convert title to a filesystem-friendly slug.
    - lowercase, replace spaces with underscores
    - remove characters outside [A-Za-z0-9._-]
    - collapse multiple underscores
    - trim length
    """
    s = (title or "untitled").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9._-]", "_", s)
    s = re.sub(r"_+", "_", s)
    if len(s) > max_len:
        s = s[:max_len].rstrip("._-")
    return s or "untitled"


def parse_effective_date(expression_frbr_uri: Optional[str]) -> Optional[str]:
    if not expression_frbr_uri:
        return None
    m = re.search(r"@(\d{4}-\d{2}-\d{2})", expression_frbr_uri)
    return m.group(1) if m else None


def parse_year_from_frbr(number: Optional[str], expression_frbr_uri: Optional[str]) -> Optional[int]:
    # number is the frbr_uri_number when available; often a year appears in expression
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
    # Laws.Africa embed typically placed in a script#track-page-properties
    script = soup.find("script", id="track-page-properties")
    if script and script.string:
        try:
            meta.update(json.loads(script.string))
        except Exception:
            pass
    # Fallback title
    t = soup.find("title")
    if t and t.string:
        title = t.string.replace("- ZimLII", "").strip()
        meta.setdefault("title", title)
    return meta


def infer_nature_from_path(path: str) -> str:
    # /akn/zw/act/..., /akn/zw/act/si/..., /akn/zw/act/ord/...
    if "/act/si/" in path:
        return "Statutory Instrument"
    if "/act/ord/" in path:
        return "Ordinance"
    return "Act"


def extract_chapter_from_row(cell_text: str) -> Optional[str]:
    # The index often shows "Chapter 7:01"
    m = re.search(r"Chapter\s+([0-9]+:[0-9]+)", cell_text, flags=re.I)
    return m.group(1) if m else None


async def fetch_and_save_doc(client: httpx.AsyncClient, href: str, out_dir: Path, delay: float) -> Tuple[CatalogRow, str]:
    url = abs_url(href)

    # Download page HTML
    r = await get(client, url)

    # Parse metadata
    soup = BeautifulSoup(r.text, "lxml")
    head_meta = extract_head_metadata(soup)
    work = head_meta.get("work_frbr_uri")
    expr = head_meta.get("expression_frbr_uri")
    number = head_meta.get("frbr_uri_number")
    language = head_meta.get("frbr_uri_language")

    akn_uri = work or expr or href
    title = head_meta.get("title") or "Untitled"
    effective_date = parse_effective_date(expr)
    year = parse_year_from_frbr(number, expr)
    nature = infer_nature_from_path(akn_uri)

    # Try to find chapter from page breadcrumbs/table if available
    chapter = None
    try:
        text = soup.get_text(" ")
        chapter = extract_chapter_from_row(text)
    except Exception:
        chapter = None

    # Build descriptive filename including title and year
    base_part = unique_filename_from_href(href).rsplit(".", 1)[0]
    title_slug = slugify_title(title)
    year_str = str(year) if year else "unknown"
    nature_slug = nature.replace(" ", "-").lower()
    descriptive = f"akn_zw_current-legislation_{title_slug}_{year_str}_{nature_slug}_{base_part}.html"
    html_path = out_dir / descriptive
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(r.text)

    await asyncio.sleep(delay)
    return (
        CatalogRow(
            akn_uri=akn_uri,
            nature=nature,
            title=title,
            chapter=chapter,
            work_frbr_uri=work,
            expression_frbr_uri=expr,
            effective_date=effective_date,
            year=year,
            source_url=url,
        ),
        r.text,
    )


async def crawl_index_page(client: httpx.AsyncClient, url: str) -> List[Tuple[str, Optional[str]]]:
    # Return list of (href, chapter_text_if_available) strictly by table rows.
    # If page is out of range (404), return [].
    try:
        resp = await get(client, url)
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "lxml")

    results: List[Tuple[str, Optional[str]]] = []
    table = soup.find("table")
    if not table:
        return results
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            # Some tables may not use td within tbody
            tds = tr.find_all("td")
        if not tds:
            continue
        title_cell = tds[0]
        # Choose ONLY the first anchor in the title cell
        a = title_cell.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if not href.startswith("/akn/zw/act/"):
            continue
        # Chapter cell is typically the second column
        chapter_text = None
        if len(tds) > 1:
            chapter_text = extract_chapter_from_row(tds[1].get_text(" "))
        results.append((href, chapter_text))
    return results


async def crawl_current_legislation(
    out_root: Path,
    max_pages: int,
    delay: float,
    concurrency: int,
    catalog_path: Path,
    years: Optional[List[int]] = None,
    natures: Optional[List[str]] = None,
) -> int:
    headers = {"User-Agent": UA}
    out_dir = out_root / "legislation"
    out_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(headers=headers) as client:
        # Helper to iterate pages for a given nature filter
        async def collect_hrefs_for_nature(nature_param: Optional[str]) -> List[Tuple[str, Optional[str]]]:
            page = 1
            hrefs: List[Tuple[str, Optional[str]]] = []
            while True:
                if max_pages > 0 and page > max_pages:
                    break
                if nature_param:
                    base = f"{INDEX_URL}?natures={nature_param}&sort=title"
                    index_url = base if page == 1 else f"{base}&page={page-1}"
                else:
                    index_url = INDEX_URL if page == 1 else f"{INDEX_URL}?page={page-1}"
                rows = await crawl_index_page(client, index_url)
                if not rows:
                    break
                # Pre-filter hrefs by requested nature to avoid downloading SIs
                filtered: List[Tuple[str, Optional[str]]] = []
                for href, chap in rows:
                    if nature_param == "act":
                        if "/act/si/" in href or "/act/ord/" in href:
                            continue
                    elif nature_param == "si":
                        if "/act/si/" not in href:
                            continue
                    elif nature_param == "ord":
                        if "/act/ord/" not in href:
                            continue
                    else:
                        # Default (no nature specified): include acts and ordinances only
                        if "/act/si/" in href:
                            continue
                    filtered.append((href, chap))
                hrefs.extend(filtered)
                page += 1
            return hrefs

        # Build list of index pages to walk: run per nature if provided, else default (all)
        all_hrefs: List[Tuple[str, Optional[str]]] = []
        if natures:
            for nat in natures:
                nat_key = nat.strip().lower()
                if nat_key in {"act", "si", "ord", "ordinance"}:
                    nat_param = "ord" if nat_key in {"ord", "ordinance"} else nat_key
                else:
                    nat_param = nat_key
                hrefs = await collect_hrefs_for_nature(nat_param)
                all_hrefs.extend(hrefs)
        else:
            all_hrefs.extend(await collect_hrefs_for_nature(None))

        # Deduplicate
        seen = set()
        unique_rows: List[Tuple[str, Optional[str]]] = []
        for href, chap in all_hrefs:
            if href not in seen:
                seen.add(href)
                unique_rows.append((href, chap))

        # Prepare catalog writer
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_fp = catalog_path.open("w", encoding="utf-8")

        processed = 0

        async def worker(href: str, chap_hint: Optional[str]):
            nonlocal processed
            async with sem:
                try:
                    print(f"Downloading {href} ...")
                    row, _ = await fetch_and_save_doc(client, href, out_dir, delay)
                    # If chapter was detected in index row and missing from page, prefer index hint
                    if chap_hint and not row.chapter:
                        row.chapter = chap_hint
                    # Year/nature filtering if provided
                    if years and row.year and row.year not in years:
                        return
                    if natures:
                        # Normalize aliases (ord -> ordinance)
                        aliases = {"ord": "ordinance", "ordinance": "ordinance", "act": "act"}
                        allowed = {aliases.get(n.lower(), n.lower()) for n in natures}
                        nature_val = row.nature.lower()
                        if nature_val not in allowed:
                            return
                    catalog_fp.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
                    processed += 1
                except Exception as e:
                    # Keep going on individual failures
                    print(f"⚠️  Failed {href}: {e}")

        await asyncio.gather(*(worker(h, c) for h, c in unique_rows))
        catalog_fp.close()
        return processed


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Crawl ZimLII current legislation with metadata")
    p.add_argument("--out", default="data/raw", type=str, help="Output root directory for raw HTML")
    p.add_argument("--catalog", default="data/processed/leg_catalog.jsonl", type=str, help="Output catalog JSONL path")
    p.add_argument("--max-pages", type=int, default=0, help="Max index pages to crawl (0=all)")
    p.add_argument("--delay", type=float, default=0.8, help="Delay between requests per worker")
    p.add_argument("--concurrency", type=int, default=8, help="Max concurrent downloads")
    p.add_argument("--years", type=str, default="", help="Comma-separated list of years to include")
    p.add_argument("--natures", type=str, default="", help="Comma-separated natures: act, ordinance, statutory instrument")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    years = [int(y) for y in args.years.split(",") if y.strip().isdigit()] if args.years else None
    natures = [n.strip() for n in args.natures.split(",") if n.strip()] if args.natures else None

    count = asyncio.run(
        crawl_current_legislation(
            out_root=Path(args.out),
            max_pages=args.max_pages,
            delay=args.delay,
            concurrency=args.concurrency,
            catalog_path=Path(args.catalog),
            years=years,
            natures=natures,
        )
    )
    print(f"Downloaded and cataloged {count} current-legislation documents")


if __name__ == "__main__":
    main()



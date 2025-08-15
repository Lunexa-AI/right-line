#!/usr/bin/env python3
"""
ZimLII crawler (polite) to auto-discover and download:
- Labour Act (specific URL, full document page + linked PDF if present)
- Legislation index (optional)
- Statutory Instruments (optional)
- Judgments via labour search (full pagination until exhausted when --unlimited)

Features:
- Async httpx client with timeouts and retries
- Parse list pages with BeautifulSoup(lxml)
- Auto-follow pagination on index/search pages (limited by --max-pages, or unlimited until no results)
- Download destination grouped by type in data/raw/<type>/
- Respects a fixed delay between requests; custom User-Agent
- Does NOT ignore robots nor terms of use (run responsibly)

Usage examples:
  # Fetch Labour Act + labour judgments (unlimited pages)
  python3 scripts/crawl_zimlii.py --out data/raw --delay 1.0 \
    --legislation --judgments --unlimited \
    --labour-act-url https://zimlii.org/akn/zw/act/1985/16/eng@2016-12-31 \
    --judgment-query labour

Links referenced:
- Legislation index: https://zimlii.org/legislation/
- SIs: https://zimlii.org/legislation/?natures=si&q=&sort=title
- Judgments search (labour): https://zimlii.org/search/?q=labour&nature=Judgment
"""
from __future__ import annotations

import argparse
import asyncio
import re
from urllib.parse import urlencode
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 30.0
RETRIES = 3
UA = "RightLineCrawler/1.0 (+https://rightline.zw)"
BASE = "https://zimlii.org"


async def get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    for attempt in range(1, RETRIES + 1):
        try:
            r = await client.get(url, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            r.raise_for_status()
            return r
        except Exception:
            await asyncio.sleep(0.8 * attempt)
    raise RuntimeError(f"GET failed for {url}")


def abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return f"{BASE}{href}"


def filename_from_url(url: str, fallback_html: bool = True) -> str:
    name = url.split("/")[-1] or ("index.html" if fallback_html else "index")
    if fallback_html and not any(name.endswith(ext) for ext in (".pdf", ".html")):
        name += ".html"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return safe


async def save_html(client: httpx.AsyncClient, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = await get(client, url)
    dest.write_text(r.text)


async def save_binary(client: httpx.AsyncClient, url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = await get(client, url)
    dest.write_bytes(r.content)


async def fetch_page_and_linked_pdfs(client: httpx.AsyncClient, page_url: str, out_dir: Path, delay: float) -> int:
    """Download the HTML page and any directly linked PDFs on it."""
    # Save page
    html_name = filename_from_url(page_url, fallback_html=True)
    html_dest = out_dir / html_name
    await save_html(client, page_url, html_dest)
    await asyncio.sleep(delay)

    # Parse and find .pdf links
    r = await get(client, page_url)
    soup = BeautifulSoup(r.text, "lxml")
    pdfs = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            pdf_url = abs_url(href)
            pdf_dest = out_dir / filename_from_url(pdf_url, fallback_html=False)
            await save_binary(client, pdf_url, pdf_dest)
            pdfs += 1
            await asyncio.sleep(delay)
    return 1 + pdfs


async def crawl_legislation_specific_act(client: httpx.AsyncClient, out_root: Path, labour_act_url: str, delay: float) -> int:
    out_dir = out_root / "legislation"
    return await fetch_page_and_linked_pdfs(client, labour_act_url, out_dir, delay)


async def crawl_legislation_index(client: httpx.AsyncClient, out_root: Path, max_pages: int, delay: float) -> int:
    url = f"{BASE}/legislation/"
    count = 0
    page = 1
    while True:
        if max_pages > 0 and page > max_pages:
            break
        page_url = url if page == 1 else f"{url}?page={page-1}"
        resp = await get(client, page_url)
        soup = BeautifulSoup(resp.text, "lxml")
        hrefs = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("/akn/zw/act/")]
        if not hrefs:
            break
        for href in hrefs:
            doc_url = abs_url(href)
            dest = out_root / "legislation" / filename_from_url(doc_url)
            await save_html(client, doc_url, dest)
            count += 1
            await asyncio.sleep(delay)
        page += 1
    return count


async def crawl_sis_index(client: httpx.AsyncClient, out_root: Path, max_pages: int, delay: float) -> int:
    url = f"{BASE}/legislation/?natures=si&q=&sort=title"
    count = 0
    page = 1
    while True:
        if max_pages > 0 and page > max_pages:
            break
        page_url = url if page == 1 else f"{url}&page={page-1}"
        resp = await get(client, page_url)
        soup = BeautifulSoup(resp.text, "lxml")
        hrefs = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("/akn/zw/act/si/")]
        if not hrefs:
            break
        for href in hrefs:
            doc_url = abs_url(href)
            dest = out_root / "sis" / filename_from_url(doc_url)
            await save_html(client, doc_url, dest)
            count += 1
            await asyncio.sleep(delay)
        page += 1
    return count


async def crawl_judgments_search(client: httpx.AsyncClient, out_root: Path, query: str, max_pages: int, delay: float) -> int:
    base_url = f"{BASE}/judgments/"
    count = 0
    page = 1
    seen = set()
    while True:
        if max_pages > 0 and page > max_pages:
            break
        # /judgments/ supports ?q= and ?page=
        sep = "?" if page == 1 else "&"
        page_param = "" if page == 1 else f"&page={page-1}"
        page_url = f"{base_url}?q={query}{page_param}"
        resp = await get(client, page_url)
        soup = BeautifulSoup(resp.text, "lxml")
        anchors = [a for a in soup.find_all("a", href=True) if "/akn/zw/judgment/" in a["href"]]
        hrefs = [a["href"] for a in anchors]
        if not hrefs:
            break
        for href in hrefs:
            if href in seen:
                continue
            seen.add(href)
            doc_url = abs_url(href)
            out_dir = out_root / "judgments"
            await fetch_page_and_linked_pdfs(client, doc_url, out_dir, delay)
            count += 1
        page += 1
    return count


async def run(args: argparse.Namespace) -> None:
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": UA}
    async with httpx.AsyncClient(headers=headers) as client:
        total = 0
        max_pages = 0 if args.unlimited else args.max_pages
        # Always fetch the Labour Act specific URL when legislation is requested
        if args.legislation:
            total += await crawl_legislation_specific_act(client, out_root, args.labour_act_url, args.delay)
            # Optionally also index the full legislation list (can be disabled if not needed now)
            if args.legislation_index:
                total += await crawl_legislation_index(client, out_root, max_pages, args.delay)
        if args.sis:
            total += await crawl_sis_index(client, out_root, max_pages, args.delay)
        if args.judgments:
            total += await crawl_judgments_search(client, out_root, args.judgment_query, max_pages, args.delay)
        print(f"Downloaded {total} items")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/raw")
    p.add_argument("--max-pages", type=int, default=1)
    p.add_argument("--unlimited", action="store_true", help="Ignore max-pages; crawl until no results")
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--legislation", action="store_true")
    p.add_argument("--legislation-index", action="store_true", help="Also crawl the legislation index list")
    p.add_argument("--labour-act-url", default="https://zimlii.org/akn/zw/act/1985/16/eng@2016-12-31")
    p.add_argument("--sis", action="store_true")
    p.add_argument("--judgments", action="store_true")
    p.add_argument("--judgment-query", default="labour")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))

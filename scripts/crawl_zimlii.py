#!/usr/bin/env python3
"""
ZimLII crawler (polite) to auto-discover and download PDFs directly to Cloudflare R2.

- Fetches Labour Act and Judgments.
- Extracts PDF links from pages.
- Uploads PDF content directly to an R2 bucket.

Features:
- Async httpx client with timeouts and retries.
- Parse pages with BeautifulSoup(lxml).
- Auto-follow pagination on search pages.
- Respects a fixed delay between requests; custom User-Agent.
- Configures R2 client from environment variables.

Usage examples:
  # Fetch Labour Act PDF + labour judgments (unlimited pages), uploading to R2.
  # Ensure R2 env vars are set: CLOUDFLARE_R2_S3_ENDPOINT, CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME
  python3 scripts/crawl_zimlii.py --delay 1.0 \
    --legislation --judgments --unlimited \
    --labour-act-url https://zimlii.org/akn/zw/act/1985/16/eng@2016-12-31 \
    --judgment-query labour
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
from pathlib import PurePath
from urllib.parse import urlparse

import boto3
import httpx
from botocore.client import Config
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 30.0
RETRIES = 3
UA = "RightLineCrawler/1.0 (+https://rightline.zw)"
BASE = "https://zimlii.org"


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


def filename_from_url(url: str) -> str:
    """Creates a safe filename from a URL, ensuring it ends with .pdf."""
    path = urlparse(url).path
    name = PurePath(path).name
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return safe_name


async def upload_to_r2(r2_client, bucket: str, key: str, content: bytes) -> None:
    """Uploads binary content to an R2 bucket."""
    print(f"  -> Uploading to R2: s3://{bucket}/{key}")
    try:
        r2_client.put_object(Bucket=bucket, Key=key, Body=content)
    except Exception as e:
        print(f"  !! R2 upload failed for key {key}: {e}")


async def fetch_and_upload_pdfs(
    http_client: httpx.AsyncClient,
    r2_client,
    page_url: str,
    r2_bucket: str,
    r2_prefix: str,
    delay: float,
) -> int:
    """Parses a page, finds all PDF links, and uploads them to R2."""
    print(f"- Scanning page for PDFs: {page_url}")
    r = await get(http_client, page_url)
    soup = BeautifulSoup(r.text, "lxml")
    pdfs_found = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            pdf_url = abs_url(href)
            pdf_filename = filename_from_url(pdf_url)
            r2_key = f"{r2_prefix}/{pdf_filename}"

            print(f"  - Found PDF: {pdf_url}")
            pdf_response = await get(http_client, pdf_url)
            await upload_to_r2(r2_client, r2_bucket, r2_key, pdf_response.content)

            pdfs_found += 1
            await asyncio.sleep(delay)
    if not pdfs_found:
        print("  - No PDFs found on page.")
    return pdfs_found


async def crawl_legislation_specific_act(
    http_client: httpx.AsyncClient,
    r2_client,
    r2_bucket: str,
    labour_act_url: str,
    delay: float,
) -> int:
    return await fetch_and_upload_pdfs(
        http_client,
        r2_client,
        labour_act_url,
        r2_bucket,
        "corpus/sources/legislation",
        delay,
    )


async def crawl_judgments_search(
    http_client: httpx.AsyncClient,
    r2_client,
    r2_bucket: str,
    query: str,
    max_pages: int,
    delay: float,
) -> int:
    base_url = f"{BASE}/judgments/"
    total_pdfs = 0
    page = 1
    seen_pages = set()
    while True:
        if max_pages > 0 and page > max_pages:
            break

        page_param = "" if page == 1 else f"&page={page - 1}"
        page_url = f"{base_url}?q={query}{page_param}"

        print(f"\nCrawling judgment search page {page}: {page_url}")
        resp = await get(http_client, page_url)
        soup = BeautifulSoup(resp.text, "lxml")
        anchors = soup.find_all("a", href=True)
        doc_links = [
            abs_url(a["href"]) for a in anchors if "/akn/zw/judgment/" in a["href"]
        ]

        if not doc_links or not set(doc_links).difference(seen_pages):
            print("- No new judgment document links found. Ending crawl.")
            break

        for doc_url in doc_links:
            if doc_url in seen_pages:
                continue
            seen_pages.add(doc_url)
            total_pdfs += await fetch_and_upload_pdfs(
                http_client,
                r2_client,
                doc_url,
                r2_bucket,
                "corpus/sources/case_law",
                delay,
            )
        page += 1
    return total_pdfs


async def run(args: argparse.Namespace) -> None:
    r2_client = get_r2_client()
    bucket_name = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    headers = {"User-Agent": UA}

    async with httpx.AsyncClient(headers=headers) as client:
        total = 0
        max_pages = 0 if args.unlimited else args.max_pages

        if args.legislation:
            print("\n--- Starting Legislation Crawl ---")
            total += await crawl_legislation_specific_act(
                client, r2_client, bucket_name, args.labour_act_url, args.delay
            )
        if args.judgments:
            print("\n--- Starting Judgments Crawl ---")
            total += await crawl_judgments_search(
                client, r2_client, bucket_name, args.judgment_query, max_pages, args.delay
            )
        print(f"\nFinished. Uploaded a total of {total} PDFs to R2 bucket '{bucket_name}'.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Crawl ZimLII for PDFs and upload them to Cloudflare R2."
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Max number of pages to crawl on paginated sites.",
    )
    p.add_argument(
        "--unlimited",
        action="store_true",
        help="Ignore max-pages; crawl until no new results are found.",
    )
    p.add_argument(
        "--delay", type=float, default=1.0, help="Polite delay between HTTP requests."
    )
    p.add_argument("--legislation", action="store_true", help="Crawl the specific Labour Act page for PDFs.")
    p.add_argument(
        "--labour-act-url",
        default="https://zimlii.org/akn/zw/act/1985/16/eng@2016-12-31",
        help="URL of the specific legislation page to scan.",
    )
    p.add_argument("--judgments", action="store_true", help="Crawl judgment search results for PDFs.")
    p.add_argument(
        "--judgment-query",
        default="labour",
        help="Search query for finding judgments.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))

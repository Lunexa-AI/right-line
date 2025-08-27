#!/usr/bin/env python3
"""
catalog_from_raw.py - Build current-legislation catalog from already-downloaded HTML

This script scans data/raw/legislation/*.html, extracts FRBR metadata and titles,
infers nature (Act | Ordinance | Statutory Instrument), effective date and year,
and writes a JSONL catalog at data/processed/leg_catalog.jsonl.

Usage:
  python scripts/catalog_from_raw.py \
    --raw_dir data/raw/legislation \
    --out data/processed/leg_catalog.jsonl

No network requests are made.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup


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


def infer_nature_from_uris(work_uri: Optional[str], expr_uri: Optional[str]) -> str:
    uri = (expr_uri or work_uri or "").lower()
    if "/act/si/" in uri:
        return "Statutory Instrument"
    if "/act/ord/" in uri:
        return "Ordinance"
    return "Act"


def parse_effective_date(expression_frbr_uri: Optional[str]) -> Optional[str]:
    if not expression_frbr_uri:
        return None
    m = re.search(r"@(\d{4}-\d{2}-\d{2})", expression_frbr_uri)
    return m.group(1) if m else None


def parse_year(number: Optional[str], expression_frbr_uri: Optional[str]) -> Optional[int]:
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


def extract_chapter_text(soup: BeautifulSoup) -> Optional[str]:
    text = soup.get_text(" ")
    m = re.search(r"Chapter\s+([0-9]+:[0-9]+)", text, flags=re.I)
    return m.group(1) if m else None


def build_catalog_entry(html_path: Path) -> Optional[CatalogRow]:
    try:
        html = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_head_metadata(soup)
    work = meta.get("work_frbr_uri")
    expr = meta.get("expression_frbr_uri")
    number = meta.get("frbr_uri_number")
    title = meta.get("title") or html_path.stem
    akn_uri = work or expr or ""
    nature = infer_nature_from_uris(work, expr)
    effective = parse_effective_date(expr) or meta.get("publication_date")
    year = parse_year(number, expr)
    chapter = extract_chapter_text(soup)
    # Build source_url from FRBR if available
    source_url = f"https://zimlii.org{expr or work}" if (expr or work) else html_path.name
    return CatalogRow(
        akn_uri=akn_uri,
        nature=nature,
        title=title,
        chapter=chapter,
        work_frbr_uri=work,
        expression_frbr_uri=expr,
        effective_date=effective,
        year=year,
        source_url=source_url,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Build catalog JSONL from downloaded current-legislation HTML")
    p.add_argument("--raw_dir", type=Path, default=Path("data/raw/legislation"))
    p.add_argument("--out", type=Path, default=Path("data/processed/leg_catalog.jsonl"))
    args = p.parse_args()

    files = sorted(args.raw_dir.glob("*.html"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}
    seen = set()
    with args.out.open("w", encoding="utf-8") as fp:
        for f in files:
            row = build_catalog_entry(f)
            if not row:
                continue
            # De-dupe on akn_uri if present, else on filename
            key = row.akn_uri or f.name
            if key in seen:
                continue
            seen.add(key)
            counts[row.nature] = counts.get(row.nature, 0) + 1
            fp.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")

    total = sum(counts.values())
    print("Built catalog:", counts, "total", total)


if __name__ == "__main__":
    main()



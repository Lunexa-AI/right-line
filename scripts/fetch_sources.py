#!/usr/bin/env python3
"""
Polite fetcher for Phase 2 sources.

- Reads a YAML manifest (docs/data/sources.yaml)
- Downloads PDFs/HTML to data/raw/<source>/<filename>
- Respects delay between requests; small retry policy
- Does not bypass robots; ensure URLs are allowed

Usage:
  python3 scripts/fetch_sources.py --config docs/data/sources.yaml --out data/raw --delay 1.0
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

DEFAULT_TIMEOUT = 30.0
RETRIES = 3


async def fetch_file(client: httpx.AsyncClient, url: str, dest: Path, retries: int = RETRIES) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return
        except Exception as e:  # noqa: BLE001 - log and continue
            last_exc = e
            await asyncio.sleep(0.8 * attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_exc}")


def sanitize_filename(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", ".")).strip()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    cfg_path = Path(args.config)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    if not cfg_path.exists():
        raise SystemExit(f"Config not found: {cfg_path}")

    data: dict[str, Any] = yaml.safe_load(cfg_path.read_text()) or {}

    # Flatten entries from sections
    entries: list[dict[str, Any]] = []
    for key, val in data.items():
        if isinstance(val, list):
            for item in val:
                item["_group"] = key
                entries.append(item)
        elif isinstance(val, dict):
            val["_group"] = key
            entries.append(val)

    headers = {
        "User-Agent": "RightLineFetcher/1.0 (+https://rightline.zw)",
        "Accept": "*/*",
    }

    async with httpx.AsyncClient(headers=headers) as client:
        for item in entries:
            url = item.get("url")
            if not url or "<" in url:
                print(f"Skipping placeholder URL for {item.get('description','(no desc)')}")
                continue
            out_dir = item.get("out_dir", item.get("_group", "misc"))
            source = item.get("source", "misc")
            filetype = item.get("type", "bin")

            # Derive a filename
            name_hint = sanitize_filename(Path(url).name) or f"{filetype}.bin"
            # Ensure proper extension for html snapshots
            if filetype == "html" and not name_hint.endswith(".html"):
                name_hint = f"{name_hint}.html"

            dest = out_root / source / out_dir / name_hint
            print(f"Downloading: {url} -> {dest}")
            await fetch_file(client, url, dest)
            await asyncio.sleep(args.delay)


if __name__ == "__main__":
    asyncio.run(main())

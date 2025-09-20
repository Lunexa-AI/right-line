#!/usr/bin/env python3
"""fix_chunk_hierarchy.py

Add constitutional hierarchy metadata to all chunk JSON files in R2 based on their doc_type.
This ensures every chunk knows its authority level and ranking.

Usage:
    python scripts/fix_chunk_hierarchy.py [--dry-run]
"""

import argparse
import json
import os
from typing import Dict, Any

import boto3
from botocore.client import Config
from dotenv import load_dotenv
from tqdm import tqdm
import structlog

logger = structlog.get_logger("fix_chunk_hierarchy")

# ---------------------------------------------------------------------------
# Hierarchy map by doc_type
# ---------------------------------------------------------------------------
HIERARCHY_MAP: Dict[str, Dict[str, Any]] = {
    "constitution": {
        "authority_level": "supreme",
        "hierarchy_rank": 1,
        "binding_scope": "all_courts",
        "subject_category": "constitutional_law",
    },
    "act": {
        "authority_level": "high",
        "hierarchy_rank": 2,
        "binding_scope": "national",
        "subject_category": "legislation",
    },
    "ordinance": {
        "authority_level": "medium",
        "hierarchy_rank": 3,
        "binding_scope": "specific",
        "subject_category": "legislation",
    },
    "si": {
        "authority_level": "medium",
        "hierarchy_rank": 3,
        "binding_scope": "specific",
        "subject_category": "legislation",
    },
}


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )


def ensure_hierarchy(chunk: Dict[str, Any]) -> bool:
    """Add hierarchy fields if missing. Returns True if modified."""
    doc_type = (chunk.get("doc_type") or "unknown").lower()
    mapping = HIERARCHY_MAP.get(doc_type)
    if not mapping:
        return False  # Unknown doc_type

    modified = False
    for field, value in mapping.items():
        if not chunk.get(field):
            chunk[field] = value
            modified = True
    return modified


def fix_chunks_in_r2(dry_run: bool = False):
    load_dotenv(".env.local")
    client = get_r2_client()
    bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]

    total_chunks = 0
    fixed_chunks = 0

    for doc_type in HIERARCHY_MAP.keys():
        prefix = f"corpus/chunks/{doc_type}/"
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            keys.extend([obj["Key"] for obj in page.get("Contents", []) if obj["Key"].endswith(".json")])

        logger.info("processing_doc_type", doc_type=doc_type, total=len(keys))
        for key in tqdm(keys, desc=f"Fixing {doc_type}"):
            total_chunks += 1
            obj = client.get_object(Bucket=bucket, Key=key)
            chunk_data = json.loads(obj["Body"].read().decode("utf-8"))
            if ensure_hierarchy(chunk_data):
                fixed_chunks += 1
                if not dry_run:
                    # Update metadata headers as well
                    new_meta = obj.get("Metadata", {})
                    mapping = HIERARCHY_MAP[doc_type]
                    new_meta.update({k: str(v) for k, v in mapping.items()})
                    client.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=json.dumps(chunk_data, default=str).encode("utf-8"),
                        ContentType="application/json",
                        Metadata=new_meta,
                    )
    logger.info("hierarchy_fix_complete", fixed=fixed_chunks, total=total_chunks)


def main():
    parser = argparse.ArgumentParser(description="Fix hierarchy metadata for chunks in R2")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading changes")
    args = parser.parse_args()

    fix_chunks_in_r2(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

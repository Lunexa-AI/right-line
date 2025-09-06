#!/usr/bin/env python3
"""delete_old_chunks.py

Utility to purge outdated chunk objects from Cloudflare R2.

This is a one-off helper to clean the `corpus/chunks/` prefix before we
switch to the new small-to-big chunking strategy.

Usage (local):
    export $(grep -v '^#' .env.local | xargs)
    poetry run python3 scripts/tools/delete_old_chunks.py \
        --prefix corpus/chunks/ --dry-run

    # Actually delete
    poetry run python3 scripts/tools/delete_old_chunks.py --prefix corpus/chunks/

Options:
    --prefix        R2 prefix to delete under (default: corpus/chunks/)
    --batch-size    S3 DeleteObjects batch size (default: 1000)
    --dry-run       List keys that *would* be deleted but do nothing

Environment variables required:
    CLOUDFLARE_R2_S3_ENDPOINT
    CLOUDFLARE_R2_ACCESS_KEY_ID
    CLOUDFLARE_R2_SECRET_ACCESS_KEY
    CLOUDFLARE_R2_BUCKET_NAME
"""

from __future__ import annotations

import argparse
import os
from typing import List

import boto3
from botocore.client import Config
from tqdm import tqdm


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
    )


def list_keys(client, bucket: str, prefix: str) -> List[str]:
    keys: List[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def delete_keys(client, bucket: str, keys: List[str], dry_run: bool, batch_size: int = 1000):
    if dry_run:
        for k in keys:
            print("[DRY-RUN] would delete", k)
        print(f"[DRY-RUN] {len(keys)} objects would be deleted.")
        return

    total = len(keys)
    if total == 0:
        print("Nothing to delete.")
        return

    with tqdm(total=total, desc="Deleting") as bar:
        for i in range(0, total, batch_size):
            batch = keys[i : i + batch_size]
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
            bar.update(len(batch))
    print(f"Deleted {total} objects from {bucket}")


def main():
    parser = argparse.ArgumentParser(description="Delete old chunk files from R2")
    parser.add_argument(
        "--prefix",
        type=str,
        default="corpus/chunks/",
        help="R2 prefix to delete under",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true", help="List objects without deleting")

    args = parser.parse_args()

    bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    client = get_r2_client()

    print(f"Listing objects under s3://{bucket}/{args.prefix} …")
    keys = list_keys(client, bucket, args.prefix)
    print(f"Found {len(keys)} objects.")

    delete_keys(client, bucket, keys, dry_run=args.dry_run, batch_size=args.batch_size)


if __name__ == "__main__":
    main()

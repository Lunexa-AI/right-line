#!/usr/bin/env python3
"""Cleanup processed data in R2 and reset Milvus collection.

Usage:
    python scripts/cleanup_processed_data.py [--confirm]

The script performs **irreversible deletions**:
1. Removes all objects under:
   - corpus/docs/
   - corpus/chunks/
   - corpus/processed/
   - corpus/indexes/
2. Drops the Milvus collection defined by env var MILVUS_COLLECTION_NAME (default "legal_chunks_v2").

It keeps corpus/sources/ intact.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pymilvus import (Collection, MilvusException, utility)  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup")

R2_PREFIXES_TO_DELETE: List[str] = [
    "corpus/docs/",
    "corpus/chunks/",
    "corpus/processed/",
    "corpus/indexes/",
]


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def delete_r2_prefix(client, bucket: str, prefix: str) -> int:
    """Delete all objects under a prefix. Returns number of deleted objects."""
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objs = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if objs:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objs})
            deleted += len(objs)
    return deleted


def drop_milvus_collection(collection_name: str):
    if utility.has_collection(collection_name):
        logger.info("Dropping Milvus collection %s", collection_name)
        Collection(collection_name).drop()
    else:
        logger.info("Milvus collection %s does not exist", collection_name)


def main():
    parser = argparse.ArgumentParser(description="Cleanup processed data from R2 and Milvus.")
    parser.add_argument("--confirm", action="store_true", help="Actually perform deletion.")
    args = parser.parse_args()

    load_dotenv(".env.local")

    bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]
    milvus_collection = os.getenv("MILVUS_COLLECTION_NAME", "legal_chunks_v2")

    if not args.confirm:
        logger.warning("This script will delete ALL processed data and drop Milvus collection '%s'.", milvus_collection)
        logger.warning("Run with --confirm to proceed.")
        sys.exit(0)

    # R2 cleanup
    r2 = get_r2_client()
    total_deleted = 0
    for prefix in R2_PREFIXES_TO_DELETE:
        try:
            count = delete_r2_prefix(r2, bucket, prefix)
            logger.info("Deleted %d objects under %s", count, prefix)
            total_deleted += count
        except ClientError as e:
            logger.error("Error deleting %s: %s", prefix, e)

    logger.info("Total R2 objects deleted: %d", total_deleted)

    # Milvus cleanup
    try:
        drop_milvus_collection(milvus_collection)
    except MilvusException as e:
        logger.error("Failed to drop Milvus collection: %s", e)

    logger.info("Cleanup complete!")


if __name__ == "__main__":
    main()

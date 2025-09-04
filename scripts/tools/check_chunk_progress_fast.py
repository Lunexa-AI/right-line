#!/usr/bin/env python3
import os, json, boto3, asyncio, aiohttp, botocore
from botocore.client import Config
from collections import defaultdict, Counter
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--max-workers", type=int, default=300,
                    help="Concurrent HEAD requests")
args = parser.parse_args()

# --- R2 client (sync for list-objects, we’ll use aiohttp for HEAD) ------------
r2 = boto3.client(
    "s3",
    endpoint_url=os.environ["CLOUDFLARE_R2_S3_ENDPOINT"],
    aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
    config=Config(signature_version="s3v4"),
)
bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]

# --- load catalog -------------------------------------------------------------
catalog = r2.get_object(Bucket=bucket,
                        Key="corpus/processed/legislation_docs.jsonl")["Body"].read()
all_docs = {json.loads(l)["doc_id"]: json.loads(l)["title"]
            for l in catalog.splitlines() if l.strip()}
pending = set(all_docs.keys())
print(f"Need chunk status for {len(pending)} documents")

# --- list chunk keys ----------------------------------------------------------
chunk_prefixes = ["corpus/chunks/act/", "corpus/chunks/ordinance/",
                  "corpus/chunks/si/"]
chunk_keys = []
for pfx in chunk_prefixes:
    for page in r2.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=pfx):
        chunk_keys += [o["Key"] for o in page.get("Contents", [])
                       if o["Key"].endswith(".json")]
print(f"Scanning {len(chunk_keys)} chunk objects (but will early-exit)")

# --- async head-object utility -----------------------------------------------
# R2 uses the same auth headers boto3 signs; easiest is presign each HEAD URL
def presign(key):
    return r2.generate_presigned_url(
        "head_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=3600
    )


async def head_and_get_doc_id(session: aiohttp.ClientSession, key: str):
    """Perform an HTTP HEAD on the pre-signed URL and return the doc_id metadata."""
    try:
        async with session.head(presign(key)) as resp:
            if resp.status == 200:
                return key, resp.headers.get("x-amz-meta-doc_id")
    except Exception:
        # Network errors are ignored; treat as missing metadata
        pass
    return key, None

# --- main loop ----------------------------------------------------------------
seen = set()
doc_chunks = defaultdict(int)

async def main():
    sem = asyncio.Semaphore(args.max_workers)

    async with aiohttp.ClientSession() as session:
        async def bound_task(k):
            async with sem:
                return await head_and_get_doc_id(session, k)

        tasks = [asyncio.create_task(bound_task(k)) for k in chunk_keys]

        for coro in asyncio.as_completed(tasks):
            try:
                key, doc_id = await coro
            except asyncio.CancelledError:
                continue
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                pending.discard(doc_id)
                if doc_id in all_docs:
                    doc_chunks[doc_id] += 1
                if not pending:
                    # All documents accounted for; cancel remaining tasks
                    for t in tasks:
                        t.cancel()
                    break


asyncio.run(main())

# --- report -------------------------------------------------------------------
print(f"\n✅ Completed: {len(seen)}")
print(f"⏳ Pending : {len(pending)}\n")
for d in list(pending)[:10]:
    print(" •", d, "-", all_docs[d])
if len(pending) > 10:
    print(f"   …and {len(pending)-10} more")
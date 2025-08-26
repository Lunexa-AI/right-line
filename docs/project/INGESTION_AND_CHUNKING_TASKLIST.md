# Ingestion & Chunking Task List (Legislation‑first, revamped)

This task list operationalizes `docs/project/INGESTION_AND_CHUNKING.md` into concrete, bite-sized tasks you can execute end-to-end to move from raw HTML → normalized docs → chunks → embeddings → Milvus collection ready for search.

References: [Milvus Docs](https://milvus.io/docs)

---

## 0) Prerequisites & Environment

- [x] Create/Open a Milvus Cloud (Zilliz Cloud) account
  - Go to `https://zilliz.com/cloud` (Managed Milvus)
  - Create a free cluster (pick nearest region)
  - Note the connection info:
    - `MILVUS_ENDPOINT` (e.g., `https://xxx.api.gcp-us-west1.zillizcloud.com`)
    - `MILVUS_TOKEN` (API key/token)
  - Acceptance:
    - You can see cluster “Healthy” in console
    - You have endpoint + token ready

- [x] Create/Open an OpenAI account and API key
  - Go to OpenAI dashboard → API Keys
  - Create a key and store it securely
  - Acceptance: `OPENAI_API_KEY` available

- [x] Populate local env vars for dev
  - Create `.env.local` or export in shell:
    ```bash
    export OPENAI_API_KEY=sk-...your-key...
    export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
    export MILVUS_ENDPOINT=https://your-milvus-endpoint
    export MILVUS_TOKEN=your-milvus-token
    export MILVUS_COLLECTION_NAME=legal_chunks
    ```
  - Acceptance: `echo $OPENAI_API_KEY` etc. returns values

- [x] Verify project deps installed (venv active)
  - ```bash
    pip install -r requirements.txt
    ```
  - Acceptance: No errors, `python3 -c "import openai, pymilvus"` succeeds

---

## 1) Prepare & Inspect Raw Data

- [x] Ensure raw HTML present
  - Legislation: `data/raw/legislation/*.html`
  - Judgments: `data/raw/judgments/*.html`
  - Acceptance: `ls data/raw/legislation`, `ls data/raw/judgments` show files

- [x] Spot-check 2–3 files from each set to understand structure
  - Manually open in editor, look for title, section anchors, headnote, metadata blocks
  - Acceptance: Key landmarks identified (document title, sections or paragraphs, dates)

---

## 2) Milvus Collection (updated schema)

- [ ] Initialize/confirm Milvus `legal_chunks` collection (updated fields)
  - ```bash
    python scripts/init-milvus.py
    ```
  - Expected actions:
    - Create/confirm scalar fields: `doc_type`, `nature`, `language`, `court`, `date_context`, `year`, `chapter`
    - Create HNSW index on `embedding` (COSINE); load collection
  - Acceptance:
    - Script prints ✓ connected, ✓ collection created or exists, ✓ index created, ✓ loaded

---

## 3) Parsing & Normalization (Documents → docs.jsonl)

- [x] Define normalized document schema (updated: add `nature`, `year`, `chapter`, `work_uri`, `akn_uri`)
  - Fields to capture: `doc_id`, `doc_type`, `title`, `source_url`, `language`, `jurisdiction`, `version_effective_date` (acts), `canonical_citation` (judgments), and `extra` JSON (court, judges, parties, etc.)
  - Acceptance: Schema written in code comments or a small README in `scripts/`

- [x] Implement HTML boilerplate removal plan (no code yet, just checklist)
  - Keep only the main document content area (remove nav, footers, scripts)
  - Normalize whitespace, fix Unicode
  - Acceptance: Document the CSS/landmark selectors to target per source type

- [x] Plan section extraction for legislation
  - Prefer AKN `section` nodes; fallback to robust heading heuristics
  - Judgments: extract headnote (if present), then body paragraphs; capture court metadata
  - Acceptance: Document the extraction heuristics (e.g., heading tags/classes, paragraph containers)

- [x] Define stable `doc_id`
  - `doc_id = sha256_16(source_url + expression_uri_or_date + title)`
  - Acceptance: Example doc IDs computed and recorded for 2 sample docs

- [x] Output plan
  - Emit one document JSON per line → `data/processed/docs.jsonl`
  - Each object contains doc-level metadata and a hierarchical section/paragraph tree
  - Acceptance: Sample target JSON documented (1 legislation, 1 judgment)

---

## 4) Chunking (docs.jsonl → chunks.jsonl)

- [x] Define chunk schema (as per INGESTION_AND_CHUNKING.md)
  - `chunk_id`, `doc_id`, `chunk_text`, `section_path`, `start_char`, `end_char`, `num_tokens`, `language`, `date_context`, `entities`, `source_url`, and `metadata` (json)
  - Acceptance: Clear field list documented and aligned with Milvus scalar/json

- [x] Define chunking strategy for legislation (adaptive)
  - Common: target 400–600 tokens; max ~5000 chars; adaptive overlap 10–20%
  - Legislation: primary unit = section; paragraph‑aware splits; greedy merge for short sections; record merged `section_ids`
  - Judgments: primary unit = paragraphs; headnote as separate chunks; windowed merge
  - Acceptance: Explicit rules table written (e.g., long/short sections handling)

- [x] Define stable `chunk_id`
  - `chunk_id = sha256_16(doc_id + section_path + start_char + end_char + text_hash)`
  - Acceptance: Example chunk IDs computed and recorded for 2 sample chunks

- [x] Output plan
  - Emit one chunk JSON per line → `data/processed/chunks.jsonl`
  - Acceptance: Target JSON lines format documented with 2 examples (legislation, judgment)

---

## 5) Enrichment (Entities & Signals)

- [x] MVP entity extraction heuristics
  - Dates (ISO), section refs (e.g., `s 12A`, `Section 12A`), court names, judges, parties
  - Store under `metadata.entities`
  - Acceptance: Regex/heuristic list documented and test strings noted

- [x] Normalize dates & citations
  - Convert to ISO, standardize section numbering format
  - Acceptance: Before/after examples documented

---

## 6) Embeddings (chunks.jsonl → chunks_with_embeddings.jsonl)

- [x] Set embedding configuration
  - Model: `text-embedding-3-small`
  - Batch size (tune later): start at 64
  - Acceptance: Values added to `.env.local`

- [x] Dry-run embeddings on 5–10 chunks
  - Estimate token usage & cost; inspect output 
  - Acceptance: Sample output saved (first 3 records) to `data/processed/chunks_with_embeddings.sample.json`

- [x] Full‑run embeddings
  - Read `data/processed/chunks.jsonl` in batches; write `data/processed/chunks_with_embeddings.jsonl`
  - Handle retries/backoff; log failures; continue
  - Acceptance: File created; counts match input; error rate < 1%

---

## 7) Milvus Upsert (chunks_with_embeddings.jsonl → Milvus)

- [ ] Verify collection (again)
  - If not exists, create via `scripts/init-milvus.py`
  - Acceptance: Collection present & loaded

- [ ] Upsert chunks in batches
  - Insert fields: `doc_id`, `doc_type`, `nature`, `language`, `court`, `date_context`, `year`, `chapter`, `chunk_text`, `embedding`, `metadata`
  - Acceptance: Insert completes; row count increases as expected

- [ ] Post-insert verification
  - Run a test vector search against 1–2 queries (via `api/retrieval.py` helper)
  - Acceptance: Reasonable results returned; latency < 500ms (vector-only)

---

## 8) Idempotency & Resume

- [ ] Implement/record ID rules formally
  - `doc_id`, `chunk_id` as content-derived hashes → stable re-runs
  - Acceptance: Document examples and how duplicates are prevented

- [ ] (Optional) Local manifest for ingestion state
  - Lightweight JSON/SQLite mapping to track processed files, last run time, counts
  - Acceptance: Manifest schema defined; storage location chosen

---

## 9) Evaluation & Monitoring (MVP)

- [ ] Golden set creation
  - 20–30 queries with expected sections/paragraphs
  - Acceptance: `docs/eval/golden_set.yaml` exists

- [ ] Recall@k script (offline)
  - Simple script to run queries vs Milvus and compute Recall@k
  - Acceptance: Scores logged; baseline noted

- [ ] Latency logging
  - Record retrieval time P50/P95 on dev machine
  - Acceptance: Report added to `docs/eval/README.md`

---

## 10) Retrieval Readiness & Ranking
 - [ ] Ensure metadata covers filters
   - `doc_type in {act, ordinance, si}`, `nature`, `year`, `chapter` present as scalars
   - Acceptance: queries can filter by nature/year/chapter
 - [ ] Keyword boosts and score fusion
   - Boost exact section numbers (e.g., 12A) and statute titles; combine with vector scores (additive or RRF)
   - Acceptance: low‑risk boosts implemented behind a flag

---

## 11) Ops & Safety

- [ ] Logging of ingestion events
  - Counts per stage, failures, retries, token usage
  - Acceptance: Logs capture per-stage metrics

- [ ] Cost guards for OpenAI
  - Track tokens; simple budget threshold alarms for dev
  - Acceptance: Document policy (per-run $ cap)

---

## 12) Acceptance Criteria Summary (End-to-End)

- [ ] `data/processed/leg_catalog.jsonl` has counts: Acts=375, Ordinances=14, SIs=16 (405 total)
- [ ] `data/processed/docs.jsonl` created with normalized documents
- [ ] `data/processed/chunks.jsonl` created with stable IDs and chunking metadata
- [ ] `data/processed/chunks_with_embeddings.jsonl` created with vectors
- [ ] Milvus collection `legal_chunks` exists, indexed (HNSW, COSINE), loaded
- [ ] Test queries return relevant results in < 500ms vector‑only; end‑to‑end P95 < 2s
- [ ] Idempotent re‑run does not create duplicates

---

## 13) Helpful Commands (Quick Reference)

```bash
# 0) Env
export OPENAI_API_KEY=sk-...
export OPENAI_EMBEDDING_MODEL=text-embedding-3-small
export MILVUS_ENDPOINT=https://your-milvus-endpoint
export MILVUS_TOKEN=your-milvus-token
export MILVUS_COLLECTION_NAME=legal_chunks

# 1) Create collection
python scripts/init-milvus.py

# 2) Parse docs → docs.jsonl
python scripts/parse_docs.py --input-dir data/raw --output data/processed/docs.jsonl

# 3) Chunk documents → chunks.jsonl
python scripts/chunk_docs.py --input_file data/processed/docs.jsonl --output_file data/processed/chunks.jsonl --fix-for-milvus

# 4) Embeddings → chunks_with_embeddings.jsonl
python scripts/generate_embeddings.py --input data/processed/chunks.jsonl

# 5) Upsert to Milvus
python scripts/milvus_upsert.py --input_file data/processed/chunks_with_embeddings.jsonl --batch_size 100
```

This checklist ensures we don’t miss any step from the plan and that each unit is small, testable, and has clear acceptance. Once complete, the collection in Milvus will be ready for retrieval and integration with the API.

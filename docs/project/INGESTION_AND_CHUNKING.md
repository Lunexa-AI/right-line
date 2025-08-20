### RightLine Ingestion, Normalization, Chunking, and Milvus Insertion Plan

This document describes a robust, scalable plan to parse ZimLII legislation and judgments HTML, normalize and enrich content, chunk with state-of-the-art strategies, embed with OpenAI, and insert into Milvus for fast retrieval. The plan is designed to support future sources (more Acts/Statutory Instruments, Constitution, more judgments and courts) with stable IDs and idempotent processing.

References: [Milvus Docs](https://milvus.io/docs)

---

## 1) Current State and Goals

- Current raw data location: `data/raw/legislation/*.html`, `data/raw/judgments/*.html` (ZimLII pages)
- API and retrieval stack: FastAPI (serverless-ready), OpenAI `text-embedding-3-small` (1536-dim), Milvus collection (HNSW index), hybrid retrieval planned
- Missing pieces: systematic parsing, normalization, stable doc/chunk IDs, production-grade chunking, embeddings & Milvus ingestion

Goals:
- Parse legislation and judgments into a normalized internal schema
- Extract essential metadata (dates, sections, parties, judges, court, citations, jurisdiction, etc.)
- Create stable, repeatable chunking with sliding window + overlap
- Generate embeddings (batch) and insert into Milvus with metadata for scalar filtering
- Idempotent, resumable ingestion that supports re-runs and new data growth

---

## 2) Source HTML Characteristics (ZimLII)

Observations from ZimLII (example: Labour Act page):
- Standard HTML with global header, menus, social/meta tags, scripts (Sentry/Matomo), and a main document content region
- AKN/FRBR metadata present in JSON blocks or attributes (e.g., `work_frbr_uri`, `expression_frbr_uri`, doctype: `act`, language `eng`, expression date `eng@2016-12-31`)
- Legislation structure generally follows hierarchy: Part > Chapter > Section (with headings and anchors)
- Judgments typically include: case title, court, neutral citation, case number, date delivered, judges, counsel, headnote/summary, body paragraphs, references

Key takeaway: We can rely on consistent landmarks to locate the main content area and structured anchors/headings.

---

## 3) Normalized Internal Schemas

### 3.1 Document Schema (stored as metadata; referenced by chunks)
- `doc_id` (string): Stable ID. Recommended: hash of `source_url` + `frbr/expression` or canonical citation (e.g., SHA256-16).
- `doc_type` (enum): `act`, `si`, `constitution`, `judgment`, `regulation`, `other`
- `title` (string): Document title (e.g., “Labour Act” or case title)
- `source_url` (string): Original ZimLII URL
- `language` (string): `eng` initially; allow future languages
- `jurisdiction` (string): `ZW`
- `version_effective_date` (date, nullable): For legislation expressions
- `created_at` (timestamp): Ingestion timestamp
- `updated_at` (timestamp): Last processed timestamp
- `canonical_citation` (string, nullable): Neutral or statute citation
- `extra` (json): Flexible bucket for doc-type–specific fields below

Doc-type specific (stored in `extra` json):
- Legislation: `chapter`, `act_number`, `part_map`, `section_ids`, `expression_uri`, `effective_start`, `effective_end`
- Judgment: `court`, `case_number`, `neutral_citation`, `date_decided`, `judges`[], `parties`{applicant/respondent or appellant/respondent}, `headnote`, `references`[]

### 3.2 Chunk Schema (Milvus scalar fields + JSON in `metadata`)
- `chunk_id` (string): Stable ID. Recommended: hash of `doc_id + section_path + char_range + text_hash` (SHA256-16)
- `doc_id` (string): FK to document
- `chunk_text` (string): Cleaned text (max ~5000 chars); aim for ~512 token target
- `section_path` (string): Hierarchical path (e.g., `Part II > Section 12A` or `Headnote > Para 3`)
- `start_char` / `end_char` (int): Character offsets into doc canonical text
- `num_tokens` (int): Token estimate used
- `language` (string): e.g., `eng`
- `date_context` (date, nullable): For legislation versions or judgment date
- `entities` (json): Optional extracted entities (people, courts, places, statute refs)
- `source_url` (string): For traceability
- `embedding` (float_vector[1536]): OpenAI embedding vector
- `metadata` (json): Anything else (court, judges, act number, canonical citation, etc.)

Note: In Milvus, we’ll store `doc_id` (varchar), `chunk_text` (varchar ~5000), `embedding` (float_vector 1536), and one `metadata` json. Store other fields redundantly inside `metadata` for flexibility and in scalar form where we want to filter (e.g., `language`, `doc_type`, `court`, `date_context`).

---

## 4) Parsing and Normalization

### 4.1 Boilerplate Removal
- Strip headers, nav, footers, menus, analytics and script tags, icons, and unrelated content
- Keep the main document content container (identify by stable CSS selectors or landmarks used by ZimLII)

### 4.2 Legislation Parsing
- Extract: Title, Chapter, Act number, FRBR/AKN URIs, language, expression date (effective date)
- Identify hierarchy by headings and anchors: Parts/Chapters/Sections
- For each section:
  - Capture heading (e.g., “Section 12A — Dismissal”) and anchor id
  - Capture section text paragraphs preserving intra-section order
  - Record `section_path`, `effective date`, and any inline citations
- Normalize whitespace, fix Unicode, collapse multiple spaces, remove page artifacts

### 4.3 Judgments Parsing
- Extract: Case title, court, neutral citation, case number, judges, counsel (if present), date delivered
- Identify and capture: headnote/summary; then body paragraphs in order
- Parse references block (if present) and inline citations to Acts and other cases
- Normalize text as above

### 4.4 Entity and Signal Extraction (MVP-level)
- Use regex + heuristics for:
  - Dates (ISO where possible)
  - Section references (e.g., “s 12A” / “Section 12A”)
  - Party names: look for patterns like `X v Y`, `Applicant`, `Respondent`
  - Court names and judges: look in document header area
- Store extracted entities in `metadata.entities`; later replace with proper NER models

### 4.5 Stable IDs
- `doc_id`: `sha256_16(source_url + expression_uri or date + title)`
- `section_id`: For legislation, use anchor-based paths; for judgments, `headnote`, `para-N`
- `chunk_id`: `sha256_16(doc_id + section_path + start_char + end_char + text_hash)`

---

## 5) Chunking Strategy (State-of-the-art, Practical)

We will chunk to balance retrieval quality and latency. Strategy depends on document type but shares common principles.

### 5.1 Common Principles
- Target ~512 tokens per chunk (approx. 750–1000 chars), hard cap ~5000 chars
- Sliding window with overlap of 15–20% tokens between consecutive chunks
- Break on natural boundaries first (section or paragraph); only spill across boundaries if chunk is too short
- Preserve section path in metadata; include short inline header in `chunk_text` only if helpful (few words)
- Compute and store `num_tokens` estimates for diagnostics

### 5.2 Legislation
- Primary unit: Section
- If section text > target size:
  - Split into paragraphs and recompose into ~512 token bins with 20% overlap
- If section text < target/2:
  - Merge with adjacent section content (in same Part) but preserve `section_path` in metadata
- Include section number and heading in metadata; optionally prefix the first line of the chunk with “Section 12A:” for clarity (not required)

### 5.3 Judgments
- Primary unit: Paragraphs
- Headnote becomes its own chunk(s)
- Compose sequential paragraphs into ~512 token chunks with 15–20% overlap; include paragraph indices (e.g., `para 14–18`) in `section_path`
- Store court, neutral citation, date decided in metadata for scalar filtering and recency/authority boosts

---

## 6) Embeddings (OpenAI) and Batching

- Model: `text-embedding-3-small` (1536-dim)
- Clean text input: ensure no HTML, normalized whitespace
- Batch size: tune to 64–128 depending on rate limits; handle retries/backoff
- Persist chunk+embedding in memory or temp before upsert to Milvus to ensure idempotency and partial-failure recovery
- Cost observability: log tokens per batch; estimate cost (~$0.02 per 1M tokens for this model per the current pricing)

---

## 7) Milvus Collections and Indexing

Primary collection: `legal_chunks`
- Fields (Milvus):
  - `id` (auto primary key, int64)
  - `doc_id` (varchar, max_length ~100)
  - `chunk_text` (varchar, max_length ~5000)
  - `embedding` (float_vector, dim=1536)
  - `metadata` (json)
- Recommended scalar fields (optional, for filters): `doc_type` (varchar), `language` (varchar), `date_context` (varchar/date), `court` (varchar)
- Index: HNSW for `embedding` with COSINE metric (e.g., `M=16`, `efConstruction=256`); load collection for search

Why this design:
- JSON metadata provides flexibility as schemas evolve
- A few promoted scalar fields enable efficient hybrid search (vector + filters)

Milvus docs useful sections:
- Manage Collections, Single-Vector Search, Hybrid Search, Index Explained [Milvus Docs](https://milvus.io/docs)

---

## 8) Ingestion Pipeline (End-to-End)

### 8.1 Stages
1) Fetch (already present): crawl ZimLII HTML into `data/raw/...`
2) Parse:
   - Detect doc_type via path/doctype hints
   - Extract doc-level metadata and clean main content
   - Build normalized document object
3) Sectionize & Paragraphize:
   - Build a hierarchical tree (Part/Chapter/Section for acts; Headnote/Body/Paragraphs for judgments)
4) Chunk:
   - Apply strategy per doc_type with sliding window + overlap
   - Compute token estimates and char ranges
5) Embed:
   - Batch requests to OpenAI; attach vectors to chunks
6) Upsert to Milvus:
   - Ensure collection exists; create HNSW index if missing; load
   - Insert `[doc_id, chunk_text, embedding, metadata]`
7) Verify:
   - Count inserted entities; sample search; scalar filter smoke tests
8) Idempotency & Resume:
   - Skip if chunk_id already present (maintain a local manifest mapping or query Milvus for existing `doc_id` if necessary)

### 8.2 Idempotency and Stability
- All IDs are content- and path-derived (hashes) → stable over re-runs
- Use `doc_id` + `chunk_id` as natural keys for dedup/prevent duplicate inserts
- Keep a small local SQLite/JSON manifest (optional) to track ingestion state without coupling to the API runtime

### 8.3 Hybrid Retrieval Readiness
- With metadata populated (`doc_type`, `court`, `date_context`), we can:
  - Filter to relevant doc types per query intent
  - Add recency filtering for judgments
  - Enable score fusion with keyword signals (RRF) later

---

## 9) Data Quality and Cleaning Rules

- Convert all dates to ISO `YYYY-MM-DD` where possible
- Normalize whitespace, quotes, dashes, and section numbering formats
- Remove duplicate paragraphs/headers/footers
- Preserve headings and anchors as metadata; avoid polluting `chunk_text` with navigation
- Detect and log anomalies (e.g., empty sections, extremely long sections)

---

## 10) Collections, Categorization, and Growth

- Start with a single `legal_chunks` collection for simplicity
- Categorization within `metadata.doc_type` + additional metadata for court, chapter, etc.
- If scale demands, split by doc_type later:
  - `legal_chunks_legislation`, `legal_chunks_judgments` for tailored indexes/filters
- Maintain a lightweight `legal_docs` catalog (e.g., in a separate JSON/SQLite or promoted to Milvus as a second collection with scalar fields only) to enable doc-level reporting and health checks

---

## 11) Evaluation and Monitoring (MVP)

- Create a tiny golden set of queries mapped to expected sections/paras; measure Recall@k and spot-check faithfulness
- Log ingestion stats: docs processed, chunks generated, avg tokens/chunk
- Track search latency from Milvus (P50/P95), and embedding batch throughput

---

## 12) Milvus and Retrieval Notes

- Use COSINE metric with HNSW index for semantic search
- Load collection before search; set `ef` at query time for quality/latency tradeoff
- For hybrid retrieval, combine Milvus similarity with keyword-based scoring (e.g., section numbers or exact legal terms) and apply simple score fusion
- Optional future: recency decay for judgments; phrase match and additional index types per the latest Milvus guidance [Milvus Docs](https://milvus.io/docs)

---

## 13) Deliverables and Next Steps

- Implement `scripts/parse_docs.py`:
  - Boilerplate removal, legislation/judgment parsing, metadata extraction, section/paragraph tree
  - Output: `data/processed/docs.jsonl` (one document object per line)
- Implement chunker in the same script or `scripts/chunk_docs.py`:
  - Output: `data/processed/chunks.jsonl` (chunk objects ready for embedding)
- Implement embeddings in `scripts/generate_embeddings.py` (already scaffolded):
  - Read chunks.jsonl → emit `chunks_with_embeddings.jsonl`
- Implement Milvus upsert (extend `scripts/generate_embeddings.py` or a new `scripts/upsert_milvus.py`):
  - Ensure collection exists; create index; upsert batches; verify counts
- Smoke-test retrieval via `api/retrieval.py` with a few queries

This plan ensures we move from raw HTML to a production-ready vector collection in Milvus with stable IDs, robust chunking, and rich metadata that enables precise filtering and fast, accurate retrieval. [Milvus Docs](https://milvus.io/docs)

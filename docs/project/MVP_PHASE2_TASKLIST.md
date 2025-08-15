# RightLine MVP Phase 2 Detailed Task List: RAG MVP

> **Goal**: Deliver a working legal RAG MVP for Zimbabwe. Hybrid retrieval (BM25 + vectors), reranking, strict citation-first answers. Minimal, fast, and observable per `.cursorrules` and `ARCHITECTURE.md`. Build on Phase 1 scaffolding (API/UI/WhatsApp). Total effort: ~45 hours.

> **Guidelines**: 
> - Follow TDD: Write tests first for each task.
> - Async everywhere; enforce latency budgets (<800ms retrieval, <400ms rerank).
> - Privacy: HMAC user IDs, no PII in logs.
> - Eval: Use golden set from task 2.5.1 for all retrieval tasks.
> - Human steps: Marked as "Human: [Action]" for external setup.

## 2.1 Corpus & Ingestion

### 2.1.1 Source acquisition & policy
- [ ] Human: Approve polite crawling plan (respect robots/Terms of Use) for ZimLII. (Effort: 0.25 hours)
- [ ] Implement automated crawl (done): snapshot HTML pages for Labour Act, SIs index, and labour-related judgments into `data/raw/` using `scripts/crawl_zimlii.py`. (Tests: folder populated; Effort: 0.5 hours)
- [ ] Ensure the crawler always fetches the Labour Act URL `https://zimlii.org/akn/zw/act/1985/16/eng@2016-12-31` and downloads any linked PDFs if present. (Tests: file exists in `data/raw/legislation/`; Effort: 0.25 hours)
- [ ] Crawl labour judgments via `/judgments/?q=labour` with unlimited pagination until no results; broaden query terms if needed (employment, dismissal, retrenchment). (Tests: files in `data/raw/judgments/`; Effort: 0.5 hours)
- [ ] Exclude raw snapshots from git (done): add `.gitignore` rule for `data/raw/**` keeping `.gitkeep`. (Acceptance: `git status` clean after crawl; Effort: 0.25 hours)
- [ ] Create/maintain `docs/data/SOURCES.md` documenting sources, access dates, and licensing notes. (Tests: Document exists and is complete; Effort: 0.5 hours)

### 2.1.2 Deterministic section chunking
- [ ] Implement parser in `services/ingestion/parser.py`: Prefer HTML (AKN pages) via BeautifulSoup/lxml to extract sections/subsections and generate stable IDs (`<act_code>:<chapter>:<section>[:<sub>]`). (Tests: Unit test with sample HTML → expected IDs; Effort: 2 hours)
- [ ] Fallback for PDFs (if linked): Use PyMuPDF to extract text and then apply the same section boundary rules. (Tests: Sample PDF → expected IDs; Effort: 1 hour)
- [ ] Metadata extraction: Parse effective dates/versions from AKN metadata (e.g., `eng@YYYY-MM-DD`) or page headers. (Tests: Known dated doc → correct dates; Effort: 0.5 hours)
- [ ] Store chunks in SQLite (extend Phase 1 DB): Tables `documents(id, source_path, source_type, ingest_date)`, `sections(id, doc_id, section_id, text, effective_start, effective_end)`. (Tests: Insert/retrieve chunk; Effort: 1 hour)
- [ ] Idempotency: Hash input + params to skip if unchanged. (Tests: Re-run on same doc → no duplicates; Effort: 0.5 hours)

### 2.1.3 Text extraction pipeline
- [ ] HTML extraction path: Strip navigation/boilerplate; isolate the statute/case content region; extract clean text with structure markers (chapter/section headings). (Tests: Sample HTML → clean content; Effort: 1 hour)
- [ ] PDF fallback path: Use PyMuPDF to extract text when PDFs are available and superior. (Tests: Sample PDF → clean text; Effort: 1 hour)
- [ ] Normalization: Trim whitespace, standardize numbering (e.g., `Section 1A`), remove footnotes and headers/footers; ensure Unicode normalization. (Tests: Noisy input → clean output; Effort: 1 hour)
- [ ] Error handling: Quarantine failed docs with logs; continue batch. (Tests: Bad file → logged error, no crash; Effort: 0.5 hours)

## 2.2 Embeddings & Vector Store

### 2.2.1 Embedding service
- [ ] Human: If using OpenAI, create account, get API key, add to `.env` as `RIGHTLINE_OPENAI_API_KEY`. (Effort: 0.5 hours)
- [ ] Implement embedder in `services/retrieval/embed.py`: Default to `bge-small-en` via sentence-transformers (add dep if needed), optional OpenAI switch via flag. (Tests: Text → vector dim 384; Effort: 1.5 hours)
- [ ] Batch embedding with retries (tenacity) and timeouts; pin model version. (Tests: Batch of 10 → all embedded; Effort: 1 hour)
- [ ] Quantize model (int8) for CPU efficiency. (Tests: Quantized vs full → similar vectors; Effort: 1 hour)

### 2.2.2 Vector DB setup
- [ ] Human: If using Qdrant cloud, create free tier account, get API key/URL, add to `.env` as `RIGHTLINE_QDRANT_URL` and `RIGHTLINE_QDRANT_KEY`. Else, use pgvector (default). (Effort: 0.5 hours)
- [ ] Extend DB schema for embeddings: Add `embedding_vector` column to `section_chunks`; store `embedding_model_version`. (Tests: Schema migration; Effort: 1 hour)
- [ ] Create index: HNSW (M=16, ef_construction=200) for vectors; add date/lang filters. (Tests: Index creation; Effort: 1 hour)
- [ ] Implement async insert/query with aiosqlite/asyncpg. (Tests: Insert vector → kNN returns it; Effort: 1 hour)

## 2.3 Retrieval & Reranking

### 2.3.1 BM25 (lexical) baseline
- [ ] Human: If using Meilisearch, install locally or create cloud instance, add URL/key to `.env`. Else, use PG FTS (flag `USE_PG_FTS=true`). (Effort: 0.5 hours)
- [ ] Implement BM25 in `services/retrieval/bm25.py`: Normalize query (lowercase, legal stop-words). (Tests: Query → tokenized terms; Effort: 1 hour)
- [ ] Search: Top-k=50 with boosting for section titles. (Tests: Known query → relevant top-5; Effort: 1 hour)

### 2.3.2 Hybrid fusion
- [ ] Implement fusion in `services/retrieval/hybrid.py`: BM25@50 + Vec@80, reciprocal rank fusion. (Tests: Fusion scores sensible; Effort: 1.5 hours)
- [ ] Add temporal filter: Query "as at YYYY-MM-DD" filters by effective dates. (Tests: Date-specific query → correct version; Effort: 1 hour)
- [ ] Eval integration: Run on golden set, compute MRR. (Tests: Hybrid > BM25 MRR; Effort: 1 hour)

### 2.3.3 Cross-encoder reranker
- [ ] Human: Download bge-reranker-base model from HuggingFace and store in `models/` (git-lfs). (Effort: 0.5 hours)
- [ ] Implement reranker in `services/retrieval/rerank.py`: ONNX/int8, time budget ≤400ms, early stop if conf>0.9. (Tests: Rerank list → improved order; Effort: 2 hours)
- [ ] Integrate with hybrid: Rerank top-100 fused. (Tests: End-to-end Top-1 improvement; Effort: 1 hour)

## 2.4 Answer Composer (Extractive)

### 2.4.1 Strict 3-line summary with citations
- [ ] Implement composer in `services/api/composer.py`: Select top chunk, generate 3 lines ≤100 chars each. (Tests: Line count/length enforcement; Effort: 1 hour)
- [ ] Inject citations: Act/chapter/section + URLs from metadata. (Tests: 100% answers have cites; Effort: 1 hour)
- [ ] Confidence from rerank scores. (Tests: Low conf → refusal; Effort: 1 hour)

### 2.4.2 Multilingual hinting (optional)
- [ ] Add `lang_hint` param to query endpoint, route to multilingual embedding if set. (Tests: en/sn/nd routing; Effort: 1 hour)
- [ ] Graceful degrade: Fallback to English if no multilingual support. (Tests: No crash on unsupported lang; Effort: 1 hour)

## 2.5 Evaluation & Golden Set

### 2.5.1 Tiny golden set
- [ ] Human: Curate 30-50 QA pairs from corpus (e.g., "minimum wage as at 2023" → specific section IDs). Save as `tests/golden_rag.yaml`. (Effort: 2 hours)
- [ ] Add YAML loader and basic eval functions. (Tests: Loader works; Effort: 1 hour)

### 2.5.2 Regression benchmark script
- [ ] Create `scripts/eval_rag.py`: Run golden set, compute Recall@k/MRR/faithfulness, output JSON. (Tests: Script runs without error; Effort: 1 hour)
- [ ] Add failure case logging. (Effort: 1 hour)

## 2.6 Ops & Observability (MVP)

### 2.6.1 Metrics & traces
- [ ] Add structured logs with timings to all RAG stages. (Tests: Logs present; Effort: 1 hour)
- [ ] Basic metrics (latency, cache hit) via structlog or Prometheus client. (Tests: Metrics exported; Effort: 1 hour)

### 2.6.2 Index jobs
- [ ] CLI in `scripts/index.py`: re-embed/reindex/backfill dates, idempotent. (Tests: Re-run → no duplicates; Effort: 2 hours)

## 2.7 Admin & APIs

### 2.7.1 Minimal admin endpoints
- [ ] Add `/admin/reindex` with API key auth (from `.env`). (Tests: Auth check; Effort: 1 hour)
- [ ] Add `/v1/sections/{id}` endpoint. (Tests: Returns chunk; Effort: 1 hour)

## 2.8 Privacy & Safety

### 2.8.1 PII & logging hygiene
- [ ] HMAC-hash user IDs in all logs/metrics. (Tests: No raw IDs in logs; Effort: 1 hour)
- [ ] Add rate limiter (Redis-based) per hashed user. (Tests: Limits enforced; Effort: 1 hour)

### Phase 2 Summary
- **Total Effort**: ~45 hours
- **Deliverable**: Working RAG MVP with hybrid retrieval, reranking, and evaluation
- **Dependencies**: Builds on Phase 1 API; run `scripts/index.py` after ingestion
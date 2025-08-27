# Retrieval Task List (Legislation-first MVP)

This is the actionable task list that implements the plan in `RETRIEVAL.md`. Tasks are ordered for a fast, reliable MVP and include validation gates. Default surface: Web and WhatsApp.

## 0) Preconditions
- [ ] Milvus collection `legal_chunks` is loaded with 20,469 embeddings (dim=3072)
- [ ] `docs.jsonl` and `chunks.jsonl` metadata is consistent: `doc_type` ∈ {act, ordinance, si, constitution}, `nature`, `year`, `chapter`
- [ ] OpenAI API set; reranker model access decided (OpenAI or local)

## 1) Query Normalization and Intent Detection
- [ ] Implement query normalization util: lowercasing, unicode normalize, quote standardization, punctuation trimming
- [ ] Detect statute+section patterns (e.g., "Labour Act s 12C", "12C of the Labour Act", "Chapter 28:01 section 4")
- [ ] Extract statute candidates from query via fuzzy match against `docs.jsonl` titles/aliases (prepare alias map)
- [ ] Identify intent flags: section_lookup, statute_lookup, general_question

## 2) Multi-Query Expansion (MQR)
- [ ] Generate 3–5 reformulations: synonym swap, expand abbreviations (e.g., SI → Statutory Instrument), paraphrase
- [ ] Add statute-aware expansions when a statute candidate is detected (include full title, short title, chapter)
- [ ] Rate-limit and dedup reformulations (case-insensitive)

## 3) Dense Retrieval (Milvus HNSW)
- [ ] Build/confirm search client using embedding model matching index dim=3072
- [ ] Use metadata filters: `doc_type in {act, ordinance, si, constitution}` and optional `nature` filter from intent
- [ ] Set search params: `top_k_dense=24`, `efSearch≈64`, `metric=COSINE`
- [ ] Ensure `doc_id` diversity (limit max-per-doc at this stage)

## 4) Sparse Retrieval (Pluggable)
- [ ] Add a pluggable sparse search provider interface (BM25 via Elasticsearch/OpenSearch or Tantivy)
- [ ] If provider present, run `top_k_sparse=50` with field boosts (`title^3`, `section_title^2`, `text^1`)
- [ ] Optional: simple fallback sparse using on-disk Tantivy if cloud not ready

## 5) Reciprocal Rank Fusion (RRF)
- [ ] Implement RRF fusion of dense and sparse (and of multiple reformulations)
- [ ] Tune `k` (e.g., 60) and return top 40 pre-rerank candidates with enforced per-`doc_id` cap

## 6) Cross-Encoder Reranking
- [ ] Integrate cross-encoder reranker (OpenAI re-rank or local bge-reranker-base-v2)
- [ ] Rerank top 40 → top 10 using query+chunk pairwise scoring
- [ ] Add statute-title/section-number boosts: if chunk metadata matches statute candidate or section pattern, add small score prior (e.g., +0.05)

## 7) Answer Context Assembly
- [ ] Build context combiner: select top 6–8 chunks with `doc_id` diversity
- [ ] Group consecutive sections from the same statute and merge if contiguous and below token limit
- [ ] Inject structured headers per chunk: Act title, Chapter, Section number/title, Year, Effective date

## 8) Confidence and Guardrails
- [ ] Compute confidence from combined similarity and reranker score distribution, adjust by diversity
- [ ] Set thresholds: `low < 0.62`, `medium 0.62–0.78`, `high ≥ 0.78`
- [ ] Low-confidence behavior: ask clarifying question or suggest specific statute/section candidates

## 9) Structured Shortcuts (Fast Paths)
- [ ] If query explicitly matches `Act + section`, try direct section lookup in `docs.jsonl` index with exact/normalized IDs
- [ ] If query matches statute-only (no section), return table-of-contents style references + ask to narrow

## 10) API Integration (FastAPI)
- [ ] Extend `api/retrieval.py` to accept `intent_flags`, `filters`, and `max_per_doc`
- [ ] Add endpoints for: `search_raw` (debug), `search_best` (fusion+rerank), `statute_lookup` (direct)
- [ ] Ensure logging/telemetry includes: query, expansions, filters, dense/sparse hits, reranker scores, chosen chunks

## 11) WhatsApp and Web UX
- [ ] WhatsApp: compact citations (Act, Chapter, Section) with 2–3 bullet contexts; add “show more” link
- [ ] Web: facets for `doc_type` and `nature`; show confidence badge; highlight matched section numbers and statute titles

## 12) Evaluation Harness
- [ ] Build `scripts/eval_retrieval.py` to run a question set and log hits@k, MRR, coverage by statute
- [ ] Seed initial eval set (20–30 Qs) across Labour, Marriage, Criminal, Constitution, SIs
- [ ] Add targeted regressions for section lookup and SI short notices

## 13) Configuration and Tuning
- [ ] Expose search params via env: `TOP_K_DENSE`, `TOP_K_SPARSE`, `EF_SEARCH`, `TOP_K_FINAL`
- [ ] Feature flags: `ENABLE_SPARSE`, `ENABLE_RERANK`, `ENABLE_RRF`
- [ ] Timeouts and fallbacks: dense only if sparse down; skip rerank if model unavailable

## 14) Observability
- [ ] Add structured logs with correlation IDs for each request
- [ ] Capture latency per stage and cache hit rate (if memoizing expansions)
- [ ] Add minimal analytics dashboard (counts by doc_type, average confidence, top statutes)

## 15) Hardening and Edge Cases
- [ ] Normalize unusual section labels (e.g., 12C, 2A) and map to parsed tree IDs
- [ ] Handle multiple versions: prefer current version, but log if multiple matches
- [ ] Ensure Constitution sections are prioritized when query mentions rights/freedoms/sections

## 16) Release Criteria (MVP)
- [ ] hits@10 ≥ 0.85 on the initial eval set
- [ ] Section lookup accuracy ≥ 0.9 for explicit section queries
- [ ] No statute-level false positives in top 5 for statute-specific queries
- [ ] P95 latency ≤ 1.5s (dense-only) and ≤ 2.3s (with rerank)

## 17) Post-MVP Roadmap Hooks
- [ ] Plug-in interface for learning-to-rank (LTR) with feedback signals
- [ ] Add caching for cross-encoder reranker
- [ ] Enhance alias map from user interactions and auto-mined synonyms



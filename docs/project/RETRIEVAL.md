### RightLine Retrieval Strategy (Legislation-first, state-of-the-art)

This document defines our retrieval approach for the legislation-only MVP and its evolution to a state-of-the-art pipeline optimized for accuracy, speed, and legal reliability across web and WhatsApp surfaces.

## Implementation Status
- [x] Preconditions: Milvus env + data presence checks in retrieval engine
- [x] Query normalization + intent detection (section/chapter extraction, statute alias map)
- [ ] Multi-query expansion + fusion (Task 2)
- [ ] Cross-encoder reranking (OpenAI)
- [ ] API integration and UX polish per plan

## 1) Context and Goals
- Corpus: 405 current-legislation documents (375 Acts, 14 Ordinances, 16 SIs), parsed and chunked into 20,469 chunks in Milvus with 3072-d embeddings (OpenAI text-embedding-3-*</>), enriched with metadata: `doc_type` (act|ordinance|si|constitution), `nature`, `year`, `chapter`, and section titles.
- Confirmed presence: Constitution of Zimbabwe (2013) is in the dataset.
- Goals:
  - Precision-first: return the exact section(s)/clause(s) relevant to the user query
  - Coverage: robust to synonyms (e.g., “maintenance” vs “spousal support”), abbreviations (e.g., “s 7”), and typos
  - Speed: sub-1.5s P95 end-to-end on web; sub-2.0s on WhatsApp
  - Transparency: always show statute title, section path, and AKN URI; deduplicate and diversify sources
  - Guardrails: sensible confidence scoring; fallback clarifying questions if confidence is low

## 2) High-level Retrieval Pipeline

1. Query understanding and normalization
   - Normalize case/punctuation; expand common legal abbreviations (e.g., s/ss, ch/chapter)
   - Extract structured elements:
     - Statute titles/aliases (e.g., “Domestic Violence Act”, “Companies Act”)
     - Chapter references (e.g., “[Chapter 5:16]”)
     - Section references (e.g., “s 7”, “section 7(2)(b)”, SI numbers like “SI 2025-078”)
     - Temporal hints (e.g., “as at 2024”, “current”)
   - Generate up to 3 query variants for robustness:
     - Original user query
     - Keyword-focused variant (remove stopwords, keep legal terms)
     - Synonym/expansion variant (domain synonyms: “maintenance” ~ “spousal support”, “custody” ~ “guardianship”, “GBV” ~ “domestic violence”)

2. Candidate generation (dense first; hybrid-ready)
   - Dense vector search in Milvus (HNSW, COSINE)
     - efSearch: 64 default; elevate to 96–128 for longer/ambiguous queries
     - top_k: 50 per subquery, then fuse
     - Metadata filters:
       - doc_type ∈ {act, ordinance, si, constitution}
       - Optional: filter by `year` if the query includes a time hint; use `chapter` if present
   - Structured shortcut (if explicit Act + Section is parsed):
     - Directly target the specific statute via title/alias and chapter, and constrain to relevant section numbers before/alongside vector search
   - Reciprocal Rank Fusion (RRF):
     - Run vector search for each query variant; fuse with RRF to combine robustness of variants
     - Apply doc_id diversity (e.g., max 3 chunks per document pre-rerank)

3. Re-ranking (precision layer)
   - Cross-encoder re-ranker over top ~50 fused candidates
     - Recommended: bge-reranker-large-v2 or Cohere Rerank v3 (English legal text performs well)
     - Budget/latency profile:
       - Web: rerank top 50 → return top 8
       - WhatsApp: rerank top 40 → return top 6
   - Features for re-ranker context:
     - Include query, chunk text, and the chunk’s section path (e.g., “Part IV > Section 7”)

4. Post-processing and packaging
   - Deduplicate by doc_id and (part, section) path
   - Limit per-document hits (e.g., max 3) to preserve diversity
   - Merge adjacent small sections when necessary to provide full context
   - Always attach:
     - Title, section path, `chapter` (if present), `nature`, `year`
     - AKN URI (from work/expression URIs) for citation
     - Source URL
   - Confidence scoring (for UX and guardrails):
     - Combine normalized dense score (max across variants), RRF rank, and re-rank score
     - Penalize over-concentration from one doc; boost matches with exact section tokens or statute name matches
     - If confidence < threshold (e.g., 0.62), ask a clarifying question rather than fabricating

## 3) Milvus and index configuration
- Vector index: HNSW, COSINE; M=16, efConstruction=256; efSearch set per-query (64–128)
- Scalar inverted indexes: `doc_type`, `nature`, `language`, `court`, `date_context`, `year`, `chapter`
- Embeddings: 3072-d (OpenAI embeddings); cosine similarity; optionally normalize vectors at ingestion (unit length) for consistency

## 4) Metadata and filters we will consistently apply
- Default filter to legislation-only types: `doc_type` in [act, ordinance, si, constitution]
- Optional filter by `nature` for facet pre-selection (e.g., user picks SIs)
- Chapter filter when queries specify [Chapter X:YY]
- Year constraint when user asks “current as at <year>” (prefer latest effective expression; keep previous if needed for historical questions later)

## 5) Domain-specific matching (boosts and heuristics)
- Boost chunks whose `section_path` or text contains:
  - Section patterns: “section 7”, “s 7(2)(b)”, “ss 12–14”
  - Statute short titles or aliases
  - Chapter numbers (e.g., “[Chapter 5:16]”)
- Penalize boilerplate or prefaces (“Preamble”, “Short title”, navigation headings) unless specifically requested
- Apply per-domain synonym maps (seed set):
  - Domestic violence ~ GBV ~ intimate partner violence
  - Maintenance ~ spousal support ~ child support
  - Marriage ~ customary marriage ~ civil marriage
  - Custody ~ guardianship ~ parental rights
  - Arrest ~ detention ~ remand ~ police powers

## 6) Query rewriting and multi-query fusion (details)
- Generate up to 2 expansions using a light LLM prompt (cache expansions per query_key):
  - A keyword-centric variant
  - A synonym-augmented variant leveraging domain map
- Run dense search for all variants; perform RRF fusion:
  - RRF score = Σ 1 / (k + rank_i), with k ≈ 60
  - Keep top 50 fused candidates → re-rank → finalize top N

## 7) Reranking options and costs
- Default: bge-reranker-large-v2 (open-source) or Cohere Rerank v3 (API) depending on deployment constraints
- Latency: budget ~150–300 ms for 50 pairs on web; reduce to 40 for WhatsApp to fit tighter budgets
- Fallback (degraded): vector-only ranking with diversity + boosts when reranker service is unavailable

## 8) Prompting and answer composition
- Provide the model with:
  - The final top-N chunks, each with title, section path, AKN URI, and short citation-friendly header
  - Instruction to cite statute title + section; avoid non-cited claims
  - Instruction to say “I’m not certain” and ask a clarifying question if confidence < threshold
- For WhatsApp: shorter answers with numbered citations; for web: expandable sections with context previews

## 9) Evaluation plan
- Build a small, focused evaluation set covering:
  - Constitution sections (fundamental rights, marriage, due process)
  - Labour/marriage/maintenance/domestic violence/common criminal code sections
  - SI-specific lookups by number and subject
- Metrics:
  - Retrieval: Recall@k (k=5,10), MRR, diversity, time-to-first-byte
  - End QA: answer accuracy with human-graded rubric, citation correctness, hallucination rate
- Iterate on:
  - efSearch, top_k, RRF k, rerank depth, boosts/penalties
  - Synonym map coverage and query rewriting prompts

## 10) Roadmap
- Near-term (MVP+):
  - Implement multi-query fusion (RRF) and cross-encoder reranking
  - Enforce doc_id diversity and better boosts for section numbers/statute titles
  - Expose `nature`/`doc_type` facets on web for quick filtering; default to legislation-only
- Mid-term:
  - Hybrid sparse+dense retrieval: add a BM25/lexical index (Elasticsearch/OpenSearch or Tantivy) and perform RRF across dense and sparse
  - Build statute alias map (short titles, common names, typos) from `docs.jsonl`; use it in structured shortcuts
  - Section-aware direct search: if query includes Act + section, first try direct section lookup
- Longer-term:
  - Domain-tuned embeddings/rerankers (legal corpora)
  - Multi-vector indexing per chunk (title vector + content vector) with field-aware fusion
  - Learning-to-rank using our graded evaluation set

## 11) Implementation notes (no code changes yet)
- `api/retrieval.py` adjustments to plan for:
  - Default filter: `doc_type` in [act, ordinance, si, constitution]
  - Query variant generation + RRF fusion step before rerank
  - Cross-encoder reranker interface (swappable provider)
  - Per-query efSearch tuning (64–128) based on query length/ambiguity
  - Confidence score and low-confidence fallback
- Milvus stays HNSW/COSINE with 3072-d vectors and inverted indexes on scalar filters.

---
This plan keeps MVP reliable and fast while charting a clear path to state-of-the-art retrieval with hybrid search, reranking, and rigorous evaluation.



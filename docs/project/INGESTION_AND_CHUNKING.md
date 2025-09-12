### RightLine v3.0 Ingestion & Chunking — PageIndex OCR + Tree-Aware Strategy

This document describes the enhanced ingestion and chunking pipeline using **PageIndex OCR + Tree Generation** for superior document structure extraction and **node-aligned chunking** for semantic coherence. The system processes PDF legislation from R2 storage with comprehensive metadata extraction and tree-guided chunking strategies.

**Key Technologies**: PageIndex API, Cloudflare R2, OpenAI Embeddings, Milvus Cloud

---

## 1) Enhanced Pipeline Architecture

### **Current State v3.0**:
- **Source Data**: 465 legislation PDFs in Cloudflare R2 (`corpus/sources/legislation/`)
- **OCR Engine**: PageIndex API for superior text extraction and document structure analysis
- **Vector Store**: Milvus Cloud with `text-embedding-3-large` (3072-dim) embeddings
- **Storage**: Cloud-native with R2 for documents/chunks, comprehensive metadata

### **Core Goals v3.0**:
- **Structure-Aware Extraction**: Use PageIndex OCR + Tree to capture document hierarchy
- **Node-Aligned Chunking**: Generate chunks that respect semantic boundaries (sections, subsections)
- **Rich Metadata**: Extract comprehensive legal metadata (AKN URIs, chapters, citations)
- **Cloud-Native Storage**: All data in R2 with proper metadata for fast filtering
- **Semantic Coherence**: Chunks aligned with legal document structure, not arbitrary token windows

---

## 2) PageIndex OCR + Tree Processing

### **PageIndex Integration**:
The system leverages PageIndex's advanced OCR and tree generation capabilities:

**OCR Extraction**:
- **Page-by-page OCR**: High-quality text extraction preserving document structure
- **Global document context**: Unlike traditional OCR, maintains relationships across pages
- **Rich markdown output**: Clean, structured text with proper formatting

**Tree Generation**:
- **Hierarchical structure**: Automatically identifies document hierarchy (Parts, Sections, Subsections)
- **Node-based organization**: Each section becomes a tree node with title, content, and position
- **Semantic boundaries**: Natural breakpoints for chunking aligned with legal structure

**Example Tree Structure**:
```json
{
  "title": "Art Unions Act",
  "node_id": "0000",
  "nodes": [
    {
      "title": "Chapter 25:01", 
      "node_id": "0001",
      "text": "Preamble and chapter content...",
      "nodes": [
        {"title": "1. Short title", "node_id": "0002", "text": "This Act may be cited..."},
        {"title": "2. Interpretation", "node_id": "0003", "text": "In this Act..."}
      ]
    }
  ]
}
```

---

## 3) Normalized Internal Schemas (updated)

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
- Legislation: `nature` (Act|Ordinance|Statutory Instrument), `year`, `chapter`, `act_number`, `part_map`, `section_ids`, `work_uri`, `expression_uri`, `akn_uri`, `effective_start`, `effective_end`
- Judgment: `court`, `case_number`, `neutral_citation`, `date_decided`, `judges`[], `parties`{applicant/respondent or appellant/respondent}, `headnote`, `references`[]

### 3.2 Chunk Schema (Milvus scalar fields + JSON in `metadata`)
- `chunk_id` (string): Stable ID. Recommended: hash of `doc_id + section_path + char_range + text_hash` (SHA256-16)
- `doc_id` (string): FK to document
- `chunk_text` (string): Cleaned text (max ~5000 chars); aim for ~512 token target
- `section_path` (string): Hierarchical path (e.g., `Part II > Section 12A` or `Headnote > Para 3`)
- `start_char` / `end_char` (int): Character offsets into doc canonical text
- `num_tokens` (int): Token estimate used
- `language` (string): e.g., `eng`
- `date_context` (date, nullable): expression effective date
- Promoted scalars for filtering: `doc_type`, `nature`, `year`, `chapter`
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
- Identify hierarchy by headings and anchors: Parts/Chapters/Sections (prefer AKN `section` nodes; fallback to heading heuristics)
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

## 5) Tree-Aware Chunking Strategy v3.0

### **Node-Aligned Chunking Principles**:
The chunking strategy leverages PageIndex tree structure for semantic coherence:

**Core Strategy**:
- **Tree Node = Chunk Boundary**: Each PageIndex tree node becomes a potential chunk
- **Semantic Coherence**: Chunks respect legal document structure (sections, subsections)
- **Size Optimization**: Target 256-512 tokens per chunk for optimal retrieval precision
- **Hierarchical Context**: Preserve parent-child relationships in metadata

### **Chunking Algorithm**:

**Step 1: Tree Traversal**
```python
def chunk_from_tree(tree_nodes, parent_path=""):
    for node in tree_nodes:
        section_path = f"{parent_path} > {node['title']}" if parent_path else node['title']
        node_text = node.get('text', '')
        
        if node_text and estimate_tokens(node_text) >= MIN_TOKENS:
            # Create chunk from node content
            yield create_chunk(node_text, section_path, node['node_id'])
        
        # Recursively process child nodes
        if 'nodes' in node:
            yield from chunk_from_tree(node['nodes'], section_path)
```

**Step 2: Size Management**
- **Small nodes** (<128 tokens): Merge with adjacent nodes in same parent
- **Large nodes** (>512 tokens): Split while preserving paragraph boundaries
- **Optimal nodes** (128-512 tokens): Use as-is for perfect semantic alignment

**Step 3: Metadata Enhancement**
```json
{
  "chunk_id": "a1b2c3d4e5f6g7h8",
  "doc_id": "parent_document_id", 
  "parent_doc_id": "parent_document_id",
  "tree_node_id": "0003",
  "section_path": "Art Unions Act > Chapter 25:01 > 2. Interpretation",
  "chunk_text": "In this Act— \"art union\" means a voluntary association...",
  "num_tokens": 287,
  "doc_type": "act",
  "chapter": "25:01",
  "nature": "Act"
}
```

---

## 6) Enhanced Embeddings & Vector Storage

### **OpenAI Embeddings v3.0**:
- **Model**: `text-embedding-3-large` (3072-dim) for superior semantic understanding
- **Input Processing**: Clean PageIndex markdown text with normalized whitespace
- **Batch Processing**: 64-128 chunks per batch with exponential backoff
- **Cost Optimization**: ~$0.13 per 1M tokens; comprehensive logging for cost tracking

### **Milvus Schema v2.0**:
```python
{
    "chunk_id": "VARCHAR(16)",      # Primary key
    "embedding": "FLOAT_VECTOR(3072)",  # Dense vector
    "num_tokens": "INT64",
    "doc_type": "VARCHAR(20)",      # act, si, ordinance
    "language": "VARCHAR(10)",      # eng
    "parent_doc_id": "VARCHAR(16)", # Link to parent document
    "tree_node_id": "VARCHAR(16)",  # PageIndex node reference
    "chunk_object_key": "VARCHAR(200)", # R2 storage key
    "source_document_key": "VARCHAR(200)", # Original PDF key
    "nature": "VARCHAR(50)",        # Act, Ordinance, SI
    "year": "INT64",               # Legislation year
    "chapter": "VARCHAR(20)",      # Chapter number
    "date_context": "VARCHAR(50)"  # Version date
}
```

---

## 7) Milvus Collections and Indexing (updated)

Primary collection: `legal_chunks`
- Fields (Milvus):
  - `id` (auto primary key, int64)
  - `doc_id` (varchar, max_length ~100)
  - `chunk_text` (varchar, max_length ~5000)
  - `embedding` (float_vector, dim=1536)
  - `metadata` (json)
- Promoted scalar fields for filters: `doc_type`, `nature`, `language`, `date_context`, `year`, `chapter`
- Index: HNSW for `embedding` with COSINE metric (e.g., `M=16`, `efConstruction=256`); load collection for search

Why this design:
- JSON metadata provides flexibility as schemas evolve
- A few promoted scalar fields enable efficient hybrid search (vector + filters)

Milvus docs useful sections:
- Manage Collections, Single-Vector Search, Hybrid Search, Index Explained [Milvus Docs](https://milvus.io/docs)

---

## 8) Ingestion Pipeline (End‑to‑End)

### 8.1 Stages
1) Fetch (done): 405 current‑legislation HTMLs under `data/raw/legislation`.
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

## 12) Retrieval policy and ranking (updated)

For legislation‑only MVP, retrieval should be extractive and citation‑faithful:
- Vector search: COSINE, HNSW, query `ef≈64`; `top_k` 6–8.
- Filters: restrict by `doc_type` in {act, ordinance, si}; optionally filter by `year`/`chapter`.
- Keyword boosts: exact section numbers and statute titles; combine via simple additive boost or RRF.
- Low‑confidence guard: if top score < 0.62 or diversity is low, ask a clarifying question before answering.
- Always include Act/SI + section numbers; prefer AKN URIs.

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

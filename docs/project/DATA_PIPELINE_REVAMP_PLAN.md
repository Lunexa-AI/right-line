# Gweta v2.1: Data Pipeline Revamp — **One Parent Doc per PDF**

**Author**: Gemini Assistant  
**Date**: 2025-09-11  
**Status**: Proposed (revised after stakeholder review)

---

## 1. Executive Summary

Our earlier revamp draft still produced an intermediate “parent document per section”. The product requirement is simpler:

**One PDF ⇒ One parent document (full text) ⇒ Many small chunks**

Hence `parent_doc_id` **must equal** the canonical `doc_id` generated exactly once in `parse_docs.py`. This document replaces the previous proposal and removes every reference to section-level parent docs.

---

## 2. Core Principle: Single Canonical `doc_id`

* Generated in `parse_docs.py` (16-char SHA-256 of R2 key × metadata).
* Immutable — survives the entire pipeline.
* Used **everywhere**:
  * Parent document filename: `corpus/docs/{doc_type}/{doc_id}.json`
  * Each small chunk records `doc_id` **and** `parent_doc_id` (identical).
  * Milvus records store both fields for clarity (but they are equal).

> There is no second hash, no section-level document ID.

---

## 3. Revised Data-Flow Diagram

```mermaid
graph TD
    A[Raw PDF in R2<br/>e.g., art_unions_act.pdf] --> B{parse_docs.py};
    B --> C[Full Parent Document (JSON)<br/><b>doc_id: 4a9fd9...</b>];
    C --> D{chunk_docs.py};
    D --> E[Small Chunk (JSON)<br/><b>chunk_id: 022ed8...</b><br/><b>doc_id / parent_doc_id: 4a9fd9...</b>];
    E --> F{milvus_upsert_v2.py};
    F --> G[Milvus Record<br/><b>chunk_id</b>, <b>parent_doc_id = doc_id</b>];
```

---

## 4. Schema Snapshots

### 4.1 Parent Document (one-to-one with PDF)
Stored at `corpus/docs/act/{doc_id}.json` (or `si/`, `ordinance/`).

```json
{
  "doc_id": "4a9fd9c4eaf81f3e",
  "doc_type": "act",
  "title": "Art Unions Act",
  "language": "eng",
  "content_tree": { ... },
  "extra": { ... }
}
```

### 4.2 Small Chunk

```json
{
  "chunk_id": "022ed8607630d55e",
  "doc_id": "4a9fd9c4eaf81f3e",
  "parent_doc_id": "4a9fd9c4eaf81f3e", // always equal
  "chunk_text": "…",
  "section_path": "Main Content > Page 18"
}
```

### 4.3 Milvus Record (v2 schema excerpt)

```json
{
  "chunk_id": "022ed8607630d55e",
  "parent_doc_id": "4a9fd9c4eaf81f3e",
  "embedding": [3072-d],
  "num_tokens": 256,
  "doc_type": "act"
}
```

---

## 5. Impact on Retrieval

1. Hybrid search returns **chunks**.  
2. For each chunk we take `doc_id` (==`parent_doc_id`).  
3. Fetch the full document at `corpus/docs/{doc_type}/{doc_id}.json` in parallel.  
4. Synthesize answer with rich context.  

No mapping layers, no intermediate lookups — O(1) path construction.

---

## 6. Implementation Plan

### Step 0 — Clean Slate
* Script `scripts/cleanup_processed_data.py` will:
  * Delete R2 prefixes: `corpus/docs/`, `corpus/chunks/`, `corpus/processed/`, `corpus/indexes/`.
  * Drop Milvus collection `legal_chunks_v2`.

### Step 1 — Fix Scripts
1. **`chunk_docs.py`**
   * Delete code that creates section-level parent docs (lines 597-620).  
   * For every generated chunk set `parent_doc_id = doc_id`.  
   * Ensure the `Chunk` Pydantic model includes `parent_doc_id`.
   * If `pageindex_tree` exists, iterate over tree nodes instead of naive pages when building chunks.
   * The chunker **always** walks the PageIndex tree; abort with error if `pageindex_tree` missing to enforce consistency.
2. **`milvus_upsert_v2.py`**
   * Remove `generate_parent_doc_id_from_chunk` helper.  
   * Expect `parent_doc_id` to be present in chunk JSON and pass it through.
3. **`parse_docs.py` → `parse_docs_v3.py`**
   * Always call PageIndex OCR + Tree using `PAGEINDEX_API_KEY`.  Pipeline aborts with clear error if key missing to guarantee high-accuracy extraction.

### Step 2 — Re-run Pipeline
```
```
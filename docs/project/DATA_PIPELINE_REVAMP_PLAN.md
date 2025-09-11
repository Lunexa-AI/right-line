# Gweta v2.1: Data Pipeline Revamp & ID Consistency Plan

**Author**: Gemini Assistant
**Date**: 2025-09-11
**Status**: Proposed

## 1. Executive Summary

Our current data pipeline suffers from a critical ID inconsistency issue, which prevents the "small-to-big" retrieval strategy from working. The root cause is the regeneration of document identifiers at different stages of the pipeline, breaking the relationship between small chunks and their parent documents.

This plan outlines a systematic revamp of the data pipeline, guided by the core principle of **a single, canonical `doc_id` that is generated once and persisted throughout**. By enforcing this principle, we will create a robust, idempotent, and transparent data flow that is essential for a production-grade RAG system.

The plan involves a one-time data cleanup, targeted fixes to the `chunk_docs.py` script, and a final end-to-end test to validate the new, consistent architecture.

## 2. Root Cause Analysis

Our forensic analysis revealed that multiple, disconnected IDs were being used for the same source document:

1.  **`parse_docs.py`**: Correctly generates a stable `doc_id` from the source PDF's metadata (e.g., `4a9fd9c4eaf81f3e`). **This is the canonical ID.**
2.  **`chunk_docs.py` (Parent Docs)**: **Incorrectly generates a new, unrelated hash** for the `parent_doc_id` (e.g., `022ed8607630d55e`) instead of using the `doc_id` from its input.
3.  **`chunk_docs.py` (Small Chunks)**: Correctly uses the original `doc_id` (`4a9fd9c4eaf81f3e`) but was missing a field to link it to the parent document's new, incorrect hash.

This resulted in a broken chain: the small chunks in Milvus and the BM25 index had no reliable way to find their parent documents in R2.

## 3. Core Principle: The Canonical `doc_id`

From this point forward, the entire system will be built around a single source of truth for document identity:

- **Definition**: The `doc_id` is a 16-character SHA256 hash generated once in `parse_docs.py` from a PDF's R2 key and metadata.
- **Immutability**: This ID is considered permanent and immutable for that specific version of the document.
- **Persistence**: The `doc_id` will be passed through and stored in every subsequent data object, including parent documents, small chunks, and Milvus records.
- **`parent_doc_id`**: For the purpose of our small-to-big architecture, the `parent_doc_id` is **always** the same as the canonical `doc_id`.

## 4. The Revamped Pipeline Flow & Schema

This diagram illustrates the new, consistent data flow and the key ID fields at each stage.

```mermaid
graph TD
    A[Raw PDF in R2<br/>e.g., art_unions_act.pdf] --> B{parse_docs.py};
    B --> C[Parsed Document (JSON)<br/><b>doc_id: 4a9fd9...</b><br/>title: "Art Unions Act"];
    C --> D{chunk_docs.py};
    D --> E[Parent Document (JSON)<br/><b>doc_id: 4a9fd9...</b><br/><b>parent_doc_id: 4a9fd9...</b><br/>(Full Section Text)];
    D --> F[Small Chunk (JSON)<br/><b>chunk_id: 022ed8...</b><br/><b>doc_id: 4a9fd9...</b><br/><b>parent_doc_id: 4a9fd9...</b><br/>(256-token text)];
    E --> G[Stored in R2<br/>corpus/docs/act/<b>4a9fd9...</b>.json];
    F --> H[Stored in R2<br/>corpus/chunks/act/<b>022ed8...</b>.json];
    F --> I{milvus_upsert_v2.py};
    I --> J[Milvus Record<br/><b>chunk_id: 022ed8...</b><br/><b>parent_doc_id: 4a9fd9...</b>];
```

### 5. Detailed Schema Definitions

#### Parsed Document (`legislation_docs.jsonl`)
This schema remains largely the same, as it was the source of truth.
```json
{
  "doc_id": "4a9fd9c4eaf81f3e", // Canonical ID
  "doc_type": "act",
  "title": "Art Unions Act",
  "content_tree": { ... }
}
```

#### Parent Document (`corpus/docs/act/{doc_id}.json`)
The filename is now the `doc_id`.
```json
{
  "parent_doc_id": "4a9fd9c4eaf81f3e", // SAME as doc_id
  "doc_id": "4a9fd9c4eaf81f3e",
  "doc_type": "act",
  "section_path": "Main Content > Page 18",
  "text": "Full section text content..."
}
```

#### Small Chunk (`corpus/chunks/act/{chunk_id}.json`)
Crucially, this now contains the `parent_doc_id`.
```json
{
  "chunk_id": "022ed8607630d55e",
  "doc_id": "4a9fd9c4eaf81f3e",
  "parent_doc_id": "4a9fd9c4eaf81f3e", // SAME as doc_id
  "chunk_text": "Small chunk text content...",
  "section_path": "Main Content > Page 18"
}
```

#### Milvus Record
The record in Milvus stores the link back to the parent document.
```
{
  "chunk_id": "022ed8607630d55e",
  "parent_doc_id": "4a9fd9c4eaf81f3e", // Link to parent
  "embedding": [ ... ]
}
```

### 6. Impact on Retrieval Strategy

This consistent data model makes the "small-to-big" retrieval strategy simple, robust, and fast:

1.  **Hybrid Search**: The `RetrievalEngine` performs a hybrid search against Milvus (dense) and the BM25 index (sparse).
2.  **Returns Small Chunks**: The search returns a list of the most relevant **small chunks**. Each of these chunks now reliably contains the correct `doc_id` (which is also the `parent_doc_id`).
3.  **Fetch Parent Docs**: The engine extracts the `doc_id` from each small chunk. It then constructs the R2 key (e.g., `corpus/docs/act/{doc_id}.json`) and fetches the corresponding **parent document** in a parallel batch.
4.  **Synthesize**: The full text from the parent documents is passed to the LLM for answer synthesis, providing rich context while maintaining high search precision.

This eliminates the need for any complex, slow, or unreliable mapping logic.

## 7. Implementation & Execution Plan

We will execute this plan systematically. No step will be skipped.

### **Step 0: Clean Slate**
-   **Action**: Create and run a new script, `scripts/cleanup_processed_data.py`.
-   **Details**:
    -   This script will delete all objects in the R2 bucket under the prefixes:
        -   `corpus/docs/`
        -   `corpus/chunks/`
        -   `corpus/processed/` (clears `legislation_docs.jsonl`)
        -   `corpus/indexes/` (clears `bm25_index.pkl`)
    -   It will also connect to Milvus and drop the existing `legal_chunks_v2` collection.
-   **Outcome**: A completely clean slate, ready for a fresh, consistent data run. `corpus/sources/` will remain untouched.

### **Step 1: Fix the Pipeline Scripts**
-   **Action**: Modify `scripts/chunk_docs.py`.
-   **Details**:
    -   In `chunk_legislation`, change the `parent_doc_id` generation. Instead of creating a new hash, it will be set to the `doc_id` passed in from the parsed document.
    -   Add the `parent_doc_id` field to the `Chunk` Pydantic model.
    -   Ensure this new `parent_doc_id` field is populated for every small chunk created.
-   **Action**: Verify `scripts/parse_docs.py` and `scripts/milvus_upsert_v2.py`.
-   **Details**: No changes are expected for `parse_docs.py`. The `milvus_upsert_v2.py` script's logic should be simplified as it no longer needs to generate a `parent_doc_id`; it will just read it from the chunk data.

### **Step 2: Full Pipeline Re-run**
-   **Action**: Execute the data pipeline scripts in the correct order.
    1.  `python scripts/parse_docs.py` (To recreate `legislation_docs.jsonl`)
    2.  `python scripts/chunk_docs.py` (To create consistent parent docs and chunks)
    3.  `python scripts/milvus_upsert_v2.py` (To populate Milvus with new data)
    4.  `python scripts/build_bm25_index.py` (To create the new BM25 index)
-   **Outcome**: All data in R2 and Milvus will be regenerated with 100% ID consistency.

### **Step 3: Robust End-to-End Testing**
-   **Action**: Execute a comprehensive test script.
-   **Details**:
    -   The test will query the API with multiple, varied search terms.
    -   It will verify that for each query:
        -   Relevant results are returned.
        -   The "small-to-big" expansion has a success rate of 100%.
        -   The content of the expanded parent documents is correct and substantial.
-   **Outcome**: Full confidence that the retrieval system is working exactly as designed before moving to the next task.

## 8. Overlooked Considerations

-   **Data Versioning**: The current `doc_id` is based on the R2 key and metadata. If a source PDF is updated (replaced at the same key), its `doc_id` will not change. For true idempotency, we should consider incorporating a content hash (e.g., MD5 of the PDF) into the `doc_id` generation in `parse_docs.py`. This is a future improvement to consider.
-   **TDD Improvements**: This incident has highlighted a gap in our testing strategy. We must create a new suite of **end-to-end data integrity tests**. These tests would run on a small, controlled set of source documents, execute the entire pipeline (`parse` -> `chunk` -> `upsert`), and then verify that all generated IDs and relationships are 100% consistent. This will prevent a similar issue from ever happening again.

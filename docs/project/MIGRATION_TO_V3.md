# Migration to V3 Schema (PageIndex Integration)

## Overview
The V3 schema introduces PageIndex OCR + Tree processing for superior chunking and retrieval. Key changes:
- One-parent-doc strategy: `parent_doc_id` always equals `doc_id`.
- Added `tree_node_id` and `section_path` for hierarchical awareness.
- Full parent docs stored in R2 with `pageindex_markdown` and `pageindex_tree`.
- Removed intermediate "section parents" from V2.

## Key Differences from V2
- **Chunk Model (ChunkV3)**:
  - `parent_doc_id`: Now always `doc_id` (no separate parent generation).
  - New: `tree_node_id` (e.g., "0006").
  - New: `section_path` (e.g., "Part II > §3").
  - Removed: `start_char`, `end_char` (not needed with tree alignment).
  - Simplified metadata.

- **Parent Document (ParentDocumentV3)**:
  - Stores full `pageindex_markdown` instead of raw text.
  - Includes `pageindex_tree` for future hierarchical queries.
  - Enhanced metadata: `title`, `chapter`, `canonical_citation`.

- **Milvus Schema**:
  - Added `tree_node_id`.
  - `parent_doc_id` now directly references the canonical doc_id.

## Migration Steps Performed
1. Dropped V2 Milvus collection.
2. Created V3 collection with updated schema (init-milvus-v2.py, but with tree_node_id).
3. Reparsed docs using parse_docs_v3.py (PageIndex API).
4. Chunked with tree-awareness (chunk_docs.py).
5. Upserted to V3 (milvus_upsert_v2.py).
6. Updated retrieval to fetch `pageindex_markdown` (retrieval.py).

## Backward Compatibility
- Old code can still import `Chunk` / `ParentDocument` (aliased to V3 versions).
- `chunk_text` and core fields remain compatible.
- Gradually refactor to use new fields like `section_path` for better answers.

## Testing
- Run full pytest suite after migration.
- Manual e2e: Query via /api/v1/test-query and verify results include tree metadata.

For questions, see INGESTION_AND_CHUNKING.md.

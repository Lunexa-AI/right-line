# Gweta v2.0 Migration Task List

This document outlines the detailed tasks required to upgrade the Gweta API from its current stateless RAG implementation to the full v2.0 Agentic Architecture.

---

## Phase 1: Foundational Changes (Authentication, State & Data Models)

*Goal: Introduce user identity, state management, and the necessary data structures before modifying the core RAG pipeline.*

### 1.1. Firebase Integration & Authentication
-   **Task**: [x] Set up a new Firebase project.
-   **Task**: [x] Configure Firebase Authentication (Email/Password, Github and Google providers).
-   **Task**: [x] Implement Firestore database and define initial security rules to lock down access.
-   **Task**: [x] Create a `libs/firebase` module to encapsulate Firebase Admin SDK initialization and client access.

### 1.2. API Layer: Authentication Middleware
-   **Task**: [x] Create a FastAPI dependency (`get_current_user`) that verifies the `Authorization: Bearer <token>` header against Firebase Auth.
-   **Task**: [x] This dependency should decode the JWT and return the user's Firebase UID and profile information.
-   **Task**: [x] Protect all relevant endpoints (`/api/v1/query`, `/api/v1/feedback`, etc.) with this new authentication dependency.
-   **Task**: [x] Update `api/models.py` to include user identification in requests and responses where necessary.

### 1.3. Firestore Data Models & State Management
-   **Task**: [x] Define Pydantic models for the Firestore collections (`User`, `Session`, `Message`, `Feedback`).
-   **Task**: [x] Implement helper functions to manage session history:
    -   `get_session_history(user_id, session_id)`: Fetches the last N messages.
    -   `add_message_to_session(user_id, session_id, role, content)`: Adds a new user or assistant message.
-   **Task**: [x] Refactor the feedback endpoint (`/api/v1/feedback`) to store feedback in the `feedback` Firestore collection, linked to a `user_id`.

### 1.4. User Management
-   **Task**: [x] Implement a `POST /api/v1/users/me` endpoint to create a user profile in Firestore upon initial signup.

# -----------------------------------------------------------------------------
#  Phase 2: Cloud-Native Data Plane (R2 + Milvus)
# -----------------------------------------------------------------------------

### 2.1. Cloudflare R2 Setup
-   **Task**: [x] Create a Cloudflare account and set up a new R2 bucket (e.g., `gweta-prod-documents`).
-   **Task**: [x] Generate R2 API credentials (Access Key ID & Secret Access Key).
-   **Task**: [x] Securely configure these credentials as environment variables for both local development (`.env`) and the production environment (Render secrets).

### 2.2. Refactor Data Ingestion & Basic Processing Scripts (COMPLETED)
-   **Task**: **Crawlers (`scripts/crawl_*.py`)**:
    -   [x] Modify the crawlers to download source documents as PDFs (not HTML).
    -   [x] Integrate the `boto3` library to upload each downloaded PDF directly to a `sources/` prefix in the R2 bucket.
-   **Task**: **Parsing & Chunking (`scripts/parse_docs.py`, `scripts/chunk_docs.py`)**:
    -   [x] Update the scripts to read source PDFs from the R2 bucket instead of the local `data/raw/` directory.
    -   [x] After chunking, upload each individual text chunk as a separate object to a `chunks/` prefix in the R2 bucket. This replaces writing to `data/processed/`.
    -   (All subtasks above are **done** and validated.)

### 2.3. Advanced Chunking Strategy – "Small-to-Big" (COMPLETED)
-   **Task**: [x] Update `scripts/chunk_docs.py` to implement the small-to-big strategy:
    1.  Produce *small* chunks (~256 tokens) with an added `parent_doc_id` field.
    2.  Generate *big* parent-document records (full sections / pages) and store them in a new `docs.jsonl` catalog on R2.
-   **Task**: [x] Ensure every small chunk carries a `parent_chunk_object_key` so it can be expanded to its parent later.
-   **Task**: [x] Upload both the new `chunks` and `docs` artifacts to R2.
-   **Task**: [x] Run the fast-progress check to verify 100 % coverage.

### 2.4. Embedding Generation & Milvus Upsert (COMPLETED)
-   **Task**: [x] Design the *new* Milvus collection schema (v2):
    -   `chunk_id` (PK, string)
    -   `embedding` (vector-float32[dim])
    -   `num_tokens` (int)
    -   `doc_type` (string<20)
    -   `language` (string<10)
    -   `parent_doc_id` (string<16)
    -   `chunk_object_key` (string)
    -   `source_document_key` (string)
    -   Additional lightweight meta fields (`nature`, `year`, `chapter`, `date_context`)
-   **Task**: [x] Re-initialize Milvus (drop old collection, create new one).
-   **Task**: [x] Update `scripts/milvus_upsert_v2.py`:
    -   Read the *small* chunks from R2.
    -   Generate embeddings (OpenAI text-embedding-3-large) in batches.
    -   Upsert into Milvus using the new schema with deduplication logic.
-   **Task**: [x] Run the full embedding→upsert pipeline and verify collection counts (56,051 entities loaded successfully).

### 2.7. PageIndex OCR & Tree Integration (MANDATORY)
-   **Task**: [ ] Configure `PAGEINDEX_API_KEY` in all environments (local, Render, CI).  Pipeline fails fast if key missing.*
-   **Task**: [ ] Create a PoC script (`scripts/pageindex_ingest_poc.py`) to upload 5 PDFs from R2, fetch markdown + tree, and log stats.*
-   **Task**: [ ] Refactor `scripts/parse_docs.py` → `parse_docs_v3.py`:
    1.  When API key is present, call PageIndex OCR & Tree.
    2.  Persist `pageindex_doc_id`, `pageindex_markdown`, and `pageindex_tree` in parent doc `extra`.
    3.  Fallback to PyMuPDF extraction if key absent.
-   **Task**: [ ] Refactor `scripts/chunk_docs.py` to **always** walk PageIndex tree for chunk boundaries.  Each chunk’s `section_path` becomes the node path. Parsing must abort if tree absent.*
-   **Task**: [ ] Update `Chunk` Pydantic model to include optional `tree_node_id`.
-   **Task**: [ ] Update end-to-end tests to mock PageIndexClient and verify new fields.*

### 2.5. Refactor API Backend for R2 (Retrieval Layer) (COMPLETED)
-   **Task**: [x] **Retrieval Logic (`api/retrieval.py`)**:
    -   Modify the `RetrievalEngine` to fetch chunk *content* from R2.
    -   After getting search results from Milvus, extract the `chunk_object_key` from the metadata.
    -   Use `boto3` to perform a batch `GetObject` operation from R2 to fetch the text for all candidate chunks in parallel, minimizing latency.
-   **Task**: [x] **Implement Secure Document Serving Endpoint**:
    -   Create a new router, `api/routers/documents.py`.
    -   Define a `GET /api/v1/documents/{document_key}` endpoint, protected by the existing user authentication dependency.
    -   The endpoint uses `boto3` to fetch the requested PDF from R2 and return it to the client using a `StreamingResponse`.

### 2.6. Frontend Integration for Document Viewing
-   **Task**: The frontend must be updated to change how it links to source documents.
-   **Task**: Source links in the UI should now point to the new `/api/v1/documents/{document_key}` endpoint.
-   **Task**: Implement an in-app PDF viewer (using an `<iframe>` or a library like `react-pdf`) that uses this API endpoint as its source, allowing users to view citations without leaving the application. Add support for jumping to a specific page using URL fragments (`#page=...`).

## Phase 3: Retrieval Quality – Hybrid, Reranking & Context Assembly


### 3.1. Retrieval Strategy: Implement Robust Hybrid Search (COMPLETED)
-   **Task**: [x] Replace the `SimpleSparseProvider` in `api/retrieval.py` with a proper BM25 implementation.
    -   ✅ Using `rank-bm25` library with production optimizations.
    -   ✅ Created `scripts/build_bm25_index.py` to build and save BM25 index from R2 corpus.
    -   ✅ The new `ProductionBM25Provider` loads index file for lightning-fast searching (0.49ms for 1K corpus).
-   **Task**: [x] Modified the `RetrievalEngine`'s `retrieve` method:
    -   ✅ Searches for the best *small chunks* using both Milvus (dense) and BM25 (sparse) providers.
    -   ✅ Uses optimized RRF (Reciprocal Rank Fusion) to combine results with performance monitoring.
    -   ✅ **Crucially**, after identifying top-k small chunks, fetches corresponding **parent documents** for rich synthesis context.
    -   ✅ Added comprehensive observability, performance monitoring, and alerting.
    -   **NEW**: [ ] After top-K parent docs are identified, call PageIndex Retrieval API (`submit_query`) in parallel and merge returned tree nodes via RRF.

### 3.2. Reranking Implementation
-   **Task**: Implement a real reranker. The `BGE-reranker-v2` (cross-encoder) is a strong choice. This can be run locally using a library like `sentence-transformers`.
-   **Task**: Replace the placeholder `OpenAIReranker` in `api/retrieval.py` with this new implementation.
-   **Task**: The reranker should take the combined candidate chunks from the hybrid search step (before parent document retrieval) and re-score them against the query to find the most relevant ones.

## Phase 4: The Agentic Loop

*Goal: Restructure the query processing flow from a linear chain into an intelligent, multi-step agentic loop.*

### 4.1. Create the Core Agentic Engine
-   **Task**: Create a new module, e.g., `api/agent.py`, to house the `AgenticEngine`.
-   **Task**: The `AgenticEngine` will be the new entry point for processing a query, replacing the direct call to `retrieval.retrieve` in the router. It will orchestrate the entire Plan -> Retrieve -> Rerank -> Synthesize flow.

### 4.2. Implement the Query Planner
-   **Task**: Inside the `AgenticEngine`, create the "Query Planner" component. This will be an LLM-powered function.
-   **Task**: The planner's first responsibility is **Query Transformation**.
    -   It must take the user's raw query and the short-term session history (from Firestore).
    -   It will make an LLM call (e.g., to `gpt-4o-mini`) to rewrite the query into a clear, standalone question.
    -   Implement **HyDE (Hypothetical Document Embeddings)**: have the planner generate a hypothetical answer to the rewritten query. This hypothetical answer is then used for the embedding search, improving retrieval quality.
-   **Task**: (Stretch Goal) Add query decomposition capabilities for more complex questions.

### 4.3. Refactor the Query Router
-   **Task**: Update the `/api/v1/query` endpoint in `api/routers/query.py`.
-   **Task**: It should now:
    1.  Get the current user from the authentication dependency.
    2.  Fetch the session history from Firestore.
    3.  Instantiate and run the new `AgenticEngine` with the query and session history.
    4.  Store the final answer back into the session history.
    5.  Return the response.

### 4.4. Update Synthesis Prompt
-   **Task**: Modify the `_build_prompt` method in `api/composer.py`.
-   **Task**: The system prompt for the synthesis model must now accept and use both the **long-term user profile summary** and the **short-term session history** to provide a more personalized and context-aware answer.
-   **Task**: Reinforce the instructions to ground the answer strictly in the provided (parent document) context and to cite sources meticulously.

## Phase 5: Long-Term Memory & Final Polish

*Goal: Implement the background processes for personalization and ensure the system is robust.*

### 5.1. Long-Term Memory Summarizer
-   **Task**: Create a background process (e.g., a Vercel Cron Job or a scheduled GitHub Action) that periodically processes user session histories.
-   **Task**: This process will use an LLM to summarize conversation threads into a `long_term_summary` field in the user's profile in Firestore (e.g., "User is interested in corporate law and PBCs.").
-   **Task**: Ensure this summary is loaded and used by the agentic planner and synthesis components.

### 5.2. Testing & Documentation
-   **Task**: Update existing unit and integration tests to account for the new authentication flow and the agentic architecture. Mocks for Firebase will be essential.
-   **Task**: Write new tests for the agentic planner, the BM25 provider, and the reranker.
-   **Task**: Update the API documentation (e.g., in `docs/api/README.md`) to reflect the new authentication requirements and session management.

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

## Phase 2: Upgrading the RAG Pipeline

*Goal: Systematically replace the components of the existing RAG pipeline with the more advanced, multi-strategy components defined in the v2.0 architecture.*

### 2.1. Chunking Strategy: Small-to-Big
-   **Task**: Modify the data ingestion scripts (`scripts/chunk_docs.py`) to implement the "small-to-big" strategy.
-   **Task**: Each small chunk (e.g., 256 tokens) must contain a reference (`parent_doc_id`) to its larger parent document. The full documents must be stored in a way they can be easily retrieved by this ID (e.g., in a JSONL file or a simple key-value store).
-   **Task**: Rerun the ingestion pipeline to generate the new `chunks.jsonl` and `docs.jsonl` artifacts.

### 2.2. Retrieval Strategy: Implement Robust Hybrid Search
-   **Task**: Replace the `SimpleSparseProvider` in `api/retrieval.py` with a proper BM25 implementation.
    -   The `rank-bm25` library is a good candidate.
    -   Create a pre-processing script to build and save the BM25 index from the corpus to a file.
    -   The new sparse provider will load this index file for searching.
-   **Task**: Modify the `RetrievalEngine`'s `retrieve` method:
    -   It should first search for the best *small chunks* using both the Milvus (dense) and the new BM25 (sparse) providers.
    -   Continue using RRF (Reciprocal Rank Fusion) to combine the results.
    -   **Crucially**, after identifying the top-k small chunks, it must then fetch their corresponding **parent documents**. These full-text parent documents will be the context passed to the synthesis stage.

### 2.3. Reranking Implementation
-   **Task**: Implement a real reranker. The `BGE-reranker-v2` (cross-encoder) is a strong choice. This can be run locally using a library like `sentence-transformers`.
-   **Task**: Replace the placeholder `OpenAIReranker` in `api/retrieval.py` with this new implementation.
-   **Task**: The reranker should take the combined candidate chunks from the hybrid search step (before parent document retrieval) and re-score them against the query to find the most relevant ones.

## Phase 3: The Agentic Loop

*Goal: Restructure the query processing flow from a linear chain into an intelligent, multi-step agentic loop.*

### 3.1. Create the Core Agentic Engine
-   **Task**: Create a new module, e.g., `api/agent.py`, to house the `AgenticEngine`.
-   **Task**: The `AgenticEngine` will be the new entry point for processing a query, replacing the direct call to `retrieval.retrieve` in the router. It will orchestrate the entire Plan -> Retrieve -> Rerank -> Synthesize flow.

### 3.2. Implement the Query Planner
-   **Task**: Inside the `AgenticEngine`, create the "Query Planner" component. This will be an LLM-powered function.
-   **Task**: The planner's first responsibility is **Query Transformation**.
    -   It must take the user's raw query and the short-term session history (from Firestore).
    -   It will make an LLM call (e.g., to `gpt-4o-mini`) to rewrite the query into a clear, standalone question.
    -   Implement **HyDE (Hypothetical Document Embeddings)**: have the planner generate a hypothetical answer to the rewritten query. This hypothetical answer is then used for the embedding search, improving retrieval quality.
-   **Task**: (Stretch Goal) Add query decomposition capabilities for more complex questions.

### 3.3. Refactor the Query Router
-   **Task**: Update the `/api/v1/query` endpoint in `api/routers/query.py`.
-   **Task**: It should now:
    1.  Get the current user from the authentication dependency.
    2.  Fetch the session history from Firestore.
    3.  Instantiate and run the new `AgenticEngine` with the query and session history.
    4.  Store the final answer back into the session history.
    5.  Return the response.

### 3.4. Update Synthesis Prompt
-   **Task**: Modify the `_build_prompt` method in `api/composer.py`.
-   **Task**: The system prompt for the synthesis model must now accept and use both the **long-term user profile summary** and the **short-term session history** to provide a more personalized and context-aware answer.
-   **Task**: Reinforce the instructions to ground the answer strictly in the provided (parent document) context and to cite sources meticulously.

## Phase 4: Long-Term Memory & Final Polish

*Goal: Implement the background processes for personalization and ensure the system is robust.*

### 4.1. Long-Term Memory Summarizer
-   **Task**: Create a background process (e.g., a Vercel Cron Job or a scheduled GitHub Action) that periodically processes user session histories.
-   **Task**: This process will use an LLM to summarize conversation threads into a `long_term_summary` field in the user's profile in Firestore (e.g., "User is interested in corporate law and PBCs.").
-   **Task**: Ensure this summary is loaded and used by the agentic planner and synthesis components.

### 4.2. Testing & Documentation
-   **Task**: Update existing unit and integration tests to account for the new authentication flow and the agentic architecture. Mocks for Firebase will be essential.
-   **Task**: Write new tests for the agentic planner, the BM25 provider, and the reranker.
-   **Task**: Update the API documentation (e.g., in `docs/api/README.md`) to reflect the new authentication requirements and session management.

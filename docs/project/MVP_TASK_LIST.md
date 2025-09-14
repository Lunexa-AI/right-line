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

### 2.7. PageIndex OCR & Tree Integration (MANDATORY) (COMPLETED)
-   **Task**: [x] Configure `PAGEINDEX_API_KEY` in all environments (local, Render, CI).  Pipeline fails fast if key missing.*
-   **Task**: [x] Create enhanced `parse_docs_v3.py` with PageIndex OCR + Tree integration, comprehensive metadata extraction, and R2 object metadata.*
-   **Task**: [x] Implement tree-aware chunking in `chunk_docs.py`:
    1.  Walk PageIndex tree structure for semantic chunk boundaries.
    2.  Generate node-aligned chunks with `tree_node_id` and hierarchical `section_path`.
    3.  Ensure `parent_doc_id = doc_id` for consistent ID linking.
-   **Task**: [x] Update `Chunk` Pydantic model to include `parent_doc_id` and `tree_node_id` fields.*
-   **Task**: [x] Enhanced Milvus schema v3.0 with `tree_node_id` field and updated upsert pipeline.*
-   **Task**: [x] Verified end-to-end pipeline: Parse (5 docs) → Chunk (33 chunks) → Embed → Milvus → BM25 → Retrieval with perfect quality.*

### 2.5. Refactor API Backend for R2 (Retrieval Layer) (COMPLETED)
-   **Task**: [x] **Retrieval Logic (`api/retrieval.py`)**:
    -   Modify the `RetrievalEngine` to fetch chunk *content* from R2.
    -   After getting search results from Milvus, extract the `chunk_object_key` from the metadata.
    -   Use `boto3` to perform a batch `GetObject` operation from R2 to fetch the text for all candidate chunks in parallel, minimizing latency.
-   **Task**: [x] **Implement Secure Document Serving Endpoint**:
    -   Create a new router, `api/routers/documents.py`.
    -   Define a `GET /api/v1/documents/{document_key}` endpoint, protected by the existing user authentication dependency.
    -   The endpoint uses `boto3` to fetch the requested PDF from R2 and return it to the client using a `StreamingResponse`.

### 2.6. Frontend Integration for Document Viewing (to be implemented in frontend)
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

### 3.2. Reranking Implementation (COMPLETED)
-   **Task**: [x] Implement BGE-reranker-base using `sentence-transformers` library for production-grade reranking.
-   **Task**: [x] Integrate reranker into `api/retrieval.py` pipeline after RRF fusion but before parent document expansion.
-   **Task**: [x] The reranker processes candidate chunks from hybrid search and re-scores them for improved relevance ranking.
-   **Task**: [x] Added comprehensive logging and performance monitoring for reranking operations.

## Phase 4: Building the Agentic Core

*Goal: Implement the state-of-the-art agentic core using LangGraph for robust, observable, and high-performance reasoning.*

> Responsibility overview (LangGraph vs You)
> - **LangGraph provides**: StateGraph runtime, node execution + state merge, checkpointing interface, tracing hooks, minimal streaming support via LangChain integration.
> - **You implement**: `AgentState` schema, node functions, routing/edges, concrete checkpointer wiring, SSE endpoint and event protocol, tool integrations (retrieval, reranker, R2 fetch), caching and guardrails, latency budgets.

### 4.1. Foundational Setup: State & Orchestrator
-   **Task**: **Refactor Repo Structure**:
    -   [ ] Create new directories: `api/schemas`, `api/orchestrators`, `api/tools`, `api/composer`.
    -   [ ] Move `api/retrieval.py` to `api/tools/retrieval_engine.py`.
    -   [ ] Move reranker logic to `api/tools/reranker.py`.
    -   [ ] Move prompt logic from `api/composer.py` to `api/composer/prompts.py` and rename the file to `synthesis.py`.
    -   **Acceptance**: App boots; imports resolve; old endpoints unchanged.
    -   **Tests**: `pytest -k "imports and routers"` runs without failures.
    -   **Responsibilities**:
        -   Framework: N/A
        -   You: File moves, imports, path updates, CI green.
    -   **Sanity checklist**:
        -   [ ] No circular imports; [ ] `uvicorn` starts; [ ] `/docs` loads; [ ] `/api/v1/query` still auth-protected.
-   **Task**: **Define Agent State**:
    -   [ ] Create `api/schemas/agent_state.py`.
    -   [ ] Implement the `AgentState` Pydantic model (v1) including `trace_id`, `raw_query`, `session_history_ids`, `jurisdiction`, `date_context`, `rewritten_query`, `hypothetical_docs`, `sub_questions`, `candidate_chunk_ids`, `reranked_chunk_ids`, `parent_doc_keys`, `final_answer`, `cited_sources`.
    -   **Acceptance**: JSON-serializable, < 8 KB typical.
    -   **Tests**: Round-trip schema tests; rejects oversize arrays; validates enums.
    -   **Responsibilities**:
        -   Framework: State merge mechanics, validation at runtime.
        -   You: Schema design, versioning, validators, migrations when evolving.
    -   **Sanity checklist**:
        -   [ ] State dumps to JSON; [ ] Enum fields validated; [ ] Oversized inputs rejected.
-   **Task**: **Implement LangGraph Orchestrator**:
    -   [ ] Create `api/orchestrators/query_orchestrator.py`.
    -   [ ] Define `StateGraph` with `AgentState`.
    -   [ ] Implement placeholder nodes: `route_intent`, `rewrite_expand`, `retrieve_concurrent`, `rerank`, `expand_parents`, `synthesize_stream`.
    -   [ ] Add edges and conditional routing logic.
    -   [ ] Integrate `MemorySaver` checkpointer (in-memory for now).
    -   [ ] Add `graph.draw_svg()` export script to `docs/diagrams/`.
    -   **Acceptance**: Graph compiles and can run a no-op flow.
    -   **Tests**: Node stubs unit-tested; compile-time test ensures edges consistent.
    -   **Responsibilities**:
        -   Framework: Graph runtime, node scheduling, state update merge.
        -   You: Node functions, edges, checkpointer selection and wiring, SVG export.
    -   **Sanity checklist**:
        -   [ ] Entry node set; [ ] All nodes reachable; [ ] Conditional routes covered; [ ] SVG exported.

### 4.2. Implement Agent Nodes: Pre-Processing
-   **Task**: **Intent Router Node**:
    -   [ ] Implement heuristics for `summarize`, `conversational`, `qa`, jurisdiction/date detection.
    -   [ ] Fallback to mini-LLM (≤ 200 tokens, temp 0.0) when ambiguous.
    -   **Acceptance**: P50 < 70 ms heuristics; P95 < 250 ms with mini-LLM.
    -   **Tests**: Heuristic unit tests; LLM stubbed with fixtures.
    -   **Responsibilities**:
        -   Framework: Node execution + merge.
        -   You: Heuristics, LLM call, timeouts, outputs (`intent`, `jurisdiction`, `date_context`).
    -   **Sanity checklist**:
        -   [ ] Ambiguous inputs route to fallback; [ ] Deterministic at temp=0; [ ] Timeouts enforced.
-   **Task**: **Rewrite & Expand Node**:
    -   [ ] Implement history-aware rewrite.
    -   [ ] Implement **Multi-HyDE** (3–5 hypotheticals, ≤ 120 tokens each) in parallel with timeouts.
    -   [ ] Optional sub-question decomposition (cap 3) behind heuristics.
    -   **Acceptance**: Produces rewrite + ≥ 2 hypotheticals under 450 ms P95.
    -   **Tests**: Async timeout tests; determinism at temp 0; schema constraints.
    -   **Responsibilities**:
        -   Framework: Node execution + merge.
        -   You: Rewrite prompt, parallel fan-out, caps/timeouts, output fields.
    -   **Sanity checklist**:
        -   [ ] Caps respected; [ ] On timeout, degrade to rewrite-only; [ ] No empty outputs.

### 4.3. Implement Agent Nodes: Retrieval & Synthesis
-   **Task**: **Integrate Retrieval as a Tool (The LangChain Way)**:
    -   [ ] **Refactor** the existing `RetrievalEngine` from `api/tools/retrieval_engine.py` into a composable LangChain `Runnable` (LCEL chain). This is a rewrite, not just an integration.
    -   [ ] Wrap the Milvus and BM25 retrievers in standard `BaseRetriever` interfaces.
    -   [ ] Use `EnsembleRetriever` to run both retrievers in parallel and fuse results with RRF.
    -   [ ] Use `ContextualCompressionRetriever` with a `CrossEncoderReranker` to handle the reranking step.
    -   [ ] Use a `RunnableLambda` for the final "Small-to-Big" step of fetching parent documents from R2.
    -   [ ] In the `retrieve_concurrent` node, invoke this unified `Runnable` chain.
    -   **Acceptance**: The entire retrieval pipeline is a single, traceable LCEL `Runnable`. P95 retrieval ≤ 350 ms. LangSmith shows a hierarchical trace for the ensemble, compression, and parent fetch steps.
    -   **Tests**: Unit test the custom `BM25Retriever` wrapper. Integration test the full LCEL chain with mocked retrievers and rerankers.
    -   **Responsibilities**:
        -   Framework: `EnsembleRetriever`, `ContextualCompressionRetriever`, `Runnable` protocols, automatic tracing.
        -   You: Wrapping your existing logic (BM25, R2 fetch) into standard interfaces and composing them into a final LCEL chain.
    -   **Sanity checklist**:
        -   [ ] Chain can be invoked; [ ] LangSmith trace is hierarchical; [ ] RRF fusion is correct; [ ] K capped before reranking.
-   **Task**: **Rerank & Parent Expansion Nodes**:
    -   [ ] `rerank`: call BGE reranker; cache scores; timeout ≤ 180 ms.
    -   [ ] `expand_parents`: fetch parent docs (M=8–12); context bundler with token caps.
    -   **Acceptance**: P95 rerank+expand ≤ 400 ms; context contains ≥ 2 authoritative sources.
    -   **Tests**: Reranker cache hit path; bundler token-cap enforcement.
    -   **Responsibilities**:
        -   Framework: Node execution + merge.
        -   You: Reranker cache, R2 fetch batching, bundling policy, source prioritization.
    -   **Sanity checklist**:
        -   [ ] Cache hit rate measured; [ ] Token cap enforced; [ ] Source allow-list applied.
-   **Task**: **Synthesis Node**:
    -   [ ] Build structured prompt and stream tokens.
    -   [ ] Implement **AttributionGate** and **QuoteVerifier**.
    -   **Acceptance**: First token ≤ 1.2 s P95; every paragraph cited.
    -   **Tests**: Streaming contract tests; gates unit tests with fixtures.
    -   **Responsibilities**:
        -   Framework: Node execution; tracing.
        -   You: Prompt contract, streaming emitter, gates, downgrade policy.
    -   **Sanity checklist**:
        -   [ ] First-token SLA met; [ ] Each paragraph has citation; [ ] Warnings emitted on gate failure.

### 4.4. Expose via Streaming API
-   **Task**: **Query Router (SSE)**:
    -   [ ] Refactor `api/routers/query.py` to `GET /api/v1/query/stream` using SSE.
    -   [ ] Instantiate orchestrator, create initial `AgentState`, run graph, stream typed events (`meta`, `token`, `citation`, `warning`, `final`).
    -   **Acceptance**: Browser receives first token < 1.2 s P95; no main-thread blocks.
    -   **Tests**: Integration test with SSE client; event types validated.
    -   **Responsibilities**:
        -   Framework: N/A (transport is app code).
        -   You: Endpoint, event protocol, keep-alive, backpressure + stall handling.
    -   **Sanity checklist**:
        -   [ ] SSE ping interval set; [ ] Client reconnect strategy documented; [ ] Errors carry `trace_id`.

## Phase 5: Production Hardening & Long-Term Memory

*Goal: Add long-term memory, robust testing, and observability to make the agentic core production-ready.*

### 5.1. Long-Term Memory
-   **Task**: **Event-Driven Memory Worker**:
    -   [ ] Trigger on session idle (30 min) or every 10 messages.
    -   [ ] Process recent messages; extract entities; generate `long_term_summary`.
    -   [ ] Redact PII or apply TTL.
    -   **Acceptance**: Job < 2 s average; no impact on live Q&A.
    -   **Tests**: Worker unit + integration tests; Firestore writes validated.
    -   **Responsibilities**:
        -   Framework: N/A
        -   You: Queue/trigger wiring, entity extraction, summary generation, privacy policy.
    -   **Sanity checklist**:
        -   [ ] Idempotent runs; [ ] TTL applied; [ ] Profile stays < 32 KB.
-   **Task**: **Integrate Memory into Agent**:
    -   [ ] `rewrite_expand` reads `long_term_summary` and biases rewrite.
    -   **Acceptance**: Rewrite mentions user topics when relevant.
    -   **Tests**: Snapshot tests with seeded profiles.
    -   **Responsibilities**:
        -   Framework: Node execution + merge.
        -   You: Memory fetch, prompt conditioning, fallback when missing.
    -   **Sanity checklist**:
        -   [ ] Absent profile → no failure; [ ] No PII echoes; [ ] Deterministic at temp=0.

### 5.2. Observability & Quality Gates
-   **Task**: **LangSmith + OpenTelemetry**:
    -   [ ] Enable `LANGCHAIN_TRACING_V2=TRUE`; attach spans per node; propagate `trace_id`.
    -   **Acceptance**: 100% node coverage in traces; timing metrics recorded.
    -   **Tests**: Trace presence asserted in integration tests.
    -   **Responsibilities**:
        -   Framework: Trace hooks in LangGraph/LangChain.
        -   You: Env config, span attributes, redaction, dashboards.
    -   **Sanity checklist**:
        -   [ ] PII redaction on; [ ] Latency histograms; [ ] Errors sampled with payload hashes.
-   **Task**: **Dev vs Prod Observability Notes**:
    -   [ ] **Dev**: Use LangGraph Studio for interactive graph viz, step-through execution, and state inspection with in-memory/SQLite checkpointer.
    -   [ ] **Prod**: Use LangSmith for run DAGs, per-node I/O, timings, errors; Redis/Firestore checkpointer for durability/replay.
    -   **Acceptance**: Studio runs locally; LangSmith shows complete traces with `trace_id` correlation in prod.
-   **Task**: **Golden Set CI Evaluator**:
    -   [ ] Curate 100 ZW legal queries with gold answers + sources.
    -   [ ] CI workflow fails on correctness < 90%, citation accuracy < 95%, or latency regression > 20%.
    -   **Acceptance**: CI gate blocks regressions.
    -   **Tests**: PR pipeline runs evaluator; sample failures reported.
-   **Task**: **Load & Chaos Testing**:
    -   [ ] k6/Locust: 50 RPS spikes; chaos: reranker timeout.
    -   **Acceptance**: P95 < 4 s, error rate < 1%; degraded mode flagged.
    -   **Tests**: Scripts and reports stored in `reports/perf/`.

### 5.3. Security & Docs
-   **Task**: **R2 Path Traversal Guard**:
    -   [ ] Server-side map from `doc_key` → R2 object key; deny unexpected prefixes.
    -   **Acceptance**: E2E test proves traversal attempts blocked.
-   **Task**: **Finalize Documentation**:
    -   [ ] Sequence diagrams; `AgentState` schema; SSE event contracts; runbooks.
    -   **Acceptance**: Docs reviewed; links referenced in README.

---

## Definition of Done (Phase 4–5)
-   All tasks above have passing unit/integration tests.
-   Golden set CI gate passes with thresholds.
-   Latency budgets achieved: first token ≤ 1.2 s P95; full answer ≤ 4 s P95.
-   Security checks: JWT enforced, R2 traversal guard, source allow-list.
-   Complete LangSmith tracing for all nodes; diagrams exported to `docs/diagrams/`.

---

## Master Sanity Checklist (Phase 4–5)
-   [ ] State size < 8 KB typical; only IDs/keys for heavy artifacts.
-   [ ] Checkpointer durable in prod; replay works by `trace_id`.
-   [ ] First token SLA ≤ 1.2 s P95; budgets enforced per node.
-   [ ] Retrieval caps (K, M) respected; fallbacks exercised.
-   [ ] Every paragraph cited; allow-list enforced; quote verifier sampled.
-   [ ] SSE emits `meta`, `token`, `citation`, `warning`, `final`; errors include `trace_id`.
-   [ ] PII redaction on traces; audit fields stored (who, when, sources, hashes).
-   [ ] CI golden set stable; load/chaos tests pass; canary/shadow plan documented.

---

## Pre-flight Checklist (Final Review)
- **TDD is Mandatory**: Is there a unit test for every node and a new entry in the Golden Set for every major capability?
- **Clean Code**: Is the code self-documenting? Are SOLID/DRY/KISS principles followed?
- **Async by Default**: Are all I/O operations non-blocking (`async`)?
- **Config & Secrets**: Is all configuration loaded from the environment via Pydantic Settings? Are secrets handled securely?
- **Dependencies**: Are all dependencies pinned in `pyproject.toml`? Have they been scanned for vulnerabilities?
- **Observability**: Is every step of the agentic process traced in LangSmith with proper metadata?

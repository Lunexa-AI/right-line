
# Gweta Agentic Core Architecture (v3.0)

## 1. Core Principles

- **Agentic & Composable**: The system is built as a graph of specialized, stateless tools orchestrated by a central `QueryOrchestrator`. This multi-agent-ready design allows new capabilities (drafting, redlining) to be added as modular subgraphs.
- **State-Driven**: Every query is executed within a versioned, explicit state machine (`AgentState`). This enables reproducibility, observability, and robust error handling.
- **Cloud-Native & Serverless**: All components are designed for a serverless environment. Heavy artifacts (PDFs, chunks, indexes) are stored in Cloudflare R2, and compute is handled by ephemeral containers (Render).
- **Performance by Design**: We target a **sub-second first-token** latency and a **< 4s full-answer** P95 latency budget through aggressive parallelism, caching, and staged degradation.

---

## 2. High-Level Architecture

The architecture is a multi-stage, asynchronous pipeline managed by a LangGraph state machine. It prioritizes speed, accuracy, and verifiability.

```mermaid
graph TD
    subgraph User Interaction
        A[Client: Web/WhatsApp] -->|HTTPS Request with JWT| B(API: FastAPI on Render)
    end

    subgraph Agentic Core
        B --> C{Query Orchestrator (LangGraph)}
        C --> D[1. Intent Router]
        D --> E[2. Rewrite & Expand]
        E --> F[3. Concurrent Retrieval]
        F --> G[4. Rerank & Fuse]
        G --> H[5. Expand to Parents]
        H --> I[6. Synthesize & Stream]
    end

    subgraph Data & State Plane
        C <-->|Read/Write State| J(State Checkpointer: Firestore)
        F -->|Hybrid Search| K(Milvus Cloud: Dense Vectors)
        F -->|Hybrid Search| L(BM25 Index on R2: Sparse Vectors)
        H -->|Fetch Parent Docs| M(Cloudflare R2: Chunks & Parent Docs)
        I -->|Cite Sources| M
    end

    subgraph Observability
        C -->|Trace Every Step| N(LangSmith)
    end

    I -->|Streaming SSE Response| B
```

---

## 3. Proposed Repo Structure Refactoring

To support a multi-agent architecture and improve modularity, we will refactor the `api/` directory. This isolates concerns and makes adding new capabilities cleaner.

**Current Structure:**
```
api/
  - retrieval.py
  - composer.py
  - routers/
  - ...
```

**Proposed Structure:**
```
api/
  schemas/              # Pydantic models for state, requests, etc.
    - agent_state.py
  orchestrators/        # High-level LangGraph state machines
    - query_orchestrator.py
  agents/               # Subgraphs for specialized tasks (future)
    - protocol.py
    - research_qa/
    - summarizer/
  tools/                # Stateless, reusable capabilities
    - retrieval_engine.py # Replaces api/retrieval.py
    - reranker.py
    - citation_resolver.py
  composer/             # Prompt engineering and LLM interaction
    - prompts.py
    - synthesis.py
  routers/              # API endpoints (no business logic)
    - query.py
    - debug.py
  main.py
```

This structure separates the "what" (schemas) from the "how" (tools, agents) and the "when" (orchestrators), which is critical for a scalable agentic system.

---

## 4. Core Components Deep Dive

### 4.1. Data Ingestion Pipeline (V3 - Current & Validated)
- **Source**: PDFs fetched and stored in `R2:corpus/sources/`.
- **Parsing**: `parse_docs_v3.py` uses **PageIndex** for OCR and to generate a structural `content_tree`.
- **Sanitization**: A robust pass removes boilerplate, OCR artifacts, and duplicate headings.
- **Chunking**: `chunk_docs.py` performs **tree-aware chunking**, creating semantic chunks aligned with document nodes. `MIN_TOKENS` is set to 10 to capture small but important documents.
- **Storage**: Parent documents (`docs/`) and chunks (`chunks/`) are stored as JSON in R2.

### 4.2. Retrieval Engine (V3 - Current & Validated)
- **Hybrid Search**: The engine runs two searches in parallel:
    - **Dense**: Milvus vector search on OpenAI embeddings (`text-embedding-3-large`) for semantic relevance.
    - **Sparse**: BM25 keyword search (index loaded from R2) for specific terms.
- **Fusion**: Results are combined using **Reciprocal Rank Fusion (RRF)** to produce a single, high-quality candidate list.
- **Reranking**: A cross-encoder model (`BGE-reranker-base`) reranks the fused list for maximum precision.
- **Small-to-Big Expansion**: The top N reranked chunks are expanded by fetching their full parent documents from R2, providing rich context for synthesis.

### 4.3. The Agentic Core (The New Implementation)
- **Orchestrator**: `QueryOrchestrator` implemented as a **LangGraph** state machine.
- **State**: A Pydantic model, `AgentState`, tracks the full lifecycle of a query, enabling retries and detailed tracing.
- **Key Nodes (Steps in the Graph)**:
    1.  **Intent Router**: Fast heuristics and a mini-LLM classify the user's goal (e.g., `rag_qa`, `conversational`). Budget: ≤ 70 ms heuristics / ≤ 250 ms LLM.
    2.  **Rewrite & Expand**: History-aware rewrite + **Multi-HyDE** (3–5 hypotheticals, ≤ 120 tokens each) run in parallel with strict timeouts. Budget: ≤ 450 ms.
    3.  **Concurrent Retrieval**: The `RetrievalEngine` runs dense+BM25 in parallel; RRF fuses results. Budget: ≤ 350 ms.
    4.  **Rerank & Fuse**: BGE cross-encoder reranker with caching and timeouts. Budget: ≤ 250 ms.
    5.  **Expand to Parents**: Fetch parent docs/pages from R2; token-aware context bundler. Budget: ≤ 150 ms.
    6.  **Synthesize & Stream**: Build structured prompt and stream tokens with guardrails. First-token budget: ≤ 400 ms from node start.
- **Observability**: Every step is traced to **LangSmith**, providing full visibility into the agent's reasoning process.

### 4.4. Streaming API (SSE Contract)
- **Endpoint**: `GET /api/v1/query/stream?session_id=...`
- **Events**:
    - `meta`: `{ trace_id, route, budgets }`
    - `token`: `{ text }`
    - `citation`: `{ doc_key, page?, confidence }`
    - `warning`: `{ type }`
    - `final`: `{ answer_key, citations, usage, timings }`
- **Timeouts & Backpressure**: First `token` within 1.2s P95; if stall > 3s, abort and emit structured error with `trace_id`.

### 4.5. Caching & Budgets
- **Semantic cache**: `(rewritten_query → chunk_ids)` LRU 15 min.
- **Reranker cache**: `(chunk_id, query_hash) → score` for 1 h.
- **Doc fetch cache**: `parent_doc_key → pages` for 1 h.
- **Adaptive degradation**: Under pressure, skip Multi-HyDE and reduce K/M.

### 4.6. Guardrails & Safety
- **AttributionGate**: Reject if < 2 citations when available or any paragraph lacks a citation.
- **QuoteVerifier**: Sampled verbatim string checks (8–15 words) against retrieved spans.
- **Policy rules**: No advice outside ZW; inject disclaimers; route to clarify if insufficient context.

### 4.7. Developer Experience & Observability Modes
- **Dev (LangGraph Studio)**: Use Studio for interactive graph visualization, step-through execution, and state inspection. Pair with in-memory/SQLite checkpointer for pause/resume and diffs.
- **Prod (LangSmith)**: Enable tracing to get per-node DAG view, inputs/outputs, timings, and errors for every run. Use Redis/Firestore checkpointer for durability and replay.
- **Docs**: Export a static SVG of the compiled graph to `docs/diagrams/agent_graph.svg` for architectural reference.
- **Acceptance**: Studio works locally (interactive step/run); LangSmith shows complete node traces in production with `trace_id` correlation.

---

## 5. Security & Compliance
- **Authentication**: All user-facing endpoints are protected by JWT-based Firebase Authentication.
- **Data Isolation**: R2 and Firestore security rules ensure users can only access their own data.
- **R2 Path Traversal Guard**: Server-side mapping from `doc_key` → R2 object key; never trust client-supplied paths.
- **Auditability**: Store trace metadata: who asked what, when, which sources, and prompt hashes.

---

## 6. Acceptance Criteria (Architecture-Level)
- **Latency**: P95 end-to-end ≤ 4s; first-token ≤ 1.2s.
- **Accuracy**: ≥ 95% answers include verifiable citations; zero uncited statutory claims.
- **Resilience**: Any single dependency failure downgrades gracefully (no blank outputs).
- **Observability**: 100% of nodes traced with input/output schemas and timings in LangSmith; Studio usable during development.
- **Security**: No direct R2 paths exposed; JWT validation enforced on all protected endpoints.

---

## 7. Final Review Notes (Pre-flight Check)
- **Testing Strategy**: TDD is mandatory. Each node must have unit tests with mocked dependencies. The full graph will be tested via the Golden Set CI evaluator, which acts as the end-to-end integration test.
- **Dependency Management**: All Python dependencies are managed by Poetry. Key libraries (`langchain`, `langgraph`, `fastapi`, `pydantic`) should be pinned to specific minor versions to prevent breaking changes. A regular dependency scan (e.g., `snyk`, `pip-audit`) is required.
- **Configuration**: All secrets (API keys, tokens) must be loaded from environment variables, never hardcoded. Use Pydantic's `BaseSettings` for type-safe configuration management.
- **Asynchronicity**: All I/O-bound operations (network calls to LLMs, R2, Milvus, Firestore) must be `async` to ensure the FastAPI server remains non-blocking.
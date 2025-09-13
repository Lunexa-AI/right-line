Awesome—let’s turn your Phase 4–5 into a **state-of-the-art, lightning-fast, production-ready agentic core** tailored for Gweta. I’ve kept your spirit, but added rigor around latency budgets, failure modes, security, and observability. Where useful, I’ve included concrete code stubs, file paths, and acceptance criteria.

---

# Phase 4 — The Agentic Core (Ultra)

## 4.0 Goals & Budgets (what “great” looks like)

* **P50/95 latency budget (interactive Q\&A, \~2–4 sources):**

  * Intent router: **≤ 70 ms** (heuristics) / **≤ 250 ms** (LLM mini)
  * Rewrite/HyDE/Multi-HyDE (parallel): **≤ 450 ms**
  * Hybrid retrieval + rerank (dense + BM25 + BGE): **≤ 600 ms**
  * Context assembly (parent expansion + pruning): **≤ 150 ms**
  * First token streamed: **≤ 800–1200 ms** (goal: sub-second feel)
  * Full answer (400–800 tokens): **≤ 2.5–4.0 s**
* **Stability:** No single step can block > 2 s; hard timeouts, fallbacks, and early-exit everywhere.
* **Accuracy:** ≥ 95% answers include **verifiable citations**; zero uncited claims on statutory text.

---

## 4.1 QueryOrchestrator & Explicit State Machine

**Rename**

* `api/agent.py`: `AgenticEngine` → `QueryOrchestrator`.

**State is the contract. Version it. Keep it small.**

* Persist **keys/IDs** to heavy objects (chunks, docs) not the objects themselves.
* Add `state_version: Literal["v1"]` and `trace_id: str` at the top.

```python
# api/schemas/agent_state.py
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field

class Citation(BaseModel):
    doc_key: str
    page: Optional[int] = None
    snippet_range: Optional[tuple[int,int]] = None
    confidence: float

class AgentState(BaseModel):
    state_version: Literal["v1"] = "v1"
    trace_id: str
    user_id: str
    session_id: str

    # Initial
    raw_query: str
    session_history_ids: List[str] = []
    user_profile_key: Optional[str] = None
    jurisdiction: Optional[str] = None  # e.g., "ZW"
    date_context: Optional[str] = None  # e.g., "as_of=2024-01-01"

    # Intermediate
    intent: Optional[str] = None  # "rag_qa" | "conversational" | "summarize" | "disambiguate"
    rewritten_query: Optional[str] = None
    sub_questions: List[str] = []
    hypothetical_docs: List[str] = []  # Multi-HyDE
    retrieval_strategy: Optional[str] = None  # "hybrid_rrf_v3"
    candidate_chunk_ids: List[str] = []
    reranked_chunk_ids: List[str] = []
    parent_doc_keys: List[str] = []
    synthesis_prompt_key: Optional[str] = None

    # Final
    final_answer: Optional[str] = None
    cited_sources: List[Citation] = []
    safety_flags: Dict[str, bool] = Field(default_factory=dict)
```

**LangGraph graph with a durable checkpointer**

* Use **LangGraph** with a **Redis**/Firestore checkpointer to resume on retries and for step-level tracing.
* Each node is **pure on inputs** (AgentState) and returns a **partial update dict**.

```python
# api/agent.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver  # replace with Redis/Firestore checkpointer in prod
from .schemas.agent_state import AgentState

graph = StateGraph(AgentState)

graph.add_node("route_intent", route_intent)                 # fast heuristics → LLM mini fallback
graph.add_node("rewrite_expand", rewrite_expand)             # history-aware rewrite + Multi-HyDE + sub-Q
graph.add_node("retrieve_concurrent", retrieve_concurrent)   # asyncio.gather dense+bm25
graph.add_node("rerank", rerank_bge)
graph.add_node("expand_parents", expand_parent_docs)
graph.add_node("synthesize_stream", synthesize_stream)       # streams tokens
graph.add_node("session_search", search_session_history)     # for “what did you just say”
graph.add_node("conversational_tool", answer_conversational)
graph.add_node("summarizer_tool", answer_summarization)

graph.set_entry_point("route_intent")

graph.add_conditional_edges(
  "route_intent", decide_route,
  {"rag_qa": "rewrite_expand",
   "conversational": "conversational_tool",
   "summarize": "summarizer_tool",
   "disambiguate": "rewrite_expand"}  # rewrite also handles clarifying Qs
)

graph.add_edge("rewrite_expand", "retrieve_concurrent")
graph.add_edge("retrieve_concurrent", "rerank")
graph.add_edge("rerank", "expand_parents")
graph.add_edge("expand_parents", "synthesize_stream")
graph.add_edge("conversational_tool", END)
graph.add_edge("summarizer_tool", END)

app = graph.compile(checkpointer=MemorySaver())
```

**Acceptance**

* ✅ Any node can be replayed in isolation by trace\_id.
* ✅ State is JSON-serializable and < 8 KB typical.
* ✅ Canary error in any node leads to **circuit-break** + next best fallback node, never a blank screen.

---

## 4.2 Multi-Stage, Cost-Aware Pre-Processing (Router++)

### Stage 1 — **Ultra-Fast Intent & Jurisdiction Router**

1. **Heuristics first** (no LLM call):

   * Regex/keyword: “summarize”, “explain differently”, “you said”, “thanks”, “what did you say”, “tl;dr”, “translate”.
   * Legal patterns → **jurisdiction/date** detection: keywords (“Statutory Instrument”, “Gazette”, “ZimLII”, “Chapter”, “SI NN of YYYY”) to set `jurisdiction="ZW"` and `date_context`.
2. **LLM-mini fallback** if ambiguous (≤ 200 tokens, temp 0.0), returns `{intent, jurisdiction?, date_context?}`.

**Why:** 80–90% of turns short-circuit without touching RAG.

### Stage 2 — **Rewrite, Multi-HyDE, Decomposition (Parallel)**

* **History-aware rewrite**: converts “what about PBCs?” → fully qualified legal Q with jurisdiction/date context.
* **Multi-HyDE (k=3–5)**: small, diverse hypotheticals (≤ 120 tokens each) in *distinct rhetorical frames*: statute summary, commentary, case-law angle, procedural angle. Embed all in parallel.
* **Sub-question decomposition** (if long/compound; enforce max 3–4 to cap latency). **Guard** with complexity heuristics (AND/OR, “compare”, “versus”, multiple entities).

**Implementation hints**

* Use `asyncio.gather` for generation; enforce **per-subcall 600 ms** timeout; on timeout, degrade to rewrite-only.

**Acceptance**

* ✅ Router P50 < 70 ms with heuristics; P95 < 250 ms with mini-LLM.
* ✅ Rewrites always add `[jurisdiction]` and `[as_of date]` when inferable.

---

## 4.3 Dynamic Tool Use & Retrieval (Zero-waste, Parallel)

**Primary tools**

1. **RetrievalEngine** (already hybrid): accept **List\[str] queries** and run **concurrently**:

   * Dense (Milvus) on: rewritten\_query + Multi-HyDE + sub-Q’s
   * BM25 (prebuilt index) on same set
   * **RRF** fuse per-query then **union** across queries with score decay
   * **Budget**: overall top-K candidates capped (e.g., K=60) to bound reranker cost
2. **SessionHistorySearch**:

   * **Local vector store** for last N messages (e.g., 200), **bi-encoder** embeddings
   * Used when intent=“conversational” or “what did you say”
3. **CitationResolver** (new):

   * Normalizes source metadata → `{doc_key, title, authority, issue_date, page}`
   * Dedupes across mirrors (e.g., Gazette vs ZimLII mirror)
4. **StatuteVersionResolver** (new, ZW-specific):

   * If statute sections amended, maps to **correct version** based on `date_context`

**Concurrency skeleton**

```python
# api/retrieval.py (sketch)
async def retrieve_concurrent(state: AgentState) -> dict:
    queries = [state.rewritten_query, *state.hypothetical_docs, *state.sub_questions]
    queries = [q for q in queries if q][:8]  # cap fan-out

    dense_task = dense_search_batch(queries)   # Milvus
    bm25_task  = bm25_search_batch(queries)    # rank-bm25

    dense, sparse = await asyncio.gather(
        asyncio.wait_for(dense_task, timeout=0.5),
        asyncio.wait_for(bm25_task, timeout=0.3),
        return_exceptions=True
    )
    candidates = rrf_fuse(dense, sparse, top_k=60)
    return {"candidate_chunk_ids": [c.id for c in candidates]}
```

**Parent expansion & context assembly**

* Expand **only** parent docs for **top-M** (e.g., M=8–12), **page-scoped** if PDFs.
* **Context window builder**:

  * Build **section-aware bundles** with **hard token cap** (e.g., 5–7k), prioritizing:

    1. exact section hits
    2. nearby sections (±1)
    3. authoritative sources over commentary
  * **Quote-ready**: retain **exact spans** for subsequent quote verification.

**Caching**

* **Semantic cache**: (rewritten\_query → chunk\_ids) LRU 15 min
* **Reranker cache**: (chunk\_id, query\_hash) → score 1 h
* **Doc fetch cache**: parent\_doc\_key → text pages 1 h

**Acceptance**

* ✅ P95 retrieval+rerank ≤ 600 ms at K=60, M=10 on typical queries.
* ✅ Context assembly guarantees **≥ 2 authoritative sources** where available.

---

## 4.4 API Router: Async + **True Streaming** (SSE/WebSocket)

**Server**

* `GET /api/v1/query/stream?session_id=...`
* **SSE** default; **WebSocket** fallback for proxies that break SSE.
* Stream **typed events**:

  * `meta`: trace\_id, route, budgets
  * `token`: partial text
  * `citation`: `{doc_key, page, confidence}`
  * `warning`: safety/coverage notes
  * `final`: `{answer_key, citations, usage, timings}`

```python
# api/routers/query.py
@router.get("/api/v1/query/stream")
async def stream_query(...):
    state = AgentState(..., trace_id=uuid4().hex)
    async def event_source():
        async for ev in orchestrator_run_stream(state):
            yield f"event:{ev.type}\n"
            yield f"data:{json.dumps(ev.payload)}\n\n"
    return EventSourceResponse(event_source(), ping=15000)  # keep-alive
```

**Client**

* Render tokens as they arrive; show **citations side-panel** live as sources stream.

**Backpressure & timeouts**

* Synthesis node **must** emit first token within 400 ms of start or downgrade model (mini) + tighter prompt.
* If streaming stalls > 3 s → **abort** and send a structured error with trace\_id.

**Acceptance**

* ✅ First token within 1.2 s P95.
* ✅ Stream never blocks main thread; UI gracefully handles `warning`/`final`.

---

## 4.5 Context-Aware Synthesis & Guardrails

**Prompt contract (strict sections)**

```
[SYSTEM]
You are Gweta, a legal copilot for Zimbabwean law. You must cite sources and never assert text not grounded in [RETRIEVED CONTEXT].

[USER PROFILE]
{profile_text}

[CONVERSATION HISTORY: last N ≤ 8]
{short_history}

[RETRIEVED CONTEXT]
Document 1 (Source: {doc_key_1}, Authority: {authority}, Date: {date}, Page: {page}): 
<<<
{excerpt_1}
>>>
Document 2 (Source: {doc_key_2}, ...):
<<<
{excerpt_2}
>>>

[INSTRUCTIONS]
- Answer ONLY from [RETRIEVED CONTEXT]. If insufficient, say what’s missing and ask a precise follow-up.
- Use neutral, professional tone. Personalize tone with [USER PROFILE].
- Cite each factual claim with (Source: doc_key[, page]).
- Prefer statutes and gazettes over commentary; if conflicting, state the conflict.
- If the answer depends on date/version, state the applicable version explicitly.
```

**Output checks (hard gates before final):**

* **AttributionGate**: reject if < 2 citations (when more exist) or if any paragraph lacks a citation.
* **QuoteVerifier**: sampled **verbatim strings (8–15 words)** from the answer must appear in retrieved snippets (fuzzy match). If mismatch → insert **warning** and request follow-up.
* **Safety rules**: block advice outside jurisdiction; inject disclaimer + route to **clarify**.

**Model policy**

* Default: gpt-4o (synthesis), gpt-4o-mini (router/rewrite)
* Fallback: OSS LLM (e.g., Qwen-Coder-ins-tiny) for continuity under outage; cap token length and clearly label.

**Acceptance**

* ✅ Every paragraph ends with at least one citation.
* ✅ If insufficient context, the assistant **explicitly asks** targeted follow-ups (not generic).

---

## 4.6 Security & Prompt-Injection Hardening

* **Context sandboxing**: never execute links or embedded instructions from retrieved docs.
* **Source allow-list**: Gazette, Veritas, ZimLII, official Acts; anything else is **secondary**.
* **Path traversal guard** on R2 keys; server-side mapping from `doc_key` to object key.
* **PII redaction** in traces (names, emails) with reversible hashing for correlating within a session.

---

## 4.7 Developer Ergonomics

* **One-click trace replay** in LangSmith by `trace_id`.
* **Graph viz**: export `graph.draw_svg()` to `/docs/diagrams/agent_graph.svg`.
* **State snapshots** persisted to Firestore on node boundaries when `debug=true`.

---

# Phase 5 — Long-Term Memory & Production Hardening (Ultra)

## 5.1 Event-Driven Memory (No cron. Real-time enough.)

**Triggering events**

* On **session idle (30 min)**, or **every 10 messages**, publish:

  * `user_id`, `session_id`, `recent_message_ids`, `time_range`.

**Queue/Infra**

* Use **Pub/Sub** (or SQS/RabbitMQ). Dead-letter queue for failures.

**Worker pipeline**

1. **Entity Extraction** (LLM mini + regex):

   * People, organizations, statutes (`Cap.`, `SI`, sections), cases, dates.
   * Deduplicate; store as structured arrays in `user.memory.entities`.
2. **Knowledge Graph Lite** (optional but powerful):

   * Build edges: `user → statute(section)`, `user → topic("PBC")`, `topic → doc_key`.
   * Store in Firestore or a tiny embedded graph (e.g., sqlite in worker + export).
3. **Reflective Summary** (`long_term_summary`):

   * 3–6 bullet points, evergreen, last updated timestamp.
4. **Privacy guard**:

   * Drop ephemeral PII; TTL for sensitive items (e.g., names → 30 days).
5. **Embeddings for memory**:

   * Create small **per-user memory index** (e.g., 200–500 vectors) for fast “personal context” retrieval in Stage 2 rewrite.

**Acceptance**

* ✅ Memory job completes in < 2 s average; never blocks live requests.
* ✅ Per-user profile stays < 32 KB and is diff-merged (no overwrites).

---

## 5.2 Observability, Testing, & Quality Gates

**Tracing**

* **LangSmith**: enable `LANGCHAIN_TRACING_V2=TRUE`.
* **OpenTelemetry**: attach spans to each node; propagate `trace_id`.
* Log **latency**, **top-K**, token counts, and **cache hit rates**.

**Golden Set E2E (critical)**

* 100 curated queries (ZW corporate, labor, criminal procedure, procurement).
* For each: gold answer, required sources (doc\_keys), rubric (correctness, relevance, citation accuracy).
* **CI gate**: run nightly & on PR; fail if:

  * Correctness < 90%,
  * Citation accuracy < 95%,
  * Latency regression > 20%.

**Automated eval**

* LLM-as-judge with constrained rubric + **hard assertions**:

  * All citations must be from allow-list.
  * At least one **primary authority** per answer when relevant.

**Load & Chaos**

* k6/Locust test: 50 RPS spike for 60 s; ensure P95 < 4 s, error rate < 1%.
* Chaos: kill reranker → verify fallback (dense-only) and degraded-quality flag.

**Canary & Shadow**

* 5% traffic on new graph version; **shadow replay** 10% for offline eval in LangSmith.

---

## 5.3 Reliability & Cost Controls

* **Circuit breakers** per external dependency (LLM, Milvus, R2); exponential backoff.
* **Time-boxed nodes** with graceful degradation (e.g., skip Multi-HyDE under pressure).
* **Adaptive budgets**:

  * Short queries (≤ 12 tokens) skip decomposition.
  * Saturation → reduce K/M and temperature=0.

---

## 5.4 Security, Compliance, Audit

* **Audit log**: who asked what, when, which docs used; store hashes of prompts/contexts.
* **Explainability pack**: attach **why these sources** (top features from reranker).
* **User controls**: memory opt-out; “forget this session” endpoint.
* **Content watermark**: append “As of \<date/version>” for statutes.

---

## 5.5 Docs & Diagrams

* **Sequence diagram**: `/docs/diagrams/sequence_agentic.svg` (User → Router → Orchestrator → Nodes → Stream).
* **Data contracts**: JSON Schemas for events (`meta`, `token`, `citation`, `final`).
* **Runbooks**: “LLM outage”, “Milvus degraded”, “R2 latency spike”.

---

# Concrete Implementation Tasks (ready to ticket)

1. **Rename + State v1**

   * [ ] Rename `AgenticEngine`→`QueryOrchestrator`.
   * [ ] Add `AgentState v1` schema and validators.
   * [ ] Add `trace_id` propagation everywhere.

2. **LangGraph Orchestrator**

   * [ ] Implement nodes (router, rewrite\_expand, retrieve\_concurrent, rerank, expand\_parents, synthesize\_stream, session\_search, conversational\_tool, summarizer\_tool).
   * [ ] Redis/Firestore checkpointer.
   * [ ] Graph SVG export.

3. **Cost-Aware Router**

   * [ ] Heuristic patterns + jurisdiction/date detectors.
   * [ ] Mini-LLM fallback (temp=0).

4. **Rewrite & Multi-HyDE**

   * [ ] Parallel generation (k=3–5), 120-token cap each.
   * [ ] Sub-Q decomposition with cap and timeouts.

5. **Retrieval Engine v3**

   * [ ] `asyncio.gather` dense+bm25, RRF, cap K=60.
   * [ ] BGE reranker cache & timeouts (≤ 180 ms).
   * [ ] Parent expansion with token-aware bundler.

6. **SessionHistorySearch**

   * [ ] Per-session mini-index; semantic search over last 200 turns.

7. **SSE/WebSocket Streaming**

   * [ ] Typed events; client UI updates for live citations.
   * [ ] Backpressure + stall detection.

8. **Synthesis & Guardrails**

   * [ ] Structured prompt; **AttributionGate**; **QuoteVerifier**.
   * [ ] Safety policies & disclaimers injection.

9. **Memory Worker**

   * [ ] Pub/Sub topic; worker w/ entity extraction + reflective summary + TTL.
   * [ ] Per-user memory index.

10. **Observability & CI Gates**

* [ ] LangSmith + OpenTelemetry spans & metrics.
* [ ] Golden set dataset; CI evaluator; latency guardrails.
* [ ] Load/chaos tests; canary + shadow deploy.

11. **Security**

* [ ] R2 key mapping & traversal guard.
* [ ] PII redaction in traces.
* [ ] Source allow-list enforcement.

---

# Example Code Stubs

### Rewriter with Multi-HyDE (parallel)

```python
# api/nodes/rewrite_expand.py
async def rewrite_expand(state: AgentState) -> dict:
    q = history_aware_rewrite(state.raw_query, state.session_history_ids, state.jurisdiction, state.date_context)
    hyde_tasks = [gen_hypothetical(q, style=s) for s in ["statute", "case_law", "procedure", "commentary"]]
    subq_task  = maybe_decompose(q)

    done = await asyncio.wait([*hyde_tasks, subq_task], timeout=0.6)
    hyde = [t.result() for t in hyde_tasks if t in done[0] and t.exception() is None]
    subq = subq_task.result() if subq_task in done[0] and subq_task.exception() is None else []

    return {"rewritten_query": q, "hypothetical_docs": hyde[:4], "sub_questions": subq[:3]}
```

### Synthesis Streaming with Gates

```python
# api/nodes/synthesize_stream.py
async def synthesize_stream(state: AgentState, emitter) -> dict:
    prompt = build_prompt(state)            # writes to R2, returns key
    async for tok in llm_stream(prompt):    # first token expected <400ms
        await emitter("token", {"text": tok})
    answer = emitter.get_buffer()

    citations = extract_citations(answer)
    if not pass_attribution_gate(answer, citations): 
        await emitter("warning", {"type": "citation_insufficient"})
    if not pass_quote_verifier(answer, state):
        await emitter("warning", {"type": "quote_mismatch"})

    await emitter("final", {"citations": citations, "usage": emitter.usage})
    return {"final_answer": answer, "cited_sources": citations}
```

---

# Why this is “robustly better”

* **Latency by design**: parallel everywhere, strict timeouts, staged degradation, and “first token fast”.
* **Accuracy by contract**: structured prompts, **AttributionGate**, and **QuoteVerifier** push hallucination risk way down.
* **Maintainable**: explicit **state machine** + versioned state + node-level traces.
* **Domain-fit**: jurisdiction/date routing, **StatuteVersionResolver**, and source allow-list for Zimbabwean law.
* **Ops-ready**: golden-set CI gates, shadow/canary, load/chaos tests, audit logs, and memory privacy controls.

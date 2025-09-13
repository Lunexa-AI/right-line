Short answer: yes—your Phase-4/5 design is **agent-extensible**. If you keep the QueryOrchestrator + LangGraph state machine as the “bus,” you can plug in specialist agents (drafting, summarizing, redlining, etc.) as additional nodes with clear I/O contracts. I took a quick look at your site; it appears to be a JS SPA that renders “Loading…” without server-side markup in this environment—which matches your “pro-grade AI for ZW law” ambition and multi-workflow direction. ([Gweta][1])

Below is a **state-of-the-art agentic layout** for Gweta: what to add, how they fit, and how to slot them into your repo with minimal coupling and maximum speed.

---

# 1) Agent families you’ll want (now → later)

## A. Core workbench agents (ship first)

* **ResearchQAAgent** (you already have): RAG + citations, version-aware statutes.
* **SummarizerAgent**: styles (executive, client-friendly, IRAC), chunk-aware, length-bounded, auto-cite.
* **DocumentDrafterAgent**: prompt-to-draft using **template + clause bank**, jurisdiction/date aware, auto-cite footnotes.
* **ContractRedlinerAgent**: compare “incoming” vs “gold master,” propose edits, classify risks (blocking/medium/minor), export **redline HTML** now; DOCX tracked-changes later.
* **Intake/TriageAgent**: structured fact collection (checklists), creates “Matter” objects, suggests next actions.

## B. Accuracy, safety, and governance agents (always on, cheap)

* **CitationGuardAgent**: verifies quotes and pincites against retrieved text, flags unverifiable claims.
* **StatuteVersionAgent**: snaps sections to the correct **as-of** version; warns on amendments.
* **Policy/RiskCheckAgent**: style/compliance rules (no advice outside ZW, confidentiality language present, etc.).
* **PII/SafetyRedactorAgent**: redacts sensitive items in traces and exported artifacts.

## C. Document understanding agents (power tools)

* **PDF/OCRNormalizerAgent**: PageIndex + layout recovery; table extraction; clause segmentation.
* **ClauseMiningAgent**: builds/maintains a clause library from user uploads; tags by purpose, risk, and jurisdiction.
* **Entity\&FactIndexerAgent**: maps matters → entities → statutes/cases for faster follow-ups.

## D. Litigation & advisory helpers (nice-to-have soon)

* **CaseBriefAgent**: IRAC/CRAC from opinions; issues/holdings/rationale with citations.
* **TimelineAgent**: builds factual/filing timelines with date certainty levels.
* **ChecklistAgent**: produces procedural checklists (e.g., company registration, employment termination) with links to sources.

## E. Automation & quality agents (ops)

* **MemoryCuratorAgent**: event-driven entity + reflective summary (your Phase-5 worker).
* **RegressionEvalAgent**: runs golden-set tests on PRs; reports correctness/citation deltas.

---

# 2) How they fit together (graph-of-graphs)

Think of **two orchestrators**:

1. **QueryOrchestrator** (you’re building): routes user turns to the right agent path.
2. **DocumentOrchestrator** (new): routes **document-centric** jobs end-to-end.

Each agent is a **LangGraph subgraph** with a common contract:

```python
# api/agents/protocol.py
class AgentSpec(BaseModel):
    name: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    capabilities: set[str]  # {"draft", "summarize", "redline", "qa", ...}
    cost_hint_ms: int       # budget for router
    def build_graph(self) -> "CompiledGraph": ...
```

### Routing pattern

* **Intent router** tags a turn with `task = {qa|summarize|draft|redline|intake}` + `artifact_ids?`.
* The orchestrator **selects one subgraph** (agent) or a **playbook** (sequence):
  e.g., *Draft → CiteGuard → RiskCheck → Redline → Export*.
* All agents read/write the shared **AgentState** (IDs only; artifacts live in R2).

### Shared services (singletons)

* RetrievalEngine (dense+BM25+reranker), SessionHistorySearch
* CitationResolver, StatuteVersionResolver, ClauseBank, TemplateStore
* PDF/OCR/Normalizer, TableExtractor, Diff/Redline, Exporters (HTML/PDF/DOCX)

This keeps agents **thin** (logic) and tools **fat** (capability), maximizing reuse and speed.

---

# 3) Repo wiring (drop-in with minimal churn)

```
api/
  agents/
    __init__.py
    protocol.py
    research_qa/      # subgraph per agent
      graph.py
      io.py
    summarizer/
    drafter/
    redliner/
    intake/
    cite_guard/
    statute_version/
    policy_risk/
    ...
  orchestrators/
    query_orchestrator.py
    document_orchestrator.py
  tools/
    retrieval/
      engine.py      # hybrid+RRF+rereank (your v3)
    citations/
      resolver.py
    statutes/
      versioning.py
    clauses/
      bank.py        # R2-backed, Milvus/FAISS index
    templates/
      store.py       # R2 docx/html templates + metadata
    docs/
      ocr_normalize.py
      tables.py
      diff.py        # html-redline now; docx later
      export.py      # pdf/html/docx
  composer/
    prompts.py
  routers/
    query.py
    documents.py
    matters.py       # upload/list artifacts, start playbooks
  schemas/
    agent_state.py
    matter.py
    artifact.py
  evaluators/
    golden_set.py
    rubric.py
docs/
  diagrams/agent_graph.svg
  playbooks/*.yaml
```

* **Playbooks as YAML** (human-editable):
  `playbooks/draft_contract.yaml` declares the chain `drafter → cite_guard → risk_check → redliner → export(docx)` with per-node budgets.
  The orchestrators load these and compile **LangGraph** on boot.

---

# 4) Concrete agent designs

## 4.1 DocumentDrafterAgent

* **Inputs:** instructions, matter\_id, template\_id, constraints (party names, governing law, dates).
* **Tools:** ClauseBank (semantic insert), TemplateStore (docx/html), RetrievalEngine (to justify clauses).
* **Flow:** select template → slot facts → fetch top clauses → assemble → **self-critique** (policy & citation checks) → emit Draft v1.
* **Artifacts:** HTML/DOCX + **provenance map** clause→source.

## 4.2 SummarizerAgent

* **Inputs:** artifact\_ids (PDF/Docx), style (“executive/IRAC/client”), length target.
* **Flow:** normalize→chunk→rank salient spans→style-specific synthesis→**CitationGuard** pass.
* **Artifacts:** Markdown/HTML summary + source map.

## 4.3 ContractRedlinerAgent

* **Inputs:** `incoming_doc_id`, `gold_master_id` (optional), policy profile (risk matrix).
* **Flow:** normalize→align sections→semantic diff (diff-match-patch on spans)→LLM suggests edits + risk labels→render **HTML redline** (+ JSON patch).
* **Export:**

  * **Now:** redline HTML/PDF + JSON patch.
  * **Later:** DOCX tracked-changes via OpenXML (server) or a Java sidecar (docx4j) if you need native Word track changes.

## 4.4 CitationGuardAgent (cross-cutting)

* **Function:** quote-match (8–15 token strings) against retrieved spans; enforce paragraph-level citations; confidence scores.
* **Output:** pass/fail + suggestions to add/replace citations.

## 4.5 StatuteVersionAgent

* **Function:** map references (Cap/SI/Section) to the **correct consolidation date**; if conflicts, insert an **as-of note**.

---

# 5) Performance notes (to keep it “lightning fast”)

* **One LLM at a time:** each agent’s subgraph is **single-LLM-call streaming** after all retrieval/reranking is done. Gates (CitationGuard/Policy) use **mini models** or pure heuristics.
* **Hard budgets:** agents declare `cost_hint_ms`; the orchestrator enforces per-node timeouts & downgrades (e.g., skip Multi-HyDE, reduce K/M).
* **Artifact caching:** R2 hits batched; parent doc pages cached; reranker scores cached by `(chunk_id, query_hash)`.

---

# 6) How you’ll *extend* safely

* **Add a new agent** = create `/api/agents/<name>/graph.py` implementing `AgentSpec`, register in `agents/__init__.py`.
* **Expose skill** = add a capability tag; the router can learn a new path without touching core nodes.
* **New workflow** = add a YAML playbook; no code changes, just composition.

---

# 7) Example playbooks you’ll likely want

* **“Draft → Review”**: `drafter → cite_guard → policy_risk → redliner → export(docx)`
* **“Summarize a bundle”**: `summarizer (style=IRAC) → cite_guard → export(pdf)`
* **“Client update”**: `intake → summarizer(client) → checklist → export(email_markdown)`
* **“Opposing counsel doc”**: `ocr_normalize → redliner (vs gold) → timeline → export(pdf)`

---

# 8) Immediate tickets (bite-sized)

1. **Agent protocol + registry** (small): interface + loader + capability tags.
2. **DocumentOrchestrator** (small): SSE endpoint, playbook executor.
3. **Drafter v0** (medium): template+clause bank, doc HTML export.
4. **Redliner v0** (medium): HTML redline + JSON patch.
5. **CitationGuard v0** (small): quote-match + paragraph-citation gate.
6. **Summarizer v0** (small): style presets + auto-cite.

---

## Final take

Your Phase-4/5 backbone absolutely supports a **multi-agent product line**—just add a thin **AgentSpec**, keep tools shared, and compose workflows via playbooks. That gives you the freedom to grow from research Q\&A to **drafting, redlining, briefing, timelines, and intake** without rewriting the core.


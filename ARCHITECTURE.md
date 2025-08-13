Awesome choice on the name—**RightLine** nails “get the law right, on the line.” Below is a production-grade, security-minded, low-latency architecture + full technical spec you can ship and scale. I’ve aimed for zero/low-budget defaults with clear upgrade paths.

---

# RightLine — Technical Architecture & Specification

## 0) Product promise (non-negotiables)

* **< 2.0s P95** end-to-end response on low bandwidth (Edge/2G) for short queries.
* **Exact section + 3-line summary + citations** every time; no free-text rambles.
* **WhatsApp-first UX**, with easy fallbacks: Telegram + lightweight Web + (later) USSD.
* **Zero user PII by default**, opt-in telemetry; all responses **traceable to sources**.
* **Runs on a \$5–10 VPS**; upgrades smoothly to multi-node.

---

# 1) High-level architecture

```
           ┌─────────────────────────────────────────────────────────────┐
           │                         Channels                             │
           │WhatsApp | Telegram | Web (PWA) | (later) USSD                │
           └──────────────┬───────────────────────────────┬───────────────┘
                          │                               │
                     ┌────▼────┐                     ┌─────▼────┐
                     │  API    │  REST/gRPC          │  Realtime│  WebSocket for web
                     │ Gateway │  Rate limit, Auth   │  Notifs  │  (change alerts)
                     └────┬────┘                     └─────┬────┘
                          │                                   │
                ┌─────────▼────────────────┐                  │
                │         Orchestrator     │                  │
                │  (FastAPI / Litestar)    │                  │
                │  – Query Router          │                  │
                │  – Guardrails + Templ.   │                  │
                │  – Cost/Latency Policy   │                  │
                └─────────┬───────┬────────┘                  │
                          │       │                           │
      ┌───────────────────▼─┐   ┌─▼───────────────────────────▼────────┐
      │ Retrieval Service    │   │  Answer Compose + Summariser         │
      │ Hybrid: BM25 + Vec   │   │  (LLM small local + optional API)    │
      │ 1) Candidate gen     │   │  – Shona/English/Ndebele templates   │
      │ 2) Cross-enc rerank  │   │  – Strict cite injection             │
      └─────────┬───────────┘   └───────────────────────────┬──────────┘
                │                                           │
        ┌───────▼─────────┐                         ┌───────▼───────────┐
        │  Indexes         │                         │   Evaluator       │
        │  - Meilisearch   │                         │  (offline judge)  │
        │  - Qdrant        │                         │  Faithfulness,    │
        │  - pgvector (alt)│                         │  Recall, Latency  │
        └───────┬──────────┘                         └────────┬──────────┘
                │                                            │
         ┌──────▼───────────┐                         ┌──────▼───────────┐
         │  Document Store  │                         │  Telemetry & Ops │
         │  Postgres        │                         │  Prom+Grafana,   │
         │  (sections, meta)│                         │  Loki, Sentry    │
         └──────┬───────────┘                         └────────┬─────────┘
                │                                            │
         ┌──────▼────────────────────────────┐        ┌──────▼──────────┐
         │    Ingestion & Versioning          │        │  Object Store   │
         │  (Celery/Arq workers)              │        │  MinIO (PDFs,   │
         │  - Scrape Veritas/Gazettes/ZimLII  │        │   OCR artifacts)│
         │  - PDF→OCR→Sections→Chunks         │        └─────────────────┘
         │  - Effective dates + graph edges   │
         └────────────────────────────────────┘
```

---

# 2) Core components and choices

## 2.1 Channels

* **WhatsApp** (primary): Meta Cloud API (lowest friction) or Twilio (easier onboarding but paid).
* **Telegram** (free fallback): Bot API.
* **Web (PWA)**: SvelteKit or Next.js static; caches UI + recently viewed sections; offline “lite” content.
* **(Later) USSD**: Through local aggregator; use pre-baked intents (“check RBZ rate rule” etc.).

**Adapter pattern:** each channel maps user messages → `/v1/query`. Responses are rendered via templates per channel (link lengths, line breaks, emoji).

## 2.2 API Gateway & Orchestrator

* **Gateway:** Traefik or NGINX with:

  * IP rate limiting (per channel key),
  * JWT service tokens (channels only; no end-user auth),
  * mTLS between gateway ⇄ services (in-cluster).

* **Orchestrator:** FastAPI (sync endpoints, async I/O inside).

  * **Query Router** decides retrieval mode (keyword vs semantic vs hybrid), applies **time filter** if user asks “as at 1 Jan 2023”.
  * **Guardrails:** refuse open-ended legal advice; always return: *section extract → 3-line summary → citations*.
  * **Policy engine:** latency/cost gates; falls back to local small LLM if API unavailable.

## 2.3 Ingestion & Versioning Pipeline

* **Workers:** Celery (Redis broker) or **Arq** (pure asyncio + Redis) for simplicity.

* **Sources:** Veritas HTML, Government Gazette PDFs, ZimLII headnotes, Hansard (optional).

* **Pipeline steps:**

  1. **Fetch & Diff**

     * Fetch feed; compute **content hash**; skip if unchanged.
     * Extract **effective\_start / effective\_end** from Gazette/Act metadata.
  2. **Normalise**

     * Parse HTML/PDF with **PyMuPDF** → plain text;
     * OCR scanned pages via **Tesseract** (`eng+sn+nd`, DPI upscale, page de-skew, Otsu binarisation).
  3. **Sectioniser**

     * Regex + heuristic parser to split **Part/Chapter/Section/Subsection**;
     * Generate **stable section IDs**: `ACT:CHAPTER:SECTION:SUBSECTION@VERSION`.
  4. **Cross-refs graph**

     * Detect “Section 99(2) refers to 98(1)” → store **edges** (`refers_to`, `amends`, `repeals`).
     * Normalise citations (`SI 118 of 2024` → canonical).
  5. **Chunking for retrieval**

     * Create **overlapping semantic chunks** (e.g., 700–900 chars, stride 200); each chunk stores:

       * full path (`Act → Part → Section`),
       * `effective_start`, `effective_end`,
       * **source link**, page numbers, SHA256 of text.
  6. **Indexing**

     * **BM25**: Meilisearch (lightweight, fast) *or* Elasticsearch/OpenSearch if you already run JVM.
     * **Vectors**: Qdrant (pure Rust; low-mem) *or* pgvector in Postgres for a single DB dependency.
     * **Embeddings:** `bge-small-en-v1.5` (+ multilingual small, or `gte-small`) to keep CPU-friendly. Store 384–768d vectors.
  7. **Quality artefacts**

     * Auto-generate **3-line abstracts** per section (local small LLM), cached;
     * Compute **NER of key terms** (RBZ, PAYE, ZiG, USD, VAT) to aid query parsing.

* **Idempotence:** every step keyed by content hash; retries are safe.

* **Reprocessing:** backfill job to recompute embeddings when models change.

## 2.4 Retrieval Service (Hybrid + Temporal)

1. **Query understanding**

   * Lightweight parser extracts **date context** (“as at 2023-01-01”), currencies, act names, section numerals.
   * Detect language; translate only the **query**, not the documents.

2. **Candidate generation**

   * **BM25 top-k (k=50)** on Meilisearch with filters: effective date, act family.
   * **Vector ANN top-k (k=80)** on Qdrant/pgvector over same filters.

3. **Merge + rerank**

   * De-dup by section ID; keep top 100.
   * **Cross-Encoder reranker** (e.g., `bge-reranker-base`) running CPU quantized; returns top 8–12.

4. **Answer selection**

   * Select **best single section** (or at most 2 where law is split) with **confidence score**.
   * If confidence < threshold, return: “We found likely sections (show 3) — pick one.”

5. **Caching**

   * Keyed by `(normalized_query, date_context)`; 5–30 min TTL.
   * Separate cache for **“top sections today”** to accelerate popular requests.

## 2.5 Answer Composition (Deterministic + Guarded)

* **Template-first** (no freeform LLM output unless needed):

  ```
  ❝ <3-line abstract> ❞
  Section: <Act> <Chapter> §<Section>[<sub>], [as amended <date>]
  Sources: <short link 1>, <short link 2>
  Commands: [Share] [See related §98] [Report issue]
  ```
* **Summariser strategy**

  * Default: **extractive** (highlight key sentences) → quick **shrink** with a **small local instruction model** (e.g., Llama 3.1-8B-Instruct or Qwen2-7B-Instruct, 4-bit GGUF via llama.cpp).
  * **Fallback / high-stakes**: route to API (e.g., GPT-4o-mini) only when:

    * complex multi-section synthesis,
    * or low confidence + user asks for “lawyer mode”.
  * **Never** remove or override citations.
* **Language rendering**: translate *summary line only* to Shona/Ndebele; keep **section/citations in original** to avoid translation errors.

## 2.6 Data model (Postgres)

* `acts(id, title, chapter, jurisdiction, first_effective, last_effective)`
* `versions(id, act_id, version_no, effective_start, effective_end, source_sha, source_url)`
* `sections(id, version_id, number, heading, text, path_jsonb)`
* `section_chunks(id, section_id, start_char, end_char, text, embedding_vector, bm25_terms)`
* `citations(id, from_section_id, to_section_id, type)`
* `sources(id, url, fetched_at, sha, ocr_quality, pages_jsonb)`
* `abstracts(section_id, lang, summary_3_lines, updated_at)`
* `queries(id, channel, text_norm, lang, date_ctx, latency_ms, answer_section_id, confidence, created_at)`
* `feedback(id, query_id, label {correct,wrong,unclear}, note, user_hash)`

**Indices:**

* `(version_id, number)`; GIN over `path_jsonb`; HNSW/IVFFlat for vectors; full-text (BM25) index for terms.

---

# 3) Non-functional requirements (SLOs, scalability, cost)

* **Availability:** 99.5% monthly (single-region) → 99.9% with active-active.
* **Latency:** P95 **< 2.0s** (WhatsApp); P99 < 3.0s.
* **Throughput:** 10 RPS baseline on \$5 VPS; scale linearly by splitting:

  * retrieval service, summariser, and ingestion workers into separate pods.

**Scaling plan:**

* **Tier-0:** Single VM (2 vCPU, 2–4GB RAM): Postgres + Meilisearch + Qdrant + API (docker-compose).
* **Tier-1:** Split DBs; move object store (MinIO) to separate VM; add Redis.
* **Tier-2:** Kubernetes (k3s) on 2–3 low-cost nodes (Hetzner/OCI free tier), HPA on CPU.
* **CDN:** Cloudflare for static PWA and source shortlinks.

**Cost guardrails:**

* Prefer local LLM; cap monthly external LLM spend (if any) via policy.
* Use **quantized models**; disable cross-encoder when cache hit rate > 70%.

---

# 4) Security, privacy, and integrity

* **PII minimisation:** No phone numbers stored; hash a channel-scoped user ID (HMAC with server secret).
* **Transport:** TLS 1.2+; **mTLS** in cluster.
* **At rest:**

  * Postgres: disk encryption (LUKS) or cloud volume encryption.
  * Secrets: Doppler/SOPS/1Password; rotate quarterly.
* **AuthN/Z:** Channel tokens at gateway; service-to-service via **short-lived JWTs** (15 min).
* **Rate limiting & abuse:** per-channel and per hashed user; bot command allowlist.
* **Prompt-injection hardening:**

  * LLM never sees the raw doc store; it sees **curated chunks + fixed template**.
  * Strip instructions from retrieved text; escape special tokens; disable tool use in summariser.
* **Tamper-evident citations:** include **SHA** and source page number; provide “open source PDF” link.
* **Compliance:** GDPR-style rights (delete telemetry); 90-day log retention; DPIA doc.

---

# 5) Observability & resilience

* **Metrics:** Prometheus + Grafana (dashboards: latency, hit-rate, confidence, reranker time, OCR quality).
* **Logs:** JSON logs to Loki (per request trace ID).
* **Tracing:** OpenTelemetry (API → retrieval → summariser).
* **Error tracking:** Sentry (PII scrubber).
* **Health:** `/healthz` (liveness), `/readyz` (dependencies).
* **Backpressure:** Circuit breakers (pybreaker) on LLM/API.
* **QoS degradation:** if vector DB down → BM25-only; if summariser fails → extractive snippet w/ **“No summary available”** banner.

---

# 6) Evaluation & QA

* **Golden set**: 50–100 curated Q→§ answers (tax, labour, currency, licensing).
* **Automated eval (nightly):**

  * Retrieval **Recall\@k** (does correct section appear in top-k?).
  * **Faithfulness** (LLM judge compares summary to section text).
  * **Latency budget** breakdown (parse/retrieve/rerank/summarise).
* **Regression checks** on each corpus update.
* **A/B testing**: reranker on/off, chunk sizes 600 vs 900, BM25 weights.

---

# 7) DevEx, CI/CD, and IaC

* **Repo split (monorepo ok):**
  `/ingestion`, `/retrieval`, `/api`, `/web`, `/ops`
* **CI:** GitHub Actions

  * Pytests + mypy + ruff,
  * Trivy (image scan),
  * Bandit (security),
  * Diff-based test selection (fast).
* **CD:** Render/Fly.io/Hetzner + blue/green deploy; DB migrations via Alembic.
* **IaC:** Terraform or Pulumi for VMs, DNS, buckets, security groups.
* **Backups:** Nightly Postgres + MinIO versions; tested restore runbook.

---

# 8) Detailed request/response flow

**WhatsApp “ZiG premium?” example**

1. Channel adapter → `/v1/query`:

   ```json
   { "text": "If I quote USD can I add premium in ZiG?", "lang_hint": "en", "channel": "wa", "user_hash": "abc..." }
   ```
2. Orchestrator:

   * Detects currency & domain; no date override → **date = today**.
   * Cache lookup (miss) → Retrieval.
3. Retrieval:

   * BM25\@50 + Vec\@80 (filtered by economic/finance tags).
   * Merge, cross-encode → top 10; select §12A + SI 118/2024.
4. Composer:

   * Pull cached 3-line abstract; light touch rewrite to user language; attach citations (shortlinks).
5. Response (rendered to WhatsApp constraints):

   ```
   ❝ Wages can be in any currency agreed in the contract.
      If you quote USD, ZiG must use RBZ mid-rate of the day.
      Extra “premium” above mid-rate is not allowed. ❞
   Section: Labour Act Ch.28:01 §12A (as amended 2024)
   Sources: gov-gazette.link/si118-2024 p.4, veritas.link/labour-12a
   [Share] [See related §99] [Report issue]
   ```
6. Telemetry: 1.6s latency, confidence 0.83, cached abstracts, cache set for 15m.

---

# 9) Data ingestion specifics (pragmatic)

* **Gazette PDFs:**

  * Watch RSS or scrape index weekly.
  * OCR pipeline with **page quality scoring**; low score → human review queue (web UI).
  * Preserve **page anchors** for deterministic citations.

* **Veritas HTML:**

  * Respect robots/terms; pull consolidated Acts; parse canonical section anchors.

* **ZimLII headnotes:**

  * Use only **headnotes & neutral citations** for context links; do not summarise judgments unless permission is clear.

* **Language tags:**

  * Store English text; compute Shona/Ndebele **glossaries** for legal terms to aid translation (e.g., wage=“mubhadharo”).

---

# 10) Model stack (local-first)

* **Embeddings:** `bge-small-en` (384d) + `bge-m3` (multilingual) as needed; quantize via `int8`.
* **Reranker:** `bge-reranker-base` int8 (onnxruntime).
* **Summariser:** `Llama 3.1 8B Instruct` or `Qwen2 7B Instruct` (4-bit GGUF, llama.cpp server).
* **Tokenizer guard:** hard cap output tokens (<= 120); enforce template placeholders.

**Routing logic:**

* If **query length < 15 words** and **top-1 score > 0.75** → extractive + tiny rewrite (no LLM).
* Else local LLM; only if **confidence < 0.5** or **user “lawyer mode”** → external API.

---

# 11) Caching & shortlinks

* **Response cache:** Redis (LRU), 30m TTL with jitter; key includes **effective date**.
* **Section cache:** pre-render common section cards.
* **Shortlinks:** Cloudflare Workers (or your API) to mint `/s/<hash>` that redirects to source PDF page; logs clicks for feedback.

---

# 12) Feedback loop & community accuracy

* **“Report issue”** attaches query, section id, and user note → triage queue.
* **Auto-learn:** boost BM25 terms or update reranker features when many users correct the same mapping.
* **Moderation:** minimal since content is statutes; rate-limit repeats.

---

# 13) Threat model (quick)

* **Scraper poisoning:** Validate sources against whitelists; store SHA & TLS pinning where possible.
* **Prompt injection via source text:** strip suspicious patterns; LLM runs with **no tool access**.
* **Spam/abuse:** per-IP and per-user\_hash quota; exponential backoff responses.
* **Data loss:** nightly encrypted backups; quarterly restore drills.

---

# 14) Testing strategy

* **Unit:** parsers, sectioniser, ID stability, date maths.
* **Integration:** retrieval ranking vs golden set; OCR fidelity on sample PDFs.
* **E2E:** synthetic WhatsApp conversations (Playwright + mock channel).
* **Load:** Locust – 10→100 RPS; ensure P95 under budget.
* **Accessibility:** web UI contrast, screen reader friendly (WCAG AA).

---

# 15) Deployment blueprints

## Single-VM (zero-to-prod)

* Docker Compose services: `api`, `retrieval`, `summariser`, `postgres+pgvector`, `meilisearch`, `qdrant`, `redis`, `minio`, `traefik`.
* Backups: nightly `pg_dump`, MinIO versioning.
* Firewall: only 80/443 open; admin UIs behind Tailscale.

## k3s (lightweight cluster)

* Helm charts; HPA on retrieval+summariser.
* Ingress via Traefik; cert-manager for TLS.
* Node labels for CPU vs GPU (future).

---

# 16) Minimal endpoint spec (REST)

* `POST /v1/query`

  * **Req:** `{ text, lang_hint?, date_ctx?, channel }`
  * **Resp:** `{ summary_3_lines, section_ref, citations:[{title,url,page,sha}], confidence, related_sections[] }`

* `POST /v1/feedback`

  * `{ query_id, label, note? }`

* `GET /v1/sections/{id}`

  * Return canonical metadata, current text, versions.

* `GET /v1/alerts` (auth)

  * User-starred Acts, diff feed since last check.

---

# 17) Rollout plan (MVP → M3)

* **MVP (2–3 weeks):**

  * Ingest: Labour Act + selected SIs; Meilisearch + Qdrant; FastAPI; WhatsApp + Web.
  * Local summariser + extractive fallback; 50-Q golden set; dashboards.

* **M2:**

  * Full Gazette diffing; cross-ref graph; change alerts; Telegram.
  * Add `as at` date queries; offline Raspberry Pi build for clinics.

* **M3:**

  * Case-law headnotes context; lawyer mode; USSD intents (pre-baked FAQs).

---

# 18) What to build first (engineering tasks)

1. **Sectioniser with stable IDs** (tests for gnarly numbering).
2. **Hybrid retrieval (BM25+Vec) + cross-encoder rerank** (feature-flagged).
3. **Template-based composer** (+ strict citation injector).
4. **Golden-set harness** (Recall\@k, Faithfulness, Latency).
5. **WhatsApp + Web adapters** (shared renderer).
6. **Ops baseline** (Prometheus, Grafana, Loki, Sentry, backups).

---

If you want, I can turn this into a repo scaffold (docker-compose, service skeletons, Alembic models, ingestion workers, and CI) in one pass—ready to clone and run on a \$5 VPS.

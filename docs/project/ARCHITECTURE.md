Awesome choice on the name—**RightLine** nails "get the law right, on the line." Below is a production-grade, security-minded, low-latency architecture + full technical spec you can ship and scale. I've aimed for zero/low-budget defaults with clear upgrade paths.

> **📝 Architecture Enhancement Notes (v2.0)**
> 
> This architecture has been enhanced with production-grade patterns while maintaining simplicity:
> - **Security**: Added WAF, zero-trust networking, comprehensive threat mitigation, and automated secret rotation
> - **Resilience**: Implemented circuit breakers, retry strategies with exponential backoff, and multi-tier degradation
> - **Performance**: Enhanced with multi-level caching, connection pooling, and request coalescing
> - **Observability**: Structured logging, distributed tracing, SLO-based alerting, and comprehensive metrics
> - **Operations**: GitOps workflow, blue-green deployments, disaster recovery with defined RTO/RPO
> - **Cost Optimization**: Added spot instance usage, tiered storage, and model quantization strategies
> - **Testing**: Comprehensive test pyramid, chaos engineering, and continuous evaluation framework
>
> All improvements maintain the zero/low-budget philosophy with clear scaling paths from $5 VPS to enterprise deployment.

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

  * **WAF Rules:** OWASP Core Rule Set, SQL injection protection, XSS prevention
  * **Rate limiting:** Token bucket per channel + sliding window per user_hash
  * **JWT service tokens** with automatic rotation (15min expiry, refresh tokens)
  * **mTLS** with certificate pinning and automatic renewal via cert-manager
  * **Request ID injection** for distributed tracing correlation
  * **Geo-blocking** for non-Zimbabwe IPs during initial rollout (configurable)

* **Orchestrator:** FastAPI with async/await throughout.

  * **Query Router** with intelligent caching hints and request deduplication
  * **Circuit Breakers** (py-breaker) with exponential backoff: 
    * Half-open after 30s, full reset after 5 successful calls
    * Separate breakers per downstream service
  * **Guardrails:** Input validation, prompt injection detection, PII scrubbing
  * **Policy engine:** Cost tracking per user_hash, automatic degradation tiers:
    * Tier 1: Full service (hybrid search + reranking + LLM)
    * Tier 2: BM25 + cached summaries only (< 500ms)
    * Tier 3: Static FAQ responses (< 100ms)
  * **Request timeout cascade:** 2s total budget, distributed as:
    * Retrieval: 800ms
    * Reranking: 400ms
    * Summarization: 600ms
    * Buffer: 200ms

## 2.3 Ingestion & Versioning Pipeline

* **Queue Architecture:** 
  * **Primary:** Arq (asyncio + Redis) for simplicity and performance
  * **Dead Letter Queue (DLQ):** Separate Redis list for failed jobs after 3 retries
  * **Priority queues:** High (legal updates), Medium (reprocessing), Low (analytics)
  * **Poison pill handling:** Auto-quarantine malformed documents
  * **Back-pressure:** Rate limiting on source fetching to respect robots.txt

* **Sources with health monitoring:**
  * Veritas HTML (daily check, alert on structure changes)
  * Government Gazette PDFs (RSS with diff detection)
  * ZimLII headnotes (respectful crawling with backoff)
  * Change detection via content hash + structure fingerprinting

* **Pipeline steps with observability:**

  1. **Fetch & Validate**
     * Content hash validation + virus scanning (ClamAV)
     * Source authenticity verification (TLS cert pinning where possible)
     * Automatic retry with exponential backoff (1s, 2s, 4s, 8s)
     * Extract temporal metadata with confidence scoring

  2. **Normalise & Clean**
     * PDF parsing with fallback chain: PyMuPDF → pdfplumber → pdf2image+OCR
     * **OCR Pipeline:**
       * Pre-processing: deskew, denoise, contrast enhancement
       * Tesseract with confidence threshold (>80% or human review)
       * Post-processing: spell correction with legal dictionary
     * Output validation against schema

  3. **Intelligent Sectioniser**
     * ML-based section boundary detection (fine-tuned LayoutLM)
     * Fallback to regex patterns with confidence scoring
     * **Stable ID generation:** Content-based hashing for deduplication
     * Version graph tracking (what changed between versions)

  4. **Knowledge Graph Construction**
     * Bidirectional reference extraction with confidence scores
     * Temporal relationship mapping (supersedes, amends, repeals)
     * Impact analysis (which sections affected by changes)
     * Export to Neo4j for complex traversals (optional)

  5. **Smart Chunking**
     * **Adaptive chunk sizes** based on section complexity:
       * Dense legal text: 500-700 chars
       * Lists/tables: preserve structure
       * Definitions: keep complete
     * **Overlap strategy:** 20% overlap with semantic boundaries
     * Chunk quality scoring for retrieval optimization

  6. **Indexing with Monitoring**
     * **Dual indexing** for zero-downtime updates:
       * Build new index alongside old
       * Atomic swap when complete
     * **Index health checks:**
       * Query latency monitoring
       * Index size tracking
       * Automatic rebalancing

  7. **Quality Assurance**
     * **Automated validation:**
       * Section count consistency
       * Cross-reference integrity
       * Temporal consistency checks
     * **Human-in-the-loop** for low-confidence extractions
     * A/B testing new extraction models

* **Reliability patterns:**
  * **Idempotency:** UUID-based operation tracking
  * **Transaction logs:** Event sourcing for full audit trail
  * **Checkpointing:** Resume from last successful step
  * **Rollback capability:** Version everything, quick revert

## 2.4 Retrieval Service (Hybrid + Temporal)

1. **Query understanding**

   * **Query normalization pipeline:**
     * Spell correction (symspellpy with legal terms dictionary)
     * Entity extraction (spaCy with custom legal NER)
     * Synonym expansion from curated legal thesaurus
   * **Intent classification** (rule-based + small classifier):
     * Definition query → prioritize glossary sections
     * Procedure query → prioritize process/timeline sections
     * Penalty query → prioritize sanctions/penalties sections
   * **Temporal context** extraction with fuzzy date parsing

2. **Candidate generation (parallel execution)**

   * **BM25 top-k (k=50)** with boosting:
     * Title matches: 2.0x boost
     * Section headings: 1.5x boost
     * Recent amendments: 1.2x boost
   * **Vector ANN top-k (k=80)** with dynamic k based on query complexity
   * **Keyword fallback** for exact statute references (e.g., "Section 47")

3. **Merge + rerank**

   * **Reciprocal Rank Fusion** (RRF) with learned weights
   * **Cross-Encoder reranker** with early stopping if confidence > 0.9
   * **Diversity injection:** ensure top results from different acts when relevant

4. **Answer selection**

   * **Confidence scoring** based on:
     * Reranker scores + score gaps between ranks
     * Query coverage (% of query terms found)
     * Temporal match accuracy
   * **Multi-section synthesis** when cross-references detected
   * **Fallback cascade:**
     * High confidence (>0.8): Single best section
     * Medium (0.5-0.8): Top 3 with disambiguation prompt
     * Low (<0.5): Suggest rephrasing + show FAQ

5. **Caching strategy**

   * **L1 Cache** (in-memory LRU): 50 most recent, 1min TTL
   * **L2 Cache** (Redis): normalized queries, 15min TTL
   * **L3 Cache** (PostgreSQL): popular queries, 24h TTL
   * **Warm cache** on startup with top 100 historical queries
   * **Cache invalidation** on document updates via pub/sub

## 2.5 Answer Composition (Deterministic + Guarded)

### Template-based Response Generation

* **Structured templates with channel adaptation:**
  ```python
  # WhatsApp template (emoji-light, link-optimized)
  whatsapp_template = '''
  ❝ {summary_3_lines} ❞
  
  📄 {act_title} §{section_number}
  🔗 {short_link_1} | {short_link_2}
  
  [Share] [Related §{related}] [Report]
  '''
  
  # Web template (rich formatting)
  web_template = '''
  <Card>
    <Summary>{summary_html}</Summary>
    <Citation>{full_citation}</Citation>
    <Actions>...</Actions>
  </Card>
  '''
  ```

### Summarization Pipeline

* **Multi-tier summarization strategy:**

  1. **Tier 1 - Extractive (< 100ms):**
     * TextRank/BERT-extractive for key sentences
     * Pre-computed during ingestion
     * Used for cache hits and high-confidence matches

  2. **Tier 2 - Local LLM (< 600ms):**
     * **Model:** Llama 3.2-3B or Phi-3-mini (2.7B) for ultra-low latency
     * **Optimization:**
       * 4-bit quantization (GGUF/GPTQ)
       * Flash Attention 2 for faster inference
       * KV cache optimization
       * Structured generation with Guidance/Outlines
     * **Prompt template:**
       ```
       Summarize this legal section in EXACTLY 3 lines.
       Each line must be under 100 characters.
       Use simple English. Focus on WHO, WHAT, WHEN.
       Section: {section_text}
       Summary:
       ```

  3. **Tier 3 - API Fallback (< 2s):**
     * Triggered only for complex multi-section synthesis
     * Uses GPT-4o-mini or Claude Haiku for cost efficiency
     * Strict token limits (max 150 output tokens)
     * Response caching for 24 hours

### Language Localization

* **Smart translation strategy:**
  * **Legal terms dictionary:** Pre-translated legal terminology
  * **Template-based translation:** Only translate summary content
  * **Preservation rules:**
    * Keep section numbers in original
    * Keep act titles in English with local name in parentheses
    * Keep citations untranslated for legal accuracy
  * **Quality assurance:**
    * Human-verified translations for top 1000 queries
    * A/B testing different translation approaches

### Response Optimization

* **Performance optimizations:**
  * **Streaming responses** where supported (Web, Telegram)
  * **Progressive enhancement:** Send fast preview, update with full response
  * **Compression:** Brotli for web, optimize for WhatsApp's 4096 char limit
  * **Link shortening:** Custom shortener with analytics
  * **Image generation:** Pre-rendered citation cards for visual platforms

## 2.6 Data model (Postgres with Read Replicas)

**Tables with partitioning strategy:**

* `acts(id, title, chapter, jurisdiction, first_effective, last_effective, is_active, metadata_jsonb)`
* `versions(id, act_id, version_no, effective_start, effective_end, source_sha, source_url)` - partitioned by year
* `sections(id, version_id, number, heading, text, path_jsonb, tsv_text, last_accessed)`
* `section_chunks(id, section_id, start_char, end_char, text, embedding_vector, bm25_terms)` - partitioned by section_id range
* `citations(id, from_section_id, to_section_id, type, confidence_score)`
* `sources(id, url, fetched_at, sha, ocr_quality, pages_jsonb, processing_status)`
* `abstracts(section_id, lang, summary_3_lines, model_version, updated_at)`
* `queries(id, channel, text_norm, lang, date_ctx, latency_ms, answer_section_id, confidence, trace_id, created_at)` - partitioned monthly
* `feedback(id, query_id, label, note, user_hash, processed_at)`
* `audit_log(id, entity_type, entity_id, action, old_value_jsonb, new_value_jsonb, user_hash, created_at)` - partitioned monthly

**Indices & Optimization:**

* **Primary indices:** B-tree on IDs with FILLFACTOR 90
* **Composite indices:** `(version_id, number)`, `(act_id, effective_start)`
* **Full-text search:** GIN index on `tsv_text` with custom legal dictionary
* **Vector search:** HNSW index (m=16, ef_construction=200) or IVFFlat (lists=100)
* **JSONB:** GIN index on frequently queried paths
* **Hot data:** Partial index on `last_accessed > NOW() - INTERVAL '7 days'`

**Connection pooling:** PgBouncer with transaction mode, 20 connections per service

**Read replica strategy:**
* Write to primary, read from replicas for:
  * Search queries
  * Analytics
  * Bulk exports
* Automatic failover with sub-second detection

---

# 3) Non-functional requirements (SLOs, scalability, cost)

## 3.1 Service Level Objectives (SLOs)

* **Availability SLO:** 
  * 99.5% monthly (43min downtime) for MVP
  * 99.9% monthly (4.3min) for production
  * Measured: Successful responses / Total requests
  * Error budget: 0.1% for experimentation

* **Latency SLO:**
  * P50 < 800ms (cached queries)
  * P95 < 2.0s (complex queries)
  * P99 < 3.0s (cold start + complex)
  * Measured at gateway ingress/egress

* **Throughput targets:**
  * Baseline: 10 RPS on $5 VPS
  * Scale: 100 RPS on 3-node cluster
  * Burst: 500 RPS for 60 seconds

## 3.2 Scalability Architecture

**Horizontal scaling dimensions:**
* **Stateless services:** Auto-scale on CPU/memory/request rate
* **Databases:** Read replicas for search, write master for updates
* **Caching layers:** Distributed cache with consistent hashing
* **Queue workers:** Scale based on queue depth and processing time

**Deployment tiers with cost optimization:**

* **Tier-0 (MVP - $5-10/month):**
  * Single VM: 2 vCPU, 4GB RAM (Hetzner/Contabo)
  * Docker Compose with resource limits
  * SQLite/PostgreSQL, Meilisearch, MinIO (single-binary mode)
  * Cloudflare free tier for CDN/WAF

* **Tier-1 (Growth - $30-50/month):**
  * 2 VMs: API/Worker + Database/Cache
  * PostgreSQL with pgBouncer
  * Redis for caching + queue
  * Dedicated Meilisearch instance
  * S3-compatible storage (Backblaze B2)

* **Tier-2 (Scale - $100-200/month):**
  * 3-5 node k3s cluster (spot instances when possible)
  * PostgreSQL with read replicas
  * Redis Cluster mode
  * Qdrant dedicated for vectors
  * Horizontal Pod Autoscaling
  * Multi-region backup

* **Tier-3 (Enterprise - $500+/month):**
  * Managed Kubernetes (EKS/GKE/AKS)
  * RDS/CloudSQL with Multi-AZ
  * ElastiCache/Memorystore
  * Global CDN with edge functions
  * Active-active multi-region

## 3.3 Cost Optimization Strategies

* **Compute optimization:**
  * Spot/preemptible instances for workers (70% cost saving)
  * Reserved instances for stable workloads (40% saving)
  * ARM-based instances where compatible (20% saving)
  * Aggressive autoscaling with fast scale-down

* **Storage optimization:**
  * Tiered storage: Hot (SSD) → Warm (HDD) → Cold (Object)
  * Compression: Zstd for logs, Brotli for API responses
  * Deduplication for document storage
  * Lifecycle policies for automatic archival

* **Model optimization:**
  * Quantization: INT8/INT4 for inference (4x smaller)
  * Model distillation for custom tiny models
  * Dynamic batching for GPU utilization
  * CPU inference with ONNX Runtime

* **Traffic optimization:**
  * Edge caching with 1-hour TTL for popular queries
  * Request coalescing for identical concurrent queries
  * WebP images, Brotli compression for web assets
  * Connection pooling and HTTP/2 multiplexing

---

# 4) Security, privacy, and integrity

## 4.1 Defense in Depth

* **Network Security:**
  * **Zero-trust architecture:** Every service authenticates every request
  * **Network segmentation:** DB tier isolated, ingestion tier sandboxed
  * **TLS 1.3** everywhere with forward secrecy
  * **mTLS** with automatic certificate rotation (cert-manager + Vault)
  * **API Gateway WAF:** Rate limiting, DDoS protection, geo-blocking

* **Application Security:**
  * **Input validation:** Strict schemas with Pydantic, length limits
  * **Output encoding:** Context-aware escaping for each channel
  * **SAST/DAST:** Automated scanning in CI (Semgrep, OWASP ZAP)
  * **Dependency scanning:** Daily vulnerability checks (Trivy, Dependabot)
  * **Container hardening:** Distroless images, non-root users, read-only filesystems

* **Data Security:**
  * **Encryption at rest:** AES-256-GCM for database, E2E for backups
  * **Encryption in transit:** TLS 1.3 with strong ciphers only
  * **Key management:** HashiCorp Vault with automatic rotation
  * **PII handling:**
    * No direct storage of phone numbers or identifiers
    * HMAC-SHA256 with rotating salts for user tracking
    * Automatic PII detection and redaction in logs

## 4.2 Access Control & Authentication

* **Service Authentication:**
  * **OAuth 2.0 + OIDC** for service-to-service (Keycloak/Ory)
  * **JWT tokens:** 15-min expiry, RS256 signing, refresh tokens
  * **API keys:** Scoped per channel, automatic rotation monthly
  * **Mutual TLS:** Certificate pinning for critical services

* **Authorization:**
  * **RBAC with ABAC:** Role-based with attribute conditions
  * **Policy as Code:** Open Policy Agent (OPA) for fine-grained control
  * **Least privilege:** Services only access what they need
  * **Audit logging:** Every access decision logged with context

## 4.3 Threat Mitigation

* **Prompt Injection Defense:**
  * **Input sanitization:** Remove control characters, limit length
  * **Template enforcement:** Fixed output structure, no dynamic execution
  * **Instruction isolation:** User input never mixed with system prompts
  * **Output validation:** Ensure responses match expected format
  * **Canary tokens:** Detect if internal prompts leak

* **Supply Chain Security:**
  * **SBOM generation:** Track all dependencies
  * **Signed commits:** GPG signing required
  * **Binary attestation:** Verify build provenance
  * **Vulnerability disclosure:** Clear security.txt and bug bounty

* **Operational Security:**
  * **Secret rotation:** Automated quarterly rotation via Vault
  * **Break-glass procedures:** Emergency access with full audit
  * **Incident response plan:** Documented runbooks, regular drills
  * **Security monitoring:** SIEM integration, anomaly detection

---

# 5) Observability & resilience

## 5.1 Observability Stack

* **Metrics (RED + USE methods):**
  * **Prometheus** with 15s scrape interval, 90-day retention
  * **Key metrics:**
    * Request rate, error rate, duration (RED)
    * Resource utilization, saturation, errors (USE)
    * Business metrics: queries/sec, confidence distribution, cache hit rate
  * **Grafana dashboards:**
    * Service overview (golden signals)
    * User journey (funnel analysis)
    * Cost tracking (API calls, compute usage)

* **Logging (Structured + Contextual):**
  * **Log aggregation:** Loki with 30-day hot, 90-day cold storage
  * **Log levels:** ERROR (immediate), WARN (review daily), INFO (debug)
  * **Correlation:** Trace ID injection, user session tracking
  * **Sensitive data:** Automatic PII masking, audit mode for debugging

* **Tracing (Distributed + Continuous):**
  * **OpenTelemetry** with Jaeger/Tempo backend
  * **Automatic instrumentation** for HTTP, DB, Redis, queues
  * **Custom spans** for business logic (retrieval, ranking, summarization)
  * **Trace sampling:** 100% for errors, 10% for success, 100% for slow (>2s)

* **Application Performance Monitoring:**
  * **Sentry** for error tracking with source maps
  * **Custom profiling** for CPU/memory hotspots
  * **Real User Monitoring (RUM)** for web UI

## 5.2 Alerting Strategy

* **Alert Levels:**
  * **P1 (Page):** Service down, >10% error rate, data loss risk
  * **P2 (Slack):** Degraded performance, high latency, low confidence
  * **P3 (Email):** Capacity warnings, certificate expiry, model drift

* **Alert Rules (SLO-based):**
  * Error budget consumption rate
  * Multi-window rate analysis (prevent flapping)
  * Predictive alerts (will breach SLO in 2 hours)

## 5.3 Resilience Patterns

* **Circuit Breaker Implementation:**
  ```python
  # Per-service configuration
  retrieval_breaker = CircuitBreaker(
      failure_threshold=5,
      recovery_timeout=30,
      expected_exception=ServiceException,
      fallback_function=use_cache_only
  )
  ```

* **Retry Strategies:**
  * **Exponential backoff** with jitter: 1s * 2^attempt + random(0, 1s)
  * **Retry budget:** Max 10% of requests in retry
  * **Selective retry:** Only on 503, 504, network errors

* **Bulkhead Pattern:**
  * **Thread pool isolation:** Separate pools per downstream service
  * **Queue management:** Bounded queues with backpressure
  * **Resource limits:** CPU/memory limits per service

* **Graceful Degradation Tiers:**
  * **Tier 1:** Full service (all features)
  * **Tier 2:** Essential only (search + cached summaries)
  * **Tier 3:** Static responses (FAQ + offline content)
  * **Tier 4:** Maintenance mode (status page only)

---

# 6) Evaluation, QA & Continuous Improvement

## 6.1 Evaluation Metrics

* **Retrieval Quality:**
  * **Precision@k:** Relevant results in top-k (target: >0.9 @10)
  * **Recall@k:** Coverage of all relevant results (target: >0.95 @50)
  * **MRR (Mean Reciprocal Rank):** Position of first relevant (target: >0.8)
  * **NDCG:** Graded relevance scoring (target: >0.85)

* **Answer Quality:**
  * **Faithfulness:** Summary accuracy vs source (target: >95%)
  * **Completeness:** All key points covered (target: >90%)
  * **Conciseness:** Under 3 lines, <300 chars (target: 100%)
  * **Citation accuracy:** Correct section references (target: >99%)

* **System Performance:**
  * **Latency breakdown:** Per component timing
  * **Cache hit rate:** Target >70% for popular queries
  * **Model inference time:** P95 < 500ms
  * **Error rate:** Target <0.1%

## 6.2 Evaluation Pipeline

```python
# Automated evaluation framework
class EvaluationPipeline:
    def __init__(self):
        self.golden_set = load_golden_dataset()
        self.metrics = []
        
    def evaluate_retrieval(self, query, results):
        # Precision, Recall, MRR, NDCG
        pass
        
    def evaluate_summary(self, summary, source):
        # Faithfulness via LLM judge
        # ROUGE scores for extractive quality
        # Length and format compliance
        pass
        
    def evaluate_latency(self, trace):
        # Component-wise latency analysis
        # Identify bottlenecks
        pass
```

## 6.3 Human-in-the-Loop QA

* **Crowd-sourced validation:**
  * Legal experts review top queries weekly
  * Community feedback via "Report Issue"
  * Lawyer verification for high-stakes sections

* **Active learning:**
  * Flag low-confidence responses for review
  * Improve model with validated corrections
  * Retrain monthly with new annotations

## 6.4 A/B Testing Framework

* **Experiment examples:**
  * Reranker models: BGE vs ColBERT vs Cross-encoder
  * Chunk sizes: 500 vs 700 vs 900 characters
  * BM25 parameters: k1=1.2 vs 1.5, b=0.75 vs 0.5
  * Cache TTL: 5min vs 15min vs 30min
  * Summary models: Llama vs Qwen vs Phi

* **Success criteria:**
  * Statistical significance (p < 0.05)
  * Minimum 5% improvement
  * No latency regression
  * Positive user feedback

## 6.5 Continuous Improvement Loop

1. **Data collection:** All queries, responses, feedback
2. **Analysis:** Weekly metrics review, anomaly detection
3. **Hypothesis:** Identify improvement opportunities
4. **Experimentation:** A/B test with control groups
5. **Validation:** Statistical analysis, user feedback
6. **Rollout:** Gradual deployment with monitoring
7. **Documentation:** Update runbooks and best practices

---

# 7) DevEx, CI/CD, and IaC

## 7.1 Developer Experience

* **Repository structure:**
  ```
  right-line/
  ├── .github/         # CI/CD workflows
  ├── services/        # Microservices
  │   ├── api/
  │   ├── retrieval/
  │   ├── ingestion/
  │   └── summarizer/
  ├── libs/           # Shared libraries
  ├── infra/          # IaC definitions
  ├── k8s/            # Kubernetes manifests
  └── scripts/        # Automation scripts
  ```

* **Local development:**
  * Docker Compose with hot-reload
  * Tilt for Kubernetes-like dev environment
  * Pre-commit hooks: formatting, linting, secrets scanning
  * Makefile for common tasks

## 7.2 Continuous Integration

* **CI Pipeline (GitHub Actions/GitLab CI):**
  ```yaml
  stages:
    - validate:     # 2 min
        - lint (ruff, mypy, black)
        - security scan (Semgrep, Bandit)
        - secrets scan (TruffleHog)
    - test:         # 5 min
        - unit tests (pytest with coverage)
        - integration tests (testcontainers)
        - contract tests (Pact)
    - build:        # 3 min
        - Docker build with cache
        - SBOM generation
        - Vulnerability scan (Trivy, Grype)
    - deploy:       # 2 min
        - Staging (automatic)
        - Production (manual approval)
  ```

* **Quality gates:**
  * Code coverage > 80%
  * No critical vulnerabilities
  * Performance regression < 10%
  * All tests passing

## 7.3 Continuous Deployment

* **Deployment strategies:**
  * **Blue-Green:** For database migrations
  * **Canary:** 5% → 25% → 50% → 100% over 1 hour
  * **Feature flags:** LaunchDarkly/Unleash for gradual rollout
  * **Rollback:** Automatic on error rate > 5%

* **GitOps workflow:**
  * ArgoCD/Flux for Kubernetes deployments
  * Git as source of truth
  * Automatic sync with drift detection
  * Environment promotion via PR

* **Database migrations:**
  * Alembic with forward/backward compatibility
  * Shadow database for testing
  * Online schema changes (pt-online-schema-change)
  * Backup before migration

## 7.4 Infrastructure as Code

* **Terraform modules:**
  ```hcl
  modules/
  ├── compute/     # VMs, Kubernetes
  ├── networking/  # VPC, Load Balancers
  ├── storage/     # Databases, Object Storage
  ├── security/    # IAM, Secrets, Firewall
  └── monitoring/  # Logging, Metrics, Alerts
  ```

* **Multi-environment management:**
  * Terraform workspaces for dev/staging/prod
  * Remote state in S3/GCS with locking
  * Automated plan on PR, apply on merge
  * Cost estimation with Infracost

## 7.5 Disaster Recovery

* **Backup strategy:**
  * **Database:** Continuous WAL archiving + daily snapshots
  * **Object storage:** Cross-region replication
  * **Configuration:** Git repository (encrypted)
  * **Secrets:** Vault backup to encrypted S3

* **Recovery objectives:**
  * **RTO (Recovery Time):** 1 hour for critical, 4 hours for all
  * **RPO (Recovery Point):** 1 hour for transactions, 24 hours for analytics
  * **Backup retention:** 7 daily, 4 weekly, 12 monthly

* **DR procedures:**
  * Documented runbooks for common scenarios
  * Quarterly DR drills with metrics
  * Automated backup verification
  * Multi-region standby (hot or warm)

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

# 14) Comprehensive Testing Strategy

## 14.1 Test Pyramid

* **Unit Tests (70% coverage):**
  * **Core logic:** Parsers, tokenizers, section extractors
  * **Data transformations:** Normalizers, cleaners, validators
  * **Business rules:** Date calculations, version management
  * **Utilities:** Caching, rate limiting, circuit breakers
  * **Tools:** pytest, hypothesis for property testing
  * **Performance:** pytest-benchmark for critical paths

* **Integration Tests (20% coverage):**
  * **Database:** Schema migrations, query performance
  * **Search:** Retrieval accuracy, ranking quality
  * **External services:** API mocking with VCR.py
  * **Message queues:** Producer-consumer contracts
  * **Tools:** testcontainers, pytest-docker

* **E2E Tests (10% coverage):**
  * **User journeys:** Complete query-to-response flows
  * **Channel integration:** WhatsApp, Telegram, Web
  * **Cross-service:** Full pipeline with real services
  * **Tools:** Playwright, Selenium, Appium (mobile)

## 14.2 Quality Assurance

* **Golden Dataset Testing:**
  ```python
  golden_queries = [
      {
          "query": "What is the penalty for tax evasion?",
          "expected_section": "Tax Act §127",
          "min_confidence": 0.85,
          "max_latency_ms": 2000
      },
      # ... 100+ curated examples
  ]
  ```

* **Regression Testing:**
  * Automated runs on every deployment
  * Comparison with baseline metrics
  * Alert on >5% degradation

* **A/B Testing Framework:**
  * Feature flags for gradual rollout
  * Statistical significance testing
  * Automatic rollback on negative impact

## 14.3 Performance Testing

* **Load Testing Scenarios:**
  ```yaml
  scenarios:
    - name: normal_load
      users: 100
      spawn_rate: 10
      duration: 10m
      
    - name: peak_load
      users: 500
      spawn_rate: 50
      duration: 5m
      
    - name: stress_test
      users: 1000
      spawn_rate: 100
      duration: 2m
  ```

* **Performance benchmarks:**
  * Query parsing: < 10ms
  * Cache lookup: < 5ms
  * Database query: < 50ms
  * Vector search: < 200ms
  * Reranking: < 300ms
  * Summary generation: < 500ms

## 14.4 Security Testing

* **Static analysis:** Semgrep, Bandit, Sonarqube
* **Dynamic testing:** OWASP ZAP, Burp Suite
* **Dependency scanning:** Snyk, Dependabot
* **Penetration testing:** Quarterly external audits
* **Fuzzing:** AFL++ for parsers, property testing

## 14.5 Chaos Engineering

* **Failure injection:**
  * Network partitions
  * Service crashes
  * Resource exhaustion
  * Clock skew
  
* **Tools:** Chaos Monkey, Litmus, Gremlin
* **Game days:** Monthly resilience testing

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

# 16) API Design & Specifications

## 16.1 RESTful API Design

**Base URL:** `https://api.rightline.zw/v1`

**Common headers:**
```http
X-Request-ID: uuid
X-Client-Version: 1.0.0
Accept-Language: en,sn,nd
Authorization: Bearer <token>
```

**Core endpoints:**

### Query Endpoint
```http
POST /v1/query
Content-Type: application/json
Idempotency-Key: <uuid>

{"$ref": "#/components/schemas/QueryRequest"}

Response 200:
{"$ref": "#/components/schemas/QueryResponse"}

Response 429: Rate limit exceeded
Response 503: Service degraded (returns cached/simple response)
```

### Batch Query (optimized for mobile)
```http
POST /v1/queries/batch
{"queries": [{"text": "...", "id": "..."}], "max_wait_ms": 2000}

Response: {"results": [...], "partial": true/false}
```

### Feedback Loop
```http
POST /v1/feedback
{"query_id": "uuid", "rating": 1-5, "correct_section": "...", "comment": "..."}
```

### Section Details
```http
GET /v1/sections/{id}?include=history,references,related
Cache-Control: public, max-age=3600
ETag: "version-hash"
```

### Search Suggestions (typeahead)
```http
GET /v1/suggest?q=labour&limit=5
Cache-Control: public, max-age=300
```

## 16.2 WebSocket for real-time

```javascript
// Connection with automatic reconnect
ws://api.rightline.zw/v1/stream

// Subscribe to changes
{"action": "subscribe", "acts": ["labour", "tax"]}

// Receive updates
{"type": "amendment", "act": "labour", "section": "12A", "summary": "..."}
```

## 16.3 GraphQL Alternative (future)

```graphql
type Query {
  search(text: String!, date: Date, limit: Int = 10): SearchResult!
  section(id: ID!): Section
  act(title: String!): Act
}

type SearchResult {
  sections: [Section!]!
  confidence: Float!
  processingTime: Int!
}
```

## 16.4 API Versioning Strategy

* **URL versioning:** `/v1/`, `/v2/` for major changes
* **Header versioning:** `API-Version: 2024-01-15` for minor
* **Deprecation policy:** 6 months notice, 12 months support
* **Feature flags:** `X-Features: new-ranking,multilingual`

## 16.5 Error Handling

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "remaining": 0,
      "reset_at": "2024-01-15T12:00:00Z"
    },
    "request_id": "uuid",
    "documentation_url": "https://docs.rightline.zw/errors#rate-limit"
  }
}
```

## 16.6 OpenAPI Specification

```yaml
openapi: 3.1.0
info:
  title: RightLine API
  version: 1.0.0
  x-api-id: rightline-core
servers:
  - url: https://api.rightline.zw/v1
    description: Production
  - url: https://staging-api.rightline.zw/v1
    description: Staging
components:
  securitySchemes:
    ApiKey:
      type: apiKey
      in: header
      name: X-API-Key
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: /oauth/token
          scopes:
            read: Read access
            write: Write access
```

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

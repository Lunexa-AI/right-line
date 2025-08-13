# RightLine

**Get the law right, on the line.**
A WhatsApp-first legal copilot for Zimbabwe that returns the **exact section + 3-line summary + citations** in Shona, Ndebele, or English.

<p align="left">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-MVP-blue">
  <img alt="PRs" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

> ⚠️ **Not legal advice.** RightLine provides statute sections and citations for information only.

---

## ✨ What it does

* **Plain-language questions → exact statute section** (with citation + page anchors).
* **Three-line summary** (extractive → lightly rewritten), rendered for WhatsApp.
* **Hybrid retrieval**: BM25 + vector ANN + cross-encoder re-rank.
* **Temporal queries**: ask “as at 1 Jan 2023” and get the right version.
* **WhatsApp, Telegram, and Web** (PWA) adapters.
* **Zero/low budget** by using public data and local models.

See the full design in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## 🧱 Repository layout

```
right-line/
├─ api/                 # FastAPI gateway + orchestration
├─ retrieval/           # Hybrid search (BM25 + vectors + reranker)
├─ ingestion/           # Scrapers, OCR, sectioniser, versioning
├─ summariser/          # Local LLM server (templated composing)
├─ web/                 # Minimal PWA (optional)
├─ ops/                 # Docker, compose, k8s, Grafana, migrations
├─ data/                # Local cache: PDFs, OCR artifacts (gitignored)
├─ tests/               # Unit/integration/e2e
├─ README.md
└─ ARCHITECTURE.md
```

> If a folder isn’t present yet in your repo, create it as you implement that component.

---

## 🚀 Quick start (single machine)

**Requirements**

* Linux/macOS (x86\_64)
* Docker + Docker Compose
* \~6–8 GB free disk (for OCR artifacts + indexes)

**1) Clone & configure**

```bash
git clone https://github.com/<you>/right-line.git
cd right-line
cp ops/.env.example .env
# Open .env and set the basics (ports, secrets, channel tokens if any)
```

**2) Bring the stack up**

```bash
docker compose -f ops/compose.yml up -d
# Services: postgres+pgvector, meilisearch, qdrant, redis, minio, api, summariser
```

**3) Seed a tiny sample corpus** (Labour Act + 1–2 Gazettes)

```bash
docker compose exec api python -m ingestion.bootstrap.sample
# Downloads sample PDFs/HTML to data/, runs OCR/sectioniser, builds indexes
```

**4) Ask your first question**

```bash
curl -s http://localhost:8080/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"text":"If I quote USD can I add a ZiG premium?","channel":"dev"}' | jq
```

You should get JSON with `summary_3_lines`, `section_ref`, and `citations`.

---

## ⚙️ Configuration

Create `.env` in the repo root (see `ops/.env.example`):

```ini
# Core
APP_ENV=dev
APP_PORT=8080
APP_SECRET=change-me-please

# Postgres (system of record)
PG_HOST=postgres
PG_PORT=5432
PG_DB=rightline
PG_USER=rightline
PG_PASSWORD=rightline_pwd

# Redis (cache/queues)
REDIS_URL=redis://redis:6379/0

# Meilisearch (BM25) - or set USE_PG_FTS=true to skip it
MEILI_HOST=http://meili:7700
MEILI_KEY=meili-master-key

# Qdrant (vectors) - or set USE_PGVECTOR=true to skip it
QDRANT_HOST=http://qdrant:6333

# MinIO (object store for PDFs/OCR)
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=rightline
MINIO_SECRET_KEY=rightline_secret
MINIO_BUCKET=rightline

# Summariser (local LLM)
SUMMARISER_URL=http://summariser:8088
SUMMARY_MAX_TOKENS=120

# Channel adapters (optional for local dev)
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_BEARER_TOKEN=...
TELEGRAM_BOT_TOKEN=...
```

**Minimalist mode:**

* Set `USE_PGVECTOR=true` to drop Qdrant and store vectors in Postgres.
* Set `USE_PG_FTS=true` to drop Meilisearch and use Postgres FTS.
  This keeps a **single DB dependency** for small deployments.

---

## 🧲 Ingestion pipeline

RightLine ingests public domain sources (e.g., Veritas ZW, Government Gazette PDFs, ZimLII headnotes).

**Run ingestion on demand**

```bash
docker compose exec api python -m ingestion.run --source=veritas --since=2024-01-01
docker compose exec api python -m ingestion.run --source=gazette --weekly
```

Pipeline stages:

1. fetch & diff → 2) OCR (Tesseract) → 3) sectioniser (stable IDs) →
2. cross-references graph → 5) chunk & embed → 6) index BM25 + vectors

> Idempotent by content hash; safe to retry. Artifacts stored in `data/` and MinIO.

---

## 🔎 API (minimal)

### `POST /v1/query`

Ask a question.
**Request**

```json
{ "text": "Can I pay wages in USD?", "lang_hint": "en", "date_ctx": null, "channel": "web" }
```

**Response**

```json
{
  "summary_3_lines": "...",
  "section_ref": { "act":"Labour Act", "chapter":"28:01", "section":"12A", "version":"2024-05-01" },
  "citations": [
    {"title":"SI 118 of 2024", "url":"https://...", "page":4, "sha":"..."}
  ],
  "confidence": 0.83,
  "related_sections": ["28:01-12", "28:01-13"]
}
```

### `POST /v1/feedback`

```json
{ "query_id":"...", "label":"wrong", "note":"Should cite §12A(2)" }
```

More endpoints are documented in **ARCHITECTURE.md**.

---

## 🤖 Local models (summariser/reranker)

* **Embeddings:** `bge-small` (CPU-friendly)
* **Reranker:** `bge-reranker-base` (ONNX int8)
* **Summariser:** `Llama 3.1 8B Instruct` or `Qwen2 7B Instruct` (4-bit via llama.cpp)

All are started by the `summariser` service. Set model names via env if you change them.

**Cost guardrail:** the API routes to local models by default; external LLMs are optional and capped.

---

## 📱 WhatsApp & Telegram (optional)

**WhatsApp (Meta Cloud API)**

* Create an app → WhatsApp → configure webhook → point `POST /channels/whatsapp/webhook`
* Set `WHATSAPP_VERIFY_TOKEN` and `WHATSAPP_BEARER_TOKEN`

**Telegram**

* @BotFather → get token → set `TELEGRAM_BOT_TOKEN`
* Start polling worker:

```bash
docker compose exec api python -m api.channels.telegram_poll
```

Both adapters simply forward messages to `POST /v1/query` and render responses to channel-friendly templates.

---

## 📊 Observability

* **Prometheus + Grafana** (in `ops/`) track: total latency, retrieval hit-rate, reranker time, OCR quality.
* **Loki** for logs (trace ID per request), **Sentry** for errors.
* Health endpoints: `/healthz` (liveness), `/readyz` (dependencies).

Open Grafana at [http://localhost:3000](http://localhost:3000) (default creds in `.env`).

---

## ✅ Quality & evaluation

* **Golden-set YAML** of 50–100 Q→section pairs (PAYE, Labour, currency rules).
* Nightly job computes:

  * **Recall\@k** (did the right section appear in top-k?)
  * **Faithfulness** (summary vs section text)
  * **P95 latency** breakdown

Run locally:

```bash
docker compose exec api python -m eval.run --dataset=eval/golden.yml
```

---

## 🔐 Security & privacy

* **No PII by default**: channel user IDs are hashed (HMAC).
* TLS everywhere; **mTLS** inside the cluster.
* Database at rest encryption (via disk/volume).
* Strict output templates: summaries cannot omit citations.
* **Delete my data** endpoint (telemetry) and 90-day log retention.

---

## 🗺️ Roadmap (high level)

* [ ] “As at DATE” queries (temporal filter UI affordance)
* [ ] Cross-references graph (related sections suggestions)
* [ ] Change alerts: “§12A amended — summary diff”
* [ ] Offline Pi image for legal-aid clinics
* [ ] USSD intents for top 50 queries

See **ARCHITECTURE.md** for the deeper plan.

---

## 🧪 Development

* Python 3.11+, Ruff, Mypy, PyTest
* Pre-commit hooks:

```bash
pipx install pre-commit
pre-commit install
```

* Tests:

```bash
docker compose exec api pytest -q
```

---

## 🤝 Contributing

PRs welcome! Please:

1. Create a small, focused branch.
2. Add tests where feasible.
3. Update docs and keep commits tidy.

By contributing, you agree your code is MIT-licensed.

---

## 📝 License

MIT — see **[LICENSE](LICENSE)**.

---

## 🙏 Acknowledgements

* Thanks to the maintainers of Meilisearch, Qdrant, llama.cpp, and the `bge` model family.
* Data sources include Government Gazette PDFs, Veritas ZW, and ZimLII headnotes (where permitted).

---

## 📫 Contact

Questions, security issues, or partnership requests: **open an issue** or email `<your-contact@domain>`.

---


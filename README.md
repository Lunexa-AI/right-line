# RightLine

**Get the law right, on the line.**  
A WhatsApp-first legal copilot for Zimbabwe that returns the **exact section + 3-line summary + citations** in Shona, Ndebele, or English.

<p align="left">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-Pre--MVP-orange">
  <img alt="Architecture" src="https://img.shields.io/badge/architecture-v2.0-blue">
  <img alt="Coverage" src="https://img.shields.io/badge/coverage-pending-yellow">
  <img alt="PRs" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

> ⚠️ **Not legal advice.** RightLine provides statute sections and citations for information only.

> 📝 **Ready to build?** Check out **[MVP_TASK_LIST.md](MVP_TASK_LIST.md)** for the detailed implementation roadmap.

---

## ✨ Features

### Core Functionality
* **Plain-language questions → exact statute section** with citations & page anchors
* **Three-line summary** via multi-tier pipeline (extractive → local LLM → API fallback)
* **Hybrid retrieval**: BM25 + vector search + cross-encoder reranking (<2s P95)
* **Temporal queries**: "as at 1 Jan 2023" returns historically accurate versions
* **Multi-channel**: WhatsApp, Telegram, Web PWA with channel-optimized responses

### Production Features
* **🔄 Resilience**: Circuit breakers, retries, graceful degradation
* **⚡ Performance**: 3-level caching, request coalescing, read replicas
* **🔒 Security**: Zero-trust, WAF, secret rotation, prompt injection defense
* **📊 Observability**: Distributed tracing, structured logging, SLO alerts
* **💰 Cost-optimized**: Runs on $5 VPS, scales to enterprise

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the complete technical specification.

---

## 🧱 Repository structure

```
right-line/
├─ services/            # Microservices
│  ├─ api/             # FastAPI gateway + orchestration
│  ├─ retrieval/       # Hybrid search engine
│  ├─ ingestion/       # Document processing pipeline
│  └─ summarizer/      # Multi-tier summarization
├─ libs/               # Shared libraries
│  ├─ common/          # Types, config, utilities
│  ├─ database/        # Models, migrations
│  └─ telemetry/       # Logging, metrics, tracing
├─ web/                # Progressive Web App
├─ infra/              # Infrastructure as Code
│  ├─ docker/          # Docker configurations
│  ├─ k8s/            # Kubernetes manifests
│  └─ terraform/       # Cloud resources
├─ tests/              # Test suites
│  ├─ unit/           # Fast, isolated tests
│  ├─ integration/    # Service integration
│  └─ e2e/            # Full system tests
├─ scripts/            # Automation scripts
├─ docs/               # Documentation
├─ .github/            # CI/CD workflows
├─ Makefile            # Common commands
├─ README.md           # This file
├─ ARCHITECTURE.md     # Technical specification
└─ MVP_TASK_LIST.md   # Implementation roadmap
```

---

## 🚀 Quick start

### Prerequisites
* Docker & Docker Compose v2+
* Python 3.11+ (for development)
* 8GB RAM, 10GB disk space
* Linux/macOS (x86_64 or ARM64)

### 1. Setup & Launch

```bash
# Clone repository
git clone https://github.com/<you>/right-line.git
cd right-line

# Setup environment
cp .env.example .env
make setup              # Install deps, pre-commit hooks

# Launch services
make up                 # Start all services
make health             # Verify health

# Seed sample data
make seed-sample        # Load Labour Act + sample Gazettes

# Test the API
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{"text":"What is the minimum wage?","channel":"api"}' | jq
```

### 2. Development workflow

```bash
# Start dev environment with hot-reload
make dev

# Run tests
make test               # All tests
make test-unit         # Unit tests only
make test-watch        # Watch mode

# Code quality
make lint              # Run linters
make format            # Auto-format
make security          # Security scan

# View logs
make logs              # All services
make logs-api          # API only
```

### 3. Access services

* **API**: http://localhost:8000 (OpenAPI docs at /docs)
* **Web UI**: http://localhost:3000
* **Grafana**: http://localhost:3001 (admin/admin)
* **MinIO**: http://localhost:9001 (console)

---

## ⚙️ Configuration

### Environment setup

Copy `.env.example` to `.env` and configure:

```bash
# Core settings
APP_ENV=development          # development|staging|production
APP_SECRET=<generate-with-openssl-rand-hex-32>
API_KEY=<your-api-key>

# Database (PostgreSQL with pgvector)
DATABASE_URL=postgresql://user:pass@localhost:5432/rightline
DB_POOL_SIZE=20

# Cache (Redis)
REDIS_URL=redis://localhost:6379/0

# Search engines
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_KEY=<master-key>
QDRANT_URL=http://localhost:6333

# Object storage (MinIO/S3)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=<access-key>
S3_SECRET_KEY=<secret-key>
S3_BUCKET=rightline

# LLM settings
LLM_MODEL=llama3.2-3b        # or phi-3-mini
LLM_MAX_TOKENS=150
LLM_TEMPERATURE=0.3

# Channel integrations
WHATSAPP_API_TOKEN=<meta-token>
WHATSAPP_PHONE_ID=<phone-id>
TELEGRAM_BOT_TOKEN=<bot-token>

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
GRAFANA_API_KEY=<grafana-key>
```

### Deployment modes

* **Minimal** ($5/month): Single PostgreSQL with pgvector + FTS
* **Standard** ($30/month): Add dedicated search engines
* **Production** ($100+/month): Full stack with redundancy

---

## 📊 Performance & monitoring

### Target SLOs
| Metric | MVP | Production | Status |
|--------|-----|------------|--------|
| P95 latency | <2.5s | <2.0s | 🟡 Pending |
| Availability | 99.0% | 99.9% | 🟡 Pending |
| Error rate | <1% | <0.1% | 🟡 Pending |
| Accuracy | >90% | >95% | 🟡 Pending |

### Observability stack
* **Metrics**: Prometheus + Grafana dashboards
* **Logging**: Structured logs with Loki
* **Tracing**: OpenTelemetry with Jaeger
* **Errors**: Sentry with PII scrubbing
* **Alerts**: PagerDuty/Opsgenie integration

Access dashboards at http://localhost:3001 (admin/admin)

---

## 🗺️ Implementation roadmap

### Phase 1: Foundation (Weeks 1-2) 🔴
- [ ] Project setup & CI/CD pipeline
- [ ] Database schema & migrations
- [ ] Core API with health checks
- [ ] Basic ingestion pipeline
- [ ] Docker Compose configuration

### Phase 2: Core Search (Weeks 3-4) 🟡
- [ ] BM25 search implementation
- [ ] Vector embeddings & storage
- [ ] Query parsing & normalization
- [ ] Caching layer setup
- [ ] API rate limiting

### Phase 3: Intelligence (Weeks 5-6) 🟡
- [ ] Cross-encoder reranking
- [ ] Local LLM integration
- [ ] Template-based responses
- [ ] Confidence scoring
- [ ] Performance optimization

### Phase 4: Channels (Weeks 7-8) 🟡
- [ ] WhatsApp adapter
- [ ] Web UI (PWA)
- [ ] Response formatting
- [ ] Error handling
- [ ] E2E testing

### Phase 5: Production (Weeks 9-10) 🟡
- [ ] Monitoring & alerting
- [ ] Security hardening
- [ ] Backup & recovery
- [ ] Performance tuning
- [ ] Launch preparation

**📝 See [MVP_TASK_LIST.md](MVP_TASK_LIST.md) for detailed task breakdown**

---

## 🤝 Contributing

We welcome contributions! Areas we need help:

* **OCR accuracy** for scanned Gazette PDFs
* **Language models** for Shona/Ndebele
* **Legal parsing** for citation extraction
* **Performance** optimization
* **Testing** expansion of golden dataset

### Contribution process

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Make changes with tests
4. Commit using conventional commits (`feat:`, `fix:`, `docs:`)
5. Push and create a Pull Request
6. Address review feedback

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 🔐 Security & privacy

### Security features
* **Zero-trust architecture** with mTLS between services
* **WAF protection** with OWASP Core Rule Set
* **Automated secret rotation** via HashiCorp Vault
* **Prompt injection defense** with input sanitization
* **No PII storage** - user IDs are HMAC-hashed
* **Encryption** at rest (AES-256) and in transit (TLS 1.3)

### Privacy compliance
* GDPR-style data rights
* 90-day log retention
* Right to deletion
* Audit logging

Report security issues to: security@rightline.zw

---

## 📚 Resources

* **Documentation**: [docs/](docs/)
* **API Reference**: http://localhost:8000/docs
* **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
* **Task List**: [MVP_TASK_LIST.md](MVP_TASK_LIST.md)
* **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

MIT — see **[LICENSE](LICENSE)**

---

## 🙏 Acknowledgements

* Veritas Zimbabwe for legal texts
* Zimbabwe Legal Information Institute
* Government of Zimbabwe Gazette
* Open-source community (Meilisearch, Qdrant, llama.cpp, BGE models)

---

**⚠️ Disclaimer**: RightLine provides legal information, not legal advice. Always consult qualified legal professionals.

**🚀 Ready to build?** Start with **[MVP_TASK_LIST.md](MVP_TASK_LIST.md)** for step-by-step implementation.
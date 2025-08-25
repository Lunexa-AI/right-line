# Gweta — AI Legal Workbench for Zimbabwe

<p align="center">
  <strong>AI‑first legal research and workflows for Zimbabwe.</strong><br>
  Enterprise‑grade, evidence‑first, and built to become agentic.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-MVP-orange">
  <a href="https://github.com/Lunexa-AI/right-line/issues"><img alt="Issues" src="https://img.shields.io/github/issues/Lunexa-AI/right-line"></a>
</p>

## What is Gweta?

Gweta is an AI‑native legal assistant and workbench for Zimbabwe.

- **Gweta Web (Enterprise)**: an enterprise research workbench for law firms, enterprises, and government. Evidence‑first RAG with citations — designed to evolve into agentic tooling (drafting, tool calling, strategy workflows, document analysis).
- **Gweta WhatsApp (Citizens)**: a free chatbot for ordinary citizens (planned continuity), built on the same retrieval foundation.

Speak in natural language (English, Shona, or Ndebele) and get cited answers from authoritative sources.

## ✨ MVP Capabilities (Today)

- **Research Omnibox**: Ask anything about Zimbabwean law; get a TL;DR, key points, and citations.
- **High‑quality retrieval**: OpenAI embeddings → Milvus Cloud → lightweight reranking.
- **Cited answers**: Every response includes sources; copy/share/feedback controls.
- **Fast**: Target P95 < 2s on typical networks.
- **Accessible**: Dark/light, keyboard flow, mobile‑friendly.

## 🌱 Coming in V2 (Agentic Workflows)

- **Document uploads and analysis** (PDF/DOCX): summarize, compare, extract; per‑matter context.
- **Tool calling / Agents**: drafting assistants, clause finder, citation checker, web search.
- **Case/matter workspaces**: multi‑doc reasoning, history, notes, and tasks.
- **Team & client onboarding**: roles/permissions, secure sharing.
- **Connectors**: Google Drive/OneDrive/SharePoint; email intake.

See the detailed roadmaps in `docs/project/MVP_ARCHITECTURE.md` and `docs/project/V2_ARCHITECTURE.md`.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Vercel CLI)
- OpenAI API account
- Milvus Cloud account (optional for Phase 1)

### Installation

```bash
# Clone the repository
git clone https://github.com/Lunexa-AI/right-line.git
cd right-line

# Install dependencies and Vercel CLI
make setup

# Copy environment variables
cp configs/example.env .env.local
# Edit .env.local with your OpenAI API key and other configuration

# Start Vercel development server
make dev
```

### Basic Usage

```bash
# Example API request (local development)
curl -X POST http://localhost:3000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "text": "What is the penalty for theft?",
    "lang_hint": "en"
  }'

# Response
{
  "summary_3_lines": "Theft carries imprisonment up to 10 years.\nFine may be imposed instead or in addition.\nCourt considers value and circumstances.",
  "section_ref": {
    "act": "Criminal Law Act",
    "chapter": "9:23",
    "section": "113"
  },
  "citations": [{
    "title": "Criminal Law (Codification and Reform) Act",
    "url": "...",
    "page": 47
  }],
  "confidence": 0.92
}
```

## 📚 Documentation

- [**MVP Architecture**](docs/project/MVP_ARCHITECTURE.md) — Search/Research MVP on Vercel + Milvus + OpenAI
- [**V2 Architecture**](docs/project/V2_ARCHITECTURE.md) — Agentic extensions (uploads, drafting, workspaces)
- [**Quick Start**](docs/QUICKSTART.md) - Get running in 5 minutes
- [**Deployment Guide**](docs/DEPLOYMENT.md) - Vercel deployment instructions
- [**Contributing**](docs/project/CONTRIBUTING.md) - How to contribute to Gweta
- [**MVP Task List**](docs/project/MVP_TASK_LIST.md) - Development milestones and progress

## 🛠️ Development

```bash
# Run tests
make test

# Format and lint
make format lint

# Security checks
make security

# View all commands
make help
```

> **Note**: Pre-commit hooks are currently disabled for rapid MVP development. See [CI Management Guide](docs/development/ci-management.md) for details.

## 🏗️ Architecture (MVP)

Serverless and unover‑engineered:

- **Vercel Functions (FastAPI + Mangum)** handle `/api/v1/query` and analytics.
- **Milvus Cloud** stores chunk embeddings for fast similarity search.
- **OpenAI** provides embeddings and answer composition.
- Static **web/** UI delivers an AI‑native chat/research experience.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- Pull request process
- Testing requirements

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Zimbabwe Legal Information Institute (ZimLII) for legal content
- The open-source community for the amazing tools we build upon

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/Lunexa-AI/right-line/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Lunexa-AI/right-line/discussions)

---

<p align="center">
  Built with ❤️ for accessible legal information in Zimbabwe
</p>
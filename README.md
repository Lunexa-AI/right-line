# RightLine

<p align="center">
  <strong>Get the law right, on the line.</strong><br>
  WhatsApp-first legal information for Zimbabwe
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-Pre--MVP-orange">
  <a href="https://github.com/Lunexa-AI/right-line/issues"><img alt="Issues" src="https://img.shields.io/github/issues/Lunexa-AI/right-line"></a>
</p>

## What is RightLine?

RightLine is a legal information assistant that provides instant access to Zimbabwean law via WhatsApp. Ask a question in plain language (English, Shona, or Ndebele) and get:

- 📜 **Exact statute section** relevant to your query
- 📝 **3-line summary** in your language
- 📚 **Citations** with page references

> ⚠️ **Disclaimer**: RightLine provides legal information, not legal advice. Always consult qualified legal counsel for legal matters.

## ✨ Key Features

- **Multi-language**: English, Shona, and Ndebele support
- **Fast responses**: Under 2 seconds on 2G networks
- **Temporal queries**: Find laws as they were on specific dates
- **Source verification**: Every response includes exact citations
- **Offline-first**: Works even with limited connectivity

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector
- Redis 7+
- Docker & Docker Compose (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/Lunexa-AI/right-line.git
cd right-line

# Install dependencies
make setup

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration

# Run with Docker Compose
make up

# Or run locally
make dev
```

### Basic Usage

```python
# Example API request
curl -X POST http://localhost:8000/v1/query \
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

- [**Architecture**](docs/project/ARCHITECTURE.md) - System design and technical specifications
- [**API Reference**](docs/api/README.md) - Complete API documentation
- [**Deployment Guide**](docs/deployment/README.md) - Production deployment instructions
- [**Contributing**](docs/project/CONTRIBUTING.md) - How to contribute to RightLine
- [**Roadmap**](docs/project/ROADMAP.md) - Development milestones and progress

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

## 🏗️ Architecture

RightLine uses a microservices architecture optimized for low latency and high reliability:

- **API Gateway** - FastAPI with request orchestration
- **Retrieval Service** - Hybrid BM25 + vector search
- **Ingestion Pipeline** - Document processing with OCR
- **Summarizer** - Multi-tier summarization (local → API)

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

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
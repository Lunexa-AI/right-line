# Gweta — AI Legal Workbench for Zimbabwe

<p align="center">
  <strong>An agentic, AI‑first legal research and workflow assistant for Zimbabwe.</strong><br>
  Enterprise‑grade, evidence‑first, and built for complex reasoning.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11+-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-v2.0%20(In%20Dev)-blue">
  <a href="https://github.com/Lunexa-AI/right-line/issues"><img alt="Issues" src="https://img.shields.io/github/issues/Lunexa-AI/right-line"></a>
</p>

## What is Gweta?

Gweta is an AI‑native legal assistant and workbench for Zimbabwe.

- **Gweta Web (Enterprise)**: An enterprise research workbench for law firms, enterprises, and government. It uses an advanced agentic RAG pipeline to deliver evidence-based answers with citations, and is designed to handle complex, multi-step legal queries.
- **Gweta WhatsApp (Citizens)**: A free chatbot for ordinary citizens (planned continuity), built on the same retrieval foundation.

Speak in natural language (English, Shona, or Ndebele) and get cited answers from authoritative sources.

## ✨ v2.0 Capabilities

- **Agentic Reasoning**: Decomposes complex questions, rewrites queries for clarity, and validates evidence before answering.
- **Advanced Hybrid Retrieval**: Combines dense vector search (Milvus), keyword search (BM25), and a powerful reranker (`BGE-reranker-v2`) for high-precision results.
- **Personalized & Stateful**: Remembers conversation history and user context via Firebase to provide more relevant answers over time.
- **Cited, High-Quality Answers**: Every response includes sources. The system uses a "small-to-big" retrieval strategy, searching small chunks but providing the LLM with full parent documents for better context.
- **Secure & Scalable**: Serverless architecture on Vercel with JWT-based authentication via Firebase.

## 🌱 Future Roadmap

- **Document Uploads and Analysis** (PDF/DOCX): Summarize, compare, extract; per‑matter context.
- **Tool Calling / Agents**: Drafting assistants, clause finder, citation checker, web search.
- **Case/Matter Workspaces**: Multi‑doc reasoning, history, notes, and tasks.
- **Connectors**: Google Drive/OneDrive/SharePoint; email intake.

See the detailed plan in the [`docs/project/MVP_TASK_LIST.md`](docs/project/MVP_TASK_LIST.md).

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for Vercel CLI)
- **Firebase Project** (for authentication and Firestore)
- OpenAI API account
- Milvus Cloud account

### Installation

```bash
# Clone the repository
git clone https://github.com/Lunexa-AI/right-line.git
cd right-line

# Install dependencies and Vercel CLI
make setup

# Copy environment variables
cp configs/example.env .env.local
# Edit .env.local with your API keys (OpenAI, Milvus) and Firebase config
```

### Running Locally
1.  **Start the frontend/backend server**:
    ```bash
    make dev
    ```
2.  **Authenticate**: The web interface (running on `http://localhost:3000`) will now require you to sign up or log in.
3.  **Get a JWT Token**: Use your browser's developer tools to find the JWT token sent in the `Authorization` header of an API request after you log in.
4.  **Make an API request**:

```bash
# Example API request (local development)
# Replace YOUR_JWT_TOKEN_HERE with the token from your browser
curl -X POST http://localhost:3000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -d '{
    "text": "What is the penalty for theft?",
    "lang_hint": "en"
  }'

# Response
{
  "tldr": "Theft can result in imprisonment for up to 10 years, or a fine, or both, depending on the circumstances of the case.",
  "key_points": [
    "The maximum penalty for theft is imprisonment for a period not exceeding ten years.",
    "A fine may be imposed as an alternative to, or in addition to, imprisonment.",
    "The court considers the value of the stolen property and other aggravating or mitigating factors."
  ],
  "citations": [{
    "title": "Criminal Law (Codification and Reform) Act",
    "url": "...",
    "page": null,
    "sha": null
  }],
  "suggestions": [
    "What factors does a court consider when sentencing for theft?",
    "Tell me more about the Criminal Law (Codification and Reform) Act"
  ],
  "confidence": 0.92,
  "source": "hybrid",
  "request_id": "req_167...",
  "processing_time_ms": 2345
}
```

## 📚 Documentation

- [**v2.0 Architecture**](docs/project/MVP_ARCHITECTURE.md) — The complete design for the agentic RAG system.
- [**v2.0 Task List**](docs/project/MVP_TASK_LIST.md) — Development milestones for the v2.0 migration.
- [**Quick Start**](docs/QUICKSTART.md) - Get running in 5 minutes.
- [**Contributing**](docs/project/CONTRIBUTING.md) - How to contribute to Gweta.

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

## 🏗️ Architecture (v2.0)

A modular, agentic system built on a serverless stack:

- **Vercel Functions (FastAPI + Mangum)**: Handles the API layer, including the core agentic engine.
- **Firebase**: Provides user authentication (Auth) and state management (Firestore) for conversations and user profiles.
- **Milvus Cloud**: Stores dense vector embeddings for semantic search.
- **BM25 Index**: Powers sparse, keyword-based search for hybrid retrieval.
- **OpenAI**: Used for embeddings, agentic reasoning (planning), and final answer synthesis.
- **Static Web UI**: Delivers a secure, authenticated AI‑native chat/research experience.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/project/CONTRIBUTING.md) for:
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
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

## ✨ Capabilities

- **Agentic Reasoning**: Decomposes complex questions, rewrites queries for clarity, and validates evidence before answering.
- **Advanced Hybrid Retrieval**: Combines dense vector search (Milvus), keyword search (BM25), and a powerful reranker (`BGE-reranker-v2`) for high-precision results.
- **Personalized & Stateful**: Remembers conversation history and user context via Firebase to provide more relevant answers over time.
- **Cited, High-Quality Answers**: Every response includes sources. The system uses a "small-to-big" retrieval strategy, searching small chunks but providing the LLM with full parent documents for better context.
- **Secure & Scalable**: Serverless architecture on Vercel with JWT-based authentication via Firebase.

---

> For detailed technical documentation, architecture, and contribution guides, please see the [**Gweta Documentation Hub**](docs/README.md).

---

## 🙏 Acknowledgments

- Zimbabwe Legal Information Institute (ZimLII) for legal content
- The open-source community for the amazing tools we build upon

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/Lunexa-AI/right-line/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Lunexa-AI/right-line/discussions)
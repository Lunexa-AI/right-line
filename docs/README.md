# Gweta Documentation

Welcome to the Gweta documentation. This directory contains comprehensive guides for using, deploying, and contributing to Gweta.

## 📚 Documentation Structure

### For Users
- **Gweta Web (Enterprise)**: Evidence‑first legal research workbench for organisations (see UI improvements in `project/MVP_UI_IMPROVEMENTS.md`)
- **Gweta WhatsApp (Citizens)**: Free chatbot — “Get the smart lawyer friend you always wanted.”
- [**API Reference**](api/README.md) - Complete API documentation with examples
- [**Quick Start Guide**](../README.md#-quick-start) - Get started quickly

### For Developers
- [**Architecture**](../ARCHITECTURE.md) - System design and technical specifications
- [**Contributing Guide**](../CONTRIBUTING.md) - How to contribute to the project
- [**Development Setup**](../CONTRIBUTING.md#-development-setup) - Local development environment

### For Operations
- [**Deployment Guide**](deployment/README.md) - Production deployment instructions
- [**Monitoring**](deployment/README.md#monitoring-setup) - Observability setup
- [**Security**](deployment/README.md#security-hardening) - Security best practices

### Project Management
- [**Roadmap**](../ROADMAP.md) - Development milestones and timeline
- [**Task List**](../MVP_TASK_LIST.md) - Detailed implementation tasks

## 🔍 Quick Links

### Getting Help
- [GitHub Issues](https://github.com/Lunexa-AI/right-line/issues) - Report bugs or request features
- [GitHub Discussions](https://github.com/Lunexa-AI/right-line/discussions) - Ask questions and share ideas

### Key Concepts
- **Hybrid Retrieval**: Combination of BM25 and vector search for optimal results
- **Multi-tier Summarization**: Local model → API fallback for cost optimization
- **Temporal Queries**: Query laws as they existed on specific dates
- **Source Verification**: Every response includes exact citations

## 📖 Additional Resources

### Technical Deep Dives
- Vector Search Implementation (coming soon)
- Prompt Engineering for Legal Text (coming soon)
- Performance Optimization Techniques (coming soon)

### Legal Domain
- Understanding Zimbabwean Legal System (coming soon)
- Legal Information vs Legal Advice (coming soon)
- Citation Standards (coming soon)

## 🚀 Getting Started

Choose your path:

1. **I want to use the API** → [API Documentation](api/README.md)
2. **I want to deploy Gweta** → [Deployment Guide](deployment/README.md)
3. **I want to contribute** → [Contributing Guide](../CONTRIBUTING.md)
4. **I want to understand the architecture** → [Architecture](../ARCHITECTURE.md)

## 📝 Documentation Standards

When contributing to documentation:

1. Use clear, concise language
2. Include code examples where relevant
3. Keep documentation close to code
4. Update docs with code changes
5. Test all examples before committing

## 🔄 Keeping Docs Updated

Documentation is maintained alongside code:
- API changes require doc updates
- New features need documentation
- Breaking changes must be clearly noted
- Examples should be tested regularly

---

*Documentation is a continuous effort. If you find errors or gaps, please [open an issue](https://github.com/Lunexa-AI/right-line/issues) or submit a PR.*

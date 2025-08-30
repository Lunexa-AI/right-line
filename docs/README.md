# Gweta Documentation Hub

Welcome to the central documentation hub for Gweta. This is the starting point for developers, contributors, and anyone interested in the technical details of the project.

---

## 📚 Core Documentation

-   [**v2.0 Architecture**](project/MVP_ARCHITECTURE.md): The complete technical design for the agentic RAG system.
-   [**v2.0 Task List**](project/MVP_TASK_LIST.md): A detailed breakdown of the development milestones for the v2.0 migration.
-   [**API Documentation**](api/README.md): Endpoint definitions, authentication details, and request/response examples.
-   [**Contributing Guide**](project/CONTRIBUTING.md): Instructions and guidelines for how to contribute to Gweta.

---

## 🚀 Getting Started: Quick Start Guide

### Prerequisites

-   Python 3.11+
-   Node.js 18+ (for Vercel CLI)
-   **Firebase Project** (for authentication and Firestore)
-   OpenAI API account
-   Milvus Cloud account

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
```

---

## 🌱 Project Roadmap

-   **Document Uploads and Analysis** (PDF/DOCX): Summarize, compare, extract; per‑matter context.
-   **Tool Calling / Agents**: Drafting assistants, clause finder, citation checker, web search.
-   **Case/Matter Workspaces**: Multi‑doc reasoning, history, notes, and tasks.
-   **Connectors**: Google Drive/OneDrive/SharePoint; email intake.

---

## 🛠️ Development & Tooling

Common development commands are available via the `Makefile`.

```bash
# Run all tests
make test

# Format code and run linters
make format lint

# Run security checks
make security

# View all available commands
make help
```

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details.

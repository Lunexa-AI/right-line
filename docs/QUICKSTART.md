# Gweta Quick Start Guide

> **Get Gweta running locally in 5 minutes.** This guide gets you from zero to a working local instance of the Gweta legal Q&A system.

## Prerequisites
- Python 3.11+
- Poetry for Python package management
- Node.js 18+ (for frontend and Vercel CLI)
- OpenAI API account
- Milvus Cloud account (optional, for full RAG capabilities)
- Firebase project for authentication and database

## Step 1: Clone and Setup (2 minutes)
```bash
# Clone repository
git clone https://github.com/Lunexa-AI/right-line.git
cd right-line

# Install Python dependencies using Poetry
poetry install

# Install frontend dependencies (assuming a frontend directory exists)
# cd frontend && npm install
```

## Step 2: Environment Setup (1 minute)
Create a `.env` file in the root of the project and add your environment variables.
```bash
# Create root .env file
cat > .env << EOF
# FastAPI Settings
APP_ENV=development
DEBUG=True
HOST="0.0.0.0"
PORT=8000
WORKERS_COUNT=1

# Firebase (replace with your actual service account JSON)
GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type": "service_account", ...}'

# AI Services
OPENAI_API_KEY=sk-proj-your-openai-api-key-here

# Vector Database (Milvus)
MILVUS_URI="your-milvus-uri"
MILVUS_TOKEN="your-milvus-token"
EOF
```

## Step 3: Start Local Development (1 minute)

### Backend (FastAPI on uvicorn)
```bash
# Start the backend server from the root directory
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# The backend API will be available at http://localhost:8000
```

### Frontend (Vercel)
If you have a frontend application, you would typically run it like this:
```bash
# Navigate to your frontend directory
# cd frontend

# Start the frontend development server
# npm run dev or vercel dev

# The frontend will be available at http://localhost:3000
```

## Step 4: Test The Backend (1 minute)
```bash
# Test API health
curl http://localhost:8000/healthz

# Test a query
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the minimum wage in Zimbabwe?", "user_id": "local-test"}'

# Open the API docs
open http://localhost:8000/docs
```

## Step 5: Deploy to Production
For full deployment instructions, please see the detailed guide:
- **[Deployment Guide](./project/DEPLOYMENT.md)**

The guide covers:
- Deploying the **backend** to **Render**.
- Deploying the **frontend** to **Vercel**.

## What You Get
✅ **Working Locally**:
- A fully functional FastAPI backend.
- API endpoints for health, queries, and user management.
- Interactive API documentation via Swagger UI.

🔴 **Next Steps**:
- Connect a frontend application to the local API.
- Run the data ingestion scripts (`scripts/`) to populate your database.
- Deploy the backend and frontend to their respective hosting providers.

## Need Help?
- Review architecture: `docs/project/MVP_ARCHITECTURE.md`
- See full deployment guide: `docs/project/DEPLOYMENT.md`
- FastAPI docs: https://fastapi.tiangolo.com/
- Render docs: https://render.com/docs
- Vercel docs: https://vercel.com/docs

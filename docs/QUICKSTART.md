# Gweta MVP Quick Start Guide (Vercel Edition)

> **Get Gweta running in 5 minutes** - This guide gets you from zero to a working serverless legal Q&A system.

## Prerequisites
- Python 3.11+
- Node.js 18+ (for Vercel CLI)
- OpenAI API account
- Milvus Cloud account (optional for Phase 1)

## Step 1: Clone and Setup (1 minute)
```bash
# Clone repository
git clone https://github.com/yourusername/gweta.git
cd gweta

# Install Vercel CLI
npm install -g vercel

# Install Python dependencies
pip install -r requirements.txt
```

## Step 2: Environment Setup (1 minute)
```bash
# Create local environment file
cat > .env.local << EOF
RIGHTLINE_SECRET_KEY=your-secret-key-at-least-32-characters-long
RIGHTLINE_APP_ENV=development
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
# Milvus (optional for Phase 1, needed for Phase 2)
# MILVUS_ENDPOINT=https://your-cluster.api.gcp-us-west1.zillizcloud.com
# MILVUS_TOKEN=your-cluster-token
EOF
```

## Step 2: Start Local Development (1 minute)
```bash
# Start Vercel development server
vercel dev

# This will:
# 1. Start local serverless functions
# 2. Serve static files
# 3. Hot reload on changes
# 4. Available at http://localhost:3000
```

## Step 3: Test It Works (1 minute)
```bash
# Test API health
curl http://localhost:3000/api/healthz

# Test a query (hardcoded responses work immediately)
curl -X POST http://localhost:3000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the minimum wage in Zimbabwe?"}'

# Open web UI
open http://localhost:3000
```

## Step 4: Deploy to Production (1 minute)
```bash
# Login to Vercel (if not already)
vercel login

# Deploy to production
vercel --prod

# Your app will be live at:
# https://gweta-your-username.vercel.app

# Set production environment variables
vercel env add OPENAI_API_KEY
# Enter your OpenAI API key when prompted
```

## What You Get
✅ **Working Now (Phase 1 - Complete)**:
- Serverless web interface for legal queries
- 36 pre-configured legal topics with hardcoded responses
- WhatsApp webhook ready
- Auto-scaling with zero server management
- Global CDN distribution

🔴 **Coming Next (Phase 2 - In Progress)**:
- Real document ingestion from ZimLII
- Milvus Cloud vector search
- OpenAI embeddings and completion
- Hybrid retrieval (keyword + semantic)

## Common Issues & Fixes

### Vercel CLI not found
```bash
# Install Node.js first, then:
npm install -g vercel
```

### Function timeout
```bash
# Check logs
vercel logs --follow

# Common causes:
# - OpenAI API slow response
# - Cold start delay (first request)
```

### Environment variables not working
```bash
# Pull production env vars to local
vercel env pull .env.local

# List all env vars
vercel env ls
```

### Local development issues
```bash
# Make sure you're in the project directory
cd gweta

# Try clearing Vercel cache
vercel dev --debug
```

## Next Steps
1. **Add WhatsApp**: Configure Meta Business API webhook to `https://your-app.vercel.app/api/webhook`
2. **Custom Domain**: Add your domain in Vercel dashboard
3. **Ingest Documents**: Run `python scripts/crawl_zimlii.py` to fetch legal documents
4. **Enable RAG**: Follow Phase 2 tasks in `docs/project/MVP_TASK_LIST.md`
5. **Monitor Costs**: Track OpenAI usage in their dashboard

## Need Help?
- Check logs: `vercel logs --follow`
- Review architecture: `docs/project/MVP_ARCHITECTURE.md`
- See full deployment guide: `docs/DEPLOYMENT.md`
- Vercel docs: https://vercel.com/docs

---
**Time to first serverless query: ~5 minutes** 🚀

# Gweta MVP Deployment Guide (Vercel Serverless Edition)

> **📦 Serverless deployment for MVP**: Vercel functions with Milvus Cloud and OpenAI. Aligns with MVP_ARCHITECTURE.md. Total setup: ~15 minutes. Pay-per-use scaling.

## 🎯 Deployment Philosophy
- **Serverless-First**: Zero server management; auto-scaling.
- **Managed Services**: Vercel + Milvus Cloud + OpenAI; no infrastructure.
- **Secure by Default**: HTTPS, API keys, edge functions.
- **Fast**: <2s responses; global CDN distribution.

## 📊 Platform: Vercel + Milvus Cloud + OpenAI
- **Vercel**: Free tier (100GB-hours/month), then $20/month Pro
- **Milvus Cloud**: Free tier (1GB storage), then $0.10/million queries
- **OpenAI**: Pay-per-use ($0.50/1M embedding tokens, $1.50/1M GPT-3.5 tokens)

## 🚀 Quick Start
### Prerequisites
- GitHub account (for code repository)
- Vercel account (free tier available)
- OpenAI API account (pay-per-use)
- Milvus Cloud account (free tier available)

### Step 1: Service Setup (5 minutes)

#### 1.1 OpenAI API Key
```bash
# Get API key from https://platform.openai.com/api-keys
# Example: sk-proj-abc123...
export OPENAI_API_KEY="sk-proj-your-key-here"
```

#### 1.2 Milvus Cloud Setup
```bash
# Sign up at https://cloud.milvus.io/
# Create a cluster (free tier: 1 cluster, 1GB storage)
# Get connection details:
export MILVUS_ENDPOINT="https://your-cluster.api.gcp-us-west1.zillizcloud.com"
export MILVUS_TOKEN="your-cluster-token"
```

#### 1.3 Vercel Account
```bash
# Sign up at https://vercel.com/
# Install Vercel CLI
npm install -g vercel
vercel login
```

### Step 2: Repository Setup (3 minutes)
```bash
# Fork/clone the repository
git clone https://github.com/yourusername/gweta.git
cd gweta

# Install dependencies locally (for development)
pip install -r requirements.txt

# Test local development
vercel dev
```

### Step 3: Environment Configuration (2 minutes)
```bash
# Set Vercel environment variables
vercel env add RIGHTLINE_SECRET_KEY
# Enter: your-secret-key-at-least-32-characters-long

vercel env add OPENAI_API_KEY
# Enter: sk-proj-your-openai-key

vercel env add MILVUS_ENDPOINT  
# Enter: https://your-cluster.api.gcp-us-west1.zillizcloud.com

vercel env add MILVUS_TOKEN
# Enter: your-cluster-token

vercel env add RIGHTLINE_APP_ENV
# Enter: production
```

### Step 4: Deploy to Vercel (2 minutes)
```bash
# Deploy to production
vercel --prod

# Your app will be available at:
# https://gweta-your-username.vercel.app
```

### Step 5: Verify Deployment (1 minute)
```bash
# Test the API health
curl https://gweta-your-username.vercel.app/api/healthz

# Test a query (should work with hardcoded responses)
curl -X POST https://gweta-your-username.vercel.app/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is minimum wage?"}'

# Check Vercel function logs
vercel logs
```

### Step 6: Custom Domain (Optional)
```bash
# In Vercel dashboard, add custom domain
# Go to Project Settings > Domains
# Add: yourdomain.com
# Configure DNS A record to point to Vercel's IP

# Or via CLI:
vercel domains add yourdomain.com
```

## 📊 Data Ingestion (Phase 2 Setup)

### Milvus Collection Setup
```python
# Run locally to set up Milvus collection
python scripts/init-milvus.py

# Expected output:
# ✅ Connected to Milvus Cloud
# ✅ Collection 'legal_chunks' created
# ✅ HNSW index created on embedding field
```

### Document Ingestion Pipeline
```bash
# 1. Crawl documents (run locally)
python scripts/crawl_zimlii.py

# 2. Parse and chunk documents
python scripts/parse_docs.py

# 3. Generate embeddings and upload to Milvus
python scripts/generate_embeddings.py
# This will use OpenAI API to generate embeddings
# and upload them to your Milvus Cloud cluster
```

## 🔄 Backup Strategy
- **Code**: Automatically backed up in GitHub
- **Milvus Data**: Managed backups by Milvus Cloud (free tier: 7-day retention)
- **Analytics**: Stored in Vercel KV (managed service)
- **No manual backups needed** for serverless architecture

## 📈 Monitoring
- **Vercel Analytics**: Built-in request monitoring and performance metrics
- **OpenAI Usage**: Track via OpenAI dashboard (tokens, costs)
- **Milvus Metrics**: Monitor via Milvus Cloud console (queries, storage)
- **Custom Logs**: View via `vercel logs` or Vercel dashboard

## 🚨 Troubleshooting

### Function timeouts
```bash
# Check function logs
vercel logs --follow

# Common issues:
# - OpenAI API timeout (increase timeout in vercel.json)
# - Milvus connection timeout (check credentials)
# - Cold start delay (first request may be slow)
```

### Environment variable issues
```bash
# List all environment variables
vercel env ls

# Update environment variable
vercel env rm OPENAI_API_KEY
vercel env add OPENAI_API_KEY

# Pull environment variables to local
vercel env pull .env.local
```

### API errors
```bash
# Test OpenAI connection locally
python -c "import openai; print(openai.embeddings.create(model='text-embedding-3-small', input='test'))"

# Test Milvus connection locally
python -c "from pymilvus import connections; connections.connect(uri='YOUR_ENDPOINT', token='YOUR_TOKEN')"
```

### Performance issues
```bash
# Check Vercel Analytics for slow functions
# Go to Vercel Dashboard > Your Project > Analytics

# Monitor OpenAI usage and costs
# Go to OpenAI Platform > Usage

# Check Milvus performance
# Go to Milvus Cloud > Your Cluster > Monitoring
```

## 📊 Scaling Path
- **Current MVP**: Auto-scales with Vercel (0 to thousands of concurrent users)
- **Cost Optimization**: Monitor usage and optimize OpenAI token usage
- **Future (V2)**: See `docs/project/V2_ARCHITECTURE.md` for advanced features

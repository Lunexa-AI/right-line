# RightLine MVP Quick Start Guide

> **Get RightLine running in 5 minutes** - This guide gets you from zero to a working legal Q&A system.

## Prerequisites
- Ubuntu 22.04 VPS with 2GB RAM (or local Docker)
- Python 3.11+
- Docker & Docker Compose

## Step 1: Clone and Setup (1 minute)
```bash
# Clone repository
git clone https://github.com/yourusername/right-line.git
cd right-line

# Create environment file
cat > .env << EOF
RIGHTLINE_SECRET_KEY=your-secret-key-at-least-32-characters-long
RIGHTLINE_DATABASE_URL=postgresql://rightline:rightline@localhost:5432/rightline
RIGHTLINE_REDIS_URL=redis://localhost:6379/0
RIGHTLINE_APP_ENV=development
EOF
```

## Step 2: Start Services (2 minutes)
```bash
# Create minimal docker-compose for MVP
cat > docker-compose.mvp.yml << 'EOF'
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: rightline
      POSTGRES_USER: rightline
      POSTGRES_PASSWORD: rightline
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  api:
    build: services/api
    ports: ["8000:8000"]
    environment:
      RIGHTLINE_APP_ENV: ${RIGHTLINE_APP_ENV}
      RIGHTLINE_SECRET_KEY: ${RIGHTLINE_SECRET_KEY}
      RIGHTLINE_DATABASE_URL: postgresql://rightline:rightline@postgres:5432/rightline
    depends_on: [postgres]

volumes:
  pgdata:
EOF

# Start services
docker-compose -f docker-compose.mvp.yml up -d
```

## Step 3: Test It Works (1 minute)
```bash
# Test API health
curl http://localhost:8000/healthz

# Test a query
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the minimum wage in Zimbabwe?"}'

# Open web UI
open http://localhost:8000
```

## Step 4: Deploy to Production (1 minute)
```bash
# On your VPS
ssh your-vps-ip

# Install Docker (if not installed)
curl -fsSL https://get.docker.com | sh

# Copy files and deploy
rsync -avz . user@your-vps-ip:/opt/rightline/
ssh user@your-vps-ip "cd /opt/rightline && docker-compose -f docker-compose.mvp.yml up -d"
```

## What You Get
✅ **Working Now (Phase 1 - Complete)**:
- Web interface for legal queries
- 36 pre-configured legal topics
- WhatsApp webhook ready
- Basic analytics and feedback

🔴 **Coming Next (Phase 2 - In Progress)**:
- Real document ingestion from ZimLII
- Vector search with pgvector
- Hybrid retrieval (keyword + semantic)
- Automatic summarization

## Common Issues & Fixes

### Port 8000 already in use
```bash
# Find and kill the process
lsof -i :8000
kill -9 <PID>
```

### Database connection failed
```bash
# Check postgres is running
docker ps
# Check logs
docker logs rightline-postgres
```

### Slow responses
- This is normal on first start while services initialize
- Subsequent queries should be <1 second

## Next Steps
1. **Add WhatsApp**: Configure Meta Business API webhook to `http://your-domain:8000/webhook`
2. **Add HTTPS**: Use Let's Encrypt with certbot
3. **Ingest Documents**: Run `python scripts/crawl_zimlii.py` to fetch legal documents
4. **Enable RAG**: Follow Phase 2 tasks in `docs/project/MVP_TASK_LIST.md`

## Need Help?
- Check logs: `docker logs rightline-api`
- Review architecture: `docs/project/MVP_ARCHITECTURE.md`
- See full deployment guide: `docs/DEPLOYMENT.md`

---
**Time to first query: ~5 minutes** 🚀

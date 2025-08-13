# Deployment Guide

## Overview

This guide covers deploying RightLine to various environments, from a simple VPS to Kubernetes clusters.

## Deployment Options

### Option 1: Single VPS (Recommended for MVP)

Suitable for: MVP, small-scale deployment (< 1000 users)

#### Requirements
- Ubuntu 22.04 LTS
- 2 CPU cores minimum
- 4GB RAM minimum  
- 20GB SSD storage
- Docker & Docker Compose installed

#### Steps

1. **Server Setup**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | bash

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Add user to docker group
sudo usermod -aG docker $USER
```

2. **Clone Repository**
```bash
git clone https://github.com/Lunexa-AI/right-line.git
cd right-line
```

3. **Configure Environment**
```bash
# Copy and edit environment variables
cp .env.example .env.production
nano .env.production

# Key variables to set:
# - SECRET_KEY (generate with: openssl rand -hex 32)
# - Database passwords
# - API tokens
# - Domain name
```

4. **Deploy with Docker Compose**
```bash
# For staging
docker-compose -f docker-compose.staging.yml up -d

# For production
docker-compose -f docker-compose.production.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

5. **Setup SSL with Certbot**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot --nginx -d api.yourdomain.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

### Option 2: Kubernetes Deployment

Suitable for: Scale-out deployments, enterprise

#### Prerequisites
- Kubernetes cluster (1.27+)
- kubectl configured
- Helm 3 installed

#### Steps

1. **Create Namespace**
```bash
kubectl create namespace rightline-production
```

2. **Install Dependencies**
```bash
# PostgreSQL with pgvector
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgres bitnami/postgresql \
  --namespace rightline-production \
  --values k8s/values/postgres.yaml

# Redis
helm install redis bitnami/redis \
  --namespace rightline-production \
  --values k8s/values/redis.yaml
```

3. **Deploy RightLine**
```bash
# Apply configurations
kubectl apply -f k8s/config/

# Deploy services
kubectl apply -f k8s/deployments/

# Expose services
kubectl apply -f k8s/services/

# Setup ingress
kubectl apply -f k8s/ingress/
```

4. **Verify Deployment**
```bash
kubectl get pods -n rightline-production
kubectl get svc -n rightline-production
kubectl get ingress -n rightline-production
```

### Option 3: Managed Cloud Services

Suitable for: Production, high availability

#### AWS Architecture
```
- ECS Fargate for services
- RDS PostgreSQL with pgvector
- ElastiCache for Redis  
- S3 for object storage
- CloudFront CDN
- Application Load Balancer
```

#### GCP Architecture
```
- Cloud Run for services
- Cloud SQL PostgreSQL
- Memorystore for Redis
- Cloud Storage for objects
- Cloud CDN
- Cloud Load Balancing
```

## Environment Variables

### Required Variables

```bash
# Core
APP_ENV=production
SECRET_KEY=<generate-strong-key>
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://host:6379/0

# Search
MEILISEARCH_URL=http://meilisearch:7700
MEILISEARCH_KEY=<master-key>
QDRANT_URL=http://qdrant:6333

# Channels
WHATSAPP_TOKEN=<whatsapp-business-api-token>
TELEGRAM_TOKEN=<telegram-bot-token>

# Monitoring
SENTRY_DSN=<sentry-project-dsn>
```

### Optional Variables

```bash
# Performance
WORKER_COUNT=4
REQUEST_TIMEOUT_MS=2000
CACHE_TTL_SECONDS=3600

# Security
RATE_LIMIT_PER_MINUTE=60
ALLOWED_ORIGINS=https://yourdomain.com
```

## Database Setup

### 1. PostgreSQL with pgvector

```sql
-- Create database
CREATE DATABASE rightline_production;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Run migrations
alembic upgrade head
```

### 2. Initial Data Loading

```bash
# Load legal documents
python scripts/load_documents.py --source data/laws/

# Build search indices
python scripts/build_indices.py

# Verify data
python scripts/verify_data.py
```

## Monitoring Setup

### Prometheus Metrics

Metrics available at `/metrics`:
- Request count and latency
- Database connection pool
- Cache hit rates
- Model inference time

### Grafana Dashboards

Import dashboards from `monitoring/grafana/`:
- Service Overview
- Database Performance
- Cache Analytics
- Error Tracking

### Health Checks

```bash
# Run health check
./scripts/health_check.sh production

# Smoke tests
./scripts/smoke_test.sh production
```

## Security Hardening

### 1. Network Security
```bash
# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Application Security
- Enable rate limiting
- Configure CORS properly
- Use secure headers
- Rotate secrets regularly

### 3. Database Security
- Use SSL connections
- Configure pg_hba.conf
- Regular backups
- Principle of least privilege

## Backup & Recovery

### Automated Backups

```bash
# Database backup script
0 2 * * * /opt/rightline/scripts/backup_db.sh

# Document backup
0 3 * * * /opt/rightline/scripts/backup_documents.sh
```

### Recovery Procedure

```bash
# Restore database
pg_restore -d rightline_production backup.dump

# Restore documents
aws s3 sync s3://backup-bucket/documents/ /data/documents/

# Rebuild indices
python scripts/rebuild_indices.py
```

## Scaling Guidelines

### Vertical Scaling
- API: 2-4 CPU, 2-4GB RAM
- Retrieval: 2-4 CPU, 4-8GB RAM  
- Database: 4-8 CPU, 8-16GB RAM

### Horizontal Scaling
- API: 2-10 replicas
- Retrieval: 2-5 replicas
- Workers: Auto-scale on queue depth

## Troubleshooting

### Common Issues

1. **High latency**
   - Check database queries
   - Review cache hit rates
   - Monitor CPU/memory usage

2. **Connection errors**
   - Verify network connectivity
   - Check connection pools
   - Review firewall rules

3. **Out of memory**
   - Adjust container limits
   - Optimize model loading
   - Enable swap (temporary fix)

### Logs Location

- Application: `/var/log/rightline/`
- Docker: `docker logs <container>`
- Kubernetes: `kubectl logs <pod>`

## Rollback Procedure

```bash
# Docker Compose
docker-compose down
git checkout <previous-version>
docker-compose up -d

# Kubernetes
kubectl rollout undo deployment/api -n rightline-production
```

## Support

For deployment support:
- Check [troubleshooting guide](troubleshooting.md)
- Review [GitHub Issues](https://github.com/Lunexa-AI/right-line/issues)
- Contact team via Slack/Discord

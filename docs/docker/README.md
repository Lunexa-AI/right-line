# Docker Setup for RightLine

## Overview

RightLine uses Docker for containerization with individual Dockerfiles for each microservice, optimized for both development and production environments.

## Service Architecture

```
rightline/
├── services/
│   ├── api/Dockerfile          # API Gateway
│   ├── ingestion/Dockerfile    # Document Processing Worker
│   ├── retrieval/Dockerfile    # Search & Ranking Service
│   └── summarizer/Dockerfile   # Text Summarization Service
├── docker-compose.dev.yml      # Development environment
├── docker-compose.staging.yml  # Staging environment
└── docker-compose.production.yml # Production environment
```

## Key Features

### 🚀 Optimization
- **Multi-stage builds**: Minimal final image size
- **Layer caching**: Fast rebuilds during development
- **Build-time model downloads**: Pre-cached ML models
- **Optimized base images**: python:3.11-slim

### 🔒 Security
- **Non-root users**: All services run as `rightline` user (UID 1000)
- **Minimal runtime dependencies**: Only essential packages
- **No build tools in production**: Clean runtime images
- **Health checks**: Built-in liveness probes

### 🎯 Service-Specific Configurations

#### API Service
- FastAPI with Uvicorn
- Port: 8000
- Workers: 2 (configurable)
- Health endpoint: `/health`

#### Ingestion Service
- Arq worker (no exposed port)
- OCR support (Tesseract)
- PDF processing (Poppler)
- Consumes from Redis queue

#### Retrieval Service
- Port: 8001
- Optimized for ML workloads
- NumPy/SciPy with OpenBLAS
- Vector search capabilities

#### Summarizer Service
- Port: 8002
- Pre-downloaded models
- PyTorch/ONNX Runtime
- CPU-optimized inference

## Building Images

### Individual Services

```bash
# Build API service
make build-api

# Build ingestion service
make build-ingestion

# Build retrieval service  
make build-retrieval

# Build summarizer service
make build-summarizer
```

### All Services

```bash
# Build all development images
make build

# Build production images
make build-prod
```

## Running Services

### Development Environment

```bash
# Start all services
make up

# View logs
make logs

# Stop services
make down
```

### Production Environment

```bash
# Start production stack
make up-prod

# With specific version
VERSION=v1.0.0 docker-compose -f docker-compose.production.yml up -d
```

## Development Workflow

### Hot Reload
Development compose mounts source code for hot reload:
```yaml
volumes:
  - ./services/api:/app/services/api:ro
  - ./libs:/app/libs:ro
```

### Debugging
Set debug environment variables:
```bash
APP_ENV=development
LOG_LEVEL=DEBUG
PYTHONDEBUG=1
```

### Local Testing
```bash
# Test individual service
docker run --rm rightline/api:dev python -m pytest

# Shell access
docker run --rm -it rightline/api:dev /bin/bash
```

## Environment Variables

### Common Variables
```bash
APP_ENV=production|staging|development
LOG_LEVEL=INFO|DEBUG|WARNING|ERROR
SERVICE_NAME=api|ingestion|retrieval|summarizer
```

### Service-Specific

#### API
```bash
PORT=8000
SECRET_KEY=<secure-key>
RATE_LIMIT_PER_MINUTE=60
```

#### Ingestion
```bash
WORKER_CONCURRENCY=4
BATCH_SIZE=100
```

#### Retrieval
```bash
OMP_NUM_THREADS=4
CACHE_TTL_SECONDS=3600
```

#### Summarizer
```bash
DEVICE=cpu|cuda
MODEL_PATH=/app/models
MAX_LENGTH=512
```

## Resource Limits

### Development
```yaml
resources:
  limits:
    cpus: '1.0'
    memory: 1G
```

### Production
```yaml
resources:
  limits:
    cpus: '2.0'
    memory: 2G
  reservations:
    cpus: '1.0'
    memory: 1G
```

## Health Checks

All services include health checks:
```dockerfile
HEALTHCHECK --interval=30s \
            --timeout=10s \
            --start-period=40s \
            --retries=3 \
  CMD curl -f http://localhost:${PORT}/health
```

## Troubleshooting

### Build Issues

1. **Poetry not found**
   ```bash
   # Ensure Poetry version matches
   ARG POETRY_VERSION=1.7.1
   ```

2. **Dependency conflicts**
   ```bash
   # Clear Docker cache
   docker system prune -a
   docker build --no-cache
   ```

3. **Out of space**
   ```bash
   # Clean up unused images
   docker image prune -a
   ```

### Runtime Issues

1. **Service not starting**
   ```bash
   # Check logs
   docker logs rightline-api-dev
   
   # Verify health
   docker inspect rightline-api-dev --format='{{.State.Health}}'
   ```

2. **Permission denied**
   ```bash
   # Ensure proper ownership
   chown -R 1000:1000 ./data
   ```

3. **Port conflicts**
   ```bash
   # Check port usage
   lsof -i :8000
   ```

## Best Practices

1. **Always use specific tags** (not `latest`)
2. **Pin dependency versions** in requirements
3. **Use .dockerignore** to exclude unnecessary files
4. **Run security scans** on images
5. **Monitor image sizes** - target < 500MB per service
6. **Use BuildKit** for improved caching:
   ```bash
   DOCKER_BUILDKIT=1 docker build .
   ```

## CI/CD Integration

GitHub Actions workflow example:
```yaml
- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    file: services/api/Dockerfile
    push: true
    tags: ghcr.io/${{ github.repository }}/api:${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

## Security Scanning

```bash
# Scan with Trivy
trivy image rightline/api:dev

# Scan with Grype
grype rightline/api:dev
```

## Monitoring

Each container exposes metrics:
- Prometheus metrics: `/metrics`
- Health status: `/health`
- Readiness: `/ready`

## Next Steps

- Set up Kubernetes manifests for orchestration
- Configure image registry (GitHub Container Registry)
- Implement automated vulnerability scanning
- Add performance profiling tools

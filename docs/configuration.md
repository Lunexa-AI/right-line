# Configuration Guide

## Overview

RightLine uses environment variables for configuration with Pydantic Settings for validation and type safety.

## Quick Start

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   nano .env
   ```

3. The application will automatically load settings on startup.

## Environment Files

- `.env.example` - Template with all available variables
- `configs/development.env` - Development defaults
- `configs/production.env` - Production template

## Core Settings

### Application
```bash
RIGHTLINE_APP_ENV=development          # development|staging|production
RIGHTLINE_LOG_LEVEL=INFO              # DEBUG|INFO|WARNING|ERROR
RIGHTLINE_DEBUG=false                 # Enable debug mode
RIGHTLINE_SECRET_KEY=your-secret-key  # Must be 32+ characters
```

### Database
```bash
RIGHTLINE_DATABASE_URL=postgresql://user:pass@host:5432/db
RIGHTLINE_DATABASE_POOL_SIZE=20       # Connection pool size
```

### Redis
```bash
RIGHTLINE_REDIS_URL=redis://localhost:6379/0
RIGHTLINE_REDIS_MAX_CONNECTIONS=20
```

### Search Engines
```bash
# Meilisearch (BM25 search)
RIGHTLINE_MEILISEARCH_URL=http://localhost:7700
RIGHTLINE_MEILISEARCH_KEY=your-master-key

# Qdrant (vector search)
RIGHTLINE_QDRANT_URL=http://localhost:6333
RIGHTLINE_QDRANT_API_KEY=optional-api-key
```

### Object Storage
```bash
RIGHTLINE_MINIO_URL=http://localhost:9000
RIGHTLINE_MINIO_ACCESS_KEY=minioadmin
RIGHTLINE_MINIO_SECRET_KEY=minioadmin
RIGHTLINE_MINIO_BUCKET=rightline-documents
```

### API Configuration
```bash
RIGHTLINE_API_HOST=0.0.0.0
RIGHTLINE_API_PORT=8000
RIGHTLINE_API_WORKERS=2               # Uvicorn workers
RIGHTLINE_API_TIMEOUT_MS=2000         # Request timeout

# Rate limiting
RIGHTLINE_RATE_LIMIT_PER_MINUTE=60
RIGHTLINE_RATE_LIMIT_BURST=10

# CORS
RIGHTLINE_CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### ML/AI Settings
```bash
RIGHTLINE_MODEL_PATH=/app/models
RIGHTLINE_DEVICE=cpu                  # cpu|cuda
RIGHTLINE_BATCH_SIZE=8
RIGHTLINE_MAX_LENGTH=512
RIGHTLINE_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Channel Integration
```bash
# WhatsApp Business API
RIGHTLINE_WHATSAPP_TOKEN=your-token
RIGHTLINE_WHATSAPP_PHONE_ID=your-phone-id
RIGHTLINE_WHATSAPP_VERIFY_TOKEN=your-verify-token

# Telegram Bot
RIGHTLINE_TELEGRAM_TOKEN=your-bot-token
```

### Monitoring
```bash
RIGHTLINE_SENTRY_DSN=your-sentry-dsn
RIGHTLINE_METRICS_ENABLED=true
RIGHTLINE_OTEL_ENABLED=false
```

## Usage in Code

```python
from libs.common.settings import settings

# Access settings
database_url = settings.database_url
is_dev = settings.is_development

# Settings are validated and typed
assert isinstance(settings.api_port, int)
```

## Environment-Specific Configuration

### Development
- Debug logging enabled
- Hot reload enabled
- Lower rate limits
- Shorter cache TTL

### Production
- Warning level logging
- Multiple workers
- Strict rate limits
- Longer cache TTL
- Monitoring enabled

## Validation

Settings are validated using Pydantic:
- Type checking
- Required field validation
- Custom validators (e.g., secret key length)
- Environment variable parsing

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use strong secret keys** (32+ characters)
3. **Rotate secrets regularly**
4. **Use different secrets** per environment
5. **Limit CORS origins** in production

## Docker Integration

Environment variables are automatically loaded in Docker containers:

```yaml
# docker-compose.yml
services:
  api:
    environment:
      RIGHTLINE_DATABASE_URL: postgresql://...
      RIGHTLINE_SECRET_KEY: ${SECRET_KEY}
```

## Troubleshooting

### Common Issues

1. **Missing required variables**
   ```
   ValidationError: field required
   ```
   Solution: Check `.env.example` for required variables

2. **Invalid secret key**
   ```
   ValueError: Secret key must be at least 32 characters
   ```
   Solution: Generate a longer secret key

3. **Database connection fails**
   ```
   Connection refused
   ```
   Solution: Verify database URL and ensure service is running

### Debugging Configuration

```python
from libs.common.settings import settings

# Print all settings (be careful with secrets!)
print(settings.model_dump())

# Check specific setting
print(f"Database URL: {settings.database_url}")
```

## Reference

All available settings are defined in `libs/common/settings.py` with:
- Type annotations
- Default values
- Validation rules
- Documentation

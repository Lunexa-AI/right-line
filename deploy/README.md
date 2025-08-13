# Deployment Configuration

This directory contains all Docker and deployment-related files that were previously cluttering the root directory.

## 📦 Files

### Docker Compose Files
- **docker-compose.dev.yml** - Development environment with hot reload
- **docker-compose.staging.yml** - Staging environment configuration  
- **docker-compose.production.yml** - Production environment with HA setup
- **docker-compose.override.yml** - Local development overrides

### Docker Configuration
- **Dockerfile** - Main application Dockerfile (moved from root)

## 🚀 Usage

### Development
```bash
# From project root
docker-compose up                    # Uses root docker-compose.yml + override
docker-compose -f deploy/docker-compose.dev.yml up  # Explicit dev config
```

### Staging
```bash
make up-staging
# or
docker-compose -f deploy/docker-compose.staging.yml up -d
```

### Production
```bash
make up-prod
# or  
docker-compose -f deploy/docker-compose.production.yml up -d
```

## 📁 Related Documentation

- **Docker Guide**: [../docs/docker/README.md](../docs/docker/README.md)
- **Deployment Guide**: [../docs/deployment/README.md](../docs/deployment/README.md)
- **Configuration**: [../docs/configuration.md](../docs/configuration.md)

---

*This organization keeps deployment files together while maintaining the convenience of `docker-compose up` from the root.*

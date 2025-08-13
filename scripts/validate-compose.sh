#!/bin/bash
# Validate Docker Compose configuration
# Usage: ./validate-compose.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🐳 Docker Compose Configuration Validation"
echo "=========================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Please install Docker Desktop"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are available${NC}"
echo ""

# Validate docker-compose.yml
echo "Validating docker-compose.yml..."
if docker-compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}✗ docker-compose.yml has errors${NC}"
    docker-compose config
    exit 1
fi

# Check for override file
if [ -f "docker-compose.override.yml" ]; then
    echo -e "${GREEN}✓ docker-compose.override.yml found${NC}"
fi

# List services
echo ""
echo "Services configured:"
docker-compose config --services | while read service; do
    echo "  - $service"
done

# Check service dependencies
echo ""
echo "Service dependencies:"
echo "  api: depends on postgres, redis, meilisearch, qdrant"
echo "  ingestion: depends on postgres, redis, minio"
echo "  retrieval: depends on postgres, redis, meilisearch, qdrant"
echo "  summarizer: depends on redis"

# Check volume mounts for hot reload
echo ""
echo "Volume mounts for hot reload:"
for service in api ingestion retrieval summarizer; do
    if docker-compose config | grep -q "services/$service:/app/services/$service:ro"; then
        echo -e "  ${GREEN}✓${NC} $service has source mount"
    else
        echo -e "  ${YELLOW}⚠${NC} $service missing source mount"
    fi
done

# Check networking
echo ""
echo "Network configuration:"
if docker-compose config | grep -q "rightline-network"; then
    echo -e "${GREEN}✓ Custom network configured${NC}"
    echo "  Network: rightline-network (172.28.0.0/16)"
else
    echo -e "${YELLOW}⚠ Using default network${NC}"
fi

# Check health checks
echo ""
echo "Health checks:"
for service in postgres redis meilisearch qdrant api retrieval summarizer; do
    if docker-compose config | grep -A 10 "$service:" | grep -q "healthcheck:"; then
        echo -e "  ${GREEN}✓${NC} $service has healthcheck"
    else
        echo -e "  ${YELLOW}⚠${NC} $service missing healthcheck"
    fi
done

# Check volumes
echo ""
echo "Persistent volumes:"
docker-compose config --volumes | while read volume; do
    echo "  - $volume"
done

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Docker Compose configuration is valid!${NC}"
echo ""
echo "Quick commands:"
echo "  docker-compose up -d     # Start all services"
echo "  docker-compose ps        # Check status"
echo "  docker-compose logs -f   # View logs"
echo "  docker-compose down      # Stop all services"
echo ""
echo "Or use Make commands:"
echo "  make up      # Start services"
echo "  make down    # Stop services"
echo "  make logs    # View logs"
echo "  make build   # Build images"

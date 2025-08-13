#!/bin/bash
# Wait for all services to be ready before starting the application
# Usage: ./wait-for-services.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
MAX_RETRIES=60
RETRY_INTERVAL=2

echo "🔄 Waiting for services to be ready..."

# Function to check if a service is ready
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local retries=0
    
    echo -n "  Checking $service_name..."
    
    while [ $retries -lt $MAX_RETRIES ]; do
        if eval "$check_command" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓ Ready${NC}"
            return 0
        fi
        
        retries=$((retries + 1))
        if [ $retries -eq $MAX_RETRIES ]; then
            echo -e " ${RED}✗ Timeout${NC}"
            return 1
        fi
        
        echo -n "."
        sleep $RETRY_INTERVAL
    done
}

# Wait for PostgreSQL
wait_for_service "PostgreSQL" "pg_isready -h ${POSTGRES_HOST:-localhost} -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-rightline}"

# Wait for Redis
wait_for_service "Redis" "redis-cli -h ${REDIS_HOST:-localhost} -p ${REDIS_PORT:-6379} ping"

# Wait for Meilisearch
wait_for_service "Meilisearch" "curl -f http://${MEILISEARCH_HOST:-localhost}:${MEILISEARCH_PORT:-7700}/health"

# Wait for Qdrant
wait_for_service "Qdrant" "curl -f http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}/"

# Wait for MinIO
wait_for_service "MinIO" "curl -f http://${MINIO_HOST:-localhost}:${MINIO_PORT:-9000}/minio/health/live"

echo -e "\n${GREEN}✅ All services are ready!${NC}"

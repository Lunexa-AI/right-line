#!/bin/bash
# DEPRECATED: Health check script for RightLine Docker services
# This script is deprecated in favor of Vercel serverless monitoring
# Use Vercel Analytics and `vercel logs` for monitoring instead
# Keep this file for reference only

set -euo pipefail

ENVIRONMENT=${1:-staging}
CHECK_INTERVAL=${CHECK_INTERVAL:-5}
MAX_CHECKS=${MAX_CHECKS:-60}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Service endpoints based on environment
if [ "$ENVIRONMENT" = "production" ]; then
    BASE_URL="https://rightline.zw"
    SERVICES=(
        "api|$BASE_URL/health"
        "postgres|postgresql://rightline:password@localhost:5432/rightline_production"
        "redis|redis://localhost:6379"
        "meilisearch|http://localhost:7700/health"
        "qdrant|http://localhost:6333/"
    )
else
    BASE_URL="https://staging.rightline.zw"
    SERVICES=(
        "api|$BASE_URL/health"
        "postgres|postgresql://rightline:password@localhost:5432/rightline_staging"
        "redis|redis://localhost:6379"
        "meilisearch|http://localhost:7700/health"
        "qdrant|http://localhost:6333/"
    )
fi

echo -e "${YELLOW}Health check for $ENVIRONMENT environment${NC}"
echo "========================================="

check_service() {
    local service_name=$1
    local service_url=$2
    local checks=0
    
    echo -n "Checking $service_name: "
    
    while [ $checks -lt $MAX_CHECKS ]; do
        if [[ "$service_url" == postgresql://* ]]; then
            # PostgreSQL check
            if pg_isready -h localhost -p 5432 -U rightline > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Healthy${NC}"
                return 0
            fi
        elif [[ "$service_url" == redis://* ]]; then
            # Redis check
            if redis-cli ping > /dev/null 2>&1; then
                echo -e "${GREEN}✓ Healthy${NC}"
                return 0
            fi
        else
            # HTTP check
            response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$service_url" 2>/dev/null || echo "000")
            if [ "$response" = "200" ]; then
                echo -e "${GREEN}✓ Healthy${NC}"
                return 0
            fi
        fi
        
        ((checks++))
        if [ $checks -lt $MAX_CHECKS ]; then
            echo -n "."
            sleep $CHECK_INTERVAL
        fi
    done
    
    echo -e "${RED}✗ Unhealthy${NC}"
    return 1
}

# Check all services
FAILED_SERVICES=()

for service_info in "${SERVICES[@]}"; do
    IFS='|' read -r service_name service_url <<< "$service_info"
    if ! check_service "$service_name" "$service_url"; then
        FAILED_SERVICES+=("$service_name")
    fi
done

# Summary
echo "========================================="
if [ ${#FAILED_SERVICES[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All services are healthy!${NC}"
    exit 0
else
    echo -e "${RED}✗ Failed services: ${FAILED_SERVICES[*]}${NC}"
    exit 1
fi

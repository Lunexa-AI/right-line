#!/bin/bash
# Verify Docker setup for RightLine
# This script checks that all Dockerfiles are valid and can be built

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🐳 RightLine Docker Setup Verification"
echo "======================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Check Docker Compose
if ! docker-compose version > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker Compose is available${NC}"

# Verify Dockerfiles exist
echo ""
echo "Checking Dockerfiles..."
SERVICES=("api" "ingestion" "retrieval" "summarizer")
MISSING=0

for service in "${SERVICES[@]}"; do
    if [ -f "services/$service/Dockerfile" ]; then
        echo -e "  ${GREEN}✓${NC} services/$service/Dockerfile exists"
    else
        echo -e "  ${RED}✗${NC} services/$service/Dockerfile missing"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -gt 0 ]; then
    echo -e "${RED}Some Dockerfiles are missing${NC}"
    exit 1
fi

# Verify docker-compose files
echo ""
echo "Checking Docker Compose files..."
COMPOSE_FILES=("docker-compose.dev.yml" "docker-compose.staging.yml" "docker-compose.production.yml")

for compose_file in "${COMPOSE_FILES[@]}"; do
    if [ -f "$compose_file" ]; then
        echo -e "  ${GREEN}✓${NC} $compose_file exists"
        # Validate YAML syntax
        if docker-compose -f "$compose_file" config > /dev/null 2>&1; then
            echo -e "    ${GREEN}✓${NC} Valid YAML syntax"
        else
            echo -e "    ${RED}✗${NC} Invalid YAML syntax"
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} $compose_file not found (optional)"
    fi
done

# Check .dockerignore
echo ""
if [ -f ".dockerignore" ]; then
    echo -e "${GREEN}✓ .dockerignore exists${NC}"
else
    echo -e "${YELLOW}⚠ .dockerignore not found (recommended)${NC}"
fi

# Dry-run build test (optional, requires Docker)
echo ""
read -p "Do you want to test building the images? This may take several minutes (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Testing Docker builds..."
    
    for service in "${SERVICES[@]}"; do
        echo -e "\n${YELLOW}Building $service...${NC}"
        if docker build -f "services/$service/Dockerfile" -t "rightline/$service:test" . --target builder > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service build successful${NC}"
            # Clean up test image
            docker rmi "rightline/$service:test" > /dev/null 2>&1
        else
            echo -e "${RED}✗ $service build failed${NC}"
        fi
    done
fi

# Summary
echo ""
echo "======================================"
echo -e "${GREEN}✅ Docker setup verification complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run 'make build' to build all images"
echo "  2. Run 'make up' to start development environment"
echo "  3. Run 'make logs' to view service logs"
echo ""
echo "For more information, see docs/docker/README.md"

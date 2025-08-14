#!/bin/bash
# Deploy RightLine MVP to production server
# Usage: ./scripts/deploy-mvp.sh <server-ip-or-domain>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REMOTE_HOST="${1:-}"
REMOTE_USER="${REMOTE_USER:-rightline}"
REMOTE_DIR="/opt/rightline"
ENV_FILE="${2:-.env.production}"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Validate inputs
if [ -z "$REMOTE_HOST" ]; then
    echo "Usage: $0 <server-ip-or-domain> [env-file]"
    echo "Example: $0 rightline.co.zw .env.production"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
fi

log_info "🚀 Starting deployment to $REMOTE_HOST..."

# Step 1: Build Docker image locally
log_info "📦 Building Docker image..."
docker build -t rightline/api:mvp -f services/api/Dockerfile . || log_error "Docker build failed"

# Step 2: Save Docker image
log_info "💾 Saving Docker image..."
docker save rightline/api:mvp | gzip > /tmp/rightline-mvp.tar.gz

# Step 3: Create deployment package
log_info "📦 Creating deployment package..."
DEPLOY_DIR=$(mktemp -d)
cp docker-compose.mvp.yml "$DEPLOY_DIR/"
cp -r nginx "$DEPLOY_DIR/" 2>/dev/null || log_warn "No nginx config found"
cp "$ENV_FILE" "$DEPLOY_DIR/.env"
cp -r scripts "$DEPLOY_DIR/"

# Step 4: Upload to server
log_info "📤 Uploading to server..."
scp -r /tmp/rightline-mvp.tar.gz "$DEPLOY_DIR"/* "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/" || log_error "Upload failed"

# Step 5: Deploy on server
log_info "🔧 Deploying on server..."
ssh "$REMOTE_USER@$REMOTE_HOST" << 'ENDSSH' || log_error "Deployment failed"
set -euo pipefail

cd /opt/rightline

echo "📥 Loading Docker image..."
docker load < rightline-mvp.tar.gz

echo "🔄 Updating services..."
# Stop existing services gracefully
docker-compose -f docker-compose.mvp.yml down --timeout 30 || true

# Start new services
docker-compose -f docker-compose.mvp.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
for i in {1..30}; do
    if docker-compose -f docker-compose.mvp.yml exec -T api curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "✅ API is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Show service status
docker-compose -f docker-compose.mvp.yml ps

# Run any migrations (if needed)
# docker-compose -f docker-compose.mvp.yml exec -T api python -m alembic upgrade head || true

# Cleanup old images
docker image prune -f

echo "✅ Deployment successful!"
ENDSSH

# Step 6: Verify deployment
log_info "🔍 Verifying deployment..."
sleep 5

# Check health endpoint
if curl -f -s "http://$REMOTE_HOST/healthz" > /dev/null 2>&1; then
    log_info "✅ Health check passed!"
else
    log_warn "Health check via HTTP failed, trying HTTPS..."
    if curl -f -s "https://$REMOTE_HOST/healthz" > /dev/null 2>&1; then
        log_info "✅ Health check passed (HTTPS)!"
    else
        log_warn "Could not verify health check - please check manually"
    fi
fi

# Cleanup
rm -rf "$DEPLOY_DIR"
rm -f /tmp/rightline-mvp.tar.gz

log_info "🎉 Deployment complete!"
log_info "📊 View logs: ssh $REMOTE_USER@$REMOTE_HOST 'docker-compose -f $REMOTE_DIR/docker-compose.mvp.yml logs -f'"
log_info "🌐 Access at: https://$REMOTE_HOST"

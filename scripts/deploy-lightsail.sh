#!/bin/bash
# Deploy RightLine MVP to AWS Lightsail
# Usage: ./scripts/deploy-lightsail.sh [instance-name] [region]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTANCE_NAME="${1:-rightline-mvp}"
REGION="${2:-af-south-1}"
ENV_FILE="${3:-.env.production}"
REMOTE_USER="ubuntu"
REMOTE_DIR="/opt/rightline"

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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check prerequisites
command -v aws >/dev/null 2>&1 || log_error "AWS CLI not installed. Run: brew install awscli"
command -v docker >/dev/null 2>&1 || log_error "Docker not installed"

# Validate environment file
if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
fi

log_info "🚀 Starting deployment to AWS Lightsail instance: $INSTANCE_NAME"

# Step 1: Get instance information
log_step "Getting instance information..."
INSTANCE_INFO=$(aws lightsail get-instance \
    --instance-name $INSTANCE_NAME \
    --region $REGION 2>/dev/null) || log_error "Instance $INSTANCE_NAME not found in region $REGION"

# Get instance IP
INSTANCE_IP=$(aws lightsail get-static-ip \
    --static-ip-name rightline-ip \
    --region $REGION \
    --query 'staticIp.ipAddress' \
    --output text 2>/dev/null) || {
    log_warn "No static IP found, using instance public IP"
    INSTANCE_IP=$(echo "$INSTANCE_INFO" | jq -r '.instance.publicIpAddress')
}

log_info "Instance IP: $INSTANCE_IP"

# Step 2: Check instance is ready
log_step "Checking instance readiness..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -i ~/.ssh/rightline-key.pem \
        $REMOTE_USER@$INSTANCE_IP "test -f /opt/rightline/.ready" 2>/dev/null; then
        log_info "Instance is ready!"
        break
    fi
    echo -n "."
    sleep 10
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_warn "Instance may not be fully configured. Proceeding anyway..."
fi

# Step 3: Build Docker image
log_step "Building Docker image..."
docker build -t rightline/api:mvp -f services/api/Dockerfile . || log_error "Docker build failed"

# Step 4: Save and compress Docker image
log_step "Saving Docker image..."
docker save rightline/api:mvp | gzip > /tmp/rightline-mvp.tar.gz

# Step 5: Create deployment package
log_step "Creating deployment package..."
DEPLOY_DIR=$(mktemp -d)
cp docker-compose.mvp.yml "$DEPLOY_DIR/"
cp -r nginx "$DEPLOY_DIR/" 2>/dev/null || mkdir -p "$DEPLOY_DIR/nginx"
cp "$ENV_FILE" "$DEPLOY_DIR/.env"
cp -r scripts "$DEPLOY_DIR/"

# Step 6: Upload to Lightsail instance
log_step "Uploading to Lightsail instance..."
scp -i ~/.ssh/rightline-key.pem -o StrictHostKeyChecking=no -r \
    /tmp/rightline-mvp.tar.gz \
    "$DEPLOY_DIR"/* \
    $REMOTE_USER@$INSTANCE_IP:$REMOTE_DIR/ || log_error "Upload failed"

# Step 7: Deploy on instance
log_step "Deploying application..."
ssh -i ~/.ssh/rightline-key.pem -o StrictHostKeyChecking=no \
    $REMOTE_USER@$INSTANCE_IP << 'ENDSSH' || log_error "Deployment failed"
set -euo pipefail

cd /opt/rightline

echo "📥 Loading Docker image..."
sudo docker load < rightline-mvp.tar.gz

echo "🔄 Stopping existing services..."
sudo docker-compose -f docker-compose.mvp.yml down --timeout 30 || true

echo "🚀 Starting new services..."
sudo docker-compose -f docker-compose.mvp.yml up -d

echo "⏳ Waiting for services to be healthy..."
for i in {1..30}; do
    if sudo docker-compose -f docker-compose.mvp.yml exec -T api curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "✅ API is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Show service status
sudo docker-compose -f docker-compose.mvp.yml ps

# Cleanup old images
sudo docker image prune -f

echo "✅ Deployment successful!"
ENDSSH

# Step 8: Create or update CloudWatch alarms
log_step "Setting up CloudWatch monitoring..."
aws cloudwatch put-metric-alarm \
    --alarm-name "${INSTANCE_NAME}-cpu-high" \
    --alarm-description "Alarm when CPU exceeds 80%" \
    --metric-name CPUUtilization \
    --namespace AWS/Lightsail \
    --statistic Average \
    --period 300 \
    --threshold 80 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=InstanceName,Value=$INSTANCE_NAME \
    --evaluation-periods 2 \
    --region $REGION || log_warn "Could not create CPU alarm"

# Step 9: Verify deployment
log_step "Verifying deployment..."
sleep 5

# Check health endpoint
if curl -f -s "http://$INSTANCE_IP/healthz" > /dev/null 2>&1; then
    log_info "✅ Health check passed!"
else
    log_warn "Health check failed - please verify manually"
fi

# Step 10: Create snapshot for backup
log_step "Creating instance snapshot..."
SNAPSHOT_NAME="${INSTANCE_NAME}-$(date +%Y%m%d-%H%M%S)"
aws lightsail create-instance-snapshot \
    --instance-name $INSTANCE_NAME \
    --instance-snapshot-name $SNAPSHOT_NAME \
    --region $REGION || log_warn "Could not create snapshot"

# Cleanup
rm -rf "$DEPLOY_DIR"
rm -f /tmp/rightline-mvp.tar.gz

# Output summary
echo ""
echo "========================================="
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "========================================="
echo ""
echo "Instance: $INSTANCE_NAME"
echo "Region: $REGION"
echo "IP Address: $INSTANCE_IP"
echo ""
echo "Access your application:"
echo "  Web UI: http://$INSTANCE_IP"
echo "  API Docs: http://$INSTANCE_IP/docs"
echo "  Health: http://$INSTANCE_IP/healthz"
echo ""
echo "Next steps:"
echo "1. Configure domain: Point your domain to $INSTANCE_IP"
echo "2. Setup SSL: ssh ubuntu@$INSTANCE_IP 'sudo certbot --nginx -d your-domain.com'"
echo "3. Monitor: Check CloudWatch dashboard in AWS Console"
echo "4. Logs: ssh ubuntu@$INSTANCE_IP 'sudo docker-compose -f /opt/rightline/docker-compose.mvp.yml logs -f'"
echo ""
echo "Lightsail Console: https://lightsail.aws.amazon.com/ls/webapp/home/instances"

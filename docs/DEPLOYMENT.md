# RightLine MVP Deployment Guide (Lightweight Edition)

> **📦 Minimal deployment for MVP**: Single VM, Docker Compose with FastAPI API and Postgres. Aligns with MVP_ARCHITECTURE.md. Total setup: ~10 minutes. Extend to V2 for production features.

## 🎯 Deployment Philosophy
- **Ultra-Low Budget**: $5/month VPS.
- **Minimal**: API + DB only; no extras until needed.
- **Secure Basics**: HTTPS via VPS, API key auth.
- **Fast**: <2s responses; local models.

## 📊 Platform: Basic VPS (e.g., Hetzner/Contabo)
- **Why**: Cheaper than Lightsail for MVP ($3-5/month, 1vCPU/2GB/20GB).
- **Alternative**: Lightsail if AWS preferred.

## 🚀 Quick Start
### Prerequisites
- VPS with Ubuntu 22.04 (2GB RAM minimum)
- SSH access as root or sudo user
- Domain name (optional for MVP)

### Step 1: Server Setup (3 minutes)
```bash
# SSH into your VPS
ssh root@your-vps-ip

# Run the setup script
wget https://raw.githubusercontent.com/yourusername/right-line/main/scripts/setup-vps.sh
bash setup-vps.sh

# Or manually:
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git ufw
sudo systemctl enable docker && sudo systemctl start docker
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw --force enable
```

### Step 2: Clone and Configure (2 minutes)
```bash
# Clone the repository
cd /opt
git clone https://github.com/yourusername/right-line.git rightline
cd rightline

# Create production environment file
cat > .env.production << 'EOF'
# Security
RIGHTLINE_SECRET_KEY=$(openssl rand -hex 32)

# Database
RIGHTLINE_DATABASE_URL=postgresql://rightline:rightline@postgres:5432/rightline

# App
RIGHTLINE_APP_ENV=production
RIGHTLINE_LOG_LEVEL=INFO

# LLM (local)
RIGHTLINE_LLM_MODEL_PATH=/models/tinyllama-1.1b-chat.Q4_K_M.gguf
RIGHTLINE_LLM_MAX_TOKENS=120
EOF

chmod 600 .env.production
```

### Step 3: Download LLM Model (1 minute)
```bash
mkdir -p models
# Example: TinyLlama 1.1B Chat Q4_K_M (adjust URL to a valid GGUF source)
curl -L -o models/tinyllama-1.1b-chat.Q4_K_M.gguf "https://your-model-hosting/tinyllama-1.1b-chat.Q4_K_M.gguf"
```

### Step 4: Deploy Application (2 minutes)
```bash
# Compose mounts ./models to /models in the container
# (already set in docker-compose.mvp.yml instructions)
docker-compose -f docker-compose.mvp.yml build
docker-compose -f docker-compose.mvp.yml up -d
```

### Step 5: Verify LLM Generation (1 minute)
```bash
curl -X POST http://localhost/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is notice period for termination?"}'
# Expect: EXACT 3 lines, ≤100 chars each, with citations appended
```

### Step 4: Verify Deployment (1 minute)
```bash
# Check services are running
docker ps

# Test the API
curl http://localhost/healthz

# Test a query
curl -X POST http://localhost/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text": "What is minimum wage?"}'

# Check logs if issues
docker logs rightline-api
```

### Step 5: Add HTTPS (Optional but Recommended)
```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx nginx

# Configure nginx as reverse proxy
sudo cat > /etc/nginx/sites-available/rightline << 'EOF'
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/rightline /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## 🔄 Backup Strategy
```bash
# Create backup script
cat > /opt/rightline/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/rightline/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker exec rightline-postgres pg_dump -U rightline rightline | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/rightline/scripts/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/rightline/scripts/backup.sh") | crontab -
```

## 📈 Monitoring
```bash
# Simple health check script
cat > /opt/rightline/scripts/health.sh << 'EOF'
#!/bin/bash
if curl -f http://localhost/healthz > /dev/null 2>&1; then
    echo "RightLine is healthy"
else
    echo "RightLine is down!"
    # Send alert (email, SMS, etc.)
fi
EOF

chmod +x /opt/rightline/scripts/health.sh

# Add to crontab (every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/rightline/scripts/health.sh") | crontab -
```

## 🚨 Troubleshooting

### Service won't start
```bash
# Check logs
docker logs rightline-api
docker logs rightline-postgres

# Check disk space
df -h

# Check memory
free -h
```

### Database connection errors
```bash
# Test postgres connection
docker exec -it rightline-postgres psql -U rightline -d rightline

# Reset database
docker-compose -f docker-compose.mvp.yml down -v
docker-compose -f docker-compose.mvp.yml up -d
```

### High memory usage
```bash
# Add swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 📊 Scaling Path
- **Current MVP**: Handles ~100 concurrent users on $5 VPS
- **Next Step**: Add Redis for caching when >100 users
- **Future (V2)**: See `docs/project/V2_ARCHITECTURE.md` for full production setup

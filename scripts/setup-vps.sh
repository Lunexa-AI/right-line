#!/bin/bash
# Initial VPS setup script for RightLine MVP
# Run as root on fresh Ubuntu 22.04 server

set -euo pipefail

# Configuration
APP_USER="rightline"
APP_DIR="/opt/rightline"
SWAP_SIZE="2G"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
fi

log_info "🚀 Starting VPS setup for RightLine MVP..."

# Step 1: Update system
log_info "📦 Updating system packages..."
apt-get update
apt-get upgrade -y
apt-get autoremove -y

# Step 2: Install essential packages
log_info "🔧 Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    unattended-upgrades \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    net-tools \
    jq

# Step 3: Setup firewall
log_info "🔥 Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

# Step 4: Configure fail2ban
log_info "🛡️ Setting up fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF
systemctl restart fail2ban

# Step 5: Install Docker
log_info "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
else
    log_warn "Docker already installed, skipping..."
fi

systemctl enable docker
systemctl start docker

# Step 6: Install Docker Compose
log_info "🐳 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | jq -r .tag_name)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    log_warn "Docker Compose already installed, skipping..."
fi

# Step 7: Create application user
log_info "👤 Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    usermod -aG docker "$APP_USER"
else
    log_warn "User $APP_USER already exists, skipping..."
fi

# Step 8: Setup application directories
log_info "📁 Creating application directories..."
mkdir -p "$APP_DIR"/{data,logs,backups,configs,nginx,ssl}
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 755 "$APP_DIR"

# Step 9: Setup swap (for low memory VPS)
log_info "💾 Setting up swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l "$SWAP_SIZE" /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
    log_warn "Swap file already exists, skipping..."
fi

# Step 10: Optimize system settings
log_info "⚡ Optimizing system settings..."
cat > /etc/sysctl.d/99-rightline.conf << EOF
# Network optimizations for RightLine
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10000 65000
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# File system optimizations
fs.file-max = 2097152
fs.nr_open = 1048576
EOF
sysctl -p /etc/sysctl.d/99-rightline.conf

# Step 11: Setup log rotation
log_info "📝 Configuring log rotation..."
cat > /etc/logrotate.d/rightline << EOF
$APP_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $APP_USER $APP_USER
    sharedscripts
    postrotate
        docker-compose -f $APP_DIR/docker-compose.mvp.yml restart nginx 2>/dev/null || true
    endscript
}
EOF

# Step 12: Setup automatic security updates
log_info "🔒 Enabling automatic security updates..."
cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Step 13: Install Nginx (optional, for SSL termination)
log_info "🌐 Installing Nginx..."
apt-get install -y nginx certbot python3-certbot-nginx

# Step 14: Create basic nginx config
cat > /etc/nginx/sites-available/rightline << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /healthz {
        proxy_pass http://localhost:8000/healthz;
        access_log off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/rightline /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Step 15: Create deployment helper script
log_info "📜 Creating deployment helper..."
cat > "$APP_DIR/deploy.sh" << 'EOF'
#!/bin/bash
# Quick deployment helper
cd /opt/rightline
docker-compose -f docker-compose.mvp.yml pull
docker-compose -f docker-compose.mvp.yml down
docker-compose -f docker-compose.mvp.yml up -d
docker-compose -f docker-compose.mvp.yml ps
EOF
chmod +x "$APP_DIR/deploy.sh"
chown "$APP_USER:$APP_USER" "$APP_DIR/deploy.sh"

# Step 16: Create backup script
log_info "💾 Creating backup script..."
cat > "$APP_DIR/backup.sh" << 'EOF'
#!/bin/bash
# Daily backup script
BACKUP_DIR="/opt/rightline/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="rightline_backup_${TIMESTAMP}.tar.gz"

cd /opt/rightline
tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" data/ logs/ docker-compose.mvp.yml .env 2>/dev/null || true

# Keep only last 7 days
find ${BACKUP_DIR} -name "rightline_backup_*.tar.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}"
EOF
chmod +x "$APP_DIR/backup.sh"
chown "$APP_USER:$APP_USER" "$APP_DIR/backup.sh"

# Add to crontab
(crontab -u "$APP_USER" -l 2>/dev/null; echo "0 2 * * * $APP_DIR/backup.sh >> $APP_DIR/logs/backup.log 2>&1") | crontab -u "$APP_USER" -

# Step 17: System info
log_info "📊 System Information:"
echo "------------------------"
echo "CPU: $(nproc) cores"
echo "RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $2}')"
echo "Swap: $(free -h | awk '/^Swap:/ {print $2}')"
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker-compose --version)"
echo "------------------------"

log_info "✅ VPS setup complete!"
log_info ""
log_info "Next steps:"
log_info "1. Copy your .env.production file to $APP_DIR/.env"
log_info "2. Run deployment: ./scripts/deploy-mvp.sh $(hostname -I | awk '{print $1}')"
log_info "3. Setup SSL: certbot --nginx -d your-domain.com"
log_info "4. Configure DNS to point to: $(curl -s ifconfig.me)"
log_info ""
log_info "Security notes:"
log_info "- Change SSH port in /etc/ssh/sshd_config"
log_info "- Setup SSH keys and disable password auth"
log_info "- Review firewall rules: ufw status"
log_info "- Check fail2ban status: fail2ban-client status"

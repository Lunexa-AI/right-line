#!/bin/bash
# AWS Lightsail User Data Script for RightLine MVP
# This script runs automatically when the instance is created

set -euo pipefail

# Log all output
exec > >(tee -a /var/log/user-data.log)
exec 2>&1

echo "Starting RightLine MVP setup at $(date)"

# Update system
apt-get update
apt-get upgrade -y

# Install essential packages
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
    lsb-release

# Setup firewall (basic rules, will be configured properly later)
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install Docker Compose
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -Po '"tag_name": "\K.*?(?=")')
curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create application user
useradd -m -s /bin/bash rightline
usermod -aG docker rightline

# Setup application directories
mkdir -p /opt/rightline/{data,logs,backups,configs,nginx,ssl}
chown -R rightline:rightline /opt/rightline

# Setup swap (important for small instances)
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Optimize system settings for production
cat > /etc/sysctl.d/99-rightline.conf << EOF
# Network optimizations
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10000 65000

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF
sysctl -p /etc/sysctl.d/99-rightline.conf

# Install CloudWatch agent for monitoring (optional but recommended)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i -E ./amazon-cloudwatch-agent.deb || true
rm amazon-cloudwatch-agent.deb

# Install AWS CLI
apt-get install -y awscli

# Install Nginx for reverse proxy
apt-get install -y nginx certbot python3-certbot-nginx

# Create basic nginx config
cat > /etc/nginx/sites-available/rightline << 'NGINX_CONFIG'
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
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINX_CONFIG

ln -sf /etc/nginx/sites-available/rightline /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Setup automatic security updates
cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Create deployment ready flag
touch /opt/rightline/.ready

echo "RightLine MVP setup completed at $(date)"
echo "Next steps:"
echo "1. SSH into the instance: ssh -i ~/.ssh/rightline-key.pem ubuntu@<INSTANCE_IP>"
echo "2. Deploy the application using: ./scripts/deploy-mvp.sh <INSTANCE_IP>"

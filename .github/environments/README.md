# GitHub Environments Configuration

## Overview

This directory contains documentation for configuring GitHub Environments for the deployment pipeline.

## Required Environments

### 1. **staging**
- **URL**: `https://staging.rightline.zw`
- **Auto-deploy**: Yes (from `develop` branch)
- **Required Reviewers**: None
- **Protection Rules**: None

### 2. **production-approval**
- **URL**: None
- **Auto-deploy**: No
- **Required Reviewers**: 1-2 maintainers
- **Protection Rules**: 
  - Required reviewers
  - Dismiss stale reviews
  - Include administrators

### 3. **production**
- **URL**: `https://rightline.zw`
- **Auto-deploy**: No
- **Required Reviewers**: 2+ maintainers
- **Protection Rules**:
  - Required reviewers
  - Dismiss stale reviews
  - Include administrators
  - Restrict who can deploy (maintainers only)

## Required Secrets

### Global Secrets
```bash
# Container Registry
GITHUB_TOKEN                # Auto-provided by GitHub
GHCR_TOKEN                  # GitHub Container Registry token

# Code Quality
CODECOV_TOKEN              # Codecov.io token
SENTRY_AUTH_TOKEN          # Sentry release tracking

# Security
SAFETY_API_KEY             # Safety vulnerability scanning

# Notifications
SLACK_WEBHOOK_URL          # Slack notifications
```

### Staging Environment Secrets
```bash
# Infrastructure
STAGING_SSH_HOST           # VPS hostname/IP
STAGING_SSH_USER           # SSH username
STAGING_SSH_KEY            # SSH private key
STAGING_KUBECONFIG         # Kubernetes config (if using k8s)

# Database
STAGING_DATABASE_URL       # PostgreSQL connection string

# API Keys
STAGING_API_KEY           # API authentication key
STAGING_HEALTH_TOKEN      # Health check authentication

# Services
STAGING_URL               # https://staging.rightline.zw
SENTRY_DSN_STAGING        # Sentry error tracking
MEILISEARCH_KEY_STAGING   # Meilisearch API key

# Secrets
SECRET_KEY_STAGING        # Django/FastAPI secret key
DB_PASSWORD               # Database password
DB_REPLICATION_PASSWORD   # Database replication password
MINIO_ACCESS_KEY          # MinIO access key
MINIO_SECRET_KEY          # MinIO secret key

# Channels
WHATSAPP_TOKEN_STAGING    # WhatsApp Business API token
TELEGRAM_TOKEN_STAGING    # Telegram Bot token

# Monitoring
GRAFANA_PASSWORD_STAGING  # Grafana admin password
```

### Production Environment Secrets
```bash
# Infrastructure
PRODUCTION_SSH_HOST        # Production server hostname/IP
PRODUCTION_SSH_USER        # SSH username
PRODUCTION_SSH_KEY         # SSH private key
PRODUCTION_KUBECONFIG      # Kubernetes config (if using k8s)

# Database
PRODUCTION_DATABASE_URL    # PostgreSQL connection string

# API Keys
PRODUCTION_API_KEY        # API authentication key
PRODUCTION_HEALTH_TOKEN   # Health check authentication

# Services
PRODUCTION_URL            # https://rightline.zw
SENTRY_DSN_PRODUCTION     # Sentry error tracking
MEILISEARCH_KEY_PRODUCTION # Meilisearch API key

# Secrets
SECRET_KEY_PRODUCTION     # Django/FastAPI secret key
DB_PASSWORD               # Database password
DB_REPLICATION_PASSWORD   # Database replication password
MINIO_ACCESS_KEY          # MinIO access key
MINIO_SECRET_KEY          # MinIO secret key

# Channels
WHATSAPP_TOKEN_PRODUCTION # WhatsApp Business API token
TELEGRAM_TOKEN_PRODUCTION # Telegram Bot token

# Monitoring
GRAFANA_PASSWORD_PRODUCTION # Grafana admin password

# AWS (if using)
AWS_ACCESS_KEY_ID         # AWS access key
AWS_SECRET_ACCESS_KEY     # AWS secret key
AWS_REGION                # AWS region
```

## Variables (Non-Secret Configuration)

### Repository Variables
```bash
DEPLOY_TARGET             # "vps" or "k8s"
PYTHON_VERSION            # "3.11"
POETRY_VERSION            # "1.7.1"
DEFAULT_BRANCH            # "main"
```

## Setting Up Environments

### Via GitHub UI

1. Go to **Settings** → **Environments**
2. Click **New environment**
3. Create each environment with the configurations above
4. Add secrets via **Environment secrets**
5. Configure protection rules

### Via GitHub CLI

```bash
# Install GitHub CLI
brew install gh

# Authenticate
gh auth login

# Create environments
gh api repos/:owner/:repo/environments/staging -X PUT
gh api repos/:owner/:repo/environments/production-approval -X PUT
gh api repos/:owner/:repo/environments/production -X PUT

# Add secrets (example)
gh secret set STAGING_DATABASE_URL --env staging
gh secret set PRODUCTION_DATABASE_URL --env production

# Add protection rules (example)
gh api repos/:owner/:repo/environments/production/deployment-branch-policies \
  -X POST \
  -f name="main"
```

## Deployment Flow

```mermaid
graph LR
    A[Push to develop] --> B[CI Tests]
    B --> C[Deploy to Staging]
    C --> D[Smoke Tests]
    D --> E[Manual Approval]
    E --> F[Deploy to Production]
    F --> G[Health Checks]
    G --> H{Success?}
    H -->|Yes| I[Complete]
    H -->|No| J[Rollback]
```

## Troubleshooting

### Common Issues

1. **Deployment fails with "secret not found"**
   - Ensure all required secrets are set in the environment
   - Check secret names match exactly (case-sensitive)

2. **SSH connection fails**
   - Verify SSH key format (use `-----BEGIN RSA PRIVATE KEY-----`)
   - Check SSH host and user are correct
   - Ensure server allows key-based authentication

3. **Kubernetes deployment fails**
   - Verify kubeconfig is base64 encoded
   - Check namespace exists
   - Ensure service account has proper permissions

4. **Health checks timeout**
   - Increase `HEALTH_CHECK_RETRIES` in workflow
   - Check service logs for startup issues
   - Verify network connectivity

## Security Best Practices

1. **Rotate secrets regularly** (every 90 days)
2. **Use different secrets** for each environment
3. **Limit secret access** to required workflows only
4. **Audit secret usage** via GitHub audit log
5. **Never commit secrets** to repository
6. **Use secret scanning** to detect leaks

## Monitoring Deployments

- **GitHub Actions**: View deployment status in Actions tab
- **Deployment History**: Check Environments tab for history
- **Slack Notifications**: Configure webhook for real-time updates
- **Grafana Dashboards**: Monitor post-deployment metrics

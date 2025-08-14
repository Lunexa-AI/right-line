# AWS Lightsail Terraform Configuration

This directory contains Terraform configuration for deploying RightLine MVP to AWS Lightsail.

## Prerequisites

1. **Install Terraform**:
   ```bash
   brew install terraform
   ```

2. **Configure AWS CLI**:
   ```bash
   aws configure
   # Enter your AWS credentials and preferred region
   ```

3. **Install required tools**:
   ```bash
   brew install jq
   ```

## Quick Start

### 1. Initialize Terraform

```bash
cd infra/terraform/lightsail
terraform init
```

### 2. Configure Variables

```bash
# Copy example variables file
cp terraform.tfvars.example terraform.tfvars

# Edit with your preferences
vim terraform.tfvars
```

### 3. Plan Deployment

```bash
# Review what will be created
terraform plan
```

### 4. Deploy Infrastructure

```bash
# Create the infrastructure
terraform apply

# Type 'yes' when prompted
```

### 5. Get Outputs

```bash
# Get instance IP
terraform output instance_public_ip

# Get SSH command
terraform output ssh_command

# Get application URL
terraform output application_url
```

## Managing Infrastructure

### View Current State

```bash
terraform show
```

### Update Infrastructure

```bash
# Make changes to main.tf or variables
terraform plan
terraform apply
```

### Destroy Infrastructure

```bash
# WARNING: This will delete everything!
terraform destroy
```

## Cost Breakdown

| Resource | Monthly Cost |
|----------|-------------|
| Lightsail Instance (2GB) | $10 |
| Static IP | Free (when attached) |
| Data Transfer (3TB) | Included |
| Snapshots (7 daily) | ~$1 |
| **Total** | **~$11/month** |

## Scaling Options

### Enable Database

Uncomment the database resource in `main.tf`:

```hcl
resource "aws_lightsail_database" "rightline" {
  # ... configuration
}
```

Cost: Additional $15/month for managed PostgreSQL

### Enable Load Balancer

Uncomment the load balancer resources in `main.tf`:

```hcl
resource "aws_lightsail_lb" "rightline" {
  # ... configuration
}
```

Cost: Additional $18/month

### Enable CDN

Add CloudFront distribution for global content delivery:

```bash
aws lightsail create-distribution \
  --origin rightline-mvp \
  --default-cache-behavior "targetOriginId=rightline-mvp,viewerProtocolPolicy=redirect-to-https"
```

Cost: Pay-per-use (~$5-20/month depending on traffic)

## Backup Strategy

### Automatic Snapshots

Enabled by default. Snapshots are taken daily and retained for 7 days.

### Manual Backup

```bash
# Create manual snapshot
aws lightsail create-instance-snapshot \
  --instance-name rightline-mvp \
  --instance-snapshot-name "manual-backup-$(date +%Y%m%d)"
```

### Restore from Snapshot

```bash
# List snapshots
aws lightsail get-instance-snapshots

# Create new instance from snapshot
aws lightsail create-instances-from-snapshot \
  --instance-names rightline-restored \
  --instance-snapshot-name <snapshot-name>
```

## Monitoring

### CloudWatch Metrics

Automatically configured alarms:
- CPU > 80% for 10 minutes
- Instance status check failed

### View Metrics

```bash
# Get CPU metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lightsail \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceName,Value=rightline-mvp \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

## Troubleshooting

### SSH Connection Issues

```bash
# Check instance status
aws lightsail get-instance --instance-name rightline-mvp

# Check SSH key permissions
chmod 600 ~/.ssh/rightline-key.pem

# Try verbose SSH
ssh -vvv -i ~/.ssh/rightline-key.pem ubuntu@<IP>
```

### Instance Not Starting

```bash
# Check instance state
aws lightsail get-instance-state --instance-name rightline-mvp

# Check system log
aws lightsail get-instance-log-events --instance-name rightline-mvp
```

### Terraform State Issues

```bash
# Refresh state
terraform refresh

# Force unlock (if locked)
terraform force-unlock <lock-id>

# Reimport resources
terraform import aws_lightsail_instance.rightline_mvp rightline-mvp
```

## Security Best Practices

1. **Restrict SSH access**: Edit the firewall rules to allow only your IP
2. **Enable automatic updates**: Already configured in user data script
3. **Use secrets manager**: Store sensitive data in AWS Secrets Manager
4. **Enable MFA**: Use MFA for AWS account access
5. **Regular snapshots**: Automated daily snapshots are configured

## Migration to Production

When ready to scale beyond Lightsail:

1. **Export to EC2**:
   ```bash
   aws lightsail export-snapshot --instance-snapshot-name <snapshot>
   ```

2. **Move to ECS/Fargate**: Use the same Docker images

3. **Migrate to RDS**: Export data and import to RDS PostgreSQL

## Support

- [AWS Lightsail Documentation](https://docs.aws.amazon.com/lightsail/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [RightLine Architecture](../../../docs/project/ARCHITECTURE.md)

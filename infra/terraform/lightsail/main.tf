# Terraform configuration for AWS Lightsail deployment
# RightLine MVP Infrastructure

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Optional: Configure backend for state storage
  # backend "s3" {
  #   bucket = "rightline-terraform-state"
  #   key    = "lightsail/terraform.tfstate"
  #   region = "af-south-1"
  # }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "RightLine"
      Environment = var.environment
      ManagedBy   = "Terraform"
      CostCenter  = "MVP"
    }
  }
}

# Variables
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "af-south-1" # Cape Town
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "instance_name" {
  description = "Name of the Lightsail instance"
  type        = string
  default     = "rightline-mvp"
}

variable "bundle_id" {
  description = "Lightsail bundle ID (instance size)"
  type        = string
  default     = "small_2_0" # 2GB RAM, 1 vCPU, $10/month
}

variable "availability_zone" {
  description = "Availability zone"
  type        = string
  default     = "af-south-1a"
}

variable "enable_snapshots" {
  description = "Enable automatic snapshots"
  type        = bool
  default     = true
}

variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

# SSH Key Pair
resource "aws_lightsail_key_pair" "rightline" {
  name = "rightline-key"
  
  # Use existing public key or generate new one
  # public_key = file("~/.ssh/rightline-key.pub")
}

# Lightsail Instance
resource "aws_lightsail_instance" "rightline_mvp" {
  name              = var.instance_name
  availability_zone = var.availability_zone
  blueprint_id      = "ubuntu_22_04"
  bundle_id         = var.bundle_id
  key_pair_name     = aws_lightsail_key_pair.rightline.name
  
  # User data script for initial setup
  user_data = file("${path.module}/../../../scripts/lightsail-userdata.sh")
  
  tags = {
    Name        = var.instance_name
    Environment = var.environment
  }
}

# Static IP
resource "aws_lightsail_static_ip" "rightline" {
  name = "rightline-ip"
}

# Attach Static IP to Instance
resource "aws_lightsail_static_ip_attachment" "rightline" {
  static_ip_name = aws_lightsail_static_ip.rightline.name
  instance_name  = aws_lightsail_instance.rightline_mvp.name
}

# Firewall Rules
resource "aws_lightsail_instance_public_ports" "rightline" {
  instance_name = aws_lightsail_instance.rightline_mvp.name
  
  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
    cidrs     = ["0.0.0.0/0"] # Restrict to your IP in production
  }
  
  port_info {
    protocol  = "tcp"
    from_port = 80
    to_port   = 80
    cidrs     = ["0.0.0.0/0"]
  }
  
  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
    cidrs     = ["0.0.0.0/0"]
  }
}

# Optional: Lightsail Database (for future scaling)
# resource "aws_lightsail_database" "rightline" {
#   relational_database_name = "rightline-db"
#   availability_zone        = var.availability_zone
#   master_database_name     = "rightline"
#   master_password          = random_password.db_password.result
#   master_username          = "rightline_admin"
#   blueprint_id             = "postgres_15"
#   bundle_id                = "micro_2_0"
#   
#   preferred_backup_window      = "02:00-03:00"
#   preferred_maintenance_window = "sun:03:00-sun:04:00"
#   backup_retention_enabled     = true
#   
#   tags = {
#     Name        = "rightline-db"
#     Environment = var.environment
#   }
# }

# Random password for database (if enabled)
# resource "random_password" "db_password" {
#   length  = 32
#   special = true
# }

# Optional: Load Balancer (for high availability)
# resource "aws_lightsail_lb" "rightline" {
#   name              = "rightline-lb"
#   health_check_path = "/healthz"
#   instance_port     = 80
#   
#   tags = {
#     Name        = "rightline-lb"
#     Environment = var.environment
#   }
# }

# Optional: Attach instance to load balancer
# resource "aws_lightsail_lb_attachment" "rightline" {
#   load_balancer_name = aws_lightsail_lb.rightline.name
#   instance_name      = aws_lightsail_instance.rightline_mvp.name
# }

# Optional: SSL Certificate (if using load balancer)
# resource "aws_lightsail_lb_certificate" "rightline" {
#   name              = "rightline-cert"
#   load_balancer_name = aws_lightsail_lb.rightline.name
#   domain_name       = var.domain_name
#   
#   subject_alternative_names = [
#     "www.${var.domain_name}"
#   ]
# }

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.instance_name}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/Lightsail"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors CPU utilization"
  
  dimensions = {
    InstanceName = aws_lightsail_instance.rightline_mvp.name
  }
}

resource "aws_cloudwatch_metric_alarm" "status_check_failed" {
  alarm_name          = "${var.instance_name}-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/Lightsail"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "0"
  alarm_description   = "This metric monitors instance status check"
  
  dimensions = {
    InstanceName = aws_lightsail_instance.rightline_mvp.name
  }
}

# Outputs
output "instance_public_ip" {
  description = "Public IP address of the instance"
  value       = aws_lightsail_static_ip.rightline.ip_address
}

output "instance_name" {
  description = "Name of the Lightsail instance"
  value       = aws_lightsail_instance.rightline_mvp.name
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/rightline-key.pem ubuntu@${aws_lightsail_static_ip.rightline.ip_address}"
}

output "application_url" {
  description = "URL to access the application"
  value       = "http://${aws_lightsail_static_ip.rightline.ip_address}"
}

# output "database_endpoint" {
#   description = "Database endpoint (if enabled)"
#   value       = try(aws_lightsail_database.rightline[0].master_endpoint_address, "N/A")
#   sensitive   = true
# }

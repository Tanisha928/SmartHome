terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "smarthome"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name       = "smarthome-${var.env}"
  account_id = data.aws_caller_identity.current.account_id
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)

  # Data-tier names (resources owned in rds.tf/s3.tf/sqs.tf). Referenced by name so compute
  # can be planned before the data tier is applied.
  clips_bucket    = "smarthome-clips-${var.env}"
  queue_name      = "inference-events"
  dlq_name        = "inference-events-dlq"
  queue_arn       = "arn:aws:sqs:${var.aws_region}:${local.account_id}:${local.queue_name}"
  dlq_arn         = "arn:aws:sqs:${var.aws_region}:${local.account_id}:${local.dlq_name}"
  queue_url       = "https://sqs.${var.aws_region}.amazonaws.com/${local.account_id}/${local.queue_name}"
  dlq_url         = "https://sqs.${var.aws_region}.amazonaws.com/${local.account_id}/${local.dlq_name}"
  ssm_prefix      = "/smarthome/${var.env}"
  metric_ns       = "SmartHome"
}

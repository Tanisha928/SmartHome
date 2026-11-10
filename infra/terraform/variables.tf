variable "env" {
  type    = string
  default = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "db_username" {
  type    = string
  default = "smart"
}

variable "db_password" {
  type      = string
  sensitive = true
  default   = "change-me"
}

# --- Compute / network (Sakshat, S18–S19) --------------------------------------------------

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "nat_per_az" {
  description = "One NAT gateway per AZ (HA) instead of a single shared one (cheaper)."
  type        = bool
  default     = false
}

variable "acm_certificate_arn" {
  description = "ACM certificate for the ALB HTTPS listener."
  type        = string
}

variable "api_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "worker_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "sweeper_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "api_min" {
  type    = number
  default = 2
}

variable "api_max" {
  type    = number
  default = 6
}

variable "worker_min" {
  type    = number
  default = 1
}

variable "worker_max" {
  type    = number
  default = 8
}

variable "artifact_bucket" {
  description = "S3 bucket holding release tarballs uploaded by scripts/deploy.sh."
  type        = string
}

variable "release" {
  description = "Release id (tarball name without .tar.gz) instances install at boot."
  type        = string
  default     = "current"
}

variable "alarm_email" {
  description = "Email subscribed to CloudWatch alarm notifications."
  type        = string
}

variable "monthly_budget_usd" {
  type    = number
  default = 100
}

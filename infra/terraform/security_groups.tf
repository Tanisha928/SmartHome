# Security groups (SDD 3.1.1). Least privilege: each tier only accepts its upstream tier.
#
#   alb      ← 0.0.0.0/0 :80,:443
#   api      ← alb :80 (nginx)
#   worker   ← (none)
#   sweeper  ← (none)
#   postgres ← api, worker, sweeper :5432
#   mongo    ← api, worker, sweeper :27017
# No SSH anywhere: operators use SSM Session Manager.

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Public ALB"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "Redirected to HTTPS"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.api.id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "api" {
  name        = "${local.name}-api"
  description = "API instances (nginx + uvicorn)"
  vpc_id      = aws_vpc.main.id
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 80
  to_port                      = 80
  ip_protocol                  = "tcp"
}

resource "aws_security_group" "worker" {
  name        = "${local.name}-worker"
  description = "Model workers (SQS consumers)"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "sweeper" {
  name        = "${local.name}-sweeper"
  description = "Singleton sweeper loops"
  vpc_id      = aws_vpc.main.id
}

# App tiers need outbound HTTPS (AWS APIs via NAT / S3 endpoint) and the data ports.
resource "aws_vpc_security_group_egress_rule" "app_https" {
  for_each = {
    api     = aws_security_group.api.id
    worker  = aws_security_group.worker.id
    sweeper = aws_security_group.sweeper.id
  }
  security_group_id = each.value
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_http_packages" {
  for_each = {
    api     = aws_security_group.api.id
    worker  = aws_security_group.worker.id
    sweeper = aws_security_group.sweeper.id
  }
  security_group_id = each.value
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "OS package mirrors at boot"
}

resource "aws_security_group" "postgres" {
  name        = "${local.name}-postgres"
  description = "RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id
}

resource "aws_security_group" "mongo" {
  name        = "${local.name}-mongo"
  description = "MongoDB on EC2"
  vpc_id      = aws_vpc.main.id
}

locals {
  app_sgs = {
    api     = aws_security_group.api.id
    worker  = aws_security_group.worker.id
    sweeper = aws_security_group.sweeper.id
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_app" {
  for_each                     = local.app_sgs
  security_group_id            = aws_security_group.postgres.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "mongo_from_app" {
  for_each                     = local.app_sgs
  security_group_id            = aws_security_group.mongo.id
  referenced_security_group_id = each.value
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_to_postgres" {
  for_each                     = local.app_sgs
  security_group_id            = each.value
  referenced_security_group_id = aws_security_group.postgres.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_to_mongo" {
  for_each                     = local.app_sgs
  security_group_id            = each.value
  referenced_security_group_id = aws_security_group.mongo.id
  from_port                    = 27017
  to_port                      = 27017
  ip_protocol                  = "tcp"
}

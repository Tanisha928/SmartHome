# Application Load Balancer: HTTPS (ACM), 80→443 redirect, path-based target groups.
# All three target groups point at the same API ASG; they are split so ingest uploads and
# SPA traffic get their own health/latency metrics and deregistration behaviour.

resource "aws_lb" "main" {
  name               = local.name
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 120 # long-lived WebSockets + 25 MB clip uploads
  drop_invalid_header_fields = true
}

locals {
  target_groups = {
    api    = { path = "/healthz", dereg = 30 }
    ingest = { path = "/healthz", dereg = 60 }
    web    = { path = "/healthz", dereg = 10 }
  }
}

resource "aws_lb_target_group" "app" {
  for_each             = local.target_groups
  name                 = "${local.name}-${each.key}"
  port                 = 80
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  target_type          = "instance"
  deregistration_delay = each.value.dereg

  load_balancing_algorithm_type = "least_outstanding_requests"

  health_check {
    path                = each.value.path
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  stickiness {
    type    = "lb_cookie"
    enabled = false
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # TLS ≥ 1.2 (NFR-6)
  certificate_arn   = var.acm_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app["web"].arn
  }
}

resource "aws_lb_listener_rule" "ingest" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10
  condition {
    path_pattern {
      values = ["/api/ingest/*"]
    }
  }
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app["ingest"].arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 20
  condition {
    path_pattern {
      values = ["/api/*", "/ws/*", "/healthz"]
    }
  }
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app["api"].arn
  }
}

# Auto Scaling groups: API (2–6, two AZs behind the ALB), model workers (1–8, scaled on SQS
# depth, finish in-flight work on scale-in), and a singleton sweeper (1–1).

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  tiers = {
    api     = { type = var.api_instance_type, sg = aws_security_group.api.id }
    worker  = { type = var.worker_instance_type, sg = aws_security_group.worker.id }
    sweeper = { type = var.sweeper_instance_type, sg = aws_security_group.sweeper.id }
  }
}

resource "aws_launch_template" "app" {
  for_each      = local.tiers
  name_prefix   = "${local.name}-${each.key}-"
  image_id      = data.aws_ssm_parameter.al2023.value
  instance_type = each.value.type

  iam_instance_profile {
    arn = aws_iam_instance_profile.app[each.key].arn
  }
  vpc_security_group_ids = [each.value.sg]

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size = 20
      volume_type = "gp3"
      encrypted   = true
    }
  }

  monitoring {
    enabled = true
  }

  user_data = base64encode(templatefile("${path.module}/user_data/bootstrap.sh.tftpl", {
    role            = each.key
    region          = var.aws_region
    env             = var.env
    artifact_bucket = var.artifact_bucket
    release         = var.release
    ssm_prefix      = local.ssm_prefix
    clips_bucket    = local.clips_bucket
    queue_url       = local.queue_url
    dlq_url         = local.dlq_url
    asg_name        = "${local.name}-${each.key}"
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${local.name}-${each.key}", Role = each.key }
  }
}

# --- API ---------------------------------------------------------------------------------

resource "aws_autoscaling_group" "api" {
  name                      = "${local.name}-api"
  min_size                  = var.api_min
  max_size                  = var.api_max
  desired_capacity          = var.api_min
  vpc_zone_identifier       = aws_subnet.app[*].id
  health_check_type         = "ELB"
  health_check_grace_period = 180
  target_group_arns         = [for tg in aws_lb_target_group.app : tg.arn]
  default_instance_warmup   = 120

  launch_template {
    id      = aws_launch_template.app["api"].id
    version = aws_launch_template.app["api"].latest_version
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name}-api"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_policy" "api_cpu" {
  name                   = "cpu-60"
  autoscaling_group_name = aws_autoscaling_group.api.name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60
  }
}

resource "aws_autoscaling_policy" "api_requests" {
  name                   = "requests-1000-per-target"
  autoscaling_group_name = aws_autoscaling_group.api.name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.main.arn_suffix}/${aws_lb_target_group.app["api"].arn_suffix}"
    }
    target_value = 1000
  }
}

# --- Model workers -----------------------------------------------------------------------

resource "aws_autoscaling_group" "worker" {
  name                      = "${local.name}-worker"
  min_size                  = var.worker_min
  max_size                  = var.worker_max
  desired_capacity          = var.worker_min
  vpc_zone_identifier       = aws_subnet.app[*].id
  health_check_type         = "EC2"
  health_check_grace_period = 120

  launch_template {
    id      = aws_launch_template.app["worker"].id
    version = aws_launch_template.app["worker"].latest_version
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  # On scale-in the instance waits in Terminating:Wait; the lifecycle watcher stops the
  # worker (SIGTERM → finish current message) and completes the action.
  initial_lifecycle_hook {
    name                 = "drain"
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
    heartbeat_timeout    = 300
    default_result       = "CONTINUE"
  }

  tag {
    key                 = "Name"
    value               = "${local.name}-worker"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_policy" "worker_out" {
  name                   = "queue-scale-out"
  autoscaling_group_name = aws_autoscaling_group.worker.name
  policy_type            = "StepScaling"
  adjustment_type        = "ChangeInCapacity"
  step_adjustment {
    metric_interval_lower_bound = 0
    metric_interval_upper_bound = 400
    scaling_adjustment          = 1
  }
  step_adjustment {
    metric_interval_lower_bound = 400
    scaling_adjustment          = 3
  }
}

resource "aws_autoscaling_policy" "worker_in" {
  name                   = "queue-scale-in"
  autoscaling_group_name = aws_autoscaling_group.worker.name
  policy_type            = "StepScaling"
  adjustment_type        = "ChangeInCapacity"
  step_adjustment {
    metric_interval_upper_bound = 0
    scaling_adjustment          = -1
  }
}

resource "aws_cloudwatch_metric_alarm" "queue_backlog_high" {
  alarm_name          = "${local.name}-queue-backlog-scale-out"
  alarm_description   = "SQS visible > 100 for 2 minutes → add model workers"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = local.queue_name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 100
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_autoscaling_policy.worker_out.arn]
}

resource "aws_cloudwatch_metric_alarm" "queue_backlog_low" {
  alarm_name          = "${local.name}-queue-backlog-scale-in"
  alarm_description   = "SQS visible < 10 for 10 minutes → remove a model worker"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = local.queue_name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 10
  comparison_operator = "LessThanThreshold"
  alarm_actions       = [aws_autoscaling_policy.worker_in.arn]
}

# --- Sweepers (exactly one) --------------------------------------------------------------
# Connectivity, stuck-event, escalation and retention loops must not run concurrently.

resource "aws_autoscaling_group" "sweeper" {
  name                = "${local.name}-sweeper"
  min_size            = 1
  max_size            = 1
  desired_capacity    = 1
  vpc_zone_identifier = aws_subnet.app[*].id
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.app["sweeper"].id
    version = aws_launch_template.app["sweeper"].latest_version
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 0
    }
  }

  tag {
    key                 = "Name"
    value               = "${local.name}-sweeper"
    propagate_at_launch = true
  }
}

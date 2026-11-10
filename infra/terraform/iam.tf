# Instance roles — no static AWS keys anywhere (edge devices hold none either).

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

locals {
  roles = toset(["api", "worker", "sweeper"])
}

resource "aws_iam_role" "app" {
  for_each           = local.roles
  name               = "${local.name}-${each.key}"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  for_each   = local.roles
  role       = aws_iam_role.app[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cw_agent" {
  for_each   = local.roles
  role       = aws_iam_role.app[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "app" {
  for_each = local.roles
  name     = "${local.name}-${each.key}"
  role     = aws_iam_role.app[each.key].name
}

# Shared by every tier: boot-time config, release download, custom metrics.
data "aws_iam_policy_document" "common" {
  statement {
    sid       = "ReadConfig"
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter${local.ssm_prefix}/*"]
  }
  statement {
    sid       = "ReadRelease"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.artifact_bucket}/releases/*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = [local.metric_ns]
    }
  }
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "Clips"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${local.clips_bucket}/clips/*"]
  }
  statement {
    sid = "ClipsAdmin" # RetentionJob lifecycle + data health
    actions = [
      "s3:ListBucket",
      "s3:GetLifecycleConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = ["arn:aws:s3:::${local.clips_bucket}"]
  }
  statement {
    sid       = "Queue"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [local.queue_arn, local.dlq_arn]
  }
  statement {
    sid       = "Notify"
    actions   = ["sns:CreateTopic", "sns:Publish", "sns:Subscribe", "sns:ListSubscriptionsByTopic"]
    resources = ["arn:aws:sns:${var.aws_region}:${local.account_id}:house-*"]
  }
  statement {
    sid       = "Sms" # direct SMS publish by phone number has no topic ARN
    actions   = ["sns:Publish"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "Clips"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.clips_bucket}/clips/*"]
  }
  statement {
    sid = "Consume"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]
    resources = [local.queue_arn]
  }
  statement {
    sid       = "Notify"
    actions   = ["sns:Publish"]
    resources = ["*"]
  }
  statement {
    sid       = "Lifecycle" # finish in-flight message before scale-in
    actions   = ["autoscaling:CompleteLifecycleAction", "autoscaling:RecordLifecycleActionHeartbeat"]
    resources = ["arn:aws:autoscaling:${var.aws_region}:${local.account_id}:autoScalingGroup:*:autoScalingGroupName/${local.name}-worker"]
  }
}

data "aws_iam_policy_document" "sweeper" {
  source_policy_documents = [data.aws_iam_policy_document.api.json]
  statement {
    sid       = "Dlq"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [local.dlq_arn]
  }
  statement {
    sid       = "Backups"
    actions   = ["rds:DescribeDBSnapshots", "rds:DescribeDBInstances"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "common" {
  for_each = local.roles
  name     = "common"
  role     = aws_iam_role.app[each.key].id
  policy   = data.aws_iam_policy_document.common.json
}

resource "aws_iam_role_policy" "tier" {
  for_each = {
    api     = data.aws_iam_policy_document.api.json
    worker  = data.aws_iam_policy_document.worker.json
    sweeper = data.aws_iam_policy_document.sweeper.json
  }
  name   = "tier"
  role   = aws_iam_role.app[each.key].id
  policy = each.value
}

variable "mongo_ami_id" {
  description = "Hardened private MongoDB AMI with mongod installed. Leave empty when using a managed MongoDB service."
  type        = string
  default     = ""
}

variable "mongo_instance_type" {
  type    = string
  default = "t3.medium"
}

data "aws_iam_policy_document" "mongo_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "mongo" {
  count              = var.mongo_ami_id == "" ? 0 : 1
  name               = "${local.name}-mongo"
  assume_role_policy = data.aws_iam_policy_document.mongo_assume.json
}

resource "aws_iam_role_policy_attachment" "mongo_ssm" {
  count      = var.mongo_ami_id == "" ? 0 : 1
  role       = aws_iam_role.mongo[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "mongo" {
  count = var.mongo_ami_id == "" ? 0 : 1
  name  = "${local.name}-mongo"
  role  = aws_iam_role.mongo[0].name
}

resource "aws_instance" "mongo" {
  count                  = var.mongo_ami_id == "" ? 0 : 1
  ami                    = var.mongo_ami_id
  instance_type          = var.mongo_instance_type
  subnet_id              = aws_subnet.data[0].id
  vpc_security_group_ids = [aws_security_group.mongo.id]
  iam_instance_profile   = aws_iam_instance_profile.mongo[0].name

  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false
  }

  user_data = <<-EOT
    #!/bin/bash
    set -eu
    systemctl enable --now mongod
  EOT

  tags = { Name = "${local.name}-mongo" }
}

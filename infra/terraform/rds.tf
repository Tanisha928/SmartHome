variable "db_instance_class" {
  type    = string
  default = "db.t3.medium"
}

resource "aws_db_instance" "smarthome" {
  identifier                 = "${local.name}-postgres"
  engine                    = "postgres"
  engine_version            = "16"
  instance_class            = var.db_instance_class
  allocated_storage         = 50
  max_allocated_storage     = 200
  storage_encrypted         = true
  db_name                   = "smarthome"
  username                  = var.db_username
  password                  = var.db_password
  db_subnet_group_name      = aws_db_subnet_group.data.name
  vpc_security_group_ids    = [aws_security_group.postgres.id]
  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  publicly_accessible       = false
  multi_az                  = true
  deletion_protection       = var.env == "prod"
  skip_final_snapshot       = var.env != "prod"
  final_snapshot_identifier = var.env == "prod" ? "${local.name}-final" : null
  copy_tags_to_snapshot     = true
  apply_immediately         = var.env != "prod"
}

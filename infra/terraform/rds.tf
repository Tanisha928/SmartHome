# Data-tier stub (Tanisha + Sakshat). Complete during Phase 11.
# RDS PostgreSQL 16 encrypted, daily snapshots.

variable "db_instance_class" {
  type    = string
  default = "db.t3.medium"
}

# resource "aws_db_instance" "smarthome" {
#   engine               = "postgres"
#   engine_version       = "16"
#   instance_class       = var.db_instance_class
#   allocated_storage    = 50
#   storage_encrypted    = true
#   db_name              = "smarthome"
#   username             = var.db_username
#   password             = var.db_password
#   skip_final_snapshot  = false
#   backup_retention_period = 7
#   publicly_accessible  = false
# }

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

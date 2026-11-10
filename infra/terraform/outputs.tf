output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "app_subnet_ids" {
  value = aws_subnet.app[*].id
}

output "data_subnet_ids" {
  description = "For RDS / MongoDB (rds.tf, mongo)."
  value       = aws_subnet.data[*].id
}

output "db_subnet_group_name" {
  value = aws_db_subnet_group.data.name
}

output "postgres_security_group_id" {
  value = aws_security_group.postgres.id
}

output "mongo_security_group_id" {
  value = aws_security_group.mongo.id
}

output "asg_names" {
  value = {
    api     = aws_autoscaling_group.api.name
    worker  = aws_autoscaling_group.worker.name
    sweeper = aws_autoscaling_group.sweeper.name
  }
}

output "alarm_topic_arn" {
  value = aws_sns_topic.alarms.arn
}

output "dashboard_url" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

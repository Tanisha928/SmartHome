# S3 clips bucket stub — SSE, block public access, VPC gateway endpoint later.

# resource "aws_s3_bucket" "clips" {
#   bucket = "smarthome-clips-${var.env}"
# }
#
# resource "aws_s3_bucket_server_side_encryption_configuration" "clips" {
#   bucket = aws_s3_bucket.clips.id
#   rule {
#     apply_server_side_encryption_by_default {
#       sse_algorithm = "AES256"
#     }
#   }
# }

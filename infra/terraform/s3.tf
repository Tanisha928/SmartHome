resource "aws_s3_bucket" "clips" {
  bucket        = local.clips_bucket
  force_destroy = var.env != "prod"
}

resource "aws_s3_bucket_public_access_block" "clips" {
  bucket                  = aws_s3_bucket.clips.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "clips" {
  bucket = aws_s3_bucket.clips.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "clips" {
  bucket = aws_s3_bucket.clips.id
  rule {
    id     = "clip-retention"
    status = "Enabled"
    filter { prefix = "clips/" }
    transition { days = 30 storage_class = "STANDARD_IA" }
    expiration { days = 90 }
  }
  rule {
    id     = "backup-retention"
    status = "Enabled"
    filter { prefix = "backups/" }
    expiration { days = 35 }
  }
}

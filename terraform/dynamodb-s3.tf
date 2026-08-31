resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# DynamoDB Table for MegaMart Orders
resource "aws_dynamodb_table" "orders" {
  name         = "megamart-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "order_id"

  attribute {
    name = "order_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "UserIdIndex"
    hash_key        = "user_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "megamart-orders"
  }
}

# S3 Bucket for MegaMart Order Receipts
resource "aws_s3_bucket" "order_receipts" {
  bucket        = "megamart-order-receipts-${random_id.bucket_suffix.hex}"
  force_destroy = false

  tags = {
    Name = "megamart-order-receipts"
  }
}

resource "aws_s3_bucket_versioning" "order_receipts" {
  bucket = aws_s3_bucket.order_receipts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "order_receipts" {
  bucket = aws_s3_bucket.order_receipts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "order_receipts" {
  bucket = aws_s3_bucket.order_receipts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "order_receipts" {
  bucket = aws_s3_bucket.order_receipts.id

  rule {
    id     = "archive-old-receipts"
    status = "Enabled"

    filter {
      prefix = "receipts/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }
  }
}

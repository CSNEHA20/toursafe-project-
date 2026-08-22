# Dedicated AWS KMS Customer Managed Key (CMK) with Annual Rotation
resource "aws_kms_key" "toursafe_cmk" {
  description             = "TourSafe Production KMS Key for KYC Document & Backup Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "toursafe-${var.environment}-cmk"
  }
}

# Private S3 Bucket for KYC Identity Documents (Prompt 18, 31, 33)
resource "aws_s3_bucket" "kyc_vault" {
  bucket        = "toursafe-kyc-vault-${var.environment}"
  force_destroy = false

  tags = {
    Name        = "toursafe-kyc-vault-${var.environment}"
    DataClass   = "Confidential-PII"
    Compliance  = "DPDP-Act-2023-GDPR"
  }
}

# Strict Block of All Public Access
resource "aws_s3_bucket_public_access_block" "kyc_vault_block" {
  bucket = aws_s3_bucket.kyc_vault.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enforce KMS Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "kyc_vault_encryption" {
  bucket = aws_s3_bucket.kyc_vault.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.toursafe_cmk.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# S3 Bucket for Automated Disaster Recovery Backups
resource "aws_s3_bucket" "backups_vault" {
  bucket        = "toursafe-backups-${var.environment}"
  force_destroy = false

  tags = {
    Name      = "toursafe-backups-${var.environment}"
    DataClass = "Encrypted-Database-Snapshots"
  }
}

resource "aws_s3_bucket_public_access_block" "backups_vault_block" {
  bucket = aws_s3_bucket.backups_vault.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

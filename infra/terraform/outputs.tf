output "vpc_id" {
  description = "ID of the TourSafe VPC"
  value       = aws_vpc.toursafe_vpc.id
}

output "kyc_bucket_name" {
  description = "S3 bucket name for encrypted KYC document storage"
  value       = aws_s3_bucket.kyc_vault.id
}

output "backups_bucket_name" {
  description = "S3 bucket name for disaster recovery backups"
  value       = aws_s3_bucket.backups_vault.id
}

output "kms_key_arn" {
  description = "ARN of the TourSafe KMS Customer Managed Key"
  value       = aws_kms_key.toursafe_cmk.arn
}

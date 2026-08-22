variable "aws_region" {
  description = "Primary AWS region for TourSafe deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Target deployment environment (production, staging, test, development)"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for TourSafe Virtual Private Cloud"
  type        = string
  default     = "10.100.0.0/16"
}

variable "kyc_retention_days" {
  description = "KYC document retention window before automated lifecycle transition"
  type        = number
  default     = 730 # 2 years
}

variable "backup_retention_days" {
  description = "Database backup snapshot retention window"
  type        = number
  default     = 90
}

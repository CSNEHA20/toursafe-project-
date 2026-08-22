terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }

  backend "s3" {
    bucket         = "toursafe-terraform-state-prod"
    key            = "platform/prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "toursafe-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "TourSafe"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Criticality = "Mission-Critical-Life-Safety"
    }
  }
}

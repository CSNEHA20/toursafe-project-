# Multi-AZ VPC with Public, Private Application, and Isolated Database Subnets
resource "aws_vpc" "toursafe_vpc" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "toursafe-${var.environment}-vpc"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.toursafe_vpc.id
  cidr_block              = "10.100.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "toursafe-public-${var.aws_region}a"
    Tier = "public"
  }
}

resource "aws_subnet" "private_app_a" {
  vpc_id            = aws_vpc.toursafe_vpc.id
  cidr_block        = "10.100.10.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "toursafe-app-${var.aws_region}a"
    Tier = "app"
  }
}

resource "aws_subnet" "private_data_a" {
  vpc_id            = aws_vpc.toursafe_vpc.id
  cidr_block        = "10.100.20.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "toursafe-data-${var.aws_region}a"
    Tier = "data-isolated"
  }
}

# Internet Gateway for Public Subnet Ingress
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.toursafe_vpc.id

  tags = {
    Name = "toursafe-${var.environment}-igw"
  }
}

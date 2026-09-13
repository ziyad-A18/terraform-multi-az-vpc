resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "multi-az-vpc"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}


resource "aws_subnet" "public" {
  for_each                = var.public_subnets
  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value
  availability_zone       = data.aws_availability_zones.available.names[index(keys(var.public_subnets), each.key)]
  map_public_ip_on_launch = true
  tags = {
    Name = each.key
  }

}
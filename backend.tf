terraform {
  backend "s3" {
    bucket         = "ziyad-alandanusi-tf-state-2026"
    key            = "multi-az-vpc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
  }
}


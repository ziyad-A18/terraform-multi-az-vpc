variable "public_subnets" {
  type = map(string)
  default = {
    "public-1" = "10.0.1.0/24"
    "public-2" = "10.0.2.0/24"
  }
}

variable "private_app_subnets" {
  type = map(string)
  default = {
    "private-app-1" = "10.0.11.0/24"
    "private-app-2" = "10.0.12.0/24"
  }
}

variable "private_db_subnets" {
  type = map(string)
  default = {
    "private-db-1" = "10.0.21.0/24"
    "private-db-2" = "10.0.22.0/24"
  }
}
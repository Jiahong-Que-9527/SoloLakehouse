variable "project" {
  type    = string
  default = "slh-gcp-test"
}

variable "stack_name" {
  type = string
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "europe-west3"
}

variable "owner" {
  type = string
}

variable "image" {
  type = string
}

variable "budget_display_name" {
  type = string
}

terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

module "batch" {
  source             = "../../modules/batch"
  project            = var.project
  stack_name         = var.stack_name
  environment        = var.environment
  region             = var.region
  owner              = var.owner
  image              = var.image
  budget_display_name = var.budget_display_name
}

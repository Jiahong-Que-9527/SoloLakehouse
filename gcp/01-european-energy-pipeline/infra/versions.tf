# [李淳风·2026-11-20] G01 cloud delivery — Terraform wiring.
# The state bucket is created once by BOOTSTRAP.md and passed at init time:
#   terraform init -backend-config="bucket=<state-bucket>"
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  backend "gcs" {
    prefix = "gcp/01-european-energy-pipeline"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

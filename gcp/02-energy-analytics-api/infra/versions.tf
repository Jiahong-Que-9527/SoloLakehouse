# [李淳风·2026-11-20] G02 Terraform wiring, G01 pattern (versions.tf mirrors
# gcp/01-european-energy-pipeline/infra/versions.tf). The state bucket is
# inherited from G01's bootstrap and passed at init time:
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
    prefix = "gcp/02-energy-analytics-api"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

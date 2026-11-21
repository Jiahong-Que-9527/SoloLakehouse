# [Kimi·2026-11-21] G04 Terraform wiring, G01–G03 pattern (versions.tf mirrors
# gcp/03-aviation-event-processing/infra/versions.tf). The state bucket is
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
    prefix = "gcp/04-governed-energy-data-product"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

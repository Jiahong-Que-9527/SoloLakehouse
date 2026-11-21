# [GLM·2026-11-21] Fraport 03 Airport Analytics — Terraform wiring.
# The state bucket (slh-gcp-test-tfstate) and the GitHub WIF pool already
# exist from G01's BOOTSTRAP; this stack only sets its own state prefix.
terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  backend "gcs" {
    prefix = "fraport/03-airport-analytics"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

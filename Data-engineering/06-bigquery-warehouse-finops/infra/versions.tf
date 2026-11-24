terraform {
    required_version = ">= 1.6.0"
    required_providers {
        google = {
            source  = "hashicorp/google"
            version = "~> 6.0"
        }
    }
    # Personal free-tier exercise: local state, no remote backend required.
}

provider "google" {
    project = var.project_id
    region  = var.region
}

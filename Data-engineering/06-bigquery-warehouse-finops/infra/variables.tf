variable "project_id" {
    description = "GCP project hosting the charging-commerce warehouse (design §1: slh-gcp-test)."
    type        = string
}

variable "region" {
    description = "BigQuery location (design §1: europe-west3 / Frankfurt)."
    type        = string
    default     = "europe-west3"
}

variable "analyst_principal" {
    description = <<-EOT
        Analyst identity for the Authorized View read split (design §5.3), e.g.
        "user:analyst@example.com" or "serviceAccount:analyst@project.iam.gserviceaccount.com".
        Empty string skips the analyst IAM bindings (e.g. during the first,
        build-only apply). The analyst never receives raw/staging access — the
        acceptance negative drill proves the 403.
    EOT
    type        = string
    default     = ""
}

locals {
    labels = {
        managed_by = "terraform"
        project    = "charging-commerce-e06"
        cost_gate  = "free-tier"
    }
}

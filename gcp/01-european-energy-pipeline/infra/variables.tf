# [李淳风·2026-11-20] Inputs for the G01 cloud delivery.

variable "project_id" {
  description = "GCP project id for the G01 test delivery (single-purpose test project)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources (bucket, registry, job, scheduler)."
  type        = string
  default     = "europe-west3"
}

variable "image" {
  description = "Container image reference for the Cloud Run job; set by the deploy workflow."
  type        = string
}

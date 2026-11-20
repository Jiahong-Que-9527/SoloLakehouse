# [李淳风·2026-11-20] Inputs for the G02 API delivery.

variable "project_id" {
  description = "GCP project id for the G02 test delivery (same single-purpose test project as G01)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources (dataset, registry, service)."
  type        = string
  default     = "europe-west3"
}

variable "image" {
  description = "Container image reference for the Cloud Run service; set by the deploy workflow."
  type        = string
}

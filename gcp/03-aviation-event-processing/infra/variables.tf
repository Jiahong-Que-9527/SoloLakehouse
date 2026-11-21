# [Kimi·2026-11-21] Inputs for the G03 event-processing delivery.

variable "project_id" {
  description = "GCP project id for the G03 test delivery (same single-purpose test project as G01/G02)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources (dataset, registry, job)."
  type        = string
  default     = "europe-west3"
}

variable "image" {
  description = "Container image reference for the Cloud Run consumer job; set by the deploy workflow."
  type        = string
}

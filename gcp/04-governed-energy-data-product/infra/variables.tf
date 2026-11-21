# [Kimi·2026-11-21] Inputs for the G04 governed-release delivery.

variable "project_id" {
  description = "GCP project id for the G04 test delivery (same single-purpose test project as G01–G03)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources (dataset, registry, job)."
  type        = string
  default     = "europe-west3"
}

variable "image" {
  description = "Container image reference for the Cloud Run publish job; set by the deploy workflow."
  type        = string
}

variable "input_release_id" {
  description = "The G01 release id the first governed publication consumes."
  type        = string
}

variable "candidate_id" {
  description = "The immutable product release id assigned to the first publication."
  type        = string
}

# [GLM·2026-11-21] Inputs for the Fraport 03 cloud delivery.

variable "project_id" {
  description = "GCP project id for the Fraport 03 delivery (shared test project)."
  type        = string
}

variable "region" {
  description = "Region for all regional resources; ADR-004 spike confirmed europe-west3."
  type        = string
  default     = "europe-west3"
}

variable "billing_account" {
  description = "Billing account id for the budget alert (Free Trial account)."
  type        = string
  default     = "01FCE3-C90698-BFE584"
}

variable "monthly_budget_eur" {
  description = "Monthly budget alert amount in EUR; alerts are informational, they do not stop spend."
  type        = number
  default     = 50
}

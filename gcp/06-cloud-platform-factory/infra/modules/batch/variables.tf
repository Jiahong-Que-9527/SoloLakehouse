variable "project" {
  type        = string
  description = "Project that hosts the stack."
}

variable "stack_name" {
  type        = string
  description = "Unique stack suffix, e.g. alpha. Enters every resource name."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.stack_name))
    error_message = "stack_name must be lowercase letters, digits or dashes, 2-21 chars."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment of the stack."
  validation {
    condition     = contains(["dev", "test"], var.environment)
    error_message = "environment must be dev or test (design §4)."
  }
}

variable "region" {
  type        = string
  default     = "europe-west3"
  description = "Region for the bucket, dataset and job."
}

variable "owner" {
  type        = string
  description = "Email of the operator accountable for the stack (recorded in labels)."
}

variable "image" {
  type        = string
  description = "Reference workload image; digest-pinned in production use."
}

variable "budget_display_name" {
  type        = string
  description = "Name of the budget alert attached at bootstrap (informational; budgets are billing-level)."
}

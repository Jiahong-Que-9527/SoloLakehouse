terraform {
  required_version = ">= 1.7.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "1.145.0"
    }
  }

  backend "local" {}
}

variable "stack" {
  description = "One workload stack. Owner is the workspace deployer's user name."
  type = object({
    team                      = string
    environment               = string
    template                  = string
    catalog                   = string
    owner                     = string
    runtime_service_principal = string
    reader_principal          = string
    disposable                = bool
  })

  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{0,22}$", var.stack.team)) &&
      contains(["dev", "prod"], var.stack.environment) &&
      var.stack.template == "batch-lakehouse" &&
      can(regex("^[a-z][a-z0-9_]{0,62}$", var.stack.catalog))
    )
    error_message = "Use a supported team slug, dev or prod, the batch-lakehouse template, and a simple catalog name."
  }

  validation {
    condition = (
      can(regex("^[A-Za-z0-9._+%-]+@[A-Za-z0-9.-]+$", var.stack.owner)) &&
      can(regex("^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$", var.stack.runtime_service_principal)) &&
      trimspace(var.stack.reader_principal) != "" &&
      lower(trimspace(var.stack.reader_principal)) != var.stack.runtime_service_principal
    )
    error_message = "Supply a workspace deployer email, a runtime application ID, and a separate Gold reader principal."
  }

  validation {
    condition     = !var.stack.disposable || var.stack.environment == "dev"
    error_message = "Only development stacks may be marked disposable."
  }
}

locals {
  stack_id = "slh-${var.stack.team}-${var.stack.environment}"
  # Encode the separator as an underscore so the names can be used directly in SQL.
  schema_prefix = replace(local.stack_id, "-", "_")
  layers        = toset(["bronze", "silver", "gold"])
  schema_names  = { for layer in local.layers : layer => "${local.schema_prefix}_${layer}" }
  job_name      = "${local.stack_id}-batch"
}

resource "databricks_schema" "layers" {
  for_each = local.schema_names

  catalog_name  = var.stack.catalog
  name          = each.value
  comment       = "D06 ${local.stack_id} managed by Terraform. Operator: ${var.stack.owner}"
  force_destroy = var.stack.disposable
}

resource "databricks_grants" "layers" {
  for_each = databricks_schema.layers

  schema = "${each.value.catalog_name}.${each.value.name}"

  grant {
    principal  = var.stack.runtime_service_principal
    privileges = ["USE_SCHEMA", "CREATE_TABLE", "SELECT", "MODIFY"]
  }

  dynamic "grant" {
    for_each = each.key == "gold" ? [trimspace(var.stack.reader_principal)] : []

    content {
      principal  = grant.value
      privileges = ["USE_SCHEMA", "SELECT"]
    }
  }
}

output "stack_id" {
  value = local.stack_id
}

output "bundle_target" {
  value = var.stack.environment
}

output "job_name" {
  value = local.job_name
}

output "bundle_vars" {
  description = "Resolved values for the same stack's Bundle deployment."
  value = {
    stack_id                  = local.stack_id
    catalog                   = var.stack.catalog
    bronze_schema             = local.schema_names.bronze
    silver_schema             = local.schema_names.silver
    gold_schema               = local.schema_names.gold
    owner                     = var.stack.owner
    runtime_service_principal = var.stack.runtime_service_principal
  }
}

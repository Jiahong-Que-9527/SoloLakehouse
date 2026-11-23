# The batch template (design #1): bucket, dataset, job, runtime
# identity and a log sink per stack. The runtime account can read its own
# bucket and write its own dataset; it cannot create IAM bindings -- the
# deploy identity does that (design #4).

terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

locals {
  prefix     = "slh-batch-${var.environment}-${var.stack_name}"
  dataset_id = replace(local.prefix, "-", "_")
  labels = {
    stack       = var.stack_name
    environment = var.environment
    owner       = var.owner
    managed_by  = "g06-factory"
  }
}

# -- storage: the stack's bucket and the smoke fixture -----------------------

resource "google_storage_bucket" "stack" {
  name                        = local.prefix
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
  labels                      = local.labels
}

resource "google_storage_bucket_object" "fixture" {
  name    = "fixture/stack.json"
  bucket  = google_storage_bucket.stack.name
  content = jsonencode({ stack_name = var.stack_name, environment = var.environment })
}

# -- warehouse: one dataset, one smoke table ---------------------------------

resource "google_bigquery_dataset" "stack" {
  dataset_id                  = local.dataset_id
  friendly_name               = local.prefix
  location                    = var.region
  delete_contents_on_destroy  = true
  labels                      = local.labels
}

resource "google_bigquery_table" "smoke_results" {
  dataset_id = google_bigquery_dataset.stack.dataset_id
  table_id   = "smoke_results"
  deletion_protection = false
  schema = jsonencode([
    { name = "stack_name", type = "STRING", mode = "REQUIRED" },
    { name = "runtime_principal", type = "STRING", mode = "REQUIRED" },
    { name = "inserted_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])
}

# -- identity: the runtime account and its scoped grants ---------------------

resource "google_service_account" "runtime" {
  account_id   = "${local.prefix}-runtime"
  display_name = "runtime identity for stack ${var.stack_name}"
}

resource "google_storage_bucket_iam_member" "runtime_read_own_bucket" {
  bucket = google_storage_bucket.stack.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_dataset_iam_member" "runtime_write_own_dataset" {
  dataset_id = google_bigquery_dataset.stack.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# -- compute: the reference job ----------------------------------------------

resource "google_cloud_run_v2_job" "smoke" {
  name     = "${local.prefix}-smoke"
  location = var.region
  labels   = local.labels

  template {
    task_count = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "300s"
      max_retries     = 0
      containers {
        image = var.image
        env {
          name  = "STACK_BUCKET"
          value = google_storage_bucket.stack.name
        }
        env {
          name  = "STACK_DATASET"
          value = google_bigquery_dataset.stack.dataset_id
        }
        resources {
          limits = { memory = "512Mi", cpu = "1" }
        }
      }
    }
  }

  depends_on = [
    google_storage_bucket_iam_member.runtime_read_own_bucket,
    google_bigquery_dataset_iam_member.runtime_write_own_dataset,
    google_project_iam_member.runtime_job_user,
  ]
}

# -- logging: the stack's sink into its own bucket ---------------------------

resource "google_logging_project_sink" "stack" {
  name        = "${local.prefix}-logs"
  destination = "storage.googleapis.com/${google_storage_bucket.stack.name}"
  filter      = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${local.prefix}-smoke\""
  unique_writer_identity = true
}

resource "google_storage_bucket_iam_member" "sink_writer" {
  bucket = google_storage_bucket.stack.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.stack.writer_identity
}

# [李淳风·2026-11-20] G01 cloud delivery: services, raw bucket, dataset and
# tables, Artifact Registry, runtime identity, Cloud Run job, weekly scheduler.
#
# Deliberately NOT here (chicken-and-egg, see infra/BOOTSTRAP.md):
#   - the Terraform state bucket
#   - the github-deployer service account and its grant set
#   - the Workload Identity Federation pool/provider for GitHub Actions

locals {
  services = [
    "run.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

resource "google_project_service" "services" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw" {
  name          = "${var.project_id}-energy-raw"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  # No versioning: objects are immutable by convention, every write is a new
  # object (design §4 Raw object).

  depends_on = [google_project_service.services["storage.googleapis.com"]]
}

resource "google_bigquery_dataset" "energy" {
  dataset_id    = "energy"
  friendly_name = "European energy pipeline"
  location      = "EUROPE-WEST3"

  depends_on = [google_project_service.services["bigquery.googleapis.com"]]
}

resource "google_bigquery_table" "metric_observation" {
  table_id            = "metric_observation"
  dataset_id          = google_bigquery_dataset.energy.dataset_id
  deletion_protection = false

  schema = jsonencode(
    [
      {
        name = "interval_start"
        type = "TIMESTAMP"
        mode = "REQUIRED"
      },
      {
        name = "interval_end"
        type = "TIMESTAMP"
        mode = "REQUIRED"
      },
      {
        name = "area"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "metric"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "value"
        type = "FLOAT64"
        mode = "REQUIRED"
      },
      {
        name = "unit"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "source"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "release_id"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "ingested_at"
        type = "TIMESTAMP"
        mode = "REQUIRED"
      },
    ]
  )

  depends_on = [google_project_service.services["bigquery.googleapis.com"]]
}

resource "google_bigquery_table" "load_release" {
  table_id            = "load_release"
  dataset_id          = google_bigquery_dataset.energy.dataset_id
  deletion_protection = false

  schema = jsonencode(
    [
      {
        name = "release_id"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "window_start"
        type = "DATE"
        mode = "REQUIRED"
      },
      {
        name = "window_end"
        type = "DATE"
        mode = "REQUIRED"
      },
      {
        name = "input_checksum"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "row_count"
        type = "INT64"
        mode = "REQUIRED"
      },
      {
        name = "git_sha"
        type = "STRING"
        mode = "NULLABLE"
      },
      {
        name = "execution_id"
        type = "STRING"
        mode = "NULLABLE"
      },
      {
        name = "quality_status"
        type = "STRING"
        mode = "REQUIRED"
      },
      {
        name = "published_at"
        type = "TIMESTAMP"
        mode = "REQUIRED"
      },
    ]
  )

  depends_on = [google_project_service.services["bigquery.googleapis.com"]]
}

resource "google_artifact_registry_repository" "energy" {
  repository_id = "energy"
  location      = var.region
  format        = "DOCKER"
  description   = "G01 energy pipeline images"

  depends_on = [google_project_service.services["artifactregistry.googleapis.com"]]
}

resource "google_service_account" "job" {
  account_id   = "energy-job"
  display_name = "Energy pipeline Cloud Run job"
}

# Least-privilege runtime identity (design §6): write raw objects, edit the
# energy dataset, run BigQuery jobs, and run the job as scheduler identity.
resource "google_storage_bucket_iam_member" "raw_create" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_storage_bucket_iam_member" "raw_view" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_bigquery_dataset_iam_member" "energy_edit" {
  dataset_id = google_bigquery_dataset.energy.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.job.email}"
}

resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.job.email}"
}

resource "google_project_iam_member" "run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.job.email}"
}

resource "google_cloud_run_v2_job" "publisher" {
  name     = "energy-pipeline"
  location = var.region
  # One task, no retries, short timeout: the sample window publishes in well
  # under a minute, and the weekly schedule cannot overlap itself at this
  # cadence (design §5: overlapping runs are prevented).
  deletion_protection = false

  template {
    task_count = 1

    template {
      service_account = google_service_account.job.email

      containers {
        image = var.image
        args = [
          "publish-cloud",
          "--mode", "sample",
          "--from", "2026-06-08",
          "--until", "2026-06-15",
          "--bucket", google_storage_bucket.raw.name,
          "--project", var.project_id,
          "--dataset", "energy",
        ]
      }

      max_retries = 0
      timeout     = "600s"
    }
  }

  depends_on = [google_project_service.services["run.googleapis.com"]]
}

resource "google_cloud_scheduler_job" "weekly" {
  name             = "energy-weekly"
  region           = var.region
  schedule         = "15 5 * * 1"
  time_zone        = "Europe/Berlin"
  paused           = false
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.publisher.name}:run"

    # *.googleapis.com endpoints expect an OAuth access token, not OIDC (an
    # OIDC token here dies with 401 UNAUTHENTICATED before IAM is consulted).
    oauth_token {
      service_account_email = google_service_account.job.email
    }
  }

  depends_on = [google_project_service.services["cloudscheduler.googleapis.com"]]
}

# [李淳风·2026-11-20] G02 cloud read path (plan Task 2.2 + 2.4): API dataset,
# authorized view over the G01 table, runtime/caller identities, Cloud Run
# service, observability.
#
# Deliberately NOT here (shared G01 infrastructure, G01 BOOTSTRAP.md):
#   - the Terraform state bucket, the github-deployer SA, WIF pool/provider
#   - the project services G01 already manages (run/storage/bigquery/
#     artifactregistry/iam/...): duplicating google_project_service here
#     would fight G01's state. Only monitoring.googleapis.com is new to
#     this project and managed below.

# --- Observability prerequisite (new to this project) -----------------------

resource "google_project_service" "monitoring" {
  service            = "monitoring.googleapis.com"
  disable_on_destroy = false
}

# Chicken-and-egg #4 (G01 lesson): build-push runs before the first apply can
# ever create the registry, so it is created by bootstrap and imported into
# state (see infra/BOOTSTRAP.md §1) — apply adopts it instead of creating it.
resource "google_artifact_registry_repository" "energy_api" {
  location      = var.region
  repository_id = "energy-api"
  format        = "DOCKER"
  description   = "G02 Energy Analytics API images"
}

# --- Identities: runtime, caller (deployer is reused from G01) --------------

resource "google_service_account" "runtime" {
  account_id   = "energy-api-runtime"
  display_name = "G02 API runtime: view-only BigQuery reads"
}

resource "google_service_account" "caller" {
  account_id   = "energy-api-caller"
  display_name = "G02 API test caller: invoker on the service"
}

# Runtime identity: dataViewer on the VIEW (table-level) + jobUser on the
# project. Nothing on dataset `energy` — the raw-table denial check in the
# acceptance record depends on this absence.
resource "google_bigquery_table_iam_member" "runtime_view_reader" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.energy_api.dataset_id
  table_id   = google_bigquery_table.api_view.table_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "runtime_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# Caller: invoker on this service only.
resource "google_cloud_run_v2_service_iam_member" "caller_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.energy_api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.caller.email}"

  depends_on = [google_cloud_run_v2_service.energy_api]
}

# --- Data: dataset, authorized view over the G01 table ----------------------

resource "google_bigquery_dataset" "energy_api" {
  dataset_id    = "energy_api"
  friendly_name = "G02 Energy Analytics API"
  location      = "EUROPE-WEST3"
}

resource "google_bigquery_table" "api_view" {
  dataset_id          = google_bigquery_dataset.energy_api.dataset_id
  table_id            = "metric_observation"
  deletion_protection = false

  view {
    query = <<-SQL
      SELECT
        interval_start, interval_end, area, metric, value, unit,
        release_id, ingested_at
      FROM `${var.project_id}.energy.metric_observation`
    SQL
    # BigQuery's tables API defaults useLegacySql to true; under legacy SQL
    # the standard-SQL backtick quoting becomes part of the project ID token
    # (first apply died with Invalid project ID '`slh-gcp-test'). Explicit
    # and non-negotiable.
    use_legacy_sql = false
  }
}

# Authorized view: the view's own authority reads the base table, so the
# runtime identity never needs (and never gets) access to dataset `energy`.
# A separate access resource on G01's dataset is safe: G01's
# google_bigquery_dataset.energy carries no inline access block (verified
# against its main.tf), so this entry is not clobbered by its applies.
resource "google_bigquery_dataset_access" "view_reads_base" {
  dataset_id = "energy"
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.energy_api.dataset_id
    table_id   = google_bigquery_table.api_view.table_id
  }
}

# --- Service ------------------------------------------------------------------

resource "google_cloud_run_v2_service" "energy_api" {
  name     = "energy-api"
  location = var.region
  # Owned and rebuilt by CI; a destroy is a deploy error, not a request.
  deletion_protection = false

  # Deploy must mean "the new revision serves". The rollback drill's
  # explicit update-traffic pin disabled Cloud Run's auto-shift to new
  # revisions, so a later code deploy would create a revision that never
  # receives traffic. Keeping the traffic policy under Terraform re-pins
  # 100% to the latest revision on every apply; latest_revision is
  # dynamic, so future revisions inherit it.
  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = 0
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.energy_api.dataset_id
      }
      env {
        name  = "BQ_VIEW"
        value = google_bigquery_table.api_view.table_id
      }
    }
  }
}

# --- Observability: error metric, alert, owner email channel (Task 2.4) -----

resource "google_logging_metric" "api_errors" {
  name        = "energy_api_errors"
  description = "ERROR-severity log entries from the energy-api service"
  filter      = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"energy-api\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_notification_channel" "owner_email" {
  display_name = "G02 owner email"
  type         = "email"
  labels = {
    email_address = "jiahongque25@gmail.com"
  }
}

resource "google_monitoring_alert_policy" "api_error_rate" {
  display_name = "energy-api error rate"
  combiner     = "OR"

  conditions {
    display_name = "energy-api logged errors"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.api_errors.name}\" AND resource.type=\"cloud_run_revision\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      trigger {
        count = 1
      }

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.owner_email.name]

  depends_on = [google_project_service.monitoring]
}

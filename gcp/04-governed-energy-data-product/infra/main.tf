# [Kimi·2026-11-21] G04 governed publication surface (design sections 3, 5, 6):
# the energy_product dataset with release ledger + quarantine, the authorised
# _current view created by the first publish, three identities with the exact
# role mapping the access tests specify, and an on-demand Cloud Run publish
# job gated on the recorded approval.
#
# Deliberately NOT here (shared G01–G03 infrastructure, their BOOTSTRAP.md):
#   - the Terraform state bucket, the github-deployer SA, WIF pool/provider
#   - project services G01 manages (run/storage/bigquery/artifactregistry/iam),
#     the monitoring API G02 manages and Pub/Sub G03 manages. Nothing new is
#     service-enabled here, so no google_project_service resources exist.

# Chicken-and-egg #4 (G01–G03 lesson): build-push runs before the first apply
# can ever create the registry, so it is created by bootstrap and imported into
# state (see infra/BOOTSTRAP.md §1) — apply adopts it instead of creating it.
resource "google_artifact_registry_repository" "product" {
  location      = var.region
  repository_id = "governed-energy-product"
  format        = "DOCKER"
  description   = "G04 Governed Energy Data Product images"
}

# --- Identities: producer, analyst, auditor (design section 1) ---------------

resource "google_service_account" "producer" {
  account_id   = "energy-product-producer"
  display_name = "G04 producer: reads the G01 input, writes the product dataset"
}

resource "google_service_account" "analyst" {
  account_id   = "energy-product-analyst"
  display_name = "G04 analyst: reads the authorised view and nothing else"
}

resource "google_service_account" "auditor" {
  account_id   = "energy-product-auditor"
  display_name = "G04 auditor: reads release records and cannot edit observations"
}

# Producer: dataViewer on G01's dataset (read the input release) plus
# dataOwner + jobUser for the publication writes. This is the ONLY identity
# with any access to the source dataset.
resource "google_bigquery_dataset_iam_member" "producer_source_reader" {
  dataset_id = "energy"
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.producer.email}"
}

# dataOwner, not dataEditor: the current view sits in the dataset access
# entries as the authorised view, and EVERY rewrite of its definition —
# DDL or the tables API — demands bigquery.datasets.update (the fifth
# live execution's 403). dataOwner scoped to this one dataset is the
# least standard role that carries it; the source dataset above stays
# read-only, and no other identity gains anything.
resource "google_bigquery_dataset_iam_member" "producer_product_owner" {
  dataset_id = google_bigquery_dataset.product.dataset_id
  role       = "roles/bigquery.dataOwner"
  member     = "serviceAccount:${google_service_account.producer.email}"
}

resource "google_project_iam_member" "producer_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.producer.email}"
}

# Analyst: dataViewer on the authorised view only (table-level), never on the
# dataset. The denial on raw and quarantine tables is the acceptance evidence;
# the grant resource lives with the view definition below.

resource "google_project_iam_member" "analyst_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.analyst.email}"
}

# Auditor: dataViewer on the release ledger table only.
resource "google_bigquery_table_iam_member" "auditor_release_reader" {
  dataset_id = google_bigquery_dataset.product.dataset_id
  table_id   = "release"
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.auditor.email}"
}

resource "google_project_iam_member" "auditor_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.auditor.email}"
}

# --- Data: dataset, release ledger, quarantine -------------------------------

resource "google_bigquery_dataset" "product" {
  dataset_id    = "energy_product"
  friendly_name = "G04 Governed Energy Data Product"
  location      = "EUROPE-WEST3"
}

# Test-project tables stay destroyable (G01–G03 pattern); the real protection
# is the 0-destroys plan rule, not deletion_protection.

resource "google_bigquery_table" "release" {
  dataset_id          = google_bigquery_dataset.product.dataset_id
  table_id            = "release"
  deletion_protection = false

  schema = jsonencode([
    { name = "product", type = "STRING", mode = "REQUIRED" },
    { name = "release_id", type = "STRING", mode = "REQUIRED" },
    { name = "input_release_id", type = "STRING", mode = "REQUIRED" },
    { name = "contract_version", type = "STRING", mode = "REQUIRED" },
    { name = "status", type = "STRING", mode = "REQUIRED" },
    { name = "output_table", type = "STRING", mode = "REQUIRED" },
    { name = "git_sha", type = "STRING" },
    { name = "approver", type = "STRING", mode = "REQUIRED" },
    { name = "checksum", type = "STRING", mode = "REQUIRED" },
    { name = "published_at", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "manifest", type = "STRING", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "quarantine" {
  dataset_id          = google_bigquery_dataset.product.dataset_id
  table_id            = "quarantine"
  deletion_protection = false

  schema = jsonencode([
    { name = "product", type = "STRING", mode = "REQUIRED" },
    { name = "release_id", type = "STRING", mode = "REQUIRED" },
    { name = "input_release_id", type = "STRING", mode = "REQUIRED" },
    { name = "check", type = "STRING", mode = "REQUIRED" },
    { name = "detail", type = "STRING", mode = "REQUIRED" },
    { name = "offending", type = "STRING", mode = "REQUIRED" },
    { name = "recorded_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# The authorised view exists from the first apply as a zero-row placeholder
# with the observation schema, so the analyst grant has a target; the first
# publish replaces its query with CREATE OR REPLACE VIEW at runtime, and
# ignore_changes keeps Terraform from reverting that pointer afterwards.
# The immutable version tables `energy_load_v<release>` remain runtime-created
# (publication is a gated decision, not infrastructure).
resource "google_bigquery_table" "energy_load_current" {
  dataset_id          = google_bigquery_dataset.product.dataset_id
  table_id            = "energy_load_current"
  deletion_protection = false

  view {
    # Zero rows, correct columns: a target for the grant and a safe empty
    # read before the first publication. (BigQuery rejects a WHERE without
    # FROM, hence the subquery.)
    query          = <<-SQL
      SELECT * FROM (
        SELECT
          CAST(NULL AS TIMESTAMP) AS interval_start,
          CAST(NULL AS TIMESTAMP) AS interval_end,
          CAST(NULL AS STRING) AS area,
          CAST(NULL AS STRING) AS metric,
          CAST(NULL AS FLOAT64) AS value,
          CAST(NULL AS STRING) AS unit,
          CAST(NULL AS STRING) AS release_id,
          CAST(NULL AS TIMESTAMP) AS ingested_at
      ) WHERE FALSE
    SQL
    use_legacy_sql = false
  }

  lifecycle {
    ignore_changes = [view]
  }
}

# Authorised view on its own dataset: the view's own authority reads the
# version tables, so the analyst needs table-level access to the view only
# (G02 pattern, applied within one dataset).
resource "google_bigquery_dataset_access" "view_reads_versions" {
  dataset_id = google_bigquery_dataset.product.dataset_id
  project    = var.project_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.product.dataset_id
    table_id   = google_bigquery_table.energy_load_current.table_id
  }
}

# The analyst grant targets the view; the empty placeholder guarantees it
# exists from the first apply.
resource "google_bigquery_table_iam_member" "analyst_view_reader" {
  dataset_id = google_bigquery_dataset.product.dataset_id
  table_id   = google_bigquery_table.energy_load_current.table_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.analyst.email}"

  depends_on = [google_bigquery_table.energy_load_current]
}

resource "google_cloud_run_v2_job" "publisher" {
  name     = "energy-product-publisher"
  location = var.region
  # Owned and rebuilt by CI; a destroy is a deploy error, not a request.
  deletion_protection = false

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.producer.email
      max_retries     = 0

      containers {
        image = var.image

        env {
          name  = "BQ_DATASET"
          value = google_bigquery_dataset.product.dataset_id
        }
        env {
          name  = "INPUT_RELEASE_ID"
          value = var.input_release_id
        }
        env {
          name  = "CANDIDATE_ID"
          value = var.candidate_id
        }
        env {
          name  = "CONTRACT_FILE"
          value = "/app/contracts/energy-load.yaml"
        }
        env {
          name  = "APPROVER"
          value = "gcp-test-gate"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }
}

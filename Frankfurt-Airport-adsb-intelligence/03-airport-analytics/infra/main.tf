# [GLM·2026-11-21] Frankfurt Airport 03 M2: landing bucket, gold storage, BigQuery
# dataset, BigLake connection, upload/runtime identities and a budget alert.
#
# Identity split (03 README, design §6):
#   - aviation-upload can only create objects in the landing bucket. It can
#     never read them back or touch any other data.
#   - aviation-ingest reads the landing bucket and runs BigQuery jobs; the
#     data files of managed Iceberg tables are written by the BigLake
#     connection's own service account (ADR-004).
#
# Deliberately NOT here (see infra/BOOTSTRAP.md): the Terraform state bucket
# and the github-deployer WIF setup shared with G01.

locals {
  services = [
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "bigqueryconnection.googleapis.com",
    "billingbudgets.googleapis.com",
    "iam.googleapis.com",
    "serviceusage.googleapis.com",
  ]
}

resource "google_project_service" "services" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "landing" {
  name          = "${var.project_id}-aviation-landing"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  # Releases are immutable once uploaded; re-uploading the same release is
  # refused by convention and the ingest job verifies checksums anyway.

  depends_on = [google_project_service.services["storage.googleapis.com"]]
}

resource "google_storage_bucket" "gold" {
  name          = "${var.project_id}-aviation-gold"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  # Holds the managed Iceberg table data and metadata (ADR-004). Only the
  # BigLake connection's service account writes here.

  depends_on = [google_project_service.services["storage.googleapis.com"]]
}

resource "google_bigquery_dataset" "aviation" {
  dataset_id    = "aviation"
  friendly_name = "Frankfurt Airport ADS-B intelligence"
  location      = "EUROPE-WEST3"

  depends_on = [google_project_service.services["bigquery.googleapis.com"]]
}

resource "google_bigquery_connection" "gold" {
  connection_id = "aviation-gold-conn"
  location      = var.region
  friendly_name = "Managed Iceberg tables for gold releases"

  cloud_resource {}

  depends_on = [google_project_service.services["bigqueryconnection.googleapis.com"]]
}

# Upload identity: create-only on the landing bucket, nothing else.
resource "google_service_account" "upload" {
  account_id   = "aviation-upload"
  display_name = "Frankfurt Airport gold release upload (create-only)"
}

resource "google_storage_bucket_iam_member" "landing_upload" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.upload.email}"
}

# Runtime identity: read the landing bucket, run BigQuery jobs, edit the
# aviation dataset, and use the BigLake connection.
resource "google_service_account" "ingest" {
  account_id   = "aviation-ingest"
  display_name = "Frankfurt Airport release ingestion (BigQuery runtime)"
}

resource "google_storage_bucket_iam_member" "landing_view" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_project_iam_member" "ingest_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_bigquery_dataset_iam_member" "aviation_edit" {
  dataset_id = google_bigquery_dataset.aviation.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingest.email}"
}

resource "google_bigquery_connection_iam_member" "ingest_connection_user" {
  connection_id = google_bigquery_connection.gold.name
  location      = var.region
  role          = "roles/bigquery.connectionUser"
  member        = "serviceAccount:${google_service_account.ingest.email}"
}

# The BigLake connection's service account owns the Iceberg data files;
# the service account id is an output-only attribute of the connection.
resource "google_storage_bucket_iam_member" "gold_connection_admin" {
  bucket = google_storage_bucket.gold.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_bigquery_connection.gold.cloud_resource[0].service_account_id}"
}

# Budget alert on the Free Trial billing account: informational only, it
# does not stop spend. Applying this resource needs the deployer to hold
# roles/billing.budgetsEditor on the billing account (see BOOTSTRAP.md).
resource "google_billing_budget" "aviation" {
  billing_account = var.billing_account
  display_name    = "frankfurt-airport-aviation-monthly"

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.monthly_budget_eur)
    }
  }

  threshold_rules {
    threshold_percent = 50
  }
  threshold_rules {
    threshold_percent = 90
  }
  threshold_rules {
    threshold_percent = 100
  }

  depends_on = [google_project_service.services["billingbudgets.googleapis.com"]]
}

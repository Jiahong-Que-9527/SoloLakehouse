# Datasets (design §4): de_raw, de_stg, de_int, de_mart, de_consumer — all in
# europe-west3, all Free-Tier SKUs (storage only), all with prevent_destroy so
# the mandated "0 destroys" plan can never drift into dataset deletion.

resource "google_bigquery_dataset" "de_raw" {
  dataset_id    = "de_raw"
  friendly_name = "de_raw (charging commerce raw layer)"
  description   = "E01 locked raw batches uploaded by charging-commerce load-bq; dbt source dataset."
  location      = var.region
  labels        = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "de_stg" {
  dataset_id    = "de_stg"
  friendly_name = "de_stg (dbt staging views)"
  description   = "dbt staging views (E02); read-only projections over de_raw."
  location      = var.region
  labels        = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "de_int" {
  dataset_id    = "de_int"
  friendly_name = "de_int (dbt intermediate views)"
  description   = "dbt intermediate views (E02 dedup/wholesale logic); not exposed to consumers."
  location      = var.region
  labels        = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "de_mart" {
  dataset_id    = "de_mart"
  friendly_name = "de_mart (dbt Kimball marts + snapshots)"
  description   = "Kimball star marts and E04 SCD2 snapshots; partitioned facts per design §1."
  location      = var.region
  labels        = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_bigquery_dataset" "de_consumer" {
  dataset_id    = "de_consumer"
  friendly_name = "de_consumer (authorized consumer view)"
  description   = "Governance boundary: the analyst-facing Authorized View lives here; raw/staging stay denied."
  location      = var.region
  labels        = local.labels

  lifecycle {
    prevent_destroy = true
  }
}

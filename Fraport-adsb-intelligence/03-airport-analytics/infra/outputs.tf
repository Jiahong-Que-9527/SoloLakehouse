# [GLM·2026-11-21] Outputs consumed by the ingest job and the workflows.

output "landing_bucket" {
  description = "Landing bucket that receives Gold releases (create-only upload)."
  value       = google_storage_bucket.landing.name
}

output "gold_bucket" {
  description = "Bucket holding the managed Iceberg table data (ADR-004)."
  value       = google_storage_bucket.gold.name
}

output "dataset_id" {
  description = "BigQuery dataset for the aviation Gold tables."
  value       = google_bigquery_dataset.aviation.dataset_id
}

output "biglake_connection" {
  description = "BigLake connection for managed Iceberg tables."
  value       = google_bigquery_connection.gold.connection_id
}

output "upload_identity" {
  description = "Create-only upload service account email."
  value       = google_service_account.upload.email
}

output "ingest_identity" {
  description = "Runtime ingestion service account email."
  value       = google_service_account.ingest.email
}

# [Kimi·2026-11-21] Outputs for the G04 governed-release delivery.

output "dataset_id" {
  description = "BigQuery dataset holding release ledger, quarantine and published views."
  value       = google_bigquery_dataset.product.dataset_id
}

output "producer_sa_email" {
  description = "Producer identity: reads the G01 input, writes the product dataset."
  value       = google_service_account.producer.email
}

output "analyst_sa_email" {
  description = "Analyst identity: dataViewer on the authorised view only."
  value       = google_service_account.analyst.email
}

output "auditor_sa_email" {
  description = "Auditor identity: dataViewer on the release ledger only."
  value       = google_service_account.auditor.email
}

output "publisher_job_name" {
  description = "Cloud Run job executed once per governed release."
  value       = google_cloud_run_v2_job.publisher.name
}

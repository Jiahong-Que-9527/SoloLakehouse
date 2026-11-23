output "bucket_name" {
  value = google_storage_bucket.stack.name
}

output "dataset_id" {
  value = google_bigquery_dataset.stack.dataset_id
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "job_name" {
  value = google_cloud_run_v2_job.smoke.name
}

output "smoke_command" {
  value = "gcloud run jobs execute ${google_cloud_run_v2_job.smoke.name} --region ${var.region} --wait"
}

output "smoke_check" {
  value = "bq query --use_legacy_sql=false --format=csv 'SELECT stack_name, runtime_principal FROM `${var.project}.${google_bigquery_dataset.stack.dataset_id}.smoke_results`'"
}

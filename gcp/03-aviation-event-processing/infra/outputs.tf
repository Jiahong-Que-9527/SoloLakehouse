# [Kimi·2026-11-21] Outputs for the G03 event-processing delivery.

output "events_topic" {
  description = "Events topic the generator publishes to."
  value       = google_pubsub_topic.events.name
}

output "pull_subscription" {
  description = "Pull subscription the consumer job drains."
  value       = google_pubsub_subscription.events_pull.name
}

output "dlq_topic" {
  description = "Dead-letter topic; the replay command republishes from here."
  value       = google_pubsub_topic.dlq.name
}

output "dlq_subscription" {
  description = "Dead-letter subscription used to inspect and replay failed bodies."
  value       = google_pubsub_subscription.dlq.name
}

output "dataset_id" {
  description = "BigQuery dataset holding receipt, state, history and quarantine tables."
  value       = google_bigquery_dataset.events.dataset_id
}

output "runtime_sa_email" {
  description = "Consumer runtime identity: subscription pull, dataset writes, DLQ publishes."
  value       = google_service_account.runtime.email
}

output "consumer_job_name" {
  description = "Cloud Run job executed on demand for each exercise."
  value       = google_cloud_run_v2_job.consumer.name
}

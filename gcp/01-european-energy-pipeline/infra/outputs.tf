# [李淳风·2026-11-20] Outputs consumed by later tasks and the deploy workflow.

output "job_name" {
  description = "Cloud Run job name; first execution is `gcloud run jobs execute <job_name> --region <region> --wait`."
  value       = google_cloud_run_v2_job.publisher.name
}

output "region" {
  description = "Region all regional resources live in."
  value       = var.region
}

output "bucket_name" {
  description = "Raw object bucket."
  value       = google_storage_bucket.raw.name
}

output "image_repository" {
  description = "Artifact Registry repository URL the workflow pushes to."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.energy.repository_id}"
}

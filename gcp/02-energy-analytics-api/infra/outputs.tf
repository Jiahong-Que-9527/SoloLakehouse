# [李淳风·2026-11-20] Outputs for the G02 API delivery.

output "service_uri" {
  description = "Base URL of the Energy Analytics API service."
  value       = google_cloud_run_v2_service.energy_api.uri
}

output "runtime_sa_email" {
  description = "Runtime identity: view-only BigQuery reads through the authorized view."
  value       = google_service_account.runtime.email
}

output "caller_sa_email" {
  description = "Test caller identity holding run.invoker on the service."
  value       = google_service_account.caller.email
}

output "alert_policy_display_name" {
  description = "Display name of the error-rate alert policy (Task 2.4)."
  value       = google_monitoring_alert_policy.api_error_rate.display_name
}

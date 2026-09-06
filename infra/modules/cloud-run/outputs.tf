output "url" {
  value       = google_cloud_run_v2_service.this.uri
  description = "The deployed service's HTTPS URL"
}

output "service_name" {
  value = google_cloud_run_v2_service.this.name
}

output "latest_revision" {
  value = google_cloud_run_v2_service.this.latest_ready_revision
}

output "api_service_url" {
  description = "URL of the API Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_service_url" {
  description = "URL of the Worker Cloud Run service"
  value       = google_cloud_run_v2_service.worker.uri
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository for containers"
  value       = google_artifact_registry_repository.containers.name
}

output "pubsub_topic_draft_requests" {
  description = "Pub/Sub topic for draft requests"
  value       = google_pubsub_topic.draft_requests.id
}

output "pubsub_topic_draft_completed" {
  description = "Pub/Sub topic for completed drafts"
  value       = google_pubsub_topic.draft_completed.id
}

output "pubsub_topic_draft_failed" {
  description = "Pub/Sub topic for failed drafts (DLQ)"
  value       = google_pubsub_topic.draft_failed.id
}

output "api_service_account_email" {
  description = "Service account email for API service"
  value       = google_service_account.api.email
}

output "worker_service_account_email" {
  description = "Service account email for Worker service"
  value       = google_service_account.worker.email
}

output "figma_feeds_bucket" {
  description = "Cloud Storage bucket for Figma feeds"
  value       = google_storage_bucket.figma_feeds.name
}

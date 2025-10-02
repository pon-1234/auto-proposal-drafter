terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "auto-proposal-drafter-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Service accounts
resource "google_service_account" "api" {
  account_id   = "api-service"
  display_name = "API Service Account"
  description  = "Service account for Cloud Run API service"
}

resource "google_service_account" "worker" {
  account_id   = "worker-service"
  display_name = "Worker Service Account"
  description  = "Service account for Pub/Sub worker"
}

resource "google_service_account" "workflows" {
  account_id   = "workflows-service"
  display_name = "Workflows Service Account"
  description  = "Service account for Cloud Workflows orchestration"
}

# Firestore database
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  concurrency_mode            = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"
}

# Cloud Storage bucket for Figma feeds
resource "google_storage_bucket" "figma_feeds" {
  name          = "${var.project_id}-figma-feeds"
  location      = var.region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    condition {
      age = 30 # Delete feeds older than 30 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
  }
}

# Pub/Sub topics and subscriptions
resource "google_pubsub_topic" "draft_requests" {
  name = "draft-requests"

  message_retention_duration = "86400s" # 1 day

  labels = {
    environment = var.environment
  }
}

resource "google_pubsub_topic" "draft_completed" {
  name = "draft-completed"

  message_retention_duration = "86400s"

  labels = {
    environment = var.environment
  }
}

resource "google_pubsub_topic" "draft_failed" {
  name = "draft-failed"

  message_retention_duration = "604800s" # 7 days (DLQ)

  labels = {
    environment = var.environment
  }
}

resource "google_pubsub_subscription" "draft_requests_worker" {
  name  = "draft-requests-worker"
  topic = google_pubsub_topic.draft_requests.id

  ack_deadline_seconds = 600 # 10 minutes for long-running generation

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.draft_failed.id
    max_delivery_attempts = 5
  }

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.worker.uri}/v1/worker/process"

    oidc_token {
      service_account_email = google_service_account.worker.email
    }
  }

  depends_on = [google_pubsub_topic_iam_member.draft_failed_publisher]
}

resource "google_pubsub_topic_iam_member" "draft_failed_publisher" {
  topic  = google_pubsub_topic.draft_failed.id
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${var.project_number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Artifact Registry repository
resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "containers"
  description   = "Container images for Auto Proposal Drafter"
  format        = "DOCKER"
}

# Cloud Run API service
resource "google_cloud_run_v2_service" "api" {
  name     = "api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.environment == "prod" ? 1 : 0
      max_instance_count = var.environment == "prod" ? 10 : 3
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/containers/api:latest"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "PUBSUB_TOPIC_DRAFT_REQUESTS"
        value = google_pubsub_topic.draft_requests.id
      }

      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 3
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 10
        timeout_seconds   = 5
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    environment = var.environment
  }
}

# Cloud Run Worker service
resource "google_cloud_run_v2_service" "worker" {
  name     = "worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.worker.email

    timeout = "600s" # 10 minutes for long-running jobs

    scaling {
      min_instance_count = 0
      max_instance_count = var.environment == "prod" ? 20 : 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/containers/worker:latest"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "PUBSUB_TOPIC_DRAFT_COMPLETED"
        value = google_pubsub_topic.draft_completed.id
      }

      env {
        name  = "VERTEX_AI_LOCATION"
        value = var.vertex_ai_location
      }

      resources {
        limits = {
          cpu    = "4"
          memory = "4Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 10
        period_seconds        = 5
        failure_threshold     = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = {
    environment = var.environment
  }
}

# IAM bindings for API service
resource "google_project_iam_member" "api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# IAM bindings for Worker service
resource "google_project_iam_member" "worker_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

# Allow public access to API (adjust for production)
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Allow Pub/Sub to invoke Worker
resource "google_cloud_run_v2_service_iam_member" "worker_pubsub" {
  name     = google_cloud_run_v2_service.worker.name
  location = google_cloud_run_v2_service.worker.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.worker.email}"
}

# Secret Manager secrets (placeholders - populate via console or CLI)
resource "google_secret_manager_secret" "notion_api_key" {
  secret_id = "notion-api-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
  }
}

resource "google_secret_manager_secret" "hubspot_api_key" {
  secret_id = "hubspot-api-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
  }
}

resource "google_secret_manager_secret" "slack_signing_secret" {
  secret_id = "slack-signing-secret"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
  }
}

resource "google_secret_manager_secret" "slack_bot_token" {
  secret_id = "slack-bot-token"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
  }
}

# Cloud Scheduler for periodic Notion polling (optional)
resource "google_cloud_scheduler_job" "notion_poll" {
  name             = "notion-poll"
  description      = "Poll Notion for new opportunities"
  schedule         = "*/15 * * * *" # Every 15 minutes
  time_zone        = "Asia/Tokyo"
  attempt_deadline = "320s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/v1/ingest/notion/poll"

    oidc_token {
      service_account_email = google_service_account.api.email
    }
  }

  depends_on = [google_cloud_run_v2_service.api]
}

# Monitoring alert policy for failed jobs
resource "google_monitoring_alert_policy" "draft_failures" {
  display_name = "Draft Generation Failures"
  combiner     = "OR"

  conditions {
    display_name = "High failure rate on draft-failed topic"

    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/topic/send_message_operation_count\" AND resource.type=\"pubsub_topic\" AND resource.label.topic_id=\"${google_pubsub_topic.draft_failed.name}\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.notification_channels

  alert_strategy {
    auto_close = "86400s" # 1 day
  }
}

# Log sink for Error Reporting
resource "google_logging_project_sink" "error_reporting" {
  name        = "error-reporting-sink"
  destination = "pubsub.googleapis.com/projects/${var.project_id}/topics/error-logs"

  filter = <<-EOT
    severity >= ERROR
    resource.type = "cloud_run_revision"
  EOT

  unique_writer_identity = true
}

# Error logs topic
resource "google_pubsub_topic" "error_logs" {
  name    = "error-logs"
  project = var.project_id
}

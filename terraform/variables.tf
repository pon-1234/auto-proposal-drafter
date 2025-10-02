variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "auto-proposal-drafter"
}

variable "project_number" {
  description = "GCP Project Number"
  type        = string
  default     = "714947184343"
}

variable "region" {
  description = "GCP region for Cloud Run services"
  type        = string
  default     = "asia-northeast1"
}

variable "firestore_location" {
  description = "Firestore location"
  type        = string
  default     = "asia-northeast1"
}

variable "vertex_ai_location" {
  description = "Vertex AI location"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "notification_channels" {
  description = "List of notification channel IDs for alerts"
  type        = list(string)
  default     = []
}

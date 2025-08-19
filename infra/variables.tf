variable "project_id" {
  description = "The GCP project ID where all resources will be deployed."
  type        = string
}

variable "region" {
  description = "The GCP region for the deployment."
  type        = string
  default     = "us-central1"
}

variable "function_name" {
  description = "The name for the Cloud Function."
  type        = string
  default     = "zombie-projects-watcher"
}

variable "organization_id" {
  description = "O ID numérico da sua Organização GCP."
  type        = string
}

variable "chat_webhook_url" {
  description = "The webhook URL for Google Chat notifications. This is sensitive."
  type        = string
  sensitive   = true
}



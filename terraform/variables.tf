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

variable "service_account_email" {
  description = "The email of the service account the function will use."
  type        = string
}

variable "chat_webhook_url" {
  description = "The webhook URL for Google Chat notifications. This is sensitive."
  type        = string
  sensitive   = true
}

variable "config_bucket_name" {
  description = "The name for the GCS bucket that will store the config.yaml file."
  type        = string
}

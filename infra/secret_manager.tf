resource "google_secret_manager_secret" "webhook_secret" {
  secret_id = "zombie-project-watcher-chat-webhook"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "webhook_secret_version" {
  secret      = google_secret_manager_secret.webhook_secret.id
  secret_data = var.chat_webhook_url
}
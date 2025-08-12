output "function_url" {
  description = "The invocation URL of the deployed Cloud Function."
  value       = google_cloudfunctions2_function.zombie_watcher_function.service_config[0].uri
}
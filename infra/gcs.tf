resource "random_id" "config_bucket_suffix" {
  byte_length = 2
}

resource "google_storage_bucket" "config_bucket" {
  name          = "zombie-watcher-config-${var.project_id}-${random_id.config_bucket_suffix.hex}"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "config_file" {
  name   = "config.yaml"
  bucket = google_storage_bucket.config_bucket.name
  source = "${path.module}/../config.yaml"

  depends_on = [google_storage_bucket.config_bucket]
}


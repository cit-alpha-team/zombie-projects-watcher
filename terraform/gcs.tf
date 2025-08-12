resource "google_storage_bucket" "config_bucket" {
  name          = var.config_bucket_name
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "config_file" {
  name   = "config.yaml"
  bucket = google_storage_bucket.config_bucket.name
  source = "../config.yaml"

  depends_on = [google_storage_bucket.config_bucket]
}


data "archive_file" "source" {
  type        = "zip"
  source_dir  = "${path.module}/../"
  output_path = "/tmp/zombie-watcher-source.zip"
  excludes = [
    "terraform/",
    ".git/",
    "*.tfvars"
  ]
}

resource "google_storage_bucket" "function_source_bucket" {
  name                        = "${var.project_id}-gcf-source"
  location                    = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "source_zip" {
  name   = "zombie-watcher-source-${data.archive_file.source.output_md5}.zip"
  bucket = google_storage_bucket.function_source_bucket.name
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "zombie_watcher_function" {
  name     = var.function_name
  location = var.region

  depends_on = [
    google_storage_bucket_object.config_file
  ]

  build_config {
    runtime     = "python313"
    entry_point = "http_request"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source_bucket.name
        object = google_storage_bucket_object.source_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    min_instance_count    = 0
    available_memory      = "256Mi"
    timeout_seconds       = 540
    service_account_email = var.service_account_email

    environment_variables = {
      CONFIG_BUCKET_NAME = google_storage_bucket.config_bucket.name
    }
  }
}

resource "google_cloud_scheduler_job" "zombie_watcher_trigger" {
  name        = "${var.function_name}-trigger"
  schedule    = "0 13 * * 1-5"
  time_zone   = "America/Sao_Paulo"
  description = "Aciona o Zombie Projects Watcher diariamente."

  http_target {
    uri         = google_cloudfunctions2_function.zombie_watcher_function.service_config[0].uri
    http_method = "POST"

    oidc_token {
      service_account_email = var.service_account_email
    }
  }
}


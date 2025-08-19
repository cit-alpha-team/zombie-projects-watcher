resource "google_service_account" "zombie_watcher_sa" {
  account_id   = "zombie-watcher-bot"
  display_name = "Zombie Projects Watcher Bot"
  description  = "Service account used by the Zombie Projects Watcher function."
}

resource "google_organization_iam_member" "org_viewer" {
  org_id = var.organization_id
  role   = "roles/viewer"
  member = google_service_account.zombie_watcher_sa.member
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = google_service_account.zombie_watcher_sa.member
}

resource "google_project_iam_member" "storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = google_service_account.zombie_watcher_sa.member
}

resource "google_project_iam_member" "run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = google_service_account.zombie_watcher_sa.member
}

resource "google_project_iam_member" "bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = google_service_account.zombie_watcher_sa.member
}


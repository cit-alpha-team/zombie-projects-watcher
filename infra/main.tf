terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }

  backend "gcs" {
    bucket = "tf-state-zombie-watcher-bot"
    prefix = "zombie-watcher/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
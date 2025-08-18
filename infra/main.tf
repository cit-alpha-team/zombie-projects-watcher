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


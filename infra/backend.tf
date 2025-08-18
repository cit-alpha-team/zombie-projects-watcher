terraform {
  backend "gcs" {
    bucket = "tf-state-zombie-watcher-bot"
    prefix = "zombie-watcher/state"
  }
}


terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "> 4.51.0"
    }
  }
}


locals {
  cert_file = filebase64("$(path.module)/../../secrets/cert.p12")
}

provider "google" {
  credentials = file(var.credentials_file)

  project = var.project
  region  = var.region
  zone    = var.zone
}

resource "google_service_account" "account" {
  account_id   = "nupy-invoker"
  display_name = "Service Account used for invoking the nupy-function."
}

resource "google_project_iam_member" "project" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"

  member = "serviceAccount:${google_service_account.account.email}"

}

resource "google_storage_bucket" "code_storage" {
  name                        = "${var.project}-gcf-source"
  location                    = "us-central1"
  uniform_bucket_level_access = true
}

data "archive_file" "init" {
  type        = "zip"
  source_dir  = "${path.module}/../"
  output_path = "files/code.zip"
  excludes    = [".env", "terraform", "secrets", ".vscode", ".github", "venv"]
}

resource "google_storage_bucket_object" "code_object" {
  name         = "source-code.zip"
  source       = data.archive_file.init.output_path
  content_type = "application/zip"
  bucket       = google_storage_bucket.code_storage.id
}

resource "google_cloudfunctions2_function" "function" {
  name        = "nupy-function" # name should use kebab-case so generated Cloud Run service name will be the same
  location    = "us-central1"
  description = "Nupy"

  build_config {
    runtime     = "python310"
    entry_point = "cardbill" # Set the entry point
    source {
      storage_source {
        bucket = google_storage_bucket.code_storage.name
        object = google_storage_bucket_object.code_object.name
      }
    }
  }

  service_config {
    min_instance_count    = 1
    available_memory      = "128Mi"
    timeout_seconds       = 60
    service_account_email = google_service_account.account.email
    environment_variables = {
      cpf  = var.cpf,
      pass = var.pass,
      ssid = var.ssid,
      cert_path = var.cert_path
    }
    secret_volumes {
      mount_path = var.cert_path
      project_id = var.project
      secret     = google_secret_manager_secret.secret-certificate.secret_id
      versions {
        version = "latest"
        path    = "cert.p12"
      }
    }
  }
  depends_on = [google_secret_manager_secret_version.secret-version-basic]
  #timeouts { #TODO REMOVE
  #  create = "2m"
  #}
}

resource "google_cloudfunctions2_function_iam_member" "invoker" {
  project        = google_cloudfunctions2_function.function.project
  location       = google_cloudfunctions2_function.function.location
  cloud_function = google_cloudfunctions2_function.function.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.account.email}"
}

resource "google_cloud_run_service_iam_member" "cloud_run_invoker" {
  project  = google_cloudfunctions2_function.function.project
  location = google_cloudfunctions2_function.function.location
  service  = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.account.email}"
}

resource "google_cloud_scheduler_job" "invoke_cloud_function" {
  name        = "invoke-nupy-function"
  description = "Schedule the HTTPS trigger for cloud function"
  schedule    = "50 23 * * 1-7"
  project     = google_cloudfunctions2_function.function.project
  region      = google_cloudfunctions2_function.function.location
  time_zone   = "America/Bahia"

  http_target {
    uri         = google_cloudfunctions2_function.function.service_config[0].uri
    http_method = "GET"
    oidc_token {
      audience              = "${google_cloudfunctions2_function.function.service_config[0].uri}/"
      service_account_email = google_service_account.account.email
    }
  }
}

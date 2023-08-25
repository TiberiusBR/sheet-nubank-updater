resource "google_secret_manager_secret" "secret-certificate" {
  secret_id = "nu-certificate"

  annotations = {
    default = "true"
  }

  replication {
    automatic = true
  }
}

resource "google_secret_manager_secret_version" "secret-version-basic" {
  secret = google_secret_manager_secret.secret-certificate.id

  secret_data = local.cert_file
  enabled = true
}
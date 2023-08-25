output "function_uri" {
  value = google_cloudfunctions2_function.function.service_config[0].uri
}

output "service_account_email" {
  value = google_service_account.account.email
}
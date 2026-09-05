output "public_ip" {
  value       = google_compute_address.web.address
  description = "Static IP. Create DNS records before enabling automatic HTTPS."
}

output "website_url" {
  value       = "http://${google_compute_address.web.address}"
  description = "Initial HTTP URL. Replace with a domain and HTTPS before production use."
}

output "instance_name" {
  value = google_compute_instance.app.name
}

output "iap_ssh_command" {
  value       = "gcloud compute ssh ${google_compute_instance.app.name} --project ${var.project_id} --zone ${var.zone} --tunnel-through-iap"
  description = "Convenience command when IAP SSH is enabled and caller IAM is configured."
}

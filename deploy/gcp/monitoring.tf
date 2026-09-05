resource "google_monitoring_notification_channel" "email" {
  count        = var.notification_email == "" ? 0 : 1
  display_name = "${var.name} email"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
  depends_on = [google_project_service.required]
}

resource "google_monitoring_uptime_check_config" "http" {
  display_name = "${var.name} HTTP readiness"
  timeout      = "10s"
  period       = "60s"

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = google_compute_address.web.address
    }
  }

  http_check {
    path         = "/readyz"
    port         = 80
    use_ssl      = false
    validate_ssl = false
  }

  content_matchers {
    content = "ready"
    matcher = "CONTAINS_STRING"
  }

  depends_on = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "uptime" {
  display_name = "${var.name}: HTTP unavailable"
  combiner     = "OR"
  enabled      = true

  documentation {
    content   = "The public /readyz endpoint has failed for at least two minutes."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "Uptime check failed"
    condition_threshold {
      filter          = "resource.type = \"uptime_url\" AND metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id = \"${google_monitoring_uptime_check_config.http.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "120s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_NEXT_OLDER"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.notification_email == "" ? [] : [google_monitoring_notification_channel.email[0].name]
  depends_on            = [google_project_service.required]
}

resource "google_monitoring_alert_policy" "cpu" {
  display_name = "${var.name}: sustained CPU saturation"
  combiner     = "OR"
  enabled      = true

  documentation {
    content   = "VM CPU utilization has exceeded 85% for ten minutes. Check queue pressure and running Lean builds."
    mime_type = "text/markdown"
  }

  conditions {
    display_name = "CPU utilization above 85%"
    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"compute.googleapis.com/instance/cpu/utilization\" AND resource.label.instance_id = \"${google_compute_instance.app.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "600s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.notification_email == "" ? [] : [google_monitoring_notification_channel.email[0].name]
  depends_on            = [google_project_service.required]
}

locals {
  labels = merge(
    {
      app        = "lean-report-card"
      managed-by = "terraform"
    },
    var.labels,
  )

  services = toset([
    "compute.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "secretmanager.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_compute_network" "main" {
  name                    = var.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required]
}

resource "google_compute_subnetwork" "main" {
  name          = var.name
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.42.0.0/24"
}

resource "google_compute_firewall" "web" {
  name    = "${var.name}-web"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  allow {
    protocol = "udp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.name}-web"]
}

resource "google_compute_firewall" "iap_ssh" {
  count   = var.enable_iap_ssh ? 1 : 0
  name    = "${var.name}-iap-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["${var.name}-ssh"]
}

resource "google_compute_firewall" "extra_ssh" {
  count   = length(var.ssh_source_ranges) > 0 ? 1 : 0
  name    = "${var.name}-extra-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.ssh_source_ranges
  target_tags   = ["${var.name}-ssh"]
}

resource "google_service_account" "vm" {
  account_id   = substr(replace(var.name, "_", "-"), 0, 30)
  display_name = "Lean Report Card VM"
  depends_on   = [google_project_service.required]
}

resource "google_project_iam_member" "logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_project_iam_member" "monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.vm.email}"
}

resource "random_password" "database" {
  length  = 32
  special = false
}

resource "random_password" "application" {
  length  = 48
  special = false
}

resource "google_secret_manager_secret" "database_password" {
  secret_id = "${var.name}-database-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "database_password" {
  secret      = google_secret_manager_secret.database_password.id
  secret_data = random_password.database.result
}

resource "google_secret_manager_secret" "application_secret" {
  secret_id = "${var.name}-application-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "application_secret" {
  secret      = google_secret_manager_secret.application_secret.id
  secret_data = random_password.application.result
}

resource "google_secret_manager_secret" "github_token" {
  count     = var.github_token == "" ? 0 : 1
  secret_id = "${var.name}-github-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "github_token" {
  count       = var.github_token == "" ? 0 : 1
  secret      = google_secret_manager_secret.github_token[0].id
  secret_data = var.github_token
}

resource "google_secret_manager_secret_iam_member" "database_password" {
  secret_id = google_secret_manager_secret.database_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_secret_manager_secret_iam_member" "application_secret" {
  secret_id = google_secret_manager_secret.application_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_secret_manager_secret_iam_member" "github_token" {
  count     = var.github_token == "" ? 0 : 1
  secret_id = google_secret_manager_secret.github_token[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_compute_address" "web" {
  name       = var.name
  region     = var.region
  depends_on = [google_project_service.required]
}

resource "google_compute_disk" "data" {
  name   = "${var.name}-data"
  type   = "pd-balanced"
  zone   = var.zone
  size   = var.data_disk_size_gb
  labels = local.labels
  depends_on = [
    google_project_service.required,
  ]
}

resource "google_compute_instance" "app" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["${var.name}-web", "${var.name}-ssh"]
  labels       = local.labels

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64"
      size  = var.boot_disk_size_gb
      type  = "pd-balanced"
    }
  }

  attached_disk {
    source      = google_compute_disk.data.id
    device_name = "lrc-data"
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main.id
    access_config {
      nat_ip = google_compute_address.web.address
    }
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    project_id                = var.project_id
    app_repo_url              = var.app_repo_url
    app_git_ref               = var.app_git_ref
    database_secret_name      = google_secret_manager_secret.database_password.secret_id
    application_secret_name   = google_secret_manager_secret.application_secret.secret_id
    github_token_secret_name  = var.github_token == "" ? "" : google_secret_manager_secret.github_token[0].secret_id
    public_ip                 = google_compute_address.web.address
  })

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  depends_on = [
    google_project_iam_member.logging,
    google_project_iam_member.monitoring,
    google_secret_manager_secret_iam_member.database_password,
    google_secret_manager_secret_iam_member.application_secret,
    google_secret_manager_secret_iam_member.github_token,
  ]
}

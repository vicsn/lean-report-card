variable "project_id" {
  description = "Existing GCP project in which to create the service."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "europe-west3"
}

variable "zone" {
  description = "GCP zone."
  type        = string
  default     = "europe-west3-a"
}

variable "name" {
  description = "Resource name prefix."
  type        = string
  default     = "lean-report-card"

  validation {
    condition = (
      length(var.name) <= 30 &&
      can(regex("^[a-z]([-a-z0-9]*[a-z0-9])?$", var.name))
    )
    error_message = "name must be a lowercase GCP-style identifier of at most 30 characters."
  }
}

variable "machine_type" {
  description = "Single VM size. Big Lean repositories can require substantial RAM."
  type        = string
  default     = "e2-standard-8"
}

variable "boot_disk_size_gb" {
  type    = number
  default = 40
}

variable "data_disk_size_gb" {
  description = "Persistent Docker data, Postgres history and Lean caches."
  type        = number
  default     = 250
}

variable "app_repo_url" {
  description = "Public Git URL for this application after you publish the scaffold."
  type        = string

  validation {
    condition = (
      can(regex("^https://[A-Za-z0-9.-]+/[A-Za-z0-9._~+/-]+$", var.app_repo_url)) &&
      !strcontains(var.app_repo_url, "..")
    )
    error_message = "app_repo_url must be a simple public HTTPS Git URL without a query or fragment."
  }
}

variable "app_git_ref" {
  description = "Branch, tag or commit of the application to deploy."
  type        = string
  default     = "main"

  validation {
    condition = (
      can(regex("^[A-Za-z0-9_./@+-]+$", var.app_git_ref)) &&
      !startswith(var.app_git_ref, "-") &&
      !strcontains(var.app_git_ref, "..") &&
      !strcontains(var.app_git_ref, "@{")
    )
    error_message = "app_git_ref must be a branch, tag or SHA containing only safe Git-ref characters."
  }
}

variable "github_token" {
  description = "Optional GitHub token used only for public API rate limits. Stored in Secret Manager."
  type        = string
  sensitive   = true
  default     = ""
}

variable "notification_email" {
  description = "Optional email address for Cloud Monitoring alerts."
  type        = string
  default     = ""
}

variable "enable_iap_ssh" {
  description = "Allow SSH from the Google IAP TCP forwarding range."
  type        = bool
  default     = true
}

variable "ssh_source_ranges" {
  description = "Additional CIDR ranges allowed to connect to SSH. Prefer an empty list plus IAP."
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Extra labels applied to the VM and disk."
  type        = map(string)
  default     = {}
}

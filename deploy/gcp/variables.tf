variable "project_id" {
  description = "Existing GCP project in which to create the service."
  type        = string
}

variable "region" {
  description = "GCP region."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone."
  type        = string
  default     = "us-central1-a"
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
  description = "HTTPS Git URL for this application. Private repositories need github_token so the VM can clone."
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

variable "posthog_project_token" {
  description = "Optional override for the public PostHog project token. Empty keeps the compiled-in default."
  type        = string
  default     = ""
}

variable "posthog_host" {
  description = "PostHog ingest host. Use https://eu.i.posthog.com for EU Cloud."
  type        = string
  default     = "https://eu.i.posthog.com"

  validation {
    condition     = can(regex("^https://[A-Za-z0-9.-]+$", var.posthog_host))
    error_message = "posthog_host must be an https origin without a path, query or fragment."
  }
}

variable "github_token" {
  description = "Optional GitHub token for private-repo clone and public API rate limits. Stored in Secret Manager."
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

# Single-VM GCP deployment

This Terraform configuration creates one Compute Engine VM, one persistent data disk, a static public IP, a small VPC, Secret Manager entries, an HTTP uptime check and CPU/uptime alert policies. The startup script installs Docker and the Google Cloud Ops Agent, clones this application, and starts Docker Compose.

## Prerequisites

1. Create a GCP project with billing enabled.
2. Install and authenticate `gcloud` and Terraform.
3. Push this repository to GitHub. A private clone needs `github_token` in `terraform.tfvars`.
4. Copy `terraform.tfvars.example` to `terraform.tfvars` and edit it.

```sh
gcloud auth application-default login
terraform init
terraform plan
terraform apply
```

Commit the generated `.terraform.lock.hcl` alongside the deployment configuration so provider
selection is reproducible.

The first boot builds both application images and can take several minutes. Inspect startup activity with:

```sh
gcloud compute ssh INSTANCE --zone ZONE --tunnel-through-iap \
  --command 'sudo tail -n 200 /var/log/lean-report-card-startup.log'
```

## Intentional limitations

This is a development-grade, single-machine layout. Postgres, Redis, the web service and both worker classes share one failure domain. The initial site is HTTP by IP. The worker mounts the Docker socket and analyzed projects retain outbound network access because Lake must fetch toolchains and dependencies. These are documented production blockers in `docs/FUTURE_WORK.md`.

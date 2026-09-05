# Future work

## Required production-readiness

- Acquire a domain, configure DNS, and enable HTTPS with an automatically renewed certificate; redirect HTTP and add HSTS only after validation.
- Create the production GCP organization/project, billing, budgets, least-privilege IAM, remote Terraform state, protected deployment identities and audited Secret Manager access.
- Replace Docker-socket execution with isolated ephemeral workers; restrict egress, remove ambient credentials, wipe job disks/caches and establish an abuse-response process.
- Add authentication or anti-abuse controls, quotas, rate limits, queue admission limits, repository allow/deny rules and legal/privacy/data-retention policies.
- Add schema migrations, automated Postgres backups with restore tests, persistent-disk snapshots, disaster recovery, dependency/image pinning and signed release provenance.
- Validate capacity for big jobs, reserve host memory, handle disk exhaustion, add job cancellation/reaping, and verify that a failed worker cannot leave containers behind.
- Configure production alerts and on-call ownership; monitor queue age, failed/timed-out jobs, database health, disk, memory, Docker, cache growth and certificate expiry.

## Optional productionization

- Split the control plane from executors; move PostgreSQL to Cloud SQL, Redis to Memorystore, logs/artifacts to Cloud Storage, and workers to managed instance groups or a batch platform.
- Autoscale small and big workers independently from queue depth and oldest-job age; add more repository size classes and preemptible capacity for retryable work.
- Add OpenTelemetry traces, structured logs, SLOs/error budgets, dashboards, synthetic scans, cost attribution and per-tool performance histories.
- Add CDN/static asset caching, read replicas, report archival/retention tiers, multi-region disaster recovery and blue/green deployment.
- Add GitHub App/webhook integration for commit-triggered scans and private repositories with narrowly scoped, short-lived credentials.

## Adding more known Lean or uLean tools

- Integrate `axiom-audit` JSON output, `#print axioms`, `leanchecker` and independent checking with `nanoda`.
- Integrate `import-graph`, `#redundant_imports`, `#min_imports`, `#find_home`, declaration dependency graphs and stored graph artifacts.
- Match more `lean-action` behavior: Lake target detection, Mathlib cache policy, `mk_all --check`, Reservoir eligibility and toolchain compatibility handling.
- Add Mathlib/Batteries linters, documentation coverage, `doc-gen4`, `lean-fmt`, warning inventories and global `[simp]`/instance/notation audits.
- Add uLean or other project-size, dependency, declaration, proof-term and elaboration-performance analyzers as versioned adapters.
- Test current, pinned and next Lean/Mathlib toolchains; classify syntax, API, instance, simplifier, import and performance regressions separately.

## Features found in Rust report cards or SSL checking services

- Stable public permalinks, embeddable badges, scheduled rescans, score-history charts and side-by-side commit/analyzer diffs.
- A documented public API, downloadable JSON/SARIF, webhooks, GitHub checks, issue/PR annotations and suggested remediation.
- Transparent grading rules, analyzer-version pinning, reproducible result bundles and a public changelog for scoring changes.
- “Why this grade?” explanations, severity-ranked findings, links to exact source locations and one-click retesting after remediation.
- Peer/percentile comparisons by project class, dependency freshness/vulnerability data, maintenance activity and OpenSSF-style repository hygiene.
- A scanner-status page, queue estimates, certificate-expiry-style reminders for stale reports, and historical trust/compatibility timelines.

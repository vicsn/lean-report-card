# Future work

## Hardening local analysis

- Sandbox the analyzer so cloning and building an untrusted repository cannot touch the host: a disposable VM or container per job, restricted egress, no ambient credentials, and a wiped disk afterwards.
- Handle disk exhaustion as deliberately as memory and timeouts are handled today, and verify an interrupted run leaves no orphaned process groups.
- Pin analyzer dependencies and record a reproducible environment alongside each report, so a score can be recomputed years later.

## Returning to automated analysis

- Trigger scans from commits via a GitHub App or webhooks, with narrowly scoped short-lived credentials, rather than a maintainer running a script.
- Restore a queue and result store if scan volume outgrows a single machine, with size classes derived from historical checkout size, dependency closure and prior peak memory.
- Add anti-abuse controls before accepting arbitrary public submissions: quotas, rate limits, admission limits and repository allow/deny rules.
- Add structured logs, dashboards and alerts on failed or timed-out jobs and per-tool performance histories.

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

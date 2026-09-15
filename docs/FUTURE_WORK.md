# Ideas for future work

- Integrate `#print axioms`, `leanchecker` and independent checking with `nanoda`.
- Integrate `#min_imports`, `#find_home`, declaration dependency graphs and stored graph artifacts.
- Match more `lean-action` behavior: Lake target detection, Mathlib cache policy, `mk_all --check`, Reservoir eligibility and toolchain compatibility handling.
- Add the remaining Mathlib/Batteries linters, `doc-gen4`, warning inventories and global instance/notation audits. `simpNF` and `synTaut` are already scored; the rest of the default set needs a `nolints`-style suppression story before it can be graded, since `docBlame` overlaps documentation coverage and `unusedArguments` fires in the hundreds on ordinary Mathlib-style code.
- Speed up the simp/tautology lint pass on projects whose modules are all top-level roots. Each root costs one environment scan, so a flat 1500-module project can exceed its own build time.
- Add uLean or other project-size, dependency, declaration, proof-term and elaboration-performance analyzers as versioned adapters.
- Test current, pinned and next Lean/Mathlib toolchains; classify syntax, API, instance, simplifier, import and performance regressions separately.

## Features found in Rust report cards or SSL checking services

- Stable public permalinks, embeddable badges, scheduled rescans, score-history charts and side-by-side commit/analyzer diffs.
- A documented public API, downloadable JSON/SARIF, webhooks, GitHub checks, issue/PR annotations and suggested remediation.
- Transparent grading rules, analyzer-version pinning, reproducible result bundles and a public changelog for scoring changes.
- “Why this grade?” explanations, severity-ranked findings, links to exact source locations and one-click retesting after remediation.
- Peer/percentile comparisons by project class, dependency freshness/vulnerability data, maintenance activity and OpenSSF-style repository hygiene.
- A scanner-status page, queue estimates, certificate-expiry-style reminders for stale reports, and historical trust/compatibility timelines.

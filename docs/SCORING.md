# Scoring model

The score is a deterministic 0–100 total from fixed mechanical checks on a pinned Git revision. Every report stores the component checks, raw counts and analyzer version. There is no LLM or reviewer judgement in the grade.

| Category | Weight | Rule |
|---|---:|---|
| Build | 25 | 25 if `lake build` exits 0; otherwise 0 |
| Verification | 10 | 10 if the configured `lake test` driver exits 0; 3 if no test driver is configured; 0 if the driver ran and failed |
| Maintainability | 10 | 10 if the configured `lake lint` driver exits 0; 4 if no lint driver is configured; 0 if the driver ran and failed |
| Axiom allowlist | 15 | After a successful build, `axiom-audit --json` inspects the compiled environment. 10 if `sorryAx` is unused (minus one per declaration that uses it, floor 0); 3 if there are no axioms outside the default allowlist (`propext`, `Classical.choice`, `Quot.sound`) plus kernel `sorryAx`/`Lean.ofReduceBool`/`Lean.ofReduceNat`; 2 if `native_decide` axioms are unused. 5 if the audit did not run |
| lean-fmt | 5 | 5 if `lake exe leanfmt`/`lean-fmt --check` exits 0; 2 if no formatter executable is available; 0 if the check ran and failed |
| Redundant imports | 5 | 5 if no project import is transitively implied by another; otherwise 5 minus the redundant import count (floor 0). 2 if analysis did not run |
| Reproducibility | 10 | 5 if `lean-toolchain` is present; 5 if `lake-manifest.json` is present |
| Documentation | 10 | 2 if a README exists; up to 4 from the share of `.lean` files whose first 8 KiB contain `/-!`; up to 4 from the share of declaration lines with `/--` or `/-!` in the 8 lines above. Shares use integer rounding: `(count * maximum + total // 2) // total` |
| Project hygiene | 10 | 2 license, 2 CI workflows, 2 if any path looks like a test file, 1 CONTRIBUTING, 1 SECURITY, 1 CHANGELOG, 1 if `TODO`/`FIXME` count is 0 |
| Build warnings | 5 | 5 if `lake build` passed and the log contains no `warning:` lines; otherwise 0 |

The 0–100 display score is `(raw * 100 + maximum // 2) // maximum`. Grades are A at 90, B at 80, C at 70, D at 60 and F below 60.

Direct import counts are recorded in the raw facts when present. They are not a separate scored category beyond the redundant-import check.

## Interpretation rules

- A failed project build scores 0 for build and for warnings, and skips axiom-audit, lean-fmt and redundant-import analysis.
- `axiom-audit` replaces source-token counts of `sorry`/`admit`/`axiom`/`native_decide` for the grade. Token scans may still appear in raw facts.
- Redundant imports are computed from source import lines (project files plus `.lake/packages` when present), matching the `#redundant_imports` transitivity test.
- Scores should be compared only when the analyzer version is the same. The website retains raw reports so grading changes can be audited.

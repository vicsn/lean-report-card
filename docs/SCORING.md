# Scoring model

The score is a deterministic 0–100 total from fixed mechanical checks on a pinned Git revision. Every report stores the component checks, raw counts, analyzer version and caveat text. There is no LLM or reviewer judgement in the grade.

| Category | Weight | Rule |
|---|---:|---|
| Build | 25 | 25 if `lake build` exits 0; otherwise 0 |
| Verification | 10 | 10 if the configured `lake test` driver exits 0; 3 if no test driver is configured; 0 if the driver ran and failed |
| Maintainability | 10 | 10 if the configured `lake lint` driver exits 0; 4 if no lint driver is configured; 0 if the driver ran and failed |
| Trust signals | 15 | Token counts outside comments and strings: 10 minus one per `sorry` or `admit` (floor 0); 3 minus one per `axiom` declaration (floor 0); 2 if `native_decide` count is 0 else 0 |
| Reproducibility | 10 | 5 if `lean-toolchain` is present; 5 if `lake-manifest.json` is present |
| Documentation | 10 | 2 if a README exists; up to 4 from the share of `.lean` files whose first 8 KiB contain `/-!`; up to 4 from the share of declaration lines with `/--` or `/-!` in the 8 lines above. Shares use integer rounding: `(count * maximum + total // 2) // total` |
| Project hygiene | 10 | 2 license, 2 CI workflows, 2 if any path looks like a test file, 1 CONTRIBUTING, 1 SECURITY, 1 CHANGELOG, 1 if `TODO`/`FIXME` count is 0 |
| Build warnings | 5 | 5 if `lake build` passed and the log contains no `warning:` lines; otherwise 0 |

The 0–100 display score is `(raw * 100 + maximum // 2) // maximum`. Grades are A at 90, B at 80, C at 70, D at 60 and F below 60.

Direct import counts are recorded in the raw facts when present. They are not scored: there is no mechanical rule that maps import fan-out onto project quality.

## Interpretation rules

- A failed project build scores 0 for build and for warnings, but an unconfigured test or lint driver is not treated like a failing driver.
- Source token scans are exact on stripped text. They are not `#print axioms`, `axiom-audit`, Lean kernel checking or an independent checker.
- Scores should be compared only when the analyzer version is the same. The website retains raw reports so grading changes can be audited.

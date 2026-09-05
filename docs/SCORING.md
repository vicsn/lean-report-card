# Initial scoring model

The score is an explained heuristic from 0 to 100. Every report contains the component checks, raw measurements, analyzer version and caveat text.

| Category | Weight | Initial evidence |
|---|---:|---|
| Build | 25 | `lake build` result |
| Verification | 10 | configured `lake test` result; partial credit when unavailable |
| Maintainability | 10 | configured `lake lint` result; partial credit when unavailable |
| Trust signals | 15 | source-level `sorry`, `admit`, `axiom` and `native_decide` scan |
| Reproducibility | 10 | `lean-toolchain` and `lake-manifest.json` |
| Documentation | 10 | README, module-doc and declaration-doc estimates |
| Architecture | 5 | direct import footprint |
| Project hygiene | 10 | license, CI, tests, contributing/security/changelog files, TODO count |
| Diagnostics | 5 | build warnings, bounded logs and toolchain installation |

Grades are A at 90, B at 80, C at 70, D at 60 and F below 60.

## Interpretation rules

- A failed project build is a strong negative signal, but an unavailable test or lint driver is not treated like a failing driver.
- Source scans are approximate. They cannot replace `#print axioms`, `axiom-audit`, Lean kernel checking or an independent checker.
- Direct import count is not universally “lower is better”; foundational and façade modules have different roles.
- Scores should be compared only when the analyzer version is the same. The website retains raw reports so grading changes can be audited.
- A future model should expose separate build, trust, maintainability, compatibility, documentation and repository-security grades rather than overemphasize one total.

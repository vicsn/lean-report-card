# Third-party integration candidates

No third-party source is copied into the application package. The Git submodules retain their own licenses and notices.

| Project | Pinned revision | Intended use |
|---|---|---|
| `leanprover/lean-action` | `96e06131c0e9943c780388fd166f55d1e2fa0433` | standard Lean CI orchestration reference and reusable scripts |
| `leanprover-community/axiom-audit` | `46024e005996495c65ef609368e11ab39c4222e3` | compiled-environment axiom allowlist report |
| `leanprover-community/import-graph` | `d8823026ac7ef130c253089d95685f9877b95323` | import/dependency analysis and graph artifacts |
| `leanprover/reservoir` | `e097550bb4dcc37284e4e4e6cf9b683b0aeace1e` | package discovery, build compatibility and presentation reference |

Review every submodule update before deployment. Re-check license compatibility when code is copied, linked, packaged or modified rather than invoked as an external tool.

# Lean tooling submodules

Run `make tooling` after cloning this repository to initialize these pinned Git submodules:

- `lean-action`: reference implementation for standard Lean build, test, lint, cache, checker and axiom-audit orchestration.
- `axiom-audit`: candidate adapter for kernel-environment axiom allowlist checks.
- `import-graph`: candidate adapter for source/import graph and redundant-import analysis.
- `reservoir`: reference implementation for package discovery, build compatibility and report presentation.

The initial runner does not execute code directly from these submodules. This keeps the base image buildable before submodules are initialized and makes compatibility failures explicit. See `docs/TOOLING_INTEGRATION.md` for the planned adapter boundary and licensing notes.

# Lean tooling integration

The repository pins four upstreams as Git submodules. Run `make tooling` to initialize their exact recorded revisions; updating a gitlink should be a reviewed dependency change.

## `lean-action`

Use its scripts and behavior as the compatibility reference for automatic Lake build/test/lint detection, Mathlib cache use, Reservoir eligibility, leanchecker, nanoda and axiom-audit orchestration. The initial runner mirrors only the basic build, optional cache, test and lint sequence.

## `axiom-audit`

Add an adapter that builds the tool with the target repository's own Lean toolchain and runs `--json` against compiled `.olean` files. The current analyzer does this after a successful `lake build` and scores `sorryAx`, `native_decide`, and home-rolled axioms from that report. Source-token scans remain in the raw facts only.

## `import-graph`

Add source-level and compiled-environment adapters for direct/transitive imports, redundant imports, minimal-import suggestions and visual graph artifacts. The current direct-import metric is a text approximation and should be replaced or annotated when the real tool is available.

## `reservoir`

Reuse package discovery and build-compatibility concepts, and investigate reusing testbed scripts where their interfaces and license permit. Reservoir is also a natural source for known package metadata and newer-toolchain compatibility results.

## Adapter contract

Each adapter should declare:

- supported Lean/tool versions;
- installation/build strategy and pinned upstream commit;
- resource class and timeout;
- whether it mutates the target checkout;
- structured result schema and confidence;
- license and attribution;
- failure semantics: failed, unsupported, unavailable or skipped.

Do not silently turn adapter incompatibility into a repository failure. Report it as a tool capability result.

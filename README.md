# Lean Report Card

A static website that publishes a public index of Lean 4 project scores. Analyses run locally and write one JSON report per repository; the site is hosted on Cloudflare Workers.

The score comes from fixed mechanical checks on a pinned Git revision. It is not a proof of mathematical correctness or security.

## How a repository is analysed

`runner/analyze.py` works on a single checkout and never reaches back into the site. For each repository it:

1. clones the public repository at a resolved commit and initialises submodules;
2. installs the pinned `lean-toolchain` with Elan;
3. retrieves the Mathlib cache when the manifest looks like it needs one;
4. runs `lake build`, then `lake test` and `lake lint` when those drivers are configured;
5. scans sources with comments and strings stripped, counting Lean files, documentation comments, tests, `sorry`, `admit`, `axiom`, `native_decide`, TODOs and common project files;
6. emits versioned JSON with bounded logs, durations and an explained score.

The score is a deterministic 0–100 total over weighted categories: build (25), trust signals (15), verification, maintainability, reproducibility, documentation and project hygiene (10 each), and build warnings (5). Token scans are exact on stripped text but remain approximations — they are not `#print axioms` or Lean kernel checking. Scores are only comparable within the same analyzer version. The exact rules are in [`docs/SCORING.md`](docs/SCORING.md).

## Hosting

The site is a Cloudflare Worker with [static assets](https://developers.cloudflare.com/workers/static-assets/). Files under `site/` are served without invoking code; anything else falls through to `worker/index.js`, which owns `/api/*` and hands unknown paths back to the asset handler. Pages therefore live at `/about` rather than `/about.html`, and the old `.html` URLs answer with a 307.

The score and contact forms post JSON to `/api/score` and `/api/contact`. Each handler validates the fields and emails the submission through the `SEND_EMAIL` binding (Cloudflare Email Service). There is no analytics or tracking code, and no API token: the binding authenticates implicitly. Two addresses configure delivery, `FORM_FROM` in `wrangler.toml` and `FORM_TO` as a Worker secret. On the Workers Free plan `FORM_TO` must be an address verified under Email Routing, since sends to a verified destination in your own account are free and quota-exempt.

## Run locally

Score repositories from the Palomar registry, writing `site/reports/{owner}/{name}.json`, a badge under `site/badge/`, and an updated `site/reports/index.json`:

```sh
make score              # add --limit N to process only a few
make rescore            # recompute scores for existing JSON, no cloning
```

Analyses run as a local subprocess and need `elan` and `lake` on `PATH`. Preview the site and exercise the form endpoints:

```sh
make site               # static files only; /api/* returns 404
npx wrangler dev        # serves assets and /api/*, simulating email delivery
```

## Lean tooling submodules

The repository pins integration candidates — `lean-action`, `axiom-audit`, `import-graph` and `reservoir` — as Git submodules. Run `make tooling` in a networked checkout to initialise them. The analyzer intentionally does not require them; see [`docs/TOOLING_INTEGRATION.md`](docs/TOOLING_INTEGRATION.md).

## Development

```sh
pip install -e '.[dev]'
ruff check .
pytest
```

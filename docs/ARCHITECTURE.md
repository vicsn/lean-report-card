# Architecture

## Request lifecycle

1. The API accepts only a public GitHub repository URL or `owner/name` shorthand.
2. It resolves repository metadata and an exact 40-character commit SHA using the GitHub API, with `git ls-remote` as a rate-limit fallback.
3. The repository row is inserted or refreshed.
4. Unless forced, the service returns the newest queued, running or successful report for the same repository, commit and analyzer version.
5. A new report is assigned to `small` or `big` and sent to the matching Celery queue.
6. The worker starts a disposable analyzer container and records a terminal report state.
7. The website and API read only persisted report data; clients do not need a Celery result backend contract.

## Queue classification

`auto` selects the big queue when either condition holds:

- GitHub reports `size >= LRC_BIG_REPO_THRESHOLD_KIB`;
- the lowercase `owner/name` appears in `LRC_KNOWN_BIG_REPOS`.

An API caller can explicitly request either queue. This is intentionally simple. Future classification should use historical checkout size, dependency closure, prior peak memory and elapsed time.

## Persistence

`repositories` stores canonical identity and the latest observed metadata. `reports` stores every requested analysis run, including commit, analyzer version, queue, status, score, summary, raw JSON, timings and errors. There is an index for cache lookup and another for repository history.

A report is immutable in meaning but changes state from queued to running to a terminal status. A forced rescan creates a separate row, preserving historical results for the same commit.

## Failure domains

The basic deployment intentionally puts Caddy, FastAPI, Redis, PostgreSQL and both workers on one VM. The attached persistent disk holds Docker data, including database volumes and Lean caches. This simplifies deployment but does not provide high availability or independent scaling.

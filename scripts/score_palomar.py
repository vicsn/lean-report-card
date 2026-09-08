#!/usr/bin/env python3
"""Score Palomar registry source projects and write site/reports JSON."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lean_report_card.badge import write_badges  # noqa: E402
from lean_report_card.scoring import CAVEAT, score_report  # noqa: E402

ANALYZER = ROOT / "runner" / "analyze.py"
PALOMAR_RECENT = "https://data.palomar-registry.org/recent.json"
ANALYZER_VERSION = "0.2.0"


class DiskFull(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def disk_free_bytes(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free


def require_disk(path: Path, minimum_bytes: int) -> int:
    free = disk_free_bytes(path)
    if free < minimum_bytes:
        raise DiskFull(
            f"Only {free / 1024**3:.1f} GiB free on {path}; stopping before the next analysis."
        )
    return free


def process_table() -> tuple[dict[int, list[int]], dict[int, int]]:
    try:
        completed = subprocess.run(
            ["ps", "-ax", "-o", "pid=,ppid=,rss="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {}, {}
    children: dict[int, list[int]] = defaultdict(list)
    rss: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            pid, ppid, rss_kb = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        children[ppid].append(pid)
        rss[pid] = rss_kb * 1024
    return children, rss


def descendant_pids(root_pid: int, children: dict[int, list[int]] | None = None) -> list[int]:
    if children is None:
        children, _ = process_table()
    found: list[int] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        found.append(pid)
        stack.extend(children.get(pid, []))
    return found


def process_tree_rss_bytes(root_pid: int) -> int:
    children, rss = process_table()
    return sum(rss.get(pid, 0) for pid in descendant_pids(root_pid, children))


def kill_process_tree(root_pid: int) -> None:
    for pid in reversed(descendant_pids(root_pid)):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    try:
        os.killpg(root_pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        return


def compact_command(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    output = str(result.get("output") or "")
    keep_output = result.get("status") not in {"passed", "unavailable", "skipped"}
    compact = {
        key: value
        for key, value in result.items()
        if key != "output"
    }
    if keep_output and output:
        compact["output_tail"] = output[-2000:]
    return compact


def compact_facts(facts: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(facts, dict):
        return {}
    commands = facts.get("commands") or {}
    return {
        "files": facts.get("files") or {},
        "static": facts.get("static") or {},
        "commands": {
            name: compact_command(value) if isinstance(value, dict) else value
            for name, value in commands.items()
        },
        "toolchain_install": compact_command(facts.get("toolchain_install") or {}),
        "mathlib_cache": compact_command(facts.get("mathlib_cache") or {}),
        "logs_truncated": facts.get("logs_truncated"),
    }


def index_summary(report: dict[str, Any]) -> str:
    status = report.get("status")
    if status == "oom_killed":
        return "Analyzer ran out of memory"
    if status != "succeeded":
        error = str(report.get("error") or "Analysis failed")
        return error.split("\n", 1)[0][:160]
    checks = {item.get("id"): item for item in report.get("checks") or [] if isinstance(item, dict)}
    bits: list[str] = []
    build = checks.get("build") or {}
    bits.append("Builds" if build.get("status") == "passed" else "Build did not pass")
    trust = checks.get("source-trust-signals") or {}
    details = trust.get("details") or {}
    if int(details.get("sorry_count") or 0) or int(details.get("admit_count") or 0):
        bits.append("sorry/admit in source")
    elif int(details.get("axiom_declaration_count") or 0):
        bits.append("axiom declarations")
    repro = checks.get("reproducibility") or {}
    if repro.get("status") == "passed":
        bits.append("pinned toolchain")
    hygiene = checks.get("project-hygiene") or {}
    if hygiene.get("status") != "passed":
        bits.append("sparse hygiene")
    return " · ".join(bits[:3])


def site_slug(owner: str, name: str, project_path: str) -> str:
    if project_path:
        return f"{owner}/{name}/{project_path}"
    return f"{owner}/{name}"


def site_file(owner: str, name: str, project_path: str) -> str:
    if not project_path:
        return f"{owner}/{name}.json"
    safe = project_path.replace("/", "__").replace("\\", "__")
    return f"{owner}/{name}__{safe}.json"


def archive_url(entry: dict[str, Any], repository: str) -> str | None:
    for item in (entry.get("preservation") or {}).get("repositories") or []:
        if item.get("source_repository") == repository and item.get("fork_repository"):
            return f"https://github.com/{item['fork_repository']}.git"
    return None


def jobs_from_catalog(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        source = entry.get("source") or {}
        repository = str(source.get("repository") or "")
        if "/" not in repository:
            continue
        project_path = str(source.get("project_path") or "").strip()
        grouped[(repository, project_path)].append(entry)

    jobs: list[dict[str, Any]] = []
    for (repository, project_path), items in grouped.items():
        items.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
        latest = items[0]
        source = latest.get("source") or {}
        owner, name = repository.split("/", 1)
        jobs.append(
            {
                "owner": owner,
                "name": name,
                "repository": repository,
                "project_path": project_path,
                "commit": source.get("commit"),
                "url": f"https://github.com/{repository}",
                "clone_url": f"https://github.com/{repository}.git",
                "archive_url": archive_url(latest, repository),
                "slug": site_slug(owner, name, project_path),
                "file": site_file(owner, name, project_path),
                "palomar_ids": [str(item.get("id")) for item in items if item.get("id")],
                "title": latest.get("title"),
                "published_at": latest.get("published_at"),
            }
        )
    jobs.sort(key=lambda item: item["slug"].lower())
    return jobs


def fetch_catalog(cache_path: Path) -> dict[str, Any]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        PALOMAR_RECENT,
        headers={"User-Agent": "lean-report-card-palomar-score/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS registry URL
        payload = json.load(response)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def load_progress(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"completed": {}, "stopped_reason": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(progress, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def rewrite_index(site_reports: Path, reports: list[dict[str, Any]]) -> None:
    ordered = sorted(
        reports,
        key=lambda item: (
            item.get("score") is None,
            -(item.get("score") or 0),
            str(item.get("slug") or "").lower(),
        ),
    )
    entries = [
        {
            "slug": item["slug"],
            "file": item["file"],
            "grade": item.get("grade"),
            "score": item.get("score"),
            "status": item.get("status"),
            "updated_at": item.get("analyzed_at") or item.get("updated_at"),
            "summary": item.get("summary"),
            "url": item.get("url"),
        }
        for item in ordered
    ]
    write_json(
        site_reports / "index.json",
        {
            "schema_version": 1,
            "generated": utcnow(),
            "source": "palomar-registry",
            "reports": entries,
        },
    )
    write_badges(site_reports.parent / "badge", entries)


def stub_report(
    job: dict[str, Any], *, status: str, error: str, analyzed_at: str
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "slug": job["slug"],
        "repository": {
            "url": job["url"],
            "owner": job["owner"],
            "name": job["name"],
            "commit_sha": job["commit"],
            "project_path": job["project_path"] or None,
        },
        "status": status,
        "analyzer_version": ANALYZER_VERSION,
        "analyzed_at": analyzed_at,
        "score": None,
        "grade": None,
        "checks": [],
        "caveat": CAVEAT,
        "facts": {},
        "error": error,
        "palomar": {
            "ids": job["palomar_ids"],
            "title": job["title"],
            "published_at": job["published_at"],
        },
    }


def to_site_report(
    job: dict[str, Any], payload: dict[str, Any], analyzed_at: str
) -> dict[str, Any]:
    scoring = payload.get("scoring") if isinstance(payload.get("scoring"), dict) else {}
    analysis_status = str(payload.get("analysis_status") or "failed")
    if analysis_status == "oom_killed":
        status = "oom_killed"
    elif analysis_status == "completed":
        status = "succeeded"
    else:
        status = "failed"
    repo = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    return {
        "schema_version": 1,
        "slug": job["slug"],
        "repository": {
            "url": job["url"],
            "owner": job["owner"],
            "name": job["name"],
            "commit_sha": repo.get("commit_sha") or job["commit"],
            "project_path": job["project_path"] or None,
        },
        "status": status,
        "analyzer_version": payload.get("analyzer_version") or ANALYZER_VERSION,
        "analyzed_at": analyzed_at,
        "score": scoring.get("score"),
        "grade": scoring.get("grade"),
        "checks": scoring.get("checks") or [],
        "caveat": scoring.get("caveat") or CAVEAT,
        "facts": compact_facts(
            payload.get("facts") if isinstance(payload.get("facts"), dict) else {}
        ),
        "error": payload.get("error"),
        "palomar": {
            "ids": job["palomar_ids"],
            "title": job["title"],
            "published_at": job["published_at"],
        },
    }


def run_analyzer(
    job: dict[str, Any],
    *,
    clone_url: str,
    workspace: Path,
    output: Path,
    memory_limit_bytes: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any] | None, str | None]:
    env = os.environ.copy()
    elan_bin = Path.home() / ".elan" / "bin"
    env["PATH"] = f"{elan_bin}{os.pathsep}{env.get('PATH', '')}"
    env.update(
        {
            "REPO_URL": clone_url,
            "GIT_SHA": str(job["commit"]),
            "ANALYZE_WORKSPACE": str(workspace),
            "ANALYZE_OUTPUT": str(output),
            "ANALYZE_PROJECT_PATH": job["project_path"],
            "PROFILE": "big",
            "ANALYZER_VERSION": ANALYZER_VERSION,
            "LEAN_NUM_THREADS": "2",
            "PYTHONPATH": str(ROOT),
            "GIT_TERMINAL_PROMPT": "0",
            "CI": "true",
        }
    )
    workspace.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(".log")
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(  # noqa: S603 - analyzer entrypoint
            [sys.executable, str(ANALYZER)],
            cwd=str(ROOT),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pgid = process.pid
        deadline = time.monotonic() + timeout_seconds
        oom = False
        timed_out = False
        while process.poll() is None:
            if time.monotonic() > deadline:
                timed_out = True
                kill_process_tree(pgid)
                break
            if process_tree_rss_bytes(pgid) > memory_limit_bytes:
                oom = True
                kill_process_tree(pgid)
                break
            time.sleep(2.0)
        process.wait()
    returncode = process.returncode
    log_tail = ""
    if log_path.is_file():
        log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    if oom or returncode in {137, -9, 9}:
        return None, "oom"
    if timed_out:
        return None, "timeout"
    if output.is_file():
        payload = json.loads(output.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            if payload.get("analysis_status") == "oom_killed":
                return payload, "oom"
            return payload, None
    return None, f"Analyzer exited {returncode}. {log_tail}".strip()


def analyze_job(
    job: dict[str, Any],
    *,
    workspace: Path,
    raw_dir: Path,
    memory_limit_bytes: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    analyzed_at = utcnow()
    raw_output = raw_dir / f"{job['file']}"
    shutil.rmtree(workspace, ignore_errors=True)
    try:
        payload, failure = run_analyzer(
            job,
            clone_url=job["clone_url"],
            workspace=workspace,
            output=raw_output,
            memory_limit_bytes=memory_limit_bytes,
            timeout_seconds=timeout_seconds,
        )
        clone_failed = (
            failure is None
            and payload is not None
            and payload.get("error") == "Repository clone failed."
        )
        if clone_failed and job.get("archive_url"):
            shutil.rmtree(workspace, ignore_errors=True)
            payload, failure = run_analyzer(
                job,
                clone_url=job["archive_url"],
                workspace=workspace,
                output=raw_output,
                memory_limit_bytes=memory_limit_bytes,
                timeout_seconds=timeout_seconds,
            )
        if failure == "oom":
            report = stub_report(
                job,
                status="oom_killed",
                error="Analyzer exceeded the memory budget and was stopped.",
                analyzed_at=analyzed_at,
            )
            if payload:
                report = to_site_report(job, payload, analyzed_at)
                report["status"] = "oom_killed"
            return report
        if failure == "timeout":
            return stub_report(
                job,
                status="timed_out",
                error="Analyzer exceeded the time budget.",
                analyzed_at=analyzed_at,
            )
        if payload is None:
            return stub_report(
                job,
                status="failed",
                error=str(failure or "Analyzer produced no report."),
                analyzed_at=analyzed_at,
            )
        return to_site_report(job, payload, analyzed_at)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def apply_mechanical_score(report: dict[str, Any]) -> dict[str, Any]:
    facts = report.get("facts")
    if isinstance(facts, dict) and facts:
        scoring = score_report(facts)
        report["score"] = scoring["score"]
        report["grade"] = scoring["grade"]
        report["checks"] = scoring["checks"]
        report["caveat"] = scoring["caveat"]
        report["analyzer_version"] = ANALYZER_VERSION
    report["summary"] = index_summary(report)
    return report


def rescore_existing_reports(site_reports: Path) -> int:
    index_path = site_reports / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {}
    updated: list[dict[str, Any]] = []
    scored = 0
    indexed_files: set[Path] = set()
    for entry in index.get("reports") or []:
        rel = entry.get("file")
        if not rel:
            updated.append(entry)
            continue
        path = site_reports / str(rel)
        indexed_files.add(path.resolve())
        if not path.is_file():
            updated.append(entry)
            continue
        report = apply_mechanical_score(json.loads(path.read_text(encoding="utf-8")))
        write_json(path, report)
        scored += 1
        updated.append(
            {
                **entry,
                "grade": report.get("grade"),
                "score": report.get("score"),
                "status": report.get("status"),
                "summary": report.get("summary"),
                "analyzed_at": report.get("analyzed_at") or entry.get("updated_at"),
            }
        )
    for path in site_reports.rglob("*.json"):
        if path.name == "index.json" or path.resolve() in indexed_files:
            continue
        report = apply_mechanical_score(json.loads(path.read_text(encoding="utf-8")))
        write_json(path, report)
        scored += 1
    rewrite_index(site_reports, updated)
    return scored


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=ROOT / "site")
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".data" / "palomar-score")
    parser.add_argument("--min-free-gib", type=float, default=20.0)
    parser.add_argument("--memory-limit-gib", type=float, default=16.0)
    parser.add_argument("--timeout-seconds", type=int, default=7800)
    parser.add_argument("--limit", type=int, default=0, help="Process at most N remaining jobs.")
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument(
        "--rescore-existing",
        action="store_true",
        help="Recompute scores for JSON already under site/reports and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir: Path = args.data_dir
    site_reports = args.site_dir / "reports"
    if args.rescore_existing:
        count = rescore_existing_reports(site_reports)
        print(f"Rescored {count} reports under {site_reports}.", flush=True)
        return 0
    catalog_path = data_dir / "recent.json"
    progress_path = data_dir / "progress.json"
    workspace = data_dir / "workspace"
    raw_dir = data_dir / "raw"
    min_free = int(args.min_free_gib * 1024**3)
    memory_limit = int(args.memory_limit_gib * 1024**3)

    if args.refresh_catalog or not catalog_path.is_file():
        catalog = fetch_catalog(catalog_path)
    else:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    jobs = jobs_from_catalog(list(catalog.get("entries") or []))
    progress = load_progress(progress_path)
    completed: dict[str, Any] = dict(progress.get("completed") or {})

    remaining = [job for job in jobs if job["slug"] not in completed]
    if args.limit:
        remaining = remaining[: args.limit]

    print(
        f"{len(jobs)} Palomar source projects, {len(completed)} already scored, "
        f"{len(remaining)} queued. Disk stop below {args.min_free_gib:g} GiB free; "
        f"OOM mark above {args.memory_limit_gib:g} GiB RSS.",
        flush=True,
    )

    try:
        require_disk(site_reports, min_free)
        for index, job in enumerate(remaining, start=1):
            free = require_disk(site_reports, min_free)
            print(
                f"[{index}/{len(remaining)}] {job['slug']} "
                f"@ {str(job['commit'])[:12]} ({free / 1024**3:.1f} GiB free)",
                flush=True,
            )
            started = time.monotonic()
            report = analyze_job(
                job,
                workspace=workspace,
                raw_dir=raw_dir,
                memory_limit_bytes=memory_limit,
                timeout_seconds=args.timeout_seconds,
            )
            report["summary"] = index_summary(report)
            write_json(site_reports / job["file"], report)
            completed[job["slug"]] = {
                "file": job["file"],
                "status": report["status"],
                "score": report.get("score"),
                "grade": report.get("grade"),
                "analyzed_at": report.get("analyzed_at"),
                "summary": report["summary"],
                "url": job["url"],
                "slug": job["slug"],
            }
            progress["completed"] = completed
            progress["updated_at"] = utcnow()
            save_progress(progress_path, progress)
            rewrite_index(site_reports, list(completed.values()))
            elapsed = int(time.monotonic() - started)
            print(
                f"    {report['status']} {report.get('grade') or '—'} "
                f"{report.get('score') if report.get('score') is not None else '—'} "
                f"in {elapsed}s",
                flush=True,
            )
    except DiskFull as exc:
        progress["stopped_reason"] = str(exc)
        progress["updated_at"] = utcnow()
        save_progress(progress_path, progress)
        print(f"STOPPED: {exc}", flush=True)
        return 2

    progress["stopped_reason"] = None
    progress["updated_at"] = utcnow()
    save_progress(progress_path, progress)
    oom_slugs = [
        slug for slug, item in completed.items() if item.get("status") == "oom_killed"
    ]
    print(
        f"Done. {len(completed)}/{len(jobs)} scored. "
        f"OOM: {len(oom_slugs)}{(' — ' + ', '.join(oom_slugs)) if oom_slugs else ''}.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

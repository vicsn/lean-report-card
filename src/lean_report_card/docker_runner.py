from __future__ import annotations

import io
import json
import tarfile
import uuid
from dataclasses import dataclass
from typing import Any

import docker
import requests
from docker.errors import APIError, ImageNotFound

from lean_report_card.config import Settings
from lean_report_card.models import Report


class RunnerError(RuntimeError):
    pass


class RunnerTimedOut(RunnerError):
    pass


class RunnerOOMError(RunnerError):
    pass


_MEMORY_SUFFIXES = {
    "": 1,
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "ki": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mi": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gi": 1024**3,
    "gib": 1024**3,
}


def memory_to_bytes(value: str) -> int:
    text = value.strip().lower().replace(" ", "")
    suffix = ""
    number = text
    for candidate in sorted(_MEMORY_SUFFIXES, key=len, reverse=True):
        if candidate and text.endswith(candidate):
            suffix = candidate
            number = text[: -len(candidate)]
            break
    amount = float(number)
    if amount <= 0:
        raise ValueError(f"Memory budget must be positive, got {value!r}.")
    return int(amount * _MEMORY_SUFFIXES[suffix])


def container_was_oom_killed(container: Any, status_code: int) -> bool:
    try:
        container.reload()
        state = container.attrs.get("State") or {}
    except Exception:  # noqa: BLE001 - inspection is best-effort after the wait
        state = {}
    return bool(state.get("OOMKilled")) or status_code == 137


@dataclass(frozen=True)
class RunnerBudget:
    timeout_seconds: int
    memory: str
    cpus: float
    lean_threads: int


def budget_for(queue_name: str, settings: Settings) -> RunnerBudget:
    if queue_name == "big":
        return RunnerBudget(
            timeout_seconds=settings.big_timeout_seconds,
            memory=settings.big_memory,
            cpus=settings.big_cpus,
            lean_threads=settings.big_lean_threads,
        )
    return RunnerBudget(
        timeout_seconds=settings.small_timeout_seconds,
        memory=settings.small_memory,
        cpus=settings.small_cpus,
        lean_threads=settings.small_lean_threads,
    )


def _read_json_from_container(container: Any, path: str) -> dict[str, Any]:
    stream, _ = container.get_archive(path)
    archive_bytes = b"".join(stream)
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as archive:
        member = next((item for item in archive.getmembers() if item.isfile()), None)
        if member is None:
            raise RunnerError("The analyzer produced an empty report archive.")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RunnerError("The analyzer report could not be extracted.")
        payload = json.load(extracted)
    if not isinstance(payload, dict):
        raise RunnerError("The analyzer report is not a JSON object.")
    return payload


def _mock_report(report: Report) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "analysis_status": "completed",
        "repository": {
            "url": report.repository.canonical_url,
            "commit_sha": report.commit_sha,
        },
        "facts": {
            "commands": {
                "build": {"status": "passed", "duration_seconds": 4, "warning_count": 0},
                "test": {"status": "unavailable"},
                "lint": {"status": "unavailable"},
            },
            "files": {
                "lean_toolchain": "mock-toolchain",
                "lake_manifest": True,
                "readme": True,
                "license": True,
                "ci": False,
                "contributing": False,
                "security": False,
                "changelog": False,
            },
            "static": {
                "lean_file_count": 1,
                "line_count": 20,
                "sorry_count": 0,
                "admit_count": 0,
                "axiom_declaration_count": 0,
                "native_decide_count": 0,
                "module_doc_ratio": 1.0,
                "declaration_doc_ratio": 0.5,
                "average_direct_imports": 1.0,
                "max_direct_imports": 1,
                "test_file_count": 0,
                "todo_count": 0,
            },
            "toolchain_install": {"status": "passed"},
            "logs_truncated": False,
        },
    }


def run_analysis_container(report: Report, settings: Settings) -> dict[str, Any]:
    if settings.runner_mode == "mock":
        return _mock_report(report)

    budget = budget_for(report.queue_name, settings)
    client = docker.from_env()
    try:
        client.images.get(settings.runner_image)
    except ImageNotFound as exc:
        raise RunnerError(
            f"Runner image {settings.runner_image!r} is missing; build runner/Dockerfile first."
        ) from exc

    container_name = f"lrc-{report.queue_name}-{str(report.id)[:12]}-{uuid.uuid4().hex[:8]}"
    container = None
    try:
        container = client.containers.run(
            settings.runner_image,
            name=container_name,
            detach=True,
            environment={
                "REPO_URL": report.repository.canonical_url,
                "GIT_SHA": report.commit_sha,
                "PROFILE": report.queue_name,
                "LEAN_NUM_THREADS": str(budget.lean_threads),
                "ANALYZER_VERSION": settings.analyzer_version,
                "MAX_LOG_BYTES": str(settings.max_log_bytes),
            },
            network_mode=settings.runner_network_mode,
            mem_limit=budget.memory,
            memswap_limit=memory_to_bytes(budget.memory),
            mem_swappiness=0,
            oom_kill_disable=False,
            oom_score_adj=800,
            nano_cpus=int(budget.cpus * 1_000_000_000),
            pids_limit=2048 if report.queue_name == "big" else 1024,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            volumes={
                settings.elan_cache_volume: {"bind": "/root/.elan", "mode": "rw"},
                settings.lake_cache_volume: {"bind": "/root/.cache", "mode": "rw"},
            },
            labels={
                "app": "lean-report-card",
                "report_id": str(report.id),
                "queue": report.queue_name,
            },
        )
        try:
            result = container.wait(timeout=budget.timeout_seconds + 30)
        except requests.exceptions.ReadTimeout as exc:
            container.kill()
            raise RunnerTimedOut(
                f"Analysis exceeded the {budget.timeout_seconds}-second {report.queue_name} budget."
            ) from exc

        status_code = int(result.get("StatusCode", 1))
        logs = container.logs(stdout=True, stderr=True, tail=5000).decode(
            "utf-8", errors="replace"
        )
        if container_was_oom_killed(container, status_code):
            raise RunnerOOMError(
                f"Analyzer exceeded the {budget.memory} {report.queue_name} memory budget "
                "and was stopped before it could take down the host."
            )
        if status_code != 0:
            raise RunnerError(
                f"Analyzer container exited with {status_code}.\n{logs[-settings.max_log_bytes:]}"
            )
        payload = _read_json_from_container(container, "/output/report.json")
        payload.setdefault("runner", {})
        payload["runner"].update(
            {
                "queue": report.queue_name,
                "timeout_seconds": budget.timeout_seconds,
                "memory": budget.memory,
                "cpus": budget.cpus,
                "lean_threads": budget.lean_threads,
            }
        )
        return payload
    except APIError as exc:
        raise RunnerError(f"Docker API error: {exc}") from exc
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except APIError:
                pass

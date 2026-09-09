"""Post-build mechanical checks: axiom-audit, lean-fmt, redundant imports."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

RUNNER_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUNNER_DIR.parent
AXIOM_AUDIT_REF = "v0.1.2"
AXIOM_AUDIT_SHA = "46024e005996495c65ef609368e11ab39c4222e3"
AXIOM_AUDIT_URL = "https://github.com/leanprover-community/axiom-audit.git"
DEFAULT_ALLOWED = {"propext", "Classical.choice", "Quot.sound"}
KERNEL_AXIOMS = {"sorryAx", "Lean.ofReduceBool", "Lean.ofReduceNat"}
IMPORT_LINE = re.compile(r"^\s*(?:(?:public|private|meta)\s+)*import(?:\s+all)?\s+(.+)$")
EXCLUDED = {".git", "build", "dist", "node_modules", "third_party", "vendor"}

RunCommand = Callable[..., dict[str, Any]]
Unavailable = Callable[[list[str], str], dict[str, Any]]


def last_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    start = text.rfind("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def parse_import_modules(line: str) -> list[str]:
    match = IMPORT_LINE.match(line)
    if not match:
        return []
    body = match.group(1).split("--", 1)[0]
    return [item for item in body.split() if item and item != "Init"]


def module_name_for(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    return ".".join(relative.parts)


def lean_files_under(root: Path) -> list[Path]:
    output: list[Path] = []
    for path in root.rglob("*.lean"):
        if any(part in EXCLUDED or part == ".lake" for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            output.append(path)
    return output


def parse_file_imports(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    found: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if stripped.startswith("/-"):
            continue
        modules = parse_import_modules(line)
        if modules:
            found.extend(modules)
            continue
        if (
            stripped.startswith("import")
            or stripped.startswith("public")
            or stripped.startswith("private")
        ):
            continue
        if stripped.startswith("module"):
            continue
        break
    return found


def import_graph(project_root: Path) -> dict[str, list[str]]:
    roots = [project_root]
    packages = project_root / ".lake" / "packages"
    if packages.is_dir():
        roots.extend(path for path in packages.iterdir() if path.is_dir())
    graph: dict[str, list[str]] = {}
    for root in roots:
        for path in lean_files_under(root):
            name = module_name_for(root, path)
            graph[name] = parse_file_imports(path)
    return graph


def redundant_in_file(direct: list[str], graph: dict[str, list[str]]) -> list[str]:
    targets = set(direct)
    found: set[str] = set()
    for imported in direct:
        stack = list(graph.get(imported, []))
        seen: set[str] = set()
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            if name in targets:
                found.add(name)
            stack.extend(graph.get(name, []))
    return sorted(found)


def find_redundant_imports(project_root: Path) -> dict[str, Any]:
    graph = import_graph(project_root)
    examples: list[dict[str, Any]] = []
    total = 0
    files = 0
    for path in lean_files_under(project_root):
        module = module_name_for(project_root, path)
        direct = graph.get(module) or parse_file_imports(path)
        redundant = redundant_in_file(direct, graph)
        if not redundant:
            continue
        files += 1
        total += len(redundant)
        if len(examples) < 20:
            examples.append({"module": module, "redundant": redundant})
    return {
        "redundant_import_count": total,
        "files_with_redundant_imports": files,
        "examples": examples,
    }


def extra_axioms(used: list[str], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed) | DEFAULT_ALLOWED
    extra = []
    for name in used:
        if name in allowed_set or name in KERNEL_AXIOMS:
            continue
        extra.append(name)
    return extra


def summarize_axiom_audit(payload: dict[str, Any]) -> dict[str, Any]:
    used = [str(item) for item in payload.get("axiomsUsed") or []]
    allowed = [str(item) for item in payload.get("allowed") or list(DEFAULT_ALLOWED)]
    violations = payload.get("violations") or []
    sorry_decls = 0
    if isinstance(violations, list):
        for item in violations:
            if not isinstance(item, dict):
                continue
            axioms = [str(name) for name in item.get("axioms") or []]
            if "sorryAx" in axioms:
                sorry_decls += 1
    extra = extra_axioms(used, allowed)
    return {
        "ok": bool(payload.get("ok")),
        "root": payload.get("root"),
        "audited": payload.get("audited"),
        "allowed": allowed,
        "axioms_used": used,
        "violation_count": len(violations) if isinstance(violations, list) else 0,
        "sorry_ax": "sorryAx" in used,
        "sorry_ax_declarations": sorry_decls,
        "native_decide": "Lean.ofReduceBool" in used or "Lean.ofReduceNat" in used,
        "extra_axioms": extra,
        "error": payload.get("error"),
    }


def tool_cache() -> Path:
    raw = os.getenv("ANALYZE_TOOL_CACHE", "")
    if raw:
        return Path(raw)
    return REPO_ROOT / ".data" / "tool-cache"


def axiom_audit_source(cache: Path) -> Path | None:
    env = os.getenv("ANALYZE_AXIOM_AUDIT_SRC", "").strip()
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.append(REPO_ROOT / "third_party" / "axiom-audit")
    cached_src = cache / "axiom-audit-src"
    candidates.append(cached_src)
    for path in candidates:
        if (path / "lakefile.toml").is_file():
            return path
    cached_src.parent.mkdir(parents=True, exist_ok=True)
    clone = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            AXIOM_AUDIT_REF,
            AXIOM_AUDIT_URL,
            str(cached_src),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if clone.returncode != 0 or not (cached_src / "lakefile.toml").is_file():
        return None
    got = subprocess.run(
        ["git", "-C", str(cached_src), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if got.stdout.strip() and got.stdout.strip() != AXIOM_AUDIT_SHA:
        shutil.rmtree(cached_src, ignore_errors=True)
        return None
    return cached_src


def build_axiom_audit(
    toolchain: str,
    *,
    env: dict[str, str],
    timeout_seconds: int,
    run_command: RunCommand,
    unavailable: Unavailable,
) -> tuple[Path | None, dict[str, Any]]:
    cache = tool_cache()
    source = axiom_audit_source(cache)
    if source is None:
        return None, unavailable(
            ["lake", "build"],
            "axiom-audit sources are not available.",
        )
    key = hashlib.sha256(toolchain.encode("utf-8")).hexdigest()[:16]
    dest = cache / "axiom-audit" / key
    binary = dest / ".lake" / "build" / "bin" / "axiom-audit"
    if binary.is_file():
        return binary, {
            "command": ["lake", "build"],
            "status": "passed",
            "returncode": 0,
            "duration_seconds": 0,
            "output": "Reused cached axiom-audit binary.",
            "truncated": False,
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(
        source,
        dest,
        ignore=shutil.ignore_patterns(".lake", ".git"),
    )
    (dest / "lean-toolchain").write_text(f"{toolchain}\n", encoding="utf-8")
    built = run_command(
        ["lake", "build"],
        cwd=dest,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    if built["status"] == "passed" and binary.is_file():
        return binary, built
    return None, built


def run_axiom_audit(
    project_root: Path,
    *,
    toolchain: str,
    env: dict[str, str],
    timeout_seconds: int,
    run_command: RunCommand,
    unavailable: Unavailable,
) -> tuple[dict[str, Any], dict[str, Any]]:
    binary, built = build_axiom_audit(
        toolchain,
        env=env,
        timeout_seconds=min(timeout_seconds, 900),
        run_command=run_command,
        unavailable=unavailable,
    )
    if binary is None:
        result = built if built.get("status") != "passed" else unavailable(
            ["lake", "env", "axiom-audit", "--json"],
            "axiom-audit did not produce a binary.",
        )
        return result, {"ok": False, "error": result.get("output") or "unavailable"}
    command = ["lake", "env", str(binary), "--json"]
    result = run_command(
        command,
        cwd=project_root,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    payload = last_json_object(str(result.get("output") or ""))
    if payload is None:
        summary = {"ok": False, "error": "axiom-audit produced no JSON."}
        if result["status"] == "passed":
            result["status"] = "failed"
        return result, summary
    summary = summarize_axiom_audit(payload)
    if result["status"] not in {"timed_out", "oom_killed"}:
        result["status"] = "passed" if summary.get("ok") else "failed"
    result["report"] = summary
    return result, summary


def run_lean_fmt(
    project_root: Path,
    *,
    env: dict[str, str],
    timeout_seconds: int,
    run_command: RunCommand,
    unavailable: Unavailable,
) -> dict[str, Any]:
    for name in ("leanfmt", "lean-fmt"):
        result = run_command(
            ["lake", "exe", name, "--check"],
            cwd=project_root,
            timeout_seconds=timeout_seconds,
            env=env,
        )
        output = str(result.get("output") or "").lower()
        unknown = result["status"] != "passed" and (
            "unknown executable" in output
            or "unknown target" in output
            or "error: unknown" in output
            or "no executable" in output
        )
        if not unknown:
            result["formatter"] = name
            return result
    which = shutil.which("lean-fmt")
    if which:
        files = lean_files_under(project_root)
        dirty = 0
        checked = 0
        for path in files:
            try:
                original = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            completed = subprocess.run(
                [which],
                input=original,
                check=False,
                capture_output=True,
                text=True,
                cwd=project_root,
                env=env,
            )
            checked += 1
            if completed.returncode != 0 or completed.stdout != original:
                dirty += 1
        return {
            "command": [which, "--check"],
            "status": "passed" if dirty == 0 else "failed",
            "returncode": 0 if dirty == 0 else 1,
            "duration_seconds": 0,
            "output": f"Checked {checked} files; {dirty} differ from lean-fmt.",
            "truncated": False,
            "formatter": "lean-fmt",
            "dirty_files": dirty,
            "checked_files": checked,
        }
    return unavailable(
        ["lake", "exe", "leanfmt", "--check"],
        "No leanfmt or lean-fmt executable is configured.",
    )


def run_post_build_checks(
    project_root: Path,
    *,
    toolchain: str,
    env: dict[str, str],
    profile: str,
    run_command: RunCommand,
    unavailable: Unavailable,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    timeout = 900 if profile == "big" else 300
    axiom_result, axiom_summary = run_axiom_audit(
        project_root,
        toolchain=toolchain,
        env=env,
        timeout_seconds=timeout,
        run_command=run_command,
        unavailable=unavailable,
    )
    fmt_result = run_lean_fmt(
        project_root,
        env=env,
        timeout_seconds=timeout,
        run_command=run_command,
        unavailable=unavailable,
    )
    redundant = find_redundant_imports(project_root)
    return (
        {"axiom_audit": axiom_result, "fmt": fmt_result},
        axiom_summary,
        redundant,
    )

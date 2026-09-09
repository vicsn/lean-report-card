from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_RUNNER_DIR = Path(__file__).resolve().parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))
from extra_checks import run_post_build_checks  # noqa: E402

try:
    from scoring import score_report
except ModuleNotFoundError:
    from lean_report_card.scoring import score_report

WORKSPACE = Path(os.getenv("ANALYZE_WORKSPACE", "/workspace"))
REPOSITORY = WORKSPACE / "repository"
OUTPUT = Path(os.getenv("ANALYZE_OUTPUT", "/output/report.json"))
MAX_LOG_BYTES = int(os.getenv("MAX_LOG_BYTES", "1000000"))
PROFILE = os.getenv("PROFILE", "small")


def configure_paths() -> None:
    global WORKSPACE, REPOSITORY, OUTPUT, MAX_LOG_BYTES, PROFILE
    WORKSPACE = Path(os.getenv("ANALYZE_WORKSPACE", "/workspace"))
    REPOSITORY = WORKSPACE / "repository"
    OUTPUT = Path(os.getenv("ANALYZE_OUTPUT", "/output/report.json"))
    MAX_LOG_BYTES = int(os.getenv("MAX_LOG_BYTES", "1000000"))
    PROFILE = os.getenv("PROFILE", "small")


def resolve_project_root(repo: Path) -> Path:
    raw = os.getenv("ANALYZE_PROJECT_PATH", "").strip()
    if not raw or raw in {".", "./"}:
        return repo
    candidate = (repo / raw).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError:
        return repo
    return candidate if candidate.is_dir() else repo

EXCLUDED_DIRECTORIES = {
    ".git",
    ".lake",
    "build",
    "dist",
    "lake-packages",
    "node_modules",
    "third_party",
    "vendor",
}
SAFE_TOOLCHAIN = re.compile(r"^[A-Za-z0-9_./:+@-]+$")
DECLARATION = re.compile(
    r"^\s*(?:(?:private|protected|noncomputable|unsafe|partial)\s+)*"
    r"(theorem|lemma|def|abbrev|opaque|axiom|structure|class|inductive|instance)\b"
)
IMPORT = re.compile(r"^\s*(?:(?:public|private)\s+)?import(?:\s+all)?\s+(.+)$")


@dataclass
class CommandResult:
    command: list[str]
    status: str
    returncode: int | None
    duration_seconds: int
    output: str
    truncated: bool


def command_result_unavailable(command: list[str], reason: str) -> dict[str, Any]:
    return asdict(
        CommandResult(
            command=command,
            status="unavailable",
            returncode=None,
            duration_seconds=0,
            output=reason,
            truncated=False,
        )
    )


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str],
) -> dict[str, Any]:
    started = time.monotonic()
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(  # noqa: S603 - command is an explicit argument vector
            command,
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        status = "failed"
        try:
            returncode = process.wait(timeout=timeout_seconds)
            if returncode == 0:
                status = "passed"
            elif returncode in {137, -9, 9}:
                status = "oom_killed"
            else:
                status = "failed"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait()
            status = "timed_out"
        duration = max(0, int(time.monotonic() - started))
        size = output.tell()
        truncated = size > MAX_LOG_BYTES
        output.seek(max(0, size - MAX_LOG_BYTES))
        text = output.read().decode("utf-8", errors="replace")
    return asdict(
        CommandResult(
            command=command,
            status=status,
            returncode=returncode,
            duration_seconds=duration,
            output=text,
            truncated=truncated,
        )
    )


def strip_lean_comments_and_strings(text: str) -> str:
    result: list[str] = []
    index = 0
    block_depth = 0
    in_string = False
    escaped = False
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if block_depth:
            if current == "/" and following == "-":
                block_depth += 1
                index += 2
                continue
            if current == "-" and following == "/":
                block_depth -= 1
                index += 2
                continue
            result.append("\n" if current == "\n" else " ")
            index += 1
            continue
        if in_string:
            if current == "\n":
                result.append("\n")
            else:
                result.append(" ")
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == '"':
                in_string = False
            index += 1
            continue
        if current == "-" and following == "-":
            while index < len(text) and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if current == "/" and following == "-":
            block_depth = 1
            result.extend([" ", " "])
            index += 2
            continue
        if current == '"':
            in_string = True
            result.append(" ")
            index += 1
            continue
        result.append(current)
        index += 1
    return "".join(result)


def lean_files(root: Path) -> list[Path]:
    output: list[Path] = []
    for path in root.rglob("*.lean"):
        if any(part in EXCLUDED_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            output.append(path)
    return sorted(output)


def scan_sources(root: Path) -> dict[str, Any]:
    paths = lean_files(root)
    line_count = 0
    sorry_count = 0
    admit_count = 0
    axiom_count = 0
    native_decide_count = 0
    todo_count = 0
    test_file_count = 0
    module_docs = 0
    declaration_count = 0
    documented_declarations = 0
    import_counts: list[int] = []

    for path in paths:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = raw.splitlines()
        line_count += len(lines)
        if "/-!" in raw[:8192]:
            module_docs += 1
        relative_lower = str(path.relative_to(root)).lower()
        if "test" in relative_lower or path.stem.lower().endswith("test"):
            test_file_count += 1
        todo_count += len(re.findall(r"\b(?:TODO|FIXME)\b", raw, flags=re.IGNORECASE))

        stripped = strip_lean_comments_and_strings(raw)
        sorry_count += len(re.findall(r"\bsorry\b", stripped))
        admit_count += len(re.findall(r"\badmit\b", stripped))
        axiom_count += len(re.findall(r"(?m)^\s*axiom\b", stripped))
        native_decide_count += len(re.findall(r"\bnative_decide\b", stripped))

        file_imports = 0
        for index, line in enumerate(lines):
            import_match = IMPORT.match(line)
            if import_match:
                import_text = import_match.group(1).split("--", 1)[0]
                modules = [item for item in import_text.split() if item]
                file_imports += len(modules)
            if DECLARATION.match(line):
                declaration_count += 1
                window = "\n".join(lines[max(0, index - 8) : index])
                if "/--" in window or "/-!" in window:
                    documented_declarations += 1
        import_counts.append(file_imports)

    average_imports = sum(import_counts) / len(import_counts) if import_counts else 0.0
    return {
        "lean_file_count": len(paths),
        "line_count": line_count,
        "sorry_count": sorry_count,
        "admit_count": admit_count,
        "axiom_declaration_count": axiom_count,
        "native_decide_count": native_decide_count,
        "todo_count": todo_count,
        "test_file_count": test_file_count,
        "module_doc_count": module_docs,
        "module_doc_ratio": module_docs / len(paths) if paths else 0.0,
        "declaration_count": declaration_count,
        "documented_declaration_count": documented_declarations,
        "declaration_doc_ratio": (
            documented_declarations / declaration_count if declaration_count else 0.0
        ),
        "average_direct_imports": average_imports,
        "max_direct_imports": max(import_counts, default=0),
    }


def find_case_insensitive(root: Path, names: set[str]) -> bool:
    lowered = {name.lower() for name in names}
    try:
        return any(path.name.lower() in lowered for path in root.iterdir() if path.is_file())
    except OSError:
        return False


def file_facts(root: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or root
    toolchain_path = root / "lean-toolchain"
    toolchain = None
    if toolchain_path.is_file():
        lines = toolchain_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        toolchain = lines[0] if lines else None

    def listed(*names: str) -> bool:
        wanted = set(names)
        return find_case_insensitive(root, wanted) or find_case_insensitive(repo_root, wanted)

    return {
        "lean_toolchain": toolchain,
        "lake_manifest": (root / "lake-manifest.json").is_file(),
        "lakefile": (root / "lakefile.lean").is_file() or (root / "lakefile.toml").is_file(),
        "readme": listed("README", "README.md", "README.rst"),
        "license": listed("LICENSE", "LICENSE.md", "COPYING"),
        "contributing": listed("CONTRIBUTING", "CONTRIBUTING.md"),
        "security": listed("SECURITY", "SECURITY.md"),
        "changelog": listed("CHANGELOG", "CHANGELOG.md", "CHANGES.md"),
        "ci": (root / ".github" / "workflows").is_dir()
        or (repo_root / ".github" / "workflows").is_dir(),
    }


def configured_driver(root: Path, driver: str) -> bool:
    content = ""
    for name in ("lakefile.lean", "lakefile.toml"):
        path = root / name
        if path.is_file():
            content += path.read_text(encoding="utf-8", errors="replace") + "\n"
    patterns = {
        "test": r"\b(?:testDriver|test_driver)\b",
        "lint": r"\b(?:lintDriver|lint_driver)\b",
    }
    return bool(re.search(patterns[driver], content))


def write_report(payload: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(OUTPUT)


def main() -> int:
    configure_paths()
    repo_url = os.environ["REPO_URL"]
    git_sha = os.environ["GIT_SHA"]
    analyzer_version = os.getenv("ANALYZER_VERSION", "dev")
    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "CI": "true",
            "LEAN_NUM_THREADS": os.getenv("LEAN_NUM_THREADS", "2"),
        }
    )

    shutil.rmtree(REPOSITORY, ignore_errors=True)
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    clone_timeout = 900 if PROFILE == "big" else 300
    clone = run_command(
        ["git", "clone", "--filter=blob:none", "--no-checkout", repo_url, str(REPOSITORY)],
        cwd=WORKSPACE,
        timeout_seconds=clone_timeout,
        env=env,
    )
    if clone["status"] != "passed":
        write_report(
            {
                "schema_version": 1,
                "analysis_status": "failed",
                "error": "Repository clone failed.",
                "repository": {"url": repo_url, "commit_sha": git_sha},
                "clone": clone,
            }
        )
        return 0

    checkout = run_command(
        ["git", "checkout", "--detach", git_sha],
        cwd=REPOSITORY,
        timeout_seconds=120,
        env=env,
    )
    if checkout["status"] != "passed":
        write_report(
            {
                "schema_version": 1,
                "analysis_status": "failed",
                "error": "Commit checkout failed.",
                "repository": {"url": repo_url, "commit_sha": git_sha},
                "clone": clone,
                "checkout": checkout,
            }
        )
        return 0

    submodules = run_command(
        ["git", "submodule", "update", "--init", "--recursive", "--depth", "1"],
        cwd=REPOSITORY,
        timeout_seconds=clone_timeout,
        env=env,
    )
    project_root = resolve_project_root(REPOSITORY)
    files = file_facts(project_root, repo_root=REPOSITORY)
    static = scan_sources(project_root)

    commands: dict[str, dict[str, Any]] = {}
    cache_result = command_result_unavailable(["lake", "exe", "cache", "get"], "Not attempted.")
    toolchain = files.get("lean_toolchain")
    if not isinstance(toolchain, str) or not toolchain or not SAFE_TOOLCHAIN.fullmatch(toolchain):
        install = command_result_unavailable(
            ["elan", "toolchain", "install"], "Missing or invalid lean-toolchain."
        )
        commands["build"] = command_result_unavailable(
            ["lake", "build"], "A valid lean-toolchain is required."
        )
        commands["test"] = command_result_unavailable(["lake", "test"], "Build was not attempted.")
        commands["lint"] = command_result_unavailable(["lake", "lint"], "Build was not attempted.")
    elif not files.get("lakefile"):
        install = command_result_unavailable(
            ["elan", "toolchain", "install", toolchain], "No Lake project found."
        )
        commands["build"] = command_result_unavailable(
            ["lake", "build"], "No lakefile.lean or lakefile.toml found."
        )
        commands["test"] = command_result_unavailable(["lake", "test"], "No Lake project found.")
        commands["lint"] = command_result_unavailable(["lake", "lint"], "No Lake project found.")
    else:
        install_timeout = 1800 if PROFILE == "big" else 900
        install = run_command(
            ["elan", "toolchain", "install", toolchain],
            cwd=project_root,
            timeout_seconds=install_timeout,
            env=env,
        )
        install_output = str(install.get("output") or "")
        if install["status"] != "passed" and "already installed" in install_output.lower():
            install["status"] = "passed"
        if install["status"] == "passed":
            manifest_path = project_root / "lake-manifest.json"
            manifest = (
                manifest_path.read_text(encoding="utf-8", errors="replace")
                if manifest_path.is_file()
                else ""
            )
            if '"mathlib"' in manifest or "mathlib4" in manifest:
                cache_result = run_command(
                    ["lake", "exe", "cache", "get"],
                    cwd=project_root,
                    timeout_seconds=1800 if PROFILE == "big" else 600,
                    env=env,
                )
            build_timeout = 5400 if PROFILE == "big" else 1200
            commands["build"] = run_command(
                ["lake", "build"],
                cwd=project_root,
                timeout_seconds=build_timeout,
                env=env,
            )
            build_output = str(commands["build"].get("output", ""))
            commands["build"]["warning_count"] = len(
                re.findall(r"(?im)^.*\bwarning:", build_output)
            )
            if commands["build"]["status"] == "passed" and configured_driver(project_root, "test"):
                commands["test"] = run_command(
                    ["lake", "test"],
                    cwd=project_root,
                    timeout_seconds=1200 if PROFILE == "big" else 300,
                    env=env,
                )
            else:
                reason = (
                    "No configured Lake test driver."
                    if commands["build"]["status"] == "passed"
                    else "Build did not pass."
                )
                commands["test"] = command_result_unavailable(["lake", "test"], reason)
            if commands["build"]["status"] == "passed" and configured_driver(project_root, "lint"):
                commands["lint"] = run_command(
                    ["lake", "lint"],
                    cwd=project_root,
                    timeout_seconds=1200 if PROFILE == "big" else 300,
                    env=env,
                )
            else:
                reason = (
                    "No configured Lake lint driver."
                    if commands["build"]["status"] == "passed"
                    else "Build did not pass."
                )
                commands["lint"] = command_result_unavailable(["lake", "lint"], reason)
            if commands["build"]["status"] == "passed":
                extra_commands, axiom_summary, redundant = run_post_build_checks(
                    project_root,
                    toolchain=str(toolchain),
                    env=env,
                    profile=PROFILE,
                    run_command=run_command,
                    unavailable=command_result_unavailable,
                )
                commands.update(extra_commands)
            else:
                commands["axiom_audit"] = command_result_unavailable(
                    ["lake", "env", "axiom-audit", "--json"],
                    "Build did not pass.",
                )
                commands["fmt"] = command_result_unavailable(
                    ["lake", "exe", "leanfmt", "--check"],
                    "Build did not pass.",
                )
                axiom_summary = {"ok": False, "error": "Build did not pass."}
                redundant = {
                    "redundant_import_count": 0,
                    "files_with_redundant_imports": 0,
                    "examples": [],
                    "error": "Build did not pass.",
                }
        else:
            commands["build"] = command_result_unavailable(
                ["lake", "build"], "Lean toolchain installation failed."
            )
            commands["test"] = command_result_unavailable(
                ["lake", "test"], "Build was not attempted."
            )
            commands["lint"] = command_result_unavailable(
                ["lake", "lint"], "Build was not attempted."
            )

    if "axiom_audit" not in commands:
        commands["axiom_audit"] = command_result_unavailable(
            ["lake", "env", "axiom-audit", "--json"],
            "Build was not attempted.",
        )
        commands["fmt"] = command_result_unavailable(
            ["lake", "exe", "leanfmt", "--check"],
            "Build was not attempted.",
        )
        axiom_summary = {"ok": False, "error": "Build was not attempted."}
        redundant = {
            "redundant_import_count": 0,
            "files_with_redundant_imports": 0,
            "examples": [],
            "error": "Build was not attempted.",
        }

    all_results = [clone, checkout, submodules, install, cache_result, *commands.values()]
    logs_truncated = any(bool(result.get("truncated")) for result in all_results)
    facts = {
        "commands": commands,
        "files": files,
        "static": static,
        "axiom_audit": axiom_summary,
        "redundant_imports": redundant,
        "toolchain_install": install,
        "mathlib_cache": cache_result,
        "submodules": submodules,
        "logs_truncated": logs_truncated,
    }
    scoring = score_report(facts)
    oom = any(
        str(result.get("status")) == "oom_killed"
        for result in [install, cache_result, *commands.values()]
    )
    project_path = os.getenv("ANALYZE_PROJECT_PATH", "").strip() or None
    payload = {
        "schema_version": 1,
        "analysis_status": "oom_killed" if oom else "completed",
        "analyzer_version": analyzer_version,
        "profile": PROFILE,
        "repository": {
            "url": repo_url,
            "commit_sha": git_sha,
            "project_path": project_path,
        },
        "clone": clone,
        "checkout": checkout,
        "facts": facts,
        "scoring": scoring,
    }
    write_report(payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - preserve analyzer failure as JSON
        write_report(
            {
                "schema_version": 1,
                "analysis_status": "failed",
                "error": f"Unhandled analyzer error: {type(exc).__name__}: {exc}",
            }
        )
        raise

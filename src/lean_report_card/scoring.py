from __future__ import annotations

from typing import Any


def _check(
    check_id: str,
    category: str,
    title: str,
    status: str,
    score: int,
    maximum: int,
    summary: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "category": category,
        "title": title,
        "status": status,
        "score": max(0, min(score, maximum)),
        "maximum": maximum,
        "summary": summary,
        "details": details or {},
    }


def _command_score(status: str, maximum: int, unavailable_score: int = 0) -> int:
    if status == "passed":
        return maximum
    if status in {"unavailable", "skipped"}:
        return unavailable_score
    return 0


def grade_for(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def score_report(facts: dict[str, Any]) -> dict[str, Any]:
    commands = facts.get("commands", {})
    static = facts.get("static", {})
    files = facts.get("files", {})
    checks: list[dict[str, Any]] = []

    build = commands.get("build", {})
    build_status = str(build.get("status", "failed"))
    checks.append(
        _check(
            "build",
            "build",
            "Lake build",
            build_status,
            _command_score(build_status, 25),
            25,
            (
                "The pinned project revision builds."
                if build_status == "passed"
                else "The build did not pass."
            ),
            {
                "duration_seconds": build.get("duration_seconds"),
                "returncode": build.get("returncode"),
            },
        )
    )

    tests = commands.get("test", {})
    test_status = str(tests.get("status", "unavailable"))
    checks.append(
        _check(
            "tests",
            "verification",
            "Project test driver",
            test_status,
            _command_score(test_status, 10, unavailable_score=3),
            10,
            "The configured Lake test driver passed."
            if test_status == "passed"
            else "No passing project test result was observed.",
            {
                "duration_seconds": tests.get("duration_seconds"),
                "returncode": tests.get("returncode"),
            },
        )
    )

    lint = commands.get("lint", {})
    lint_status = str(lint.get("status", "unavailable"))
    checks.append(
        _check(
            "lint",
            "maintainability",
            "Project lint driver",
            lint_status,
            _command_score(lint_status, 10, unavailable_score=4),
            10,
            "The configured Lake lint driver passed."
            if lint_status == "passed"
            else "No passing project lint result was observed.",
            {
                "duration_seconds": lint.get("duration_seconds"),
                "returncode": lint.get("returncode"),
            },
        )
    )

    sorry_count = int(static.get("sorry_count", 0))
    admit_count = int(static.get("admit_count", 0))
    axiom_count = int(static.get("axiom_declaration_count", 0))
    native_decide_count = int(static.get("native_decide_count", 0))
    trust_issues = sorry_count + admit_count
    trust_score = 10 if trust_issues == 0 else max(0, 10 - min(10, trust_issues))
    trust_score += 3 if axiom_count == 0 else max(0, 3 - min(3, axiom_count))
    trust_score += 2 if native_decide_count == 0 else 0
    checks.append(
        _check(
            "source-trust-signals",
            "trust",
            "Source-level trust signals",
            "passed" if trust_score == 15 else "warning",
            trust_score,
            15,
            "No obvious source-level trust exceptions were found."
            if trust_score == 15
            else "Potential trust exceptions need review; source scanning is not an axiom audit.",
            {
                "sorry_count": sorry_count,
                "admit_count": admit_count,
                "axiom_declaration_count": axiom_count,
                "native_decide_count": native_decide_count,
            },
        )
    )

    has_toolchain = bool(files.get("lean_toolchain"))
    has_manifest = bool(files.get("lake_manifest"))
    reproducibility_score = (5 if has_toolchain else 0) + (5 if has_manifest else 0)
    checks.append(
        _check(
            "reproducibility",
            "reproducibility",
            "Pinned toolchain and dependencies",
            "passed" if reproducibility_score == 10 else "warning",
            reproducibility_score,
            10,
            "Lean and Lake dependencies are pinned."
            if reproducibility_score == 10
            else "Add lean-toolchain and lake-manifest.json for reproducible runs.",
            {"lean_toolchain": files.get("lean_toolchain"), "lake_manifest": has_manifest},
        )
    )

    module_doc_ratio = float(static.get("module_doc_ratio", 0.0))
    declaration_doc_ratio = float(static.get("declaration_doc_ratio", 0.0))
    docs_score = min(4, round(module_doc_ratio * 4)) + min(4, round(declaration_doc_ratio * 4))
    docs_score += 2 if files.get("readme") else 0
    checks.append(
        _check(
            "documentation",
            "documentation",
            "Documentation coverage",
            "passed" if docs_score >= 8 else "warning",
            docs_score,
            10,
            "README, module docs and declaration docs are estimated from source text.",
            {
                "module_doc_ratio": round(module_doc_ratio, 3),
                "declaration_doc_ratio": round(declaration_doc_ratio, 3),
            },
        )
    )

    average_imports = float(static.get("average_direct_imports", 0.0))
    max_imports = int(static.get("max_direct_imports", 0))
    if average_imports <= 10:
        import_score = 5
    elif average_imports <= 25:
        import_score = 4
    elif average_imports <= 50:
        import_score = 2
    else:
        import_score = 1
    checks.append(
        _check(
            "imports",
            "architecture",
            "Direct import footprint",
            "passed" if import_score >= 4 else "warning",
            import_score,
            5,
            (
                "Lower direct-import counts generally reduce hidden coupling; "
                "this is only a coarse signal."
            ),
            {
                "average_direct_imports": round(average_imports, 2),
                "max_direct_imports": max_imports,
            },
        )
    )

    hygiene_score = 0
    hygiene_score += 2 if files.get("license") else 0
    hygiene_score += 2 if files.get("ci") else 0
    hygiene_score += 2 if int(static.get("test_file_count", 0)) > 0 else 0
    hygiene_score += 1 if files.get("contributing") else 0
    hygiene_score += 1 if files.get("security") else 0
    hygiene_score += 1 if files.get("changelog") else 0
    hygiene_score += 1 if int(static.get("todo_count", 0)) == 0 else 0
    checks.append(
        _check(
            "project-hygiene",
            "project",
            "Repository hygiene",
            "passed" if hygiene_score >= 8 else "warning",
            hygiene_score,
            10,
            "Checks for common maintenance files, CI and test sources.",
            {
                "test_file_count": static.get("test_file_count", 0),
                "todo_count": static.get("todo_count", 0),
            },
        )
    )

    warning_count = int(build.get("warning_count", 0))
    diagnostics_score = 3 if warning_count == 0 else 2 if warning_count <= 5 else 0
    diagnostics_score += 1 if facts.get("logs_truncated") is False else 0
    diagnostics_score += 1 if facts.get("toolchain_install", {}).get("status") == "passed" else 0
    checks.append(
        _check(
            "diagnostics",
            "performance",
            "Warnings and run diagnostics",
            "passed" if diagnostics_score >= 4 else "warning",
            diagnostics_score,
            5,
            "Build warnings and analyzer resource limits are visible in the report.",
            {"warning_count": warning_count, "logs_truncated": facts.get("logs_truncated")},
        )
    )

    total = sum(int(item["score"]) for item in checks)
    maximum = sum(int(item["maximum"]) for item in checks)
    score = round(total * 100 / maximum) if maximum else 0
    return {
        "score": score,
        "grade": grade_for(score),
        "checks": checks,
        "maximum_raw_score": maximum,
        "raw_score": total,
        "caveat": (
            "This is a heuristic maintainability report, not a proof of mathematical correctness, "
            "soundness, security or project fitness."
        ),
    }

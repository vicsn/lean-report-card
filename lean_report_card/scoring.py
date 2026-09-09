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


def _ratio_points(numerator: int, denominator: int, maximum: int) -> int:
    if denominator <= 0 or numerator <= 0:
        return 0
    if numerator >= denominator:
        return maximum
    return (numerator * maximum + denominator // 2) // denominator


def _count_from_ratio(ratio: float, total: int) -> int:
    if total <= 0:
        return 0
    return min(total, max(0, int(ratio * total + 0.5)))


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

    audit = facts.get("axiom_audit") or {}
    audit_status = str(commands.get("axiom_audit", {}).get("status", "unavailable"))
    used = [str(item) for item in audit.get("axioms_used") or []]
    extra = [str(item) for item in audit.get("extra_axioms") or []]
    sorry_decls = int(audit.get("sorry_ax_declarations") or 0)
    if audit.get("sorry_ax") and sorry_decls == 0:
        sorry_decls = 1
    if audit_status in {"unavailable", "skipped"} or audit.get("error"):
        trust_status = "unavailable"
        trust_score = 5
        trust_summary = "axiom-audit did not run on a compiled environment."
    else:
        trust_score = 10 if sorry_decls == 0 else max(0, 10 - min(10, sorry_decls))
        trust_score += 3 if not extra else max(0, 3 - min(3, len(extra)))
        trust_score += 0 if audit.get("native_decide") else 2
        trust_status = "passed" if trust_score == 15 else "warning"
        if trust_score == 15:
            trust_summary = "axiom-audit found no sorryAx, native_decide, or home-rolled axioms."
        elif extra:
            trust_summary = "axiom-audit found axioms outside the default allowlist."
        else:
            trust_summary = (
                "axiom-audit found sorryAx and/or native_decide in the compiled environment."
            )
    checks.append(
        _check(
            "axiom-audit",
            "trust",
            "Axiom allowlist",
            trust_status,
            trust_score,
            15,
            trust_summary,
            {
                "ok": audit.get("ok"),
                "audited": audit.get("audited"),
                "sorry_ax": bool(audit.get("sorry_ax")),
                "native_decide": bool(audit.get("native_decide")),
                "extra_axioms": extra[:20],
                "violation_count": audit.get("violation_count"),
                "axioms_used": used[:20],
            },
        )
    )

    fmt = commands.get("fmt", {})
    fmt_status = str(fmt.get("status", "unavailable"))
    checks.append(
        _check(
            "fmt",
            "maintainability",
            "lean-fmt",
            fmt_status,
            _command_score(fmt_status, 5, unavailable_score=2),
            5,
            "lean-fmt --check passed."
            if fmt_status == "passed"
            else "No passing lean-fmt check was observed.",
            {
                "formatter": fmt.get("formatter"),
                "dirty_files": fmt.get("dirty_files"),
                "returncode": fmt.get("returncode"),
            },
        )
    )

    redundant = facts.get("redundant_imports") or {}
    redundant_count = int(redundant.get("redundant_import_count") or 0)
    if redundant.get("error"):
        redundant_status = "unavailable"
        redundant_score = 2
        redundant_summary = "Redundant-import analysis did not run."
    else:
        redundant_score = 5 if redundant_count == 0 else max(0, 5 - min(5, redundant_count))
        redundant_status = "passed" if redundant_count == 0 else "warning"
        redundant_summary = (
            "No transitively redundant imports in project sources."
            if redundant_count == 0
            else f"Counted {redundant_count} transitively redundant import(s)."
        )
    checks.append(
        _check(
            "redundant-imports",
            "maintainability",
            "Redundant imports",
            redundant_status,
            redundant_score,
            5,
            redundant_summary,
            {
                "redundant_import_count": redundant_count,
                "files_with_redundant_imports": redundant.get("files_with_redundant_imports"),
                "examples": redundant.get("examples") or [],
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

    lean_file_count = int(static.get("lean_file_count", 0))
    module_doc_count = int(static.get("module_doc_count", 0))
    if "module_doc_count" not in static:
        module_doc_count = _count_from_ratio(
            float(static.get("module_doc_ratio", 0.0)), lean_file_count
        )
    declaration_count = int(static.get("declaration_count", 0))
    documented_declaration_count = int(static.get("documented_declaration_count", 0))
    if "documented_declaration_count" not in static:
        documented_declaration_count = _count_from_ratio(
            float(static.get("declaration_doc_ratio", 0.0)), declaration_count
        )
    docs_score = _ratio_points(module_doc_count, lean_file_count, 4)
    docs_score += _ratio_points(documented_declaration_count, declaration_count, 4)
    docs_score += 2 if files.get("readme") else 0
    checks.append(
        _check(
            "documentation",
            "documentation",
            "Documentation coverage",
            "passed" if docs_score >= 8 else "warning",
            docs_score,
            10,
            "README present; module-doc and declaration-doc comments scored by count.",
            {
                "module_doc_count": module_doc_count,
                "lean_file_count": lean_file_count,
                "documented_declaration_count": documented_declaration_count,
                "declaration_count": declaration_count,
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
    diagnostics_score = 5 if build_status == "passed" and warning_count == 0 else 0
    checks.append(
        _check(
            "diagnostics",
            "performance",
            "Build warnings",
            "passed" if diagnostics_score == 5 else "warning",
            diagnostics_score,
            5,
            (
                "The build produced no warning lines."
                if diagnostics_score == 5
                else "The build was not clean, or no passing build was observed."
            ),
            {"warning_count": warning_count},
        )
    )

    total = sum(int(item["score"]) for item in checks)
    maximum = sum(int(item["maximum"]) for item in checks)
    score = (total * 100 + maximum // 2) // maximum if maximum else 0
    return {
        "score": score,
        "grade": grade_for(score),
        "checks": checks,
        "maximum_raw_score": maximum,
        "raw_score": total,
    }

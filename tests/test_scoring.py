from __future__ import annotations

from lean_report_card.scoring import grade_for, score_report


def good_facts() -> dict[str, object]:
    return {
        "commands": {
            "build": {"status": "passed", "warning_count": 0},
            "test": {"status": "passed"},
            "lint": {"status": "passed"},
            "axiom_audit": {"status": "passed"},
            "fmt": {"status": "passed", "formatter": "leanfmt"},
        },
        "files": {
            "lean_toolchain": "leanprover/lean4:v4.20.0",
            "lake_manifest": True,
            "readme": True,
            "license": True,
            "ci": True,
            "contributing": True,
            "security": True,
            "changelog": True,
        },
        "static": {
            "sorry_count": 0,
            "admit_count": 0,
            "axiom_declaration_count": 0,
            "native_decide_count": 0,
            "lean_file_count": 2,
            "module_doc_count": 2,
            "declaration_count": 8,
            "documented_declaration_count": 8,
            "module_doc_ratio": 1.0,
            "declaration_doc_ratio": 1.0,
            "test_file_count": 3,
            "todo_count": 0,
        },
        "axiom_audit": {
            "ok": True,
            "audited": 12,
            "axioms_used": ["propext", "Classical.choice", "Quot.sound"],
            "extra_axioms": [],
            "sorry_ax": False,
            "native_decide": False,
            "violation_count": 0,
        },
        "redundant_imports": {
            "redundant_import_count": 0,
            "files_with_redundant_imports": 0,
            "examples": [],
        },
        "toolchain_install": {"status": "passed"},
        "logs_truncated": False,
    }


def test_good_project_scores_a() -> None:
    result = score_report(good_facts())
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert len(result["checks"]) == 10
    assert all(check["id"] != "source-trust-signals" for check in result["checks"])
    assert any(check["id"] == "axiom-audit" for check in result["checks"])


def test_home_rolled_axioms_reduce_score() -> None:
    facts = good_facts()
    facts["axiom_audit"] = dict(
        facts["axiom_audit"],  # type: ignore[arg-type]
        extra_axioms=["MyLib.myAxiom"],
        axioms_used=["propext", "MyLib.myAxiom"],
        ok=False,
        violation_count=1,
    )
    facts["commands"]["axiom_audit"] = {"status": "failed"}  # type: ignore[index]
    result = score_report(facts)
    audit = next(item for item in result["checks"] if item["id"] == "axiom-audit")
    assert audit["score"] < 15
    assert result["score"] < 100


def test_failed_build_gets_no_warning_points() -> None:
    facts = good_facts()
    facts["commands"]["build"] = {"status": "failed", "warning_count": 0}  # type: ignore[index]
    result = score_report(facts)
    diagnostics = next(item for item in result["checks"] if item["id"] == "diagnostics")
    assert diagnostics["score"] == 0


def test_grade_boundaries() -> None:
    assert grade_for(90) == "A"
    assert grade_for(80) == "B"
    assert grade_for(70) == "C"
    assert grade_for(60) == "D"
    assert grade_for(59) == "F"

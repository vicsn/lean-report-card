from __future__ import annotations

from lean_report_card.scoring import grade_for, score_report


def good_facts() -> dict[str, object]:
    return {
        "commands": {
            "build": {"status": "passed", "warning_count": 0},
            "test": {"status": "passed"},
            "lint": {"status": "passed"},
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
            "module_doc_ratio": 1.0,
            "declaration_doc_ratio": 1.0,
            "average_direct_imports": 4.0,
            "max_direct_imports": 8,
            "test_file_count": 3,
            "todo_count": 0,
        },
        "toolchain_install": {"status": "passed"},
        "logs_truncated": False,
    }


def test_good_project_scores_a() -> None:
    result = score_report(good_facts())
    assert result["score"] == 100
    assert result["grade"] == "A"
    assert len(result["checks"]) == 9


def test_trust_exceptions_reduce_score() -> None:
    facts = good_facts()
    facts["static"] = dict(  # type: ignore[arg-type]
        facts["static"], sorry_count=4, axiom_declaration_count=2
    )
    result = score_report(facts)
    assert result["score"] < 100


def test_grade_boundaries() -> None:
    assert grade_for(90) == "A"
    assert grade_for(80) == "B"
    assert grade_for(70) == "C"
    assert grade_for(60) == "D"
    assert grade_for(59) == "F"

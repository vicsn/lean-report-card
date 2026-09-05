from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_analyzer() -> object:
    path = Path(__file__).parents[1] / "runner" / "analyze.py"
    spec = importlib.util.spec_from_file_location("lrc_runner_analyze", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_static_scan_ignores_comments_and_strings(tmp_path: Path) -> None:
    analyzer = load_analyzer()
    (tmp_path / "Demo.lean").write_text(
        (
            '/-! Module docs -/\nimport Std -- one import\n\n'
            '/-- docs -/\ndef x := "sorry"\n-- admit\n#check x\n'
        ),
        encoding="utf-8",
    )
    facts = analyzer.scan_sources(tmp_path)  # type: ignore[attr-defined]
    assert facts["lean_file_count"] == 1
    assert facts["sorry_count"] == 0
    assert facts["admit_count"] == 0
    assert facts["average_direct_imports"] == 1.0
    assert facts["declaration_doc_ratio"] == 1.0

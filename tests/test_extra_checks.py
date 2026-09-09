from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from extra_checks import find_redundant_imports, last_json_object, parse_file_imports


def test_last_json_object_reads_trailing_payload() -> None:
    text = "noise\n{\"ok\": true, \"audited\": 3}\n"
    payload = last_json_object(text)
    assert payload == {"ok": True, "audited": 3}


def test_redundant_imports_detect_transitive_duplicate(tmp_path: Path) -> None:
    (tmp_path / "A.lean").write_text("import B\nimport C\n", encoding="utf-8")
    (tmp_path / "B.lean").write_text("import C\n", encoding="utf-8")
    (tmp_path / "C.lean").write_text("def x := 1\n", encoding="utf-8")
    result = find_redundant_imports(tmp_path)
    assert result["redundant_import_count"] == 1
    assert result["examples"][0]["module"] == "A"
    assert result["examples"][0]["redundant"] == ["C"]


def test_parse_stops_after_header(tmp_path: Path) -> None:
    path = tmp_path / "Demo.lean"
    path.write_text("import Foo\n\ndef x := 1\nimport Bar\n", encoding="utf-8")
    assert parse_file_imports(path) == ["Foo"]

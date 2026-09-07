from __future__ import annotations

from pathlib import Path

from lean_report_card.badge import (
    badge_file_for_slug,
    render_badge_svg,
    write_badges,
    write_badges_from_index,
)


def test_render_badge_svg_includes_grade_and_score() -> None:
    svg = render_badge_svg("B", 85)
    assert 'aria-label="Lean report: B · 85"' in svg
    assert ">B · 85<" in svg
    assert 'fill="#97ca00"' in svg


def test_render_badge_svg_unknown_without_grade() -> None:
    svg = render_badge_svg(None, None)
    assert 'aria-label="Lean report: unknown"' in svg
    assert ">unknown<" in svg


def test_write_badges_from_index(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "index.json").write_text(
        """{
          "reports": [
            {"slug": "gdahia/DensityHalesJewett", "grade": "B", "score": 85}
          ]
        }""",
        encoding="utf-8",
    )
    stale = tmp_path / "badge" / "owner" / "gone.svg"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    written = write_badges_from_index(tmp_path)
    path = tmp_path / "badge" / "gdahia" / "DensityHalesJewett.svg"
    assert written == 1
    assert path.is_file()
    assert "B · 85" in path.read_text(encoding="utf-8")
    assert not stale.exists()


def test_badge_file_rejects_unsafe_slugs(tmp_path: Path) -> None:
    assert badge_file_for_slug(tmp_path, "../etc/passwd") is None
    assert badge_file_for_slug(tmp_path, "only-one") is None
    assert write_badges(tmp_path, [{"slug": "a/b/c", "grade": "A", "score": 90}]) == 0

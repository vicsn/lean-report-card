"""Shields-style SVG badges for published Lean Report Card grades."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

LABEL = "lean report"
LABEL_WIDTH = 102
GRADE_FILL = {
    "A": "#4c1",
    "B": "#97ca00",
    "C": "#dfb317",
    "D": "#fe7d37",
    "F": "#e05d44",
}


def badge_value(grade: str | None, score: int | None) -> str:
    if grade:
        if score is None:
            return str(grade)
        return f"{grade} · {score}"
    return "unknown"


def render_badge_svg(grade: str | None = None, score: int | None = None) -> str:
    value = badge_value(grade, score)
    safe_value = html.escape(value)
    fill = GRADE_FILL.get(str(grade or "").upper(), "#9f9f9f")
    value_width = max(72, 8 * len(value) + 18)
    total = LABEL_WIDTH + value_width
    value_midpoint = LABEL_WIDTH + value_width / 2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20"
 role="img" aria-label="Lean report: {safe_value}">
<linearGradient id="s" x2="0" y2="100%">
  <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
  <stop offset="1" stop-opacity=".1"/>
</linearGradient>
<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)">
  <rect width="{LABEL_WIDTH}" height="20" fill="#555"/>
  <rect x="{LABEL_WIDTH}" width="{value_width}" height="20" fill="{fill}"/>
  <rect width="{total}" height="20" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif"
 font-size="11">
  <text x="51" y="15" fill="#010101" fill-opacity=".3">{LABEL}</text>
  <text x="51" y="14">{LABEL}</text>
  <text x="{value_midpoint}" y="15" fill="#010101" fill-opacity=".3">{safe_value}</text>
  <text x="{value_midpoint}" y="14">{safe_value}</text>
</g>
</svg>
"""


def badge_file_for_slug(badge_dir: Path, slug: str) -> Path | None:
    parts = [part for part in slug.strip("/").split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} or "/" in part or "\\" in part for part in parts):
        return None
    owner, name = parts
    return badge_dir / owner / f"{name}.svg"


def write_badge(path: Path, grade: str | None, score: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".svg.tmp")
    temporary.write_text(render_badge_svg(grade, score), encoding="utf-8")
    temporary.replace(path)


def write_badges(badge_dir: Path, reports: list[dict[str, Any]]) -> int:
    written = 0
    keep: set[Path] = set()
    for item in reports:
        slug = str(item.get("slug") or "")
        path = badge_file_for_slug(badge_dir, slug)
        if path is None:
            continue
        score = item.get("score")
        write_badge(path, item.get("grade"), score if isinstance(score, int) else None)
        keep.add(path.resolve())
        written += 1
    if badge_dir.is_dir():
        for path in badge_dir.rglob("*.svg"):
            if path.resolve() not in keep:
                path.unlink()
    return written


def write_badges_from_index(site_dir: Path) -> int:
    index_path = site_dir / "reports" / "index.json"
    if not index_path.is_file():
        return 0
    index = json.loads(index_path.read_text(encoding="utf-8"))
    reports = [item for item in (index.get("reports") or []) if isinstance(item, dict)]
    return write_badges(site_dir / "badge", reports)

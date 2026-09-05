from __future__ import annotations

import pytest

from lean_report_card.github import RepositoryInputError, parse_github_repository, validate_ref


@pytest.mark.parametrize(
    ("value", "slug"),
    [
        ("leanprover/lean4", "leanprover/lean4"),
        ("github.com/leanprover/lean4", "leanprover/lean4"),
        ("https://github.com/leanprover/lean4", "leanprover/lean4"),
        ("https://github.com/leanprover/lean4.git", "leanprover/lean4"),
    ],
)
def test_parse_github_repository(value: str, slug: str) -> None:
    parsed = parse_github_repository(value)
    assert parsed.slug == slug
    assert parsed.canonical_url == f"https://github.com/{slug}.git"


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/leanprover/lean4",
        "https://gitlab.com/leanprover/lean4",
        "https://github.com/leanprover/lean4/issues",
        "https://user:pass@github.com/leanprover/lean4",
        "file:///etc/passwd",
    ],
)
def test_parse_rejects_unsafe_targets(value: str) -> None:
    with pytest.raises(RepositoryInputError):
        parse_github_repository(value)


def test_ref_validation() -> None:
    assert validate_ref("refs/tags/v4.0.0") == "refs/tags/v4.0.0"
    for invalid in ("../../etc/passwd", "-upload-pack", "/main", "feature//branch", "main."):
        with pytest.raises(RepositoryInputError):
            validate_ref(invalid)

from __future__ import annotations

from lean_report_card.config import Settings
from lean_report_card.github import ParsedRepository, ResolvedRepository
from lean_report_card.queueing import choose_queue


def resolved(slug: str, size_kib: int | None) -> ResolvedRepository:
    owner, name = slug.split("/", 1)
    return ResolvedRepository(
        parsed=ParsedRepository(owner=owner, name=name),
        commit_sha="a" * 40,
        requested_ref=None,
        default_branch="main",
        size_kib=size_kib,
    )


def test_auto_queue_uses_size() -> None:
    settings = Settings(big_repo_threshold_kib=100, known_big_repos="")
    assert choose_queue(resolved("example/tiny", 99), "auto", settings) == "small"
    assert choose_queue(resolved("example/large", 100), "auto", settings) == "big"


def test_known_big_and_override() -> None:
    settings = Settings(big_repo_threshold_kib=1_000_000, known_big_repos="example/known")
    target = resolved("example/known", 1)
    assert choose_queue(target, "auto", settings) == "big"
    assert choose_queue(target, "small", settings) == "small"

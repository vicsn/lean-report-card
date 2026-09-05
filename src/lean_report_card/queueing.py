from __future__ import annotations

from typing import Literal

from lean_report_card.config import Settings
from lean_report_card.github import ResolvedRepository

QueueName = Literal["small", "big"]


def choose_queue(
    resolved: ResolvedRepository,
    requested: Literal["auto", "small", "big"],
    settings: Settings,
) -> QueueName:
    if requested in {"small", "big"}:
        return requested
    slug = resolved.parsed.slug.lower()
    known_big = {
        item.strip().lower()
        for item in settings.known_big_repos.split(",")
        if item.strip()
    }
    if slug in known_big:
        return "big"
    if resolved.size_kib is not None and resolved.size_kib >= settings.big_repo_threshold_kib:
        return "big"
    return "small"

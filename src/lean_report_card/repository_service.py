from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from lean_report_card.config import Settings
from lean_report_card.github import ResolvedRepository
from lean_report_card.models import Report, Repository


CACHEABLE_STATUSES = {"queued", "running", "succeeded"}


def upsert_repository(db: Session, resolved: ResolvedRepository) -> Repository:
    repository = db.scalar(
        select(Repository).where(Repository.canonical_url == resolved.parsed.canonical_url)
    )
    if repository is None:
        repository = Repository(
            canonical_url=resolved.parsed.canonical_url,
            host="github.com",
            owner=resolved.parsed.owner,
            name=resolved.parsed.name,
        )
        db.add(repository)
    repository.default_branch = resolved.default_branch or repository.default_branch
    if resolved.size_kib is not None:
        repository.size_kib = resolved.size_kib
    repository.last_seen_sha = resolved.commit_sha
    db.flush()
    return repository


def find_cached_report(
    db: Session,
    repository_id: object,
    commit_sha: str,
    settings: Settings,
) -> Report | None:
    return db.scalar(
        select(Report)
        .options(selectinload(Report.repository))
        .where(
            Report.repository_id == repository_id,
            Report.commit_sha == commit_sha,
            Report.analyzer_version == settings.analyzer_version,
            Report.status.in_(CACHEABLE_STATUSES),
        )
        .order_by(desc(Report.requested_at))
        .limit(1)
    )


def get_report(db: Session, report_id: uuid.UUID | str) -> Report | None:
    normalized_id = report_id if isinstance(report_id, uuid.UUID) else uuid.UUID(report_id)
    return db.scalar(
        select(Report)
        .options(selectinload(Report.repository))
        .where(Report.id == normalized_id)
    )


def recent_reports(db: Session, limit: int = 20) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .options(selectinload(Report.repository))
            .order_by(desc(Report.requested_at))
            .limit(limit)
        )
    )


def repository_history(db: Session, repository_id: object, limit: int = 50) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .options(selectinload(Report.repository))
            .where(Report.repository_id == repository_id)
            .order_by(desc(Report.requested_at))
            .limit(limit)
        )
    )

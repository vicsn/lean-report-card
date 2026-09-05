from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScanRequest(BaseModel):
    repository: str = Field(examples=["https://github.com/leanprover-community/aesop"])
    ref: str | None = Field(default=None, max_length=250)
    queue: Literal["auto", "small", "big"] = "auto"
    force: bool = False


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_url: str
    host: str
    owner: str
    name: str
    default_branch: str | None
    size_kib: int | None
    last_seen_sha: str | None
    created_at: datetime
    updated_at: datetime


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    requested_ref: str | None
    analyzer_version: str
    queue_name: str
    status: str
    score: int | None
    grade: str | None
    summary: dict[str, Any] | None
    error: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: int | None
    repository: RepositoryOut


class ScanAccepted(BaseModel):
    report: ReportOut
    cache_hit: bool
    report_url: str

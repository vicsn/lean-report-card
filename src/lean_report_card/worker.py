from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from celery import Celery

from lean_report_card.analytics import capture_exception, init_analytics
from lean_report_card.config import get_settings
from lean_report_card.database import SessionLocal, init_db
from lean_report_card.docker_runner import (
    RunnerError,
    RunnerOOMError,
    RunnerTimedOut,
    run_analysis_container,
)
from lean_report_card.models import Report
from lean_report_card.repository_service import get_report
from lean_report_card.scoring import score_report

logger = logging.getLogger(__name__)
settings = get_settings()
init_analytics(settings)
celery_app = Celery("lean_report_card", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@celery_app.task(bind=True, name="lean_report_card.analyze_report")
def analyze_report(self: object, report_id: str) -> None:
    report_uuid = uuid.UUID(report_id)
    init_db()
    db = SessionLocal()
    started = _utcnow()
    try:
        report = get_report(db, report_uuid)
        if report is None:
            return
        if report.status not in {"queued", "running"}:
            return
        report.status = "running"
        report.started_at = started
        report.task_id = getattr(getattr(self, "request", None), "id", report.task_id)
        db.commit()

        payload = run_analysis_container(report, settings)
        if payload.get("analysis_status") != "completed":
            report.raw_report = payload
            raise RunnerError(str(payload.get("error") or "Analyzer did not complete."))
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            raise RunnerError("Analyzer output is missing a facts object.")
        scoring = score_report(facts)
        payload["scoring"] = scoring

        completed = _utcnow()
        report.status = "succeeded"
        report.score = int(scoring["score"])
        report.grade = str(scoring["grade"])
        report.summary = {
            "score": scoring["score"],
            "grade": scoring["grade"],
            "checks": scoring["checks"],
            "caveat": scoring["caveat"],
            "repository_stats": facts.get("static", {}),
            "commands": facts.get("commands", {}),
        }
        report.raw_report = payload
        report.error = None
        report.completed_at = completed
        report.duration_seconds = max(0, int((completed - started).total_seconds()))
        db.commit()
    except RunnerTimedOut as exc:
        completed = _utcnow()
        report = db.get(Report, report_uuid)
        if report is not None:
            report.status = "timed_out"
            report.error = str(exc)
            report.completed_at = completed
            report.duration_seconds = max(0, int((completed - started).total_seconds()))
            db.commit()
    except RunnerOOMError as exc:
        completed = _utcnow()
        report = db.get(Report, report_uuid)
        if report is not None:
            report.status = "oom_killed"
            report.error = str(exc)
            report.completed_at = completed
            report.duration_seconds = max(0, int((completed - started).total_seconds()))
            db.commit()
    except Exception as exc:  # noqa: BLE001 - task boundary must persist all failures
        logger.exception("Analysis failed for report %s", report_uuid)
        completed = _utcnow()
        report = db.get(Report, report_uuid)
        if report is not None:
            report.status = "failed"
            report.error = str(exc)
            report.completed_at = completed
            report.duration_seconds = max(0, int((completed - started).total_seconds()))
            db.commit()
        if not isinstance(exc, RunnerError):
            capture_exception(exc, {"phase": "analyze_report", "report_id": str(report_uuid)})
            raise
    finally:
        db.close()

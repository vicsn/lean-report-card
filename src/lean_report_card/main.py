from __future__ import annotations

import html
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, make_asgi_app
from sqlalchemy import desc, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from lean_report_card.analytics import capture, capture_exception, init_analytics
from lean_report_card.config import Settings, get_settings
from lean_report_card.database import engine, get_db, init_db
from lean_report_card.github import RepositoryInputError, RepositoryLookupError, resolve_repository
from lean_report_card.models import Report, Repository
from lean_report_card.queueing import choose_queue
from lean_report_card.repository_service import (
    find_cached_report,
    get_report,
    recent_reports,
    repository_history,
    upsert_repository,
)
from lean_report_card.schemas import ReportOut, ScanAccepted, ScanRequest
from lean_report_card.task_dispatch import enqueue_report

REQUESTS = Counter(
    "lrc_http_requests_total", "HTTP requests", labelnames=("method", "path", "status")
)
REQUEST_TIME = Histogram(
    "lrc_http_request_duration_seconds", "HTTP request duration", labelnames=("path",)
)
REPORT_REQUESTS = Counter(
    "lrc_report_requests_total", "Report submissions", labelnames=("queue", "cache_hit")
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    init_analytics(settings)
    yield


settings = get_settings()
PACKAGE_DIR = Path(__file__).resolve().parent
app = FastAPI(title=settings.app_name, version=settings.analyzer_version, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")
app.mount("/metrics", make_asgi_app())
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))
templates.env.globals["settings"] = settings


@app.middleware("http")
async def observe_requests(request: Request, call_next: Any) -> Response:
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        capture_exception(exc, {"method": request.method, "path": request.url.path})
        raise
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    REQUEST_TIME.labels(path=path).observe(time.perf_counter() - started)
    REQUESTS.labels(method=request.method, path=path, status=response.status_code).inc()
    return response


def _report_out(report: Report) -> ReportOut:
    return ReportOut.model_validate(report)


async def _submit(
    payload: ScanRequest,
    db: Session,
    app_settings: Settings,
) -> tuple[Report, bool]:
    resolved = await resolve_repository(payload.repository, payload.ref, app_settings)
    queue_name = choose_queue(resolved, payload.queue, app_settings)
    repository = upsert_repository(db, resolved)

    if not payload.force:
        cached = find_cached_report(db, repository.id, resolved.commit_sha, app_settings)
        if cached is not None:
            REPORT_REQUESTS.labels(queue=cached.queue_name, cache_hit="true").inc()
            db.commit()
            capture(
                "report_requested",
                {"queue": cached.queue_name, "cache_hit": True, "forced": False},
            )
            return cached, True

    report = Report(
        repository=repository,
        commit_sha=resolved.commit_sha,
        requested_ref=resolved.requested_ref,
        analyzer_version=app_settings.analyzer_version,
        queue_name=queue_name,
        status="queued",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        report.task_id = enqueue_report(str(report.id), queue_name)
    except Exception as exc:  # noqa: BLE001 - queue failure becomes report state
        capture_exception(exc, {"phase": "enqueue", "queue": queue_name})
        report.status = "failed"
        report.error = f"Unable to enqueue analysis: {exc}"
    db.commit()
    db.refresh(report)
    REPORT_REQUESTS.labels(queue=queue_name, cache_hit="false").inc()
    capture(
        "report_requested",
        {"queue": queue_name, "cache_hit": False, "forced": payload.force},
    )
    return report, False


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Annotated[Session, Depends(get_db)]) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"reports": recent_reports(db), "settings": settings, "error": None},
    )


@app.post("/scan", response_class=HTMLResponse)
async def scan_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[str, Form()],
    ref: Annotated[str | None, Form()] = None,
    queue: Annotated[str, Form()] = "auto",
    force: Annotated[bool, Form()] = False,
) -> Response:
    try:
        payload = ScanRequest(repository=repository, ref=ref or None, queue=queue, force=force)
        report, _ = await _submit(payload, db, settings)
        return RedirectResponse(url=f"/reports/{report.id}", status_code=status.HTTP_303_SEE_OTHER)
    except (RepositoryInputError, RepositoryLookupError, ValueError) as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"reports": recent_reports(db), "settings": settings, "error": str(exc)},
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@app.post("/api/v1/reports", response_model=ScanAccepted)
async def create_report(
    payload: ScanRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> ScanAccepted:
    try:
        report, cache_hit = await _submit(payload, db, settings)
    except RepositoryInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RepositoryLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    response.status_code = status.HTTP_200_OK if cache_hit else status.HTTP_202_ACCEPTED
    return ScanAccepted(
        report=_report_out(report),
        cache_hit=cache_hit,
        report_url=f"{settings.public_base_url.rstrip('/')}/reports/{report.id}",
    )


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def report_page(
    request: Request,
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    history = repository_history(db, report.repository_id, limit=20)
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={"report": report, "history": history, "settings": settings},
    )


@app.get("/api/v1/reports/{report_id}", response_model=ReportOut)
def report_api(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_out(report)


@app.get("/api/v1/reports/{report_id}/raw")
def report_raw(
    report_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse(report.raw_report or {"status": report.status, "error": report.error})


@app.get("/api/v1/repositories/{owner}/{name}/history", response_model=list[ReportOut])
def repository_history_api(
    owner: str,
    name: str,
    db: Annotated[Session, Depends(get_db)],
    limit: int = 20,
) -> list[ReportOut]:
    repository = db.scalar(
        select(Repository).where(
            Repository.owner.ilike(owner),
            Repository.name.ilike(name.removesuffix(".git")),
        )
    )
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    bounded_limit = max(1, min(limit, 100))
    return [_report_out(item) for item in repository_history(db, repository.id, bounded_limit)]


@app.get("/api/v1/repositories/{owner}/{name}/latest", response_model=ReportOut)
def repository_latest_api(
    owner: str,
    name: str,
    db: Annotated[Session, Depends(get_db)],
) -> ReportOut:
    report = db.scalar(
        select(Report)
        .join(Repository)
        .options(selectinload(Report.repository))
        .where(
            Repository.owner.ilike(owner),
            Repository.name.ilike(name.removesuffix(".git")),
            Report.status == "succeeded",
        )
        .order_by(desc(Report.completed_at))
        .limit(1)
    )
    if report is None:
        raise HTTPException(status_code=404, detail="No successful report found")
    return _report_out(report)


@app.get("/badge/{owner}/{name}.svg")
def badge(
    owner: str,
    name: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    report = db.scalar(
        select(Report)
        .join(Repository)
        .where(
            Repository.owner.ilike(owner),
            Repository.name.ilike(name.removesuffix(".git")),
            Report.status == "succeeded",
        )
        .order_by(desc(Report.completed_at))
        .limit(1)
    )
    value = f"{report.grade} · {report.score}" if report and report.grade else "unknown"
    safe_value = html.escape(value)
    label_width = 102
    value_width = max(72, 8 * len(value) + 18)
    total = label_width + value_width
    value_midpoint = label_width + value_width / 2
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20"
 role="img" aria-label="Lean report: {safe_value}">
<linearGradient id="s" x2="0" y2="100%">
  <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
  <stop offset="1" stop-opacity=".1"/>
</linearGradient>
<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)">
  <rect width="{label_width}" height="20" fill="#555"/>
  <rect x="{label_width}" width="{value_width}" height="20" fill="#337ab7"/>
  <rect width="{total}" height="20" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif"
 font-size="11">
  <text x="51" y="15" fill="#010101" fill-opacity=".3">lean report</text>
  <text x="51" y="14">lean report</text>
  <text x="{value_midpoint}" y="15" fill="#010101" fill-opacity=".3">{safe_value}</text>
  <text x="{value_midpoint}" y="14">{safe_value}</text>
</g>
</svg>"""
    headers = {"Cache-Control": "public, max-age=300"}
    return Response(svg, media_type="image/svg+xml", headers=headers)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}

from __future__ import annotations

import logging
from typing import Any

from lean_report_card.config import Settings

logger = logging.getLogger(__name__)

_client: Any = None
_initialized = False
_SERVER_DISTINCT_ID = "lean-report-card-server"


def init_analytics(settings: Settings) -> None:
    global _client, _initialized
    if _initialized:
        return
    _initialized = True
    if not settings.posthog_project_token:
        return
    from posthog import Posthog

    _client = Posthog(
        settings.posthog_project_token,
        host=settings.posthog_host,
        disable_geoip=True,
        enable_exception_autocapture=False,
    )


def analytics_enabled() -> bool:
    return _client is not None


def reset_for_tests() -> None:
    global _client, _initialized
    _client = None
    _initialized = False


def capture(event: str, properties: dict[str, Any] | None = None) -> None:
    if _client is None:
        return
    payload = {"$process_person_profile": False, **(properties or {})}
    try:
        _client.capture(_SERVER_DISTINCT_ID, event, payload)
    except Exception:  # noqa: BLE001 - analytics must not break the service
        logger.exception("PostHog capture failed for %s", event)


def capture_exception(exc: BaseException, properties: dict[str, Any] | None = None) -> None:
    if _client is None:
        return
    payload = {"$process_person_profile": False, **(properties or {})}
    try:
        _client.capture_exception(
            exc,
            distinct_id=_SERVER_DISTINCT_ID,
            properties=payload,
        )
    except Exception:  # noqa: BLE001 - analytics must not break the service
        logger.exception("PostHog exception capture failed")

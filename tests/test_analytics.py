from __future__ import annotations

from lean_report_card.analytics import (
    analytics_enabled,
    capture,
    capture_exception,
    init_analytics,
    reset_for_tests,
)
from lean_report_card.config import Settings


def test_analytics_disabled_without_token() -> None:
    reset_for_tests()
    init_analytics(Settings(posthog_project_token=""))
    assert analytics_enabled() is False
    capture("report_requested", {"queue": "small"})
    capture_exception(RuntimeError("boom"))


def test_init_is_idempotent(monkeypatch) -> None:
    reset_for_tests()
    created: list[object] = []

    class FakePosthog:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created.append(kwargs)

        def capture(self, *args: object, **kwargs: object) -> None:
            return None

        def capture_exception(self, *args: object, **kwargs: object) -> None:
            return None

    monkeypatch.setattr("posthog.Posthog", FakePosthog)
    settings = Settings(posthog_project_token="phc_test", posthog_host="https://us.i.posthog.com")
    init_analytics(settings)
    init_analytics(settings)
    assert analytics_enabled() is True
    assert len(created) == 1
    reset_for_tests()

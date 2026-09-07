from __future__ import annotations

from fastapi.testclient import TestClient

from lean_report_card.main import app


def test_health_and_index() -> None:
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").status_code == 200
        response = client.get("/")
        assert response.status_code == 200
        assert "Lean Report Card" in response.text
        assert "posthog" not in response.text.lower()


def test_unknown_badge_svg() -> None:
    with TestClient(app) as client:
        response = client.get("/badge/missing/repo.svg")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")
        assert "unknown" in response.text

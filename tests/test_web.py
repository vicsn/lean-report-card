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
        assert "posthog.init" in response.text
        assert "phc_s94Q4HVoFQHHZCXNvYYY84f9FKuDjGFKgwpBCWjwGr2K" in response.text
        assert "cookieless_mode" in response.text
        assert "Anonymous page views" in response.text


def test_index_omits_posthog_when_token_cleared(monkeypatch) -> None:
    from lean_report_card import main

    monkeypatch.setattr(main.settings, "posthog_project_token", "")
    with TestClient(app) as client:
        assert "posthog.init" not in client.get("/").text

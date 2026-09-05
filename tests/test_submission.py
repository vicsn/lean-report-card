from __future__ import annotations

from fastapi.testclient import TestClient

from lean_report_card import main
from lean_report_card.database import SessionLocal
from lean_report_card.github import ParsedRepository, ResolvedRepository


async def fake_resolve(repository: str, ref: str | None, settings: object) -> ResolvedRepository:
    del repository, settings
    return ResolvedRepository(
        parsed=ParsedRepository(owner="fixture-owner", name="fixture-repo"),
        commit_sha="b" * 40,
        requested_ref=ref,
        default_branch="main",
        size_kib=10,
    )


def test_submission_is_queued_then_cached(monkeypatch: object) -> None:
    queued: list[tuple[str, str]] = []

    def fake_enqueue(report_id: str, queue_name: str) -> str:
        queued.append((report_id, queue_name))
        return "task-fixture"

    monkeypatch.setattr(main, "resolve_repository", fake_resolve)  # type: ignore[attr-defined]
    monkeypatch.setattr(main, "enqueue_report", fake_enqueue)  # type: ignore[attr-defined]

    with TestClient(main.app) as client:
        payload = {"repository": "fixture-owner/fixture-repo", "queue": "auto"}
        first = client.post("/api/v1/reports", json=payload)
        second = client.post("/api/v1/reports", json=payload)

    assert first.status_code == 202
    assert first.json()["cache_hit"] is False
    assert first.json()["report"]["queue_name"] == "small"
    assert second.status_code == 200
    assert second.json()["cache_hit"] is True
    assert second.json()["report"]["id"] == first.json()["report"]["id"]
    assert len(queued) == 1


def test_report_lookup_accepts_celery_string_id(monkeypatch: object) -> None:
    monkeypatch.setattr(main, "resolve_repository", fake_resolve)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main,
        "enqueue_report",
        lambda report_id, queue_name: "task-fixture",
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/reports",
            json={"repository": "fixture-owner/fixture-repo", "force": True},
        )
        report_id = response.json()["report"]["id"]

    with SessionLocal() as db:
        report = main.get_report(db, report_id)

    assert report is not None
    assert str(report.id) == report_id


def test_forced_rescans_remain_in_repository_history(monkeypatch: object) -> None:
    async def resolve_history(
        repository: str, ref: str | None, settings: object
    ) -> ResolvedRepository:
        del repository, settings
        return ResolvedRepository(
            parsed=ParsedRepository(owner="fixture-owner", name="history-repo"),
            commit_sha="c" * 40,
            requested_ref=ref,
            default_branch="main",
            size_kib=10,
        )

    monkeypatch.setattr(main, "resolve_repository", resolve_history)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        main,
        "enqueue_report",
        lambda report_id, queue_name: f"task-{report_id}",
    )

    with TestClient(main.app) as client:
        first = client.post(
            "/api/v1/reports",
            json={"repository": "fixture-owner/history-repo", "force": True},
        )
        second = client.post(
            "/api/v1/reports",
            json={"repository": "fixture-owner/history-repo", "force": True},
        )
        history = client.get(
            "/api/v1/repositories/fixture-owner/history-repo/history"
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert history.status_code == 200
    reports = history.json()
    assert len(reports) == 2
    assert reports[0]["id"] != reports[1]["id"]
    assert {item["commit_sha"] for item in reports} == {"c" * 40}

from __future__ import annotations


def enqueue_report(report_id: str, queue_name: str) -> str:
    """Queue a report without importing Celery during read-only web startup/tests."""
    from lean_report_card.worker import analyze_report

    task = analyze_report.apply_async(args=[report_id], queue=queue_name)
    return str(task.id)

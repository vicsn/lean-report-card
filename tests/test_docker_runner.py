from __future__ import annotations

from types import SimpleNamespace

import pytest

from lean_report_card.docker_runner import container_was_oom_killed, memory_to_bytes


def test_memory_to_bytes() -> None:
    assert memory_to_bytes("4g") == 4 * 1024**3
    assert memory_to_bytes("512m") == 512 * 1024**2
    assert memory_to_bytes("1GiB") == 1024**3


def test_memory_to_bytes_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        memory_to_bytes("0g")


def test_container_was_oom_killed_from_state() -> None:
    container = SimpleNamespace(attrs={"State": {"OOMKilled": True}})
    container.reload = lambda: None
    assert container_was_oom_killed(container, 1) is True


def test_container_was_oom_killed_from_exit_code() -> None:
    container = SimpleNamespace(attrs={"State": {"OOMKilled": False}})
    container.reload = lambda: None
    assert container_was_oom_killed(container, 137) is True
    assert container_was_oom_killed(container, 1) is False

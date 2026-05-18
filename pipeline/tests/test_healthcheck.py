from __future__ import annotations

from reservoirs.healthcheck import ping_healthcheck


def test_ping_healthcheck_noops_without_url(monkeypatch) -> None:
    monkeypatch.delenv("HEALTHCHECK_URL", raising=False)

    assert ping_healthcheck() is False

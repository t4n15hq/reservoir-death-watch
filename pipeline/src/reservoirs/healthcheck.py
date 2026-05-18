"""Healthcheck ping helpers for scheduled pipeline runs."""

from __future__ import annotations

import os

import requests


def ping_healthcheck(url: str | None = None, *, timeout: int = 10) -> bool:
    """Ping healthchecks.io when configured.

    Local development runs have no `HEALTHCHECK_URL`, so this is a no-op there.
    """

    target = url or os.environ.get("HEALTHCHECK_URL")
    if not target:
        return False
    response = requests.get(target, timeout=timeout)
    response.raise_for_status()
    return True

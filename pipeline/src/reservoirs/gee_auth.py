"""Google Earth Engine authentication helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_CREDENTIALS_PATH = (
    Path.home()
    / ".secrets"
    / "reservoir-death-watch"
    / "reservoir-death-watch-0bc6b0a1aa14.json"
)
ALTERNATE_CREDENTIALS_PATHS = (
    DEFAULT_CREDENTIALS_PATH,
    Path.home() / ".secrets" / "reservoir-death-watch" / "gee_service_account.json"
)


class GEEAuthError(RuntimeError):
    """Raised when Earth Engine credentials are missing or unusable."""


def resolve_credentials_path(credentials_path: str | Path | None = None) -> Path:
    """Resolve the service account JSON path.

    Priority:
    1. Explicit function argument
    2. GOOGLE_APPLICATION_CREDENTIALS
    3. Local development defaults under ~/.secrets/reservoir-death-watch
    """

    raw_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not raw_path:
        for candidate in ALTERNATE_CREDENTIALS_PATHS:
            if candidate.exists():
                return candidate
        raw_path = DEFAULT_CREDENTIALS_PATH

    path = Path(raw_path).expanduser()
    if not path.exists():
        expected_paths = ", ".join(str(path) for path in ALTERNATE_CREDENTIALS_PATHS)
        msg = (
            "Earth Engine service account JSON not found. Set "
            "GOOGLE_APPLICATION_CREDENTIALS or place it at "
            f"one of: {expected_paths}."
        )
        raise GEEAuthError(msg)
    return path


def load_service_account_info(credentials_path: str | Path | None = None) -> dict:
    """Load non-secret metadata from the service account JSON."""

    path = resolve_credentials_path(credentials_path)
    with path.open(encoding="utf-8") as handle:
        info = json.load(handle)

    if info.get("type") != "service_account":
        raise GEEAuthError("credentials JSON is not a service account key")
    if not info.get("client_email"):
        raise GEEAuthError("credentials JSON is missing client_email")
    if not info.get("project_id"):
        raise GEEAuthError("credentials JSON is missing project_id")
    return info


def initialize_earth_engine(
    credentials_path: str | Path | None = None,
    *,
    project: str | None = None,
) -> None:
    """Initialize Earth Engine with a service account JSON key."""

    path = resolve_credentials_path(credentials_path)
    info = load_service_account_info(path)

    try:
        import ee
    except ImportError as exc:
        msg = "earthengine-api is not installed. Install the pipeline dependencies first."
        raise GEEAuthError(msg) from exc

    credentials = ee.ServiceAccountCredentials(info["client_email"], str(path))
    ee.Initialize(credentials, project=project or info["project_id"])

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reservoirs.gee_auth import GEEAuthError, load_service_account_info, resolve_credentials_path


def _write_service_account(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "reservoir-death-watch",
                "client_email": "rdw-pipeline@reservoir-death-watch.iam.gserviceaccount.com",
                "private_key": "not-a-real-key",
            }
        ),
        encoding="utf-8",
    )


def test_resolve_credentials_path_prefers_explicit_path(tmp_path: Path) -> None:
    credentials = tmp_path / "service-account.json"
    _write_service_account(credentials)

    assert resolve_credentials_path(credentials) == credentials


def test_resolve_credentials_path_uses_google_application_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = tmp_path / "service-account.json"
    _write_service_account(credentials)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials))

    assert resolve_credentials_path() == credentials


def test_resolve_credentials_path_falls_back_to_default_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = tmp_path / "reservoir-death-watch-0bc6b0a1aa14.json"
    _write_service_account(credentials)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr("reservoirs.gee_auth.ALTERNATE_CREDENTIALS_PATHS", (credentials,))
    monkeypatch.setattr("reservoirs.gee_auth.DEFAULT_CREDENTIALS_PATH", credentials)

    assert resolve_credentials_path() == credentials


def test_load_service_account_info_validates_shape(tmp_path: Path) -> None:
    credentials = tmp_path / "service-account.json"
    _write_service_account(credentials)

    info = load_service_account_info(credentials)

    assert info["project_id"] == "reservoir-death-watch"
    assert info["client_email"] == "rdw-pipeline@reservoir-death-watch.iam.gserviceaccount.com"


def test_load_service_account_info_rejects_wrong_json_type(tmp_path: Path) -> None:
    credentials = tmp_path / "not-service-account.json"
    credentials.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")

    with pytest.raises(GEEAuthError):
        load_service_account_info(credentials)

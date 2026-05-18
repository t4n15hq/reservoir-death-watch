"""Atomic dashboard data export helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel


def write_json_atomic(path: Path, payload: BaseModel | dict) -> None:
    """Write JSON through a temp file, fsync, then rename."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload

    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    tmp_path.replace(path)


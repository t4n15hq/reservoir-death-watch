"""Shared filesystem paths and constants for the pipeline."""

from __future__ import annotations

from pathlib import Path

MODEL_VERSION = "1.0.0"

PIPELINE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PIPELINE_ROOT.parent
DOCS_DIR = REPO_ROOT / "docs"
RESERVOIRS_CSV = DOCS_DIR / "reservoirs.csv"
AOI_DIR = PIPELINE_ROOT / "data" / "aois"
CWC_DIR = PIPELINE_ROOT / "data" / "cwc"
CWC_BULLETINS_GLOB = "bulletin_*.csv"
CWC_PHASE0_STORAGE_CSV = CWC_DIR / "phase0_storage_2026_04_09.csv"
CWC_NAME_ALIASES_CSV = CWC_DIR / "cwc_name_aliases.csv"
DASHBOARD_DATA_DIR = REPO_ROOT / "dashboard" / "public" / "data"

DEFAULT_WINDOW_DAYS = 90
DEFAULT_DEAD_STORAGE_AREA_FRACTION = 0.10
PHASE0_GATE_TOLERANCE = 0.10
PHASE0_GATE_WINDOW_DAYS = 180

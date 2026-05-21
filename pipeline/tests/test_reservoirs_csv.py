"""Structural integrity test for `docs/reservoirs.csv`.

This is the master list driving every phase. A bad row here cascades
silently into AOI loading, the pipeline, and the dashboard — pin it.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from reservoirs.config import RESERVOIRS_CSV

REQUIRED_FIELDS = (
    "id",
    "name",
    "river",
    "state",
    "cwc_name",
    "lat",
    "lon",
    "priority",
    "aoi_file",
    "scope",
)
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
EXPECTED_ROWS = 53
EXPECTED_CORE_ROWS = 25
ALLOWED_SCOPES = {"core_city", "expanded_cwc"}

# Coarse India lat/lon bounding box, slightly padded for offshore island groups.
LAT_RANGE = (6.0, 37.0)
LON_RANGE = (67.0, 98.5)


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    return list(csv.DictReader(RESERVOIRS_CSV.open()))


def test_row_count_matches_curated_universe(rows):
    assert len(rows) == EXPECTED_ROWS, (
        f"expected {EXPECTED_ROWS} curated core + expanded reservoirs, got {len(rows)}. "
        f"See docs/PRD.md for scope rationale."
    )


def test_every_row_has_city_or_region_label(rows):
    """Rows must show an understandable beneficiary label in the UI."""

    missing = [r["id"] for r in rows if not r.get("city_served", "").strip()]
    assert not missing, f"rows without city_served: {missing}"


def test_scope_is_explicit_and_core_count_is_pinned(rows):
    bad = [r["id"] for r in rows if r.get("scope") not in ALLOWED_SCOPES]
    assert not bad, f"rows with invalid scope: {bad}"
    core = [r for r in rows if r["scope"] == "core_city"]
    assert len(core) == EXPECTED_CORE_ROWS


def test_required_fields_present(rows):
    for row in rows:
        for field in REQUIRED_FIELDS:
            assert row.get(field), f"reservoir {row.get('id')!r} missing required field {field!r}"


def test_ids_are_unique_and_snake_case(rows):
    ids = [r["id"] for r in rows]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate ids: {duplicates}"
    bad = [i for i in ids if not ID_PATTERN.match(i)]
    assert not bad, f"ids must match {ID_PATTERN.pattern}: {bad}"


def test_priorities_form_contiguous_range(rows):
    priorities = sorted(int(r["priority"]) for r in rows)
    assert priorities == list(range(1, EXPECTED_ROWS + 1)), (
        f"priorities must be 1..{EXPECTED_ROWS} with no gaps or duplicates"
    )


def test_coordinates_lie_within_india_bounds(rows):
    out_of_bounds = []
    for row in rows:
        lat = float(row["lat"])
        lon = float(row["lon"])
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            out_of_bounds.append((row["id"], lat, lon))
    assert not out_of_bounds, f"coordinates outside India bbox: {out_of_bounds}"


def test_aoi_file_path_matches_id(rows):
    for row in rows:
        expected = f"pipeline/data/aois/{row['id']}.geojson"
        assert row["aoi_file"] == expected, (
            f"reservoir {row['id']!r}: aoi_file is {row['aoi_file']!r}, expected {expected!r}"
        )


def test_capacities_when_present_are_positive(rows):
    for row in rows:
        for field in ("full_pool_capacity_bcm", "dead_storage_capacity_bcm"):
            value = row.get(field)
            if value:
                assert float(value) >= 0, f"{row['id']}.{field}={value} must be ≥ 0"


def test_phase0_reservoirs_have_aoi_files_on_disk():
    """Phase 0 (priority 1–3) is shipped; their AOI files must exist."""
    phase0_ids = {"krs", "mettur", "indira_sagar"}
    for row in csv.DictReader(RESERVOIRS_CSV.open()):
        if row["id"] in phase0_ids:
            aoi_path = Path(__file__).resolve().parents[2] / row["aoi_file"]
            assert aoi_path.exists(), f"phase 0 AOI missing on disk: {aoi_path}"

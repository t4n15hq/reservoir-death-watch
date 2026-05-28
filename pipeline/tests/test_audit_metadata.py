"""Pins what we know about each reservoir's metadata against the audit script.

Backstop against silent metadata regressions. The audit script writes
data_provenance.json; the dashboard surfaces those counts in the Data
Quality card. If counts shift in either direction, this test forces an
explicit acknowledgement.

Update the expected counts here whenever you legitimately verify another
reservoir (e.g. drop a CWC bulletin for it, update coord_verified_at, etc.).
"""

from __future__ import annotations

import csv
from datetime import date

import pytest

from reservoirs.config import RESERVOIRS_CSV
from scripts.audit_metadata import build_health, build_provenance  # type: ignore[import-not-found]


@pytest.fixture(scope="module")
def provenance() -> dict:
    # Add the scripts dir to importable path. Pytest's rootdir is `pipeline/`.
    return build_provenance()


def test_total_reservoirs_matches_csv(provenance):
    rows = list(csv.DictReader(RESERVOIRS_CSV.open()))
    assert provenance["counts"]["total_reservoirs"] == len(rows) == 53


def test_cwc_anchored_count_pins_current_bulletin_ingest(provenance):
    """As of the expanded-scope audit, seven local CWC bulletins match 52
    reservoirs. Expanded rows now have JRC history and current Sentinel
    observations; dense recent Sentinel-2 series remains flagged separately."""

    assert provenance["counts"]["cwc_reference_available"] == 52, (
        "CWC reference count changed. If you added a bulletin, update this "
        "expected value AND re-confirm docs/PROVENANCE.md counts."
    )
    assert provenance["counts"]["storage_cwc_calibrated"] == 51, (
        "CWC-calibrated count changed. If you added a bulletin, update this "
        "expected value AND re-confirm docs/PROVENANCE.md counts."
    )


def test_metadata_verification_is_explicit(provenance):
    """Only CWC-covered reservoirs have FRL capacity from CWC; no reservoir
    has dead-storage capacity or population externally sourced yet.

    Coordinate verification ticks up as `coord_source` is populated; the
    remaining source checks tick up as you fill `dead_storage_source` and
    `population_source` in docs/reservoirs.csv. The dashboard's
    Data Quality card shows these explicitly so readers know what's
    measured vs editorial.
    """

    c = provenance["counts"]
    assert c["lat_lon_verified"] == 10, "bump test when coord_source coverage changes"
    assert c["full_pool_capacity_from_cwc"] == 52, "bump test when CWC rows change"
    assert c["aoi_available"] == 53, "bump test when AOI availability changes"
    assert c["dead_storage_capacity_verified"] == 0, (
        "bump test only after adding an explicit dead-storage source"
    )
    assert c["capacity_verified_against_cwc"] == 0, (
        "full capacity is not fully verified until both FRL and dead-storage "
        "capacity have external sources"
    )
    assert c["population_verified_against_census"] == 0, (
        "bump test when population_source populated"
    )


def test_health_summary_tracks_freshness_and_current_only(provenance):
    snapshot = {
        "generated_at": "2026-05-25T00:00:00Z",
        "model_version": "test",
        "reservoirs": [
            {"id": "fresh", "flags": [], "current": {"as_of": "2026-05-20"}},
            {
                "id": "current-only",
                "flags": ["current_only_no_history"],
                "current": {"as_of": "2026-05-18"},
            },
            {"id": "pending", "flags": [], "current": {"as_of": "1900-01-01"}},
        ],
    }

    health = build_health(snapshot, provenance, today=date(2026, 5, 25))

    assert health["status"] == "stale"
    assert health["total_reservoirs"] == 3
    assert health["fresh_within_14_days"] == 2
    assert health["fresh_percent"] == 66.7
    assert health["current_only_reservoirs"] == 1
    assert health["max_observation_age_days"] == 7


def test_cwc_capacity_values_come_from_cwc_rows(provenance):
    by_id = {r["id"]: r for r in provenance["reservoirs"]}

    assert by_id["krs"]["full_pool_capacity_bcm"]["value"] == 1.163
    assert by_id["indira_sagar"]["full_pool_capacity_bcm"]["value"] == 9.745
    assert by_id["hirakud"]["full_pool_capacity_bcm"]["value"] == 5.378
    assert by_id["krs"]["full_pool_capacity_bcm"]["source"].startswith("CWC bulletin")
    assert by_id["indira_sagar"]["dead_storage_capacity_bcm"]["verified"] is False


def test_every_reservoir_classified(provenance):
    """Each row in the master CSV must show up in the provenance JSON
    so the dashboard can render its data-quality card without falling back."""

    seen_ids = {r["id"] for r in provenance["reservoirs"]}
    rows = list(csv.DictReader(RESERVOIRS_CSV.open()))
    csv_ids = {r["id"] for r in rows}
    assert seen_ids == csv_ids


def test_core_aoi_files_are_distinct_from_manual_review(provenance):
    by_id = {r["id"]: r for r in provenance["reservoirs"]}

    assert by_id["srisailam"]["scope"] == "core_city"
    assert by_id["srisailam"]["aoi"]["available"] is True
    assert by_id["srisailam"]["aoi"]["verified"] is False
    assert by_id["hirakud"]["scope"] == "expanded_cwc"
    assert by_id["hirakud"]["aoi"]["available"] is True
    assert by_id["hirakud"]["aoi"]["verified"] is False


def test_storage_method_is_one_of_known_classifications(provenance):
    """Catches a schema drift where the audit classifies a reservoir into
    an unknown bucket."""

    allowed = {
        "cwc_calibrated_power_law",
        "cwc_live_reference",
        "area_ratio_proxy",
        "pending",
        "unknown",
    }
    for r in provenance["reservoirs"]:
        method = r["storage_calibration"]["method"]
        assert method in allowed, f"reservoir {r['id']} storage method '{method}' not recognised"

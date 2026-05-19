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

import pytest

from reservoirs.config import RESERVOIRS_CSV
from scripts.audit_metadata import build_provenance  # type: ignore[import-not-found]


@pytest.fixture(scope="module")
def provenance() -> dict:
    # Add the scripts dir to importable path. Pytest's rootdir is `pipeline/`.
    return build_provenance()


def test_total_reservoirs_matches_csv(provenance):
    rows = list(csv.DictReader(RESERVOIRS_CSV.open()))
    assert provenance["counts"]["total_reservoirs"] == len(rows) == 25


def test_cwc_anchored_count_pins_at_three(provenance):
    """As of last audit: KRS, Mettur, Indira Sagar. Goes up when you add
    more CWC bulletin CSVs (drop into pipeline/data/cwc/)."""

    assert provenance["counts"]["storage_cwc_calibrated"] == 3, (
        "CWC-calibrated count changed. If you added a bulletin, update this "
        "expected value AND re-confirm docs/PROVENANCE.md counts."
    )


def test_metadata_verification_is_zero_by_default(provenance):
    """No reservoir has lat/lon, capacity, or population verified yet.

    These start at zero and tick up as you populate `coord_verified_at`,
    `population_source` columns in docs/reservoirs.csv. The dashboard's
    Data Quality card shows these explicitly so readers know what's
    measured vs editorial.
    """

    c = provenance["counts"]
    assert c["lat_lon_verified"] == 0, "bump test when coord_verified_at populated"
    assert c["capacity_verified_against_cwc"] == 0 or c["capacity_verified_against_cwc"] == 3, (
        "CWC anchor count drives capacity verification: 3 (Phase 0) or 0 (no data)"
    )
    assert c["population_verified_against_census"] == 0, (
        "bump test when population_source populated"
    )


def test_every_reservoir_classified(provenance):
    """Each row in the master CSV must show up in the provenance JSON
    so the dashboard can render its data-quality card without falling back."""

    seen_ids = {r["id"] for r in provenance["reservoirs"]}
    rows = list(csv.DictReader(RESERVOIRS_CSV.open()))
    csv_ids = {r["id"] for r in rows}
    assert seen_ids == csv_ids


def test_storage_method_is_one_of_known_classifications(provenance):
    """Catches a schema drift where the audit classifies a reservoir into
    an unknown bucket."""

    allowed = {"cwc_calibrated_power_law", "area_ratio_proxy", "pending", "unknown"}
    for r in provenance["reservoirs"]:
        method = r["storage_calibration"]["method"]
        assert method in allowed, f"reservoir {r['id']} storage method '{method}' not recognised"

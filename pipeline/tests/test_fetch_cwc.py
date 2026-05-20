"""Tests for the offline parts of `scripts/fetch_data_gov_in.py`.

We don't try to mock HTTP calls — the value of the script is in
(a) column-name resolution across schema drift, (b) record →
bulletin-CSV transformation, (c) MCM → BCM conversion math. Those
are all pure functions.

The earlier `fetch_cwc_bulletin.py` (RSMS PDF scraper) is now a
deprecated stub and has no test surface.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_data_gov_in import (  # noqa: E402
    CWC_STORAGE_REQUIRED_COLUMNS,
    RESOURCE_ID,
    pick,
    to_bulletin_rows,
)


def test_pick_finds_canonical_name() -> None:
    record = {"reservoir_name": "Mettur", "state": "Tamil Nadu"}
    assert pick(record, "reservoir_name") == "Mettur"
    assert pick(record, "state") == "Tamil Nadu"


def test_pick_falls_back_through_candidates() -> None:
    # data.gov.in has at times used title-case, ALL-CAPS, and "Dam_Name".
    record_titlecase = {"Reservoir_Name": "Mettur"}
    record_allcaps = {"RESERVOIR": "Mettur"}
    record_damname = {"Dam_Name": "Mettur"}
    assert pick(record_titlecase, "reservoir_name") == "Mettur"
    assert pick(record_allcaps, "reservoir_name") == "Mettur"
    assert pick(record_damname, "reservoir_name") == "Mettur"


def test_pick_returns_none_for_missing_or_empty() -> None:
    assert pick({}, "reservoir_name") is None
    assert pick({"reservoir_name": ""}, "reservoir_name") is None
    assert pick({"reservoir_name": "NA"}, "reservoir_name") is None


def test_to_bulletin_rows_writes_required_columns() -> None:
    records = [
        {
            "reservoir_name": "Mettur",
            "date": "2026-04-09",
            "current_live_storage": "1254.0",  # MCM
            "live_capacity_at_frl": "2647.0",  # MCM
            "percentage_storage": "47.37",
        }
    ]
    aliases = {"Mettur": "mettur"}
    frame = to_bulletin_rows(records, aliases=aliases, since=None)
    assert list(frame.columns) == list(CWC_STORAGE_REQUIRED_COLUMNS)
    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["reservoir_id"] == "mettur"
    # MCM → BCM conversion (divide by 1000).
    assert abs(row["live_storage_bcm"] - 1.254) < 1e-9
    assert abs(row["live_capacity_at_frl_bcm"] - 2.647) < 1e-9
    assert abs(row["percent_frl"] - 47.37) < 1e-6
    # Daily feed doesn't carry long-period averages.
    assert row["normal_storage_bcm"] is None or str(row["normal_storage_bcm"]) == "nan"
    assert row["percent_normal"] is None or str(row["percent_normal"]) == "nan"
    assert row["source_url"].endswith(RESOURCE_ID)


def test_to_bulletin_rows_drops_unknown_reservoirs() -> None:
    records = [
        {"reservoir_name": "Mettur", "date": "2026-04-09",
         "current_live_storage": "1254", "live_capacity_at_frl": "2647"},
        {"reservoir_name": "SomeOtherDam", "date": "2026-04-09",
         "current_live_storage": "100", "live_capacity_at_frl": "200"},
    ]
    frame = to_bulletin_rows(records, aliases={"Mettur": "mettur"}, since=None)
    assert len(frame) == 1
    assert frame.iloc[0]["reservoir_id"] == "mettur"


def test_to_bulletin_rows_alias_match_is_case_insensitive() -> None:
    records = [
        {"reservoir_name": "METTUR", "date": "2026-04-09",
         "current_live_storage": "1254", "live_capacity_at_frl": "2647"},
    ]
    frame = to_bulletin_rows(records, aliases={"Mettur": "mettur"}, since=None)
    assert len(frame) == 1
    assert frame.iloc[0]["reservoir_id"] == "mettur"


def test_to_bulletin_rows_filters_by_since() -> None:
    records = [
        {"reservoir_name": "Mettur", "date": "2026-04-09",
         "current_live_storage": "1254", "live_capacity_at_frl": "2647"},
        {"reservoir_name": "Mettur", "date": "2026-01-01",
         "current_live_storage": "1500", "live_capacity_at_frl": "2647"},
    ]
    frame = to_bulletin_rows(
        records, aliases={"Mettur": "mettur"}, since=date(2026, 3, 1)
    )
    assert len(frame) == 1
    assert frame.iloc[0]["date"] == date(2026, 4, 9)


def test_to_bulletin_rows_computes_percent_when_missing() -> None:
    # If the API omits percentage_storage we compute it from the two values.
    records = [
        {"reservoir_name": "Mettur", "date": "2026-04-09",
         "current_live_storage": "1000", "live_capacity_at_frl": "2000"},
    ]
    frame = to_bulletin_rows(records, aliases={"Mettur": "mettur"}, since=None)
    assert abs(frame.iloc[0]["percent_frl"] - 50.0) < 1e-9

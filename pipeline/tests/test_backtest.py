"""Phase 1 historical backtests.

These call into the live pipeline against historical `as_of` dates. They
require Earth Engine credentials and the AOI files for KRS, Mettur, and
Jayakwadi. When credentials or AOIs are missing they skip with a clear
reason — they do not silently pass.

Per `docs/BACKTESTS.md`, do **not** tune thresholds to make these pass.
Investigate area-volume calibration, then regression window, then El Niño
delta, in that order.
"""

from __future__ import annotations

import json
import os
from datetime import date

import pytest

from reservoirs.backtest import BACKTEST_CASES
from reservoirs.config import AOI_DIR, DASHBOARD_DATA_DIR
from reservoirs.schemas import DashboardSnapshot

REQUIRES_EE = pytest.mark.skipif(
    not os.environ.get("RDW_RUN_BACKTESTS"),
    reason=(
        "Backtests require Earth Engine credentials and pull historical satellite "
        "data; opt in with RDW_RUN_BACKTESTS=1."
    ),
)


def _require_aoi(reservoir_id: str) -> None:
    path = AOI_DIR / f"{reservoir_id}.geojson"
    if not path.exists():
        pytest.skip(f"AOI not yet digitized: {path}")


def _run(reservoir_id: str, as_of: date):
    # Imported lazily so tests can collect even when EE isn't installed.
    from reservoirs.pipeline import run_pipeline

    snapshot = run_pipeline(as_of=as_of, reservoirs=[reservoir_id], export=False)
    assert len(snapshot.reservoirs) == 1
    return snapshot.reservoirs[0]


@REQUIRES_EE
def test_krs_dec_2023_flagged_critical() -> None:
    case = BACKTEST_CASES["krs_2023_12_31"]
    _require_aoi(case["reservoir_id"])
    result = _run(case["reservoir_id"], case["as_of"])
    assert result.tier in case["tiers"], (
        f"KRS @ {case['as_of']}: expected one of {case['tiers']}, got {result.tier}. "
        f"Investigate area-volume curve first, then regression window, then El Niño delta."
    )


@REQUIRES_EE
def test_mettur_march_2019_flagged() -> None:
    case = BACKTEST_CASES["mettur_2019_03_31"]
    _require_aoi(case["reservoir_id"])
    result = _run(case["reservoir_id"], case["as_of"])
    assert result.tier in case["tiers"], (
        f"Mettur @ {case['as_of']}: expected one of {case['tiers']}, got {result.tier}."
    )


@REQUIRES_EE
def test_jayakwadi_2016_flagged() -> None:
    case = BACKTEST_CASES["jayakwadi_2016_03_31"]
    _require_aoi(case["reservoir_id"])
    result = _run(case["reservoir_id"], case["as_of"])
    assert result.tier in case["tiers"], (
        f"Jayakwadi @ {case['as_of']}: expected one of {case['tiers']}, got {result.tier}."
    )


@REQUIRES_EE
def test_jayakwadi_2019_flagged() -> None:
    case = BACKTEST_CASES["jayakwadi_2019_03_31"]
    _require_aoi(case["reservoir_id"])
    result = _run(case["reservoir_id"], case["as_of"])
    assert result.tier in case["tiers"], (
        f"Jayakwadi @ {case['as_of']}: expected one of {case['tiers']}, got {result.tier}."
    )


def test_backtest_cases_metadata_is_complete() -> None:
    """Cheap structural check that always runs — catches typos in BACKTEST_CASES."""

    expected = {
        "krs_2023_12_31",
        "mettur_2019_03_31",
        "jayakwadi_2016_03_31",
        "jayakwadi_2019_03_31",
    }
    assert set(BACKTEST_CASES) == expected
    for case in BACKTEST_CASES.values():
        assert case["reservoir_id"] in {"krs", "mettur", "jayakwadi"}
        assert isinstance(case["as_of"], date)
        assert case["tiers"]
        assert case["tiers"].issubset({"critical", "warning", "watch", "stable"})


def test_checked_in_backtest_snapshots_validate_against_schema() -> None:
    for case_id in BACKTEST_CASES:
        path = DASHBOARD_DATA_DIR / f"backtest_{case_id}.json"
        snapshot = DashboardSnapshot.model_validate(json.loads(path.read_text()))

        assert snapshot.backtest is not None
        assert snapshot.backtest.case_id == case_id
        assert snapshot.backtest.as_of == BACKTEST_CASES[case_id]["as_of"]
        assert (
            snapshot.data_sources_used.cwc_bulletin is None
            or snapshot.data_sources_used.cwc_bulletin <= snapshot.backtest.as_of
        )
        for reservoir in snapshot.reservoirs:
            assert (
                reservoir.current.cwc_as_of is None
                or reservoir.current.cwc_as_of <= snapshot.backtest.as_of
            )

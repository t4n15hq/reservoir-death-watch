"""Calibration regression tests.

These pin the area-to-volume calibration so that a future change does not
silently reintroduce the +21%/+39% Mettur/Indira Sagar bias that the
explicit dead-storage anchor was producing.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from reservoirs.pipeline import _calibrate_curve, _full_pool_area_km2
from reservoirs.schemas import ReservoirAOI
from reservoirs.sentinel import RecentArea

POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]}


def _aoi(
    *,
    reservoir_id="mettur",
    full_pool_capacity_bcm=2.647,
    dead_storage_capacity_bcm=0.21,
    aoi_area_km2=133.4,
) -> ReservoirAOI:
    return ReservoirAOI(
        id=reservoir_id,
        name=reservoir_id.title(),
        river="Test",
        state="Test",
        cwc_name=reservoir_id.upper(),
        city_served="",
        population_served=None,
        lat=0.0,
        lon=0.0,
        full_pool_capacity_bcm=full_pool_capacity_bcm,
        dead_storage_capacity_bcm=dead_storage_capacity_bcm,
        priority=1,
        aoi_file=f"pipeline/data/aois/{reservoir_id}.geojson",
        aoi_area_km2=aoi_area_km2,
        aoi_review_status=None,
        polygon=POLYGON,
        notes="",
    )


def test_full_pool_area_uses_observed_max_not_polygon() -> None:
    aoi = _aoi(aoi_area_km2=133.4)
    jrc = pd.DataFrame({"month": ["2020-01"], "area_km2": [131.6]})
    current = RecentArea(area_km2=88.0, as_of=date(2026, 4, 7), data_source="sentinel_2")

    assert _full_pool_area_km2(aoi, jrc, current) == pytest.approx(131.6)


def test_full_pool_area_falls_back_to_polygon_when_no_observations() -> None:
    aoi = _aoi(aoi_area_km2=133.4)
    empty = pd.DataFrame(columns=["month", "area_km2"])
    current = RecentArea(area_km2=0.0, as_of=date(2026, 4, 7), data_source="sentinel_2")

    assert _full_pool_area_km2(aoi, empty, current) == pytest.approx(133.4)


def test_curve_passes_through_cwc_anchor_within_one_percent() -> None:
    """With a single CWC bulletin, the 2-point fit must reproduce it exactly."""

    aoi = _aoi()
    history = pd.DataFrame(
        [
            {"date": date(2020, 1, 1), "area_km2": 131.6, "data_source": "jrc"},
            {"date": date(2026, 4, 7), "area_km2": 88.0, "data_source": "sentinel_2"},
        ]
    )
    cwc_row = pd.Series(
        {
            "reservoir_id": "mettur",
            "date": date(2026, 4, 9),
            "live_storage_bcm": 1.254,
        }
    )

    curve, flags = _calibrate_curve(
        aoi,
        full_pool_area_km2=131.6,
        full_capacity_bcm=2.647,
        history=history,
        cwc_row=cwc_row,
    )

    assert curve is not None
    # 2 perfectly co-linear-in-log-space points → fit recovers both volumes.
    assert curve.area_to_volume(88.0) == pytest.approx(1.254, rel=0.01)
    assert curve.area_to_volume(131.6) == pytest.approx(2.647, rel=0.01)
    # Exponent for a realistic reservoir geometry should be well above 1.
    assert curve.exponent_b > 1.3
    assert "cwc_calibrated_single_point" in flags


def test_curve_does_not_use_dead_storage_anchor() -> None:
    """Regression: the linear dead-storage proxy was biasing the fit flat."""

    aoi = _aoi(dead_storage_capacity_bcm=0.21)
    history = pd.DataFrame(
        [
            {"date": date(2020, 1, 1), "area_km2": 131.6, "data_source": "jrc"},
            {"date": date(2026, 4, 7), "area_km2": 88.0, "data_source": "sentinel_2"},
        ]
    )
    cwc_row = pd.Series(
        {
            "reservoir_id": "mettur",
            "date": date(2026, 4, 9),
            "live_storage_bcm": 1.254,
        }
    )

    curve, _ = _calibrate_curve(
        aoi,
        full_pool_area_km2=131.6,
        full_capacity_bcm=2.647,
        history=history,
        cwc_row=cwc_row,
    )

    assert curve is not None
    # The previous (buggy) fit predicted ~1.50 BCM at 88 km². The corrected
    # 2-point fit predicts close to 1.254. Anything > 1.30 means the dead
    # storage anchor crept back in.
    assert curve.area_to_volume(88.0) < 1.30


def test_curve_passes_through_indira_sagar_anchor() -> None:
    """Same property for Indira Sagar — the +39% miss must be gone."""

    aoi = _aoi(
        reservoir_id="indira_sagar",
        full_pool_capacity_bcm=12.21,
        dead_storage_capacity_bcm=3.39,
        aoi_area_km2=954.0,
    )
    history = pd.DataFrame(
        [
            {"date": date(2020, 10, 1), "area_km2": 864.7, "data_source": "jrc"},
            {"date": date(2026, 4, 5), "area_km2": 641.5, "data_source": "sentinel_2"},
        ]
    )
    cwc_row = pd.Series(
        {
            "reservoir_id": "indira_sagar",
            "date": date(2026, 4, 9),
            "live_storage_bcm": 4.192,
        }
    )

    curve, _ = _calibrate_curve(
        aoi,
        full_pool_area_km2=864.7,
        full_capacity_bcm=9.745,
        history=history,
        cwc_row=cwc_row,
    )

    assert curve is not None
    assert curve.area_to_volume(641.5) == pytest.approx(4.192, rel=0.01)


def test_curve_returns_none_when_only_full_pool_anchor() -> None:
    aoi = _aoi()
    history = pd.DataFrame(columns=["date", "area_km2", "data_source"])
    curve, flags = _calibrate_curve(
        aoi,
        full_pool_area_km2=131.6,
        full_capacity_bcm=2.647,
        history=history,
        cwc_row=None,
    )

    assert curve is None
    assert "needs_cwc_calibration" in flags

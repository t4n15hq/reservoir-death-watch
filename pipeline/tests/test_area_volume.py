from __future__ import annotations

from datetime import UTC, datetime

import pytest

from reservoirs.area_volume import (
    AreaVolumeCalibrationError,
    dead_storage_area_km2,
    fit_power_law_curve,
)


def test_fit_power_law_curve_recovers_synthetic_geometry() -> None:
    points = [(area, 0.003 * area**1.42) for area in (20, 35, 50, 80, 120)]

    curve = fit_power_law_curve(
        "synthetic",
        points,
        calibrated_at=datetime(2026, 5, 18, tzinfo=UTC),
    )

    assert curve.coefficient_a == pytest.approx(0.003, rel=1e-6)
    assert curve.exponent_b == pytest.approx(1.42, rel=1e-6)
    assert curve.r_squared == pytest.approx(1.0)
    assert curve.confidence_flag == "high"


def test_fit_power_law_curve_rejects_non_positive_points() -> None:
    with pytest.raises(AreaVolumeCalibrationError):
        fit_power_law_curve("bad", [(10, 0.2), (0, 0.3)])


def test_dead_storage_area_uses_capacity_when_available() -> None:
    curve = fit_power_law_curve("synthetic", [(20, 0.3), (80, 2.4), (120, 4.6)])

    area, flag = dead_storage_area_km2(
        curve=curve,
        dead_storage_capacity_bcm=0.3,
        full_pool_area_km2=100,
    )

    assert area == pytest.approx(curve.volume_to_area(0.3))
    assert flag is None


def test_dead_storage_area_uses_documented_proxy_without_capacity() -> None:
    curve = fit_power_law_curve("synthetic", [(20, 0.3), (80, 2.4), (120, 4.6)])

    area, flag = dead_storage_area_km2(
        curve=curve,
        dead_storage_capacity_bcm=None,
        full_pool_area_km2=100,
    )

    assert area == pytest.approx(10)
    assert flag == "dead_storage_area_proxy"


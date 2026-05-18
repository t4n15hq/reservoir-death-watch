from __future__ import annotations

from datetime import date, timedelta

import pytest

from reservoirs.model import compute_tier, fit_depletion, project_to_dead_storage
from reservoirs.schemas import Projection


def _declining_series(start: date, areas: list[float]) -> list[tuple[date, float]]:
    return [(start + timedelta(days=index * 10), area) for index, area in enumerate(areas)]


def test_fit_depletion_returns_expected_negative_slope() -> None:
    observations = _declining_series(date(2026, 1, 1), [100, 95, 90, 85, 80, 75, 70])

    fit = fit_depletion("krs", observations, as_of=date(2026, 3, 2), window_days=90)

    assert fit is not None
    assert fit.slope_km2_per_day == pytest.approx(-0.5)
    assert fit.r_squared == pytest.approx(1.0)
    assert fit.fit_quality == "good"


def test_fit_depletion_rejects_rising_series() -> None:
    observations = _declining_series(date(2026, 1, 1), [70, 75, 80, 85, 90, 95])

    assert fit_depletion("krs", observations, as_of=date(2026, 2, 20)) is None


def test_fit_depletion_rejects_too_few_observations() -> None:
    observations = _declining_series(date(2026, 1, 1), [100, 95, 90])

    assert fit_depletion("krs", observations, as_of=date(2026, 1, 21)) is None


def test_project_to_dead_storage_computes_date_and_ci() -> None:
    fit = fit_depletion(
        "krs",
        _declining_series(date(2026, 1, 1), [100, 95, 90, 85, 80, 75, 70]),
        as_of=date(2026, 3, 2),
    )
    assert fit is not None

    projection = project_to_dead_storage(
        fit,
        current_area_km2=70,
        dead_storage_area_km2=50,
        as_of=date(2026, 3, 2),
    )

    assert projection.days_to_dead_storage == 40
    assert projection.dead_storage_date == date(2026, 4, 11)
    assert projection.confidence_interval_days is not None


def test_project_to_dead_storage_applies_el_nino_delta() -> None:
    fit = fit_depletion(
        "krs",
        _declining_series(date(2026, 1, 1), [100, 95, 90, 85, 80, 75, 70]),
        as_of=date(2026, 3, 2),
    )
    assert fit is not None

    projection = project_to_dead_storage(
        fit,
        current_area_km2=70,
        dead_storage_area_km2=50,
        as_of=date(2026, 3, 2),
        scenario="el_nino_monsoon",
        el_nino_area_delta_km2=-5,
    )

    assert projection.days_to_dead_storage == 30


def test_compute_tier_matches_spec_ordering() -> None:
    neutral = Projection(
        scenario="neutral_monsoon",
        days_to_dead_storage=45,
        dead_storage_date=date(2026, 6, 1),
        confidence_interval_days=(38, 52),
    )
    el_nino = Projection(
        scenario="el_nino_monsoon",
        days_to_dead_storage=70,
        dead_storage_date=date(2026, 6, 26),
        confidence_interval_days=(55, 85),
    )

    assert (
        compute_tier(
            neutral_projection=neutral,
            el_nino_projection=el_nino,
            current_percent_full=40,
        )
        == "critical"
    )


"""Transparent depletion model used for reservoir projections."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil, floor

import numpy as np

from reservoirs.schemas import AreaObservation, DepletionFit, Projection, Scenario, Tier


@dataclass(frozen=True)
class Observation:
    date: date
    area_km2: float


def fit_depletion(
    reservoir_id: str,
    observations: Iterable[AreaObservation | Observation | tuple[date, float]],
    *,
    as_of: date | None = None,
    window_days: int = 90,
    min_observations: int = 6,
    min_r_squared: float = 0.70,
) -> DepletionFit | None:
    """Fit area = m * day + c over the latest window.

    Returns None when the available observations do not meet the spec's
    minimum evidence bar.
    """

    normalized = sorted(_normalize_observations(observations), key=lambda item: item.date)
    if not normalized:
        return None

    end_date = as_of or normalized[-1].date
    start_date = end_date - timedelta(days=window_days)
    window = [obs for obs in normalized if start_date <= obs.date <= end_date]

    if len(window) < min_observations:
        return None

    first_date = window[0].date
    x = np.array([(obs.date - first_date).days for obs in window], dtype=float)
    y = np.array([obs.area_km2 for obs in window], dtype=float)

    if len(set(x.tolist())) < 2:
        return None

    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    r_squared = _r_squared(y, predicted)
    std_error = _standard_error(y, predicted)

    if slope >= 0 or r_squared < min_r_squared:
        return None

    fit_quality = "good" if r_squared >= 0.85 else "low_confidence"
    return DepletionFit(
        reservoir_id=reservoir_id,
        slope_km2_per_day=float(slope),
        intercept=float(intercept),
        std_error=std_error,
        r_squared=r_squared,
        n_observations=len(window),
        window_days=window_days,
        fit_quality=fit_quality,
    )


def project_to_dead_storage(
    fit: DepletionFit,
    *,
    current_area_km2: float,
    dead_storage_area_km2: float,
    as_of: date,
    scenario: Scenario = "neutral_monsoon",
    el_nino_area_delta_km2: float = 0.0,
    sentinel_1: bool = False,
) -> Projection:
    """Project when the fitted line reaches the dead-storage area."""

    if current_area_km2 <= 0:
        msg = "current_area_km2 must be positive"
        raise ValueError(msg)
    if dead_storage_area_km2 <= 0:
        msg = "dead_storage_area_km2 must be positive"
        raise ValueError(msg)
    if fit.slope_km2_per_day >= 0:
        return Projection(
            scenario=scenario,
            days_to_dead_storage=None,
            dead_storage_date=None,
            confidence_interval_days=None,
        )

    adjusted_current_area = current_area_km2 + el_nino_area_delta_km2
    if adjusted_current_area <= dead_storage_area_km2:
        days = 0
    else:
        days = ceil((adjusted_current_area - dead_storage_area_km2) / -fit.slope_km2_per_day)

    widen = 1.0
    if current_area_km2 < dead_storage_area_km2 * 2:
        widen *= 1.5
    if sentinel_1:
        widen *= 1.3
    if days > 120:
        widen *= 2.0

    ci_radius = max(1, ceil((fit.std_error / abs(fit.slope_km2_per_day)) * 1.28 * widen))
    ci_low = max(0, floor(days - ci_radius))
    ci_high = ceil(days + ci_radius)

    return Projection(
        scenario=scenario,
        days_to_dead_storage=days,
        dead_storage_date=as_of + timedelta(days=days),
        confidence_interval_days=(ci_low, ci_high),
    )


def compute_tier(
    *,
    neutral_projection: Projection,
    el_nino_projection: Projection,
    current_percent_full: float,
    five_year_average_for_month: float | None = None,
) -> Tier:
    """Apply the criticality table from docs/TDD.md §3.4."""

    neutral_days = neutral_projection.days_to_dead_storage
    el_nino_days = el_nino_projection.days_to_dead_storage

    if neutral_days is not None and neutral_days < 60:
        return "critical"
    if (neutral_days is not None and neutral_days < 120) or (
        el_nino_days is not None and el_nino_days < 60
    ):
        return "warning"
    if (
        five_year_average_for_month is not None
        and current_percent_full < five_year_average_for_month
    ):
        return "watch"
    return "stable"


def _normalize_observations(
    observations: Iterable[AreaObservation | Observation | tuple[date, float]],
) -> list[Observation]:
    normalized = []
    for obs in observations:
        if isinstance(obs, AreaObservation):
            normalized.append(Observation(obs.date, obs.area_km2))
        elif isinstance(obs, Observation):
            normalized.append(obs)
        else:
            obs_date, area = obs
            normalized.append(Observation(obs_date, float(area)))

    if any(obs.area_km2 <= 0 for obs in normalized):
        msg = "observation areas must be positive"
        raise ValueError(msg)
    return normalized


def _r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    residual_sum = float(np.sum((actual - predicted) ** 2))
    total_sum = float(np.sum((actual - actual.mean()) ** 2))
    if total_sum == 0:
        return 1.0 if residual_sum == 0 else 0.0
    return max(0.0, min(1.0, 1 - residual_sum / total_sum))


def _standard_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    degrees = len(actual) - 2
    if degrees <= 0:
        return 0.0
    return float(np.sqrt(np.sum((actual - predicted) ** 2) / degrees))

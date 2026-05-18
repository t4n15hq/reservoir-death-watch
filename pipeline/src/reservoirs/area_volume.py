"""Area-to-volume calibration utilities."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

import numpy as np

from reservoirs.schemas import AreaVolumeCurve


class AreaVolumeCalibrationError(ValueError):
    """Raised when an area-volume curve cannot be fit defensibly."""


def fit_power_law_curve(
    reservoir_id: str,
    calibration_points: Iterable[tuple[float, float]],
    *,
    calibrated_at: datetime | None = None,
) -> AreaVolumeCurve:
    """Fit V = a * A^b in log space from (area_km2, volume_bcm) points."""

    points = [(float(area), float(volume)) for area, volume in calibration_points]
    if len(points) < 2:
        msg = "at least two calibration points are required"
        raise AreaVolumeCalibrationError(msg)
    if any(area <= 0 or volume <= 0 for area, volume in points):
        msg = "calibration areas and volumes must be positive"
        raise AreaVolumeCalibrationError(msg)

    areas = np.array([point[0] for point in points], dtype=float)
    volumes = np.array([point[1] for point in points], dtype=float)

    log_areas = np.log(areas)
    log_volumes = np.log(volumes)
    exponent_b, log_a = np.polyfit(log_areas, log_volumes, 1)
    coefficient_a = float(np.exp(log_a))

    predicted = coefficient_a * (areas**exponent_b)
    r_squared = _r_squared(volumes, predicted)

    return AreaVolumeCurve(
        reservoir_id=reservoir_id,
        coefficient_a=coefficient_a,
        exponent_b=float(exponent_b),
        r_squared=r_squared,
        n_calibration_points=len(points),
        calibrated_at=calibrated_at or datetime.now(UTC),
        confidence_flag=_confidence_flag(r_squared),
    )


def dead_storage_area_km2(
    *,
    curve: AreaVolumeCurve,
    dead_storage_capacity_bcm: float | None,
    full_pool_area_km2: float,
    default_fraction: float = 0.10,
) -> tuple[float, str | None]:
    """Convert known dead-storage capacity to area, or use the documented proxy."""

    if full_pool_area_km2 <= 0:
        msg = "full_pool_area_km2 must be positive"
        raise ValueError(msg)
    if dead_storage_capacity_bcm and dead_storage_capacity_bcm > 0:
        return curve.volume_to_area(dead_storage_capacity_bcm), None
    return full_pool_area_km2 * default_fraction, "dead_storage_area_proxy"


def _r_squared(actual: np.ndarray, predicted: np.ndarray) -> float:
    residual_sum = float(np.sum((actual - predicted) ** 2))
    total_sum = float(np.sum((actual - actual.mean()) ** 2))
    if total_sum == 0:
        return 1.0 if residual_sum == 0 else 0.0
    return max(0.0, min(1.0, 1 - residual_sum / total_sum))


def _confidence_flag(r_squared: float) -> str:
    if r_squared >= 0.95:
        return "high"
    if r_squared >= 0.85:
        return "medium"
    return "low"


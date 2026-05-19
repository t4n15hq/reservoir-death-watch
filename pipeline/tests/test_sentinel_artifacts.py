from __future__ import annotations

from datetime import date

import pandas as pd

from reservoirs.sentinel import drop_implausible_cloud_artifacts


def _series(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [date(2026, 5, 1 + i) for i in range(len(values))],
            "area_km2": values,
            "data_source": ["sentinel_2"] * len(values),
            "cloud_coverage_percent": [10.0] * len(values),
        }
    )


def test_drops_isolated_cloud_dip_between_two_higher_neighbours() -> None:
    frame = _series([33.0, 3.9, 13.0])
    result = drop_implausible_cloud_artifacts(frame, max_drop_ratio=0.5)
    assert result["area_km2"].tolist() == [33.0, 13.0]


def test_keeps_sustained_decline() -> None:
    frame = _series([100.0, 80.0, 60.0, 40.0])
    result = drop_implausible_cloud_artifacts(frame, max_drop_ratio=0.5)
    assert result["area_km2"].tolist() == [100.0, 80.0, 60.0, 40.0]


def test_keeps_two_adjacent_low_values() -> None:
    # If both readings are low, it's a real regime change, not a cloud spike.
    frame = _series([100.0, 30.0, 25.0, 80.0])
    result = drop_implausible_cloud_artifacts(frame, max_drop_ratio=0.5)
    # The 80 at the end neighbours 25 → 80, ratio fine; only the 30 looks
    # isolated against 100 and 25, but 25 is also low so neighbour floor=25
    # and 30 > 12.5 ⇒ kept. The 25 neighbours 30 and 80 → floor=30 ⇒ kept.
    assert result["area_km2"].tolist() == [100.0, 30.0, 25.0, 80.0]


def test_short_series_returns_unchanged() -> None:
    frame = _series([100.0, 1.0])
    result = drop_implausible_cloud_artifacts(frame)
    assert result["area_km2"].tolist() == [100.0, 1.0]

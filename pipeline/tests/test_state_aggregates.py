from __future__ import annotations

from datetime import UTC, date, datetime

from reservoirs.schemas import (
    DepletionFit,
    Projection,
    ReservoirCurrent,
    ReservoirResult,
)
from reservoirs.state_aggregates import build_state_aggregates


def _result(rid, state, capacity, storage, tier):
    percent_full = (storage / capacity * 100) if capacity else 0.0
    return ReservoirResult(
        id=rid,
        name=rid.title(),
        river="Test",
        state=state,
        city_served="",
        population_served=None,
        full_pool_area_km2=100.0,
        full_pool_capacity_bcm=capacity if capacity else None,
        dead_storage_capacity_bcm=0.1,
        lat=0.0,
        lon=0.0,
        current=ReservoirCurrent(
            as_of=date(2026, 5, 18),
            area_km2=50.0,
            estimated_storage_bcm=storage,
            cwc_reported_bcm=None,
            cwc_as_of=None,
            percent_full=percent_full,
            data_source="sentinel_2",
        ),
        history=[],
        fit=DepletionFit(
            reservoir_id=rid,
            slope_km2_per_day=-1.0,
            intercept=100.0,
            std_error=1.0,
            r_squared=0.9,
            n_observations=10,
            window_days=90,
            fit_quality="good",
        ),
        projection={
            "neutral_monsoon": Projection(
                scenario="neutral_monsoon",
                days_to_dead_storage=None,
                dead_storage_date=None,
                confidence_interval_days=None,
            ),
            "el_nino_monsoon": Projection(
                scenario="el_nino_monsoon",
                days_to_dead_storage=None,
                dead_storage_date=None,
                confidence_interval_days=None,
            ),
        },
        tier=tier,
        model_version="1.0.0",
        flags=[],
    )


def test_state_aggregates_groups_and_counts_tiers() -> None:
    reservoirs = [
        _result("krs", "Karnataka", 1.0, 0.4, "critical"),
        _result("almatti", "Karnataka", 3.0, 1.5, "warning"),
        _result("mettur", "Tamil Nadu", 2.5, 1.2, "stable"),
    ]

    out = build_state_aggregates(reservoirs, generated_at=datetime(2026, 5, 18, tzinfo=UTC))

    assert [s["state"] for s in out["states"]] == ["Karnataka", "Tamil Nadu"]
    karnataka = out["states"][0]
    assert karnataka["reservoir_count"] == 2
    assert karnataka["total_capacity_bcm"] == 4.0
    assert karnataka["current_storage_bcm"] == 1.9
    assert karnataka["tier_counts"] == {
        "critical": 1,
        "warning": 1,
        "watch": 0,
        "stable": 0,
    }
    assert karnataka["reservoir_ids"] == ["almatti", "krs"]


def test_state_aggregates_handles_missing_capacity() -> None:
    reservoirs = [_result("foo", "X", 0.0, 0.0, "stable")]
    out = build_state_aggregates(reservoirs, generated_at=datetime(2026, 1, 1, tzinfo=UTC))
    assert out["states"][0]["percent_full"] == 0.0

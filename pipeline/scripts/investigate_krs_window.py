#!/usr/bin/env python
"""KRS 2023 backtest investigation step (2): regression window variants.

Per AGENT.md non-negotiable #2 failure handling, after (1) area-volume curve
the next debugging step is (2) regression window. Goal: find whether any
combination of `window_days`, `min_observations`, and cloud-filter threshold
produces a usable depletion fit on KRS for the Dec 31 2023 backtest.

Uses the observations already cached in `backtest_krs_2023_12_31.json` so
this runs offline. No new GEE quota burnt.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from reservoirs.model import Observation, fit_depletion


def load_observations() -> list[tuple[Observation, float | None]]:
    path = Path(__file__).resolve().parents[2] / (
        "dashboard/public/data/backtest_krs_2023_12_31.json"
    )
    snap = json.loads(path.read_text())
    obs = snap["reservoirs"][0]["history"]
    pairs: list[tuple[Observation, float | None]] = []
    for o in obs:
        if o["area_km2"] <= 0:
            continue
        if o["data_source"] not in ("sentinel_2", "sentinel_1"):
            continue
        d = date.fromisoformat(o["date"])
        if d.year != 2023:
            continue
        pairs.append((Observation(d, float(o["area_km2"])), o.get("cloud_coverage_percent")))
    return pairs


def run_variant(
    pairs: list[tuple[Observation, float | None]],
    *,
    window_days: int,
    min_observations: int,
    cloud_threshold: float | None,
) -> None:
    filtered = [
        obs
        for obs, cloud in pairs
        if cloud_threshold is None or cloud is None or cloud <= cloud_threshold
    ]
    fit = fit_depletion(
        "krs",
        filtered,
        as_of=date(2023, 12, 31),
        window_days=window_days,
        min_observations=min_observations,
    )
    n_in_window = sum(
        1
        for obs in filtered
        if (date(2023, 12, 31) - obs.date).days <= window_days
    )
    label = (
        f"window={window_days:>3}d  min_obs={min_observations}  "
        f"cloud<={cloud_threshold if cloud_threshold is not None else 'no-filter'}"
    )
    if fit is None:
        print(
            f"  {label:50s}  n_in_window={n_in_window:>2}  → fit REJECTED "
            f"(too few obs, positive slope, or r² < 0.7)"
        )
        return
    days = None
    # Quick days-to-dead estimate using a 38 km² dead-storage area (b=2.0
    # on the known KRS capacity ratio 0.13/1.163 ≈ 0.112 → A_dead/A_full ≈ 0.335
    # × 113 km² FRL ≈ 38 km²). Use 65.57 km² as current area (last KRS obs).
    if fit.slope_km2_per_day < 0:
        days = (65.57 - 38) / -fit.slope_km2_per_day
    print(
        f"  {label:50s}  n_in_window={fit.n_observations:>2}  "
        f"slope={fit.slope_km2_per_day:+.3f} km²/d  r²={fit.r_squared:.2f}  "
        f"quality={fit.fit_quality}  days-to-dead≈{days:.0f}" if days else
        f"  {label:50s}  n_in_window={fit.n_observations:>2}  "
        f"slope={fit.slope_km2_per_day:+.3f} km²/d  r²={fit.r_squared:.2f}  "
        f"quality={fit.fit_quality}  (slope ≥ 0, no projection)"
    )


def main() -> int:
    pairs = load_observations()
    print(f"KRS 2023 Sentinel-2 observations available: {len(pairs)}")
    for obs, cloud in pairs:
        cloud_str = f"{cloud:>4.0f}%" if cloud is not None else "  n/a"
        print(f"  {obs.date}  {obs.area_km2:6.2f} km²  cloud={cloud_str}")
    print()
    print("Trying combinations:")
    print()

    variants = [
        # Pipeline defaults — the configuration that currently produces no fit.
        (90, 6, 50),
        # Loosen cloud filter
        (90, 6, 70),
        (90, 6, None),
        # Lower min_observations
        (90, 5, 50),
        (90, 4, 50),
        (90, 5, 70),
        # Widen window
        (120, 6, 50),
        (120, 6, 70),
        (120, 5, 50),
        (150, 6, 50),
        (150, 6, 70),
        # Most permissive
        (150, 4, None),
    ]
    for window, min_obs, cloud in variants:
        run_variant(pairs, window_days=window, min_observations=min_obs, cloud_threshold=cloud)

    print()
    print("Interpretation guide:")
    print("- fit REJECTED with positive slope → satellite obs trend UP, not DOWN")
    print("  (KRS was actually decreasing per CWC; the satellite signal is")
    print("   contaminated by cloud masking that randomly affects pixel counts)")
    print("- fit REJECTED with r² < 0.7 → real signal swamped by cloud noise")
    print("- fit found with days-to-dead > 60 → won't trigger critical tier")
    print("  even though CWC ground truth says KRS was at 16% in late 2023")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

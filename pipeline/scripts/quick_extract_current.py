#!/usr/bin/env python
"""Fast current-area extraction for reservoirs whose full JRC history would
take too long to backfill in one sitting.

For each requested reservoir:
  1. Run the existing `extract_recent_area` to get a current S2 (or S1) area.
  2. Use the AOI polygon's historical max water area as the FRL proxy.
  3. Compute storage via the simple area-ratio proxy (no curve calibration).
  4. Update that reservoir's entry in `reservoirs.json` in place.

Flags every updated reservoir with `current_only_no_history` so the dashboard
can show "no history yet" honestly. Run a full `python -m reservoirs.pipeline`
later to backfill the JRC trace and proper area-volume calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from reservoirs.aois import load_aois
from reservoirs.config import DASHBOARD_DATA_DIR, MODEL_VERSION, RESERVOIRS_CSV
from reservoirs.cwc_scraper import load_cwc_storage
from reservoirs.schemas import DashboardSnapshot
from reservoirs.sentinel import extract_recent_area
from reservoirs.state_aggregates import build_state_aggregates


def quick_extract(
    reservoir_id: str,
    as_of_str: str | None,
    cwc_latest: dict[str, dict],
) -> dict:
    aois = load_aois([reservoir_id])
    if not aois:
        raise SystemExit(f"reservoir not in metadata: {reservoir_id}")
    aoi = aois[0]

    print(f"{reservoir_id}: extracting current S2/S1 area...", flush=True)
    as_of = datetime.fromisoformat(as_of_str).date() if as_of_str else None
    current = extract_recent_area(aoi, as_of=as_of, days=30)
    print(
        f"{reservoir_id}: area={current.area_km2:.2f} km² on {current.as_of} "
        f"({current.data_source})",
        flush=True,
    )

    cwc_row = cwc_latest.get(reservoir_id)
    cwc_reported = _opt_float(cwc_row.get("live_storage_bcm") if cwc_row else None)
    cwc_as_of = cwc_row.get("date").isoformat() if cwc_row else None
    cwc_capacity = _opt_float(cwc_row.get("live_capacity_at_frl_bcm") if cwc_row else None)

    # Use the AOI polygon's geometric area as a coarse FRL proxy for storage.
    # The seed_aois recurrence band approximates the FRL footprint, so this is
    # a reasonable upper bound until JRC backfill provides the true historical max.
    full_pool_area_km2 = aoi.aoi_area_km2 or current.area_km2
    capacity = cwc_capacity or aoi.full_pool_capacity_bcm or 0.0
    storage = (
        max(0.0, (current.area_km2 / full_pool_area_km2) * capacity)
        if full_pool_area_km2 > 0 and capacity > 0
        else 0.0
    )
    percent_full = (storage / capacity * 100) if capacity > 0 else 0.0

    return {
        "id": aoi.id,
        "name": aoi.name,
        "river": aoi.river,
        "state": aoi.state,
        "city_served": aoi.city_served,
        "population_served": aoi.population_served,
        "full_pool_area_km2": round(full_pool_area_km2, 3),
        "full_pool_capacity_bcm": capacity if capacity else None,
        "dead_storage_capacity_bcm": aoi.dead_storage_capacity_bcm,
        "lat": aoi.lat,
        "lon": aoi.lon,
        "current": {
            "as_of": current.as_of.isoformat(),
            "area_km2": round(current.area_km2, 3),
            "estimated_storage_bcm": round(storage, 3),
            "cwc_reported_bcm": round(cwc_reported, 3) if cwc_reported is not None else None,
            "cwc_as_of": cwc_as_of,
            "percent_full": round(percent_full, 1),
            "data_source": current.data_source,
        },
        "history": [],
        "fit": None,
        "projection": {
            "neutral_monsoon": {
                "scenario": "neutral_monsoon",
                "days_to_dead_storage": None,
                "dead_storage_date": None,
                "confidence_interval_days": None,
                "method": "linear_extrapolation",
            },
            "el_nino_monsoon": {
                "scenario": "el_nino_monsoon",
                "days_to_dead_storage": None,
                "dead_storage_date": None,
                "confidence_interval_days": None,
                "method": "linear_extrapolation",
            },
        },
        "tier": _coarse_tier(percent_full),
        "model_version": MODEL_VERSION,
        "scope": aoi.scope,
        "flags": sorted(
            {
                "current_only_no_history",
                "volume_area_ratio_proxy",
                "needs_full_pipeline_run",
                aoi.aoi_review_status or "first_pass_needs_manual_review",
            }
        ),
    }


def _opt_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coarse_tier(percent_full: float) -> str:
    """Without a depletion fit we cannot compute days-to-dead-storage.

    Fall back to a percent-full heuristic for the pin colour. This is a
    coarse proxy and is flagged with `current_only_no_history`; the proper
    tier comes from the full pipeline + projection.
    """

    if percent_full < 15:
        return "critical"
    if percent_full < 30:
        return "warning"
    if percent_full < 50:
        return "watch"
    return "stable"


def update_snapshot(snapshot: dict, updates: dict[str, dict]) -> dict:
    by_id = {r["id"]: r for r in snapshot["reservoirs"]}
    for rid, entry in updates.items():
        by_id[rid] = entry
    ordered_ids = reservoir_order()
    snapshot["reservoirs"] = sorted(
        by_id.values(),
        key=lambda r: ordered_ids.get(r["id"], 9999),
    )
    return snapshot


def reservoir_order() -> dict[str, int]:
    import csv

    with RESERVOIRS_CSV.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: int(row["priority"]) for row in csv.DictReader(handle)}


def latest_cwc_by_reservoir() -> dict[str, dict]:
    try:
        cwc = load_cwc_storage()
    except Exception as exc:  # noqa: BLE001
        print(f"CWC storage unavailable: {exc}", file=sys.stderr, flush=True)
        return {}
    latest: dict[str, dict] = {}
    for record in cwc.sort_values("date").to_dict("records"):
        latest[str(record["reservoir_id"])] = record
    return latest


def recompute_aggregates(snapshot: dict) -> dict:
    observed = [
        r
        for r in snapshot["reservoirs"]
        if "awaiting_first_observation" not in (r.get("flags") or [])
    ]
    total_capacity = sum(r.get("full_pool_capacity_bcm") or 0 for r in observed)
    current_storage = sum(r["current"]["estimated_storage_bcm"] or 0 for r in observed)

    tiers = {"critical": 0, "warning": 0, "watch": 0, "stable": 0}
    for r in observed:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1

    at_risk = sum(
        r.get("population_served") or 0
        for r in observed
        if r["tier"] in {"critical", "warning"}
    )

    snapshot["national_aggregate"] = {
        "total_capacity_bcm": round(total_capacity, 3),
        "current_storage_bcm": round(current_storage, 3),
        "percent_full": round((current_storage / total_capacity * 100), 1)
        if total_capacity
        else 0.0,
        "reservoirs_critical": tiers["critical"],
        "reservoirs_warning": tiers["warning"],
        "reservoirs_watch": tiers["watch"],
        "reservoirs_stable": tiers["stable"],
        "people_at_risk_neutral": at_risk,
        "people_at_risk_el_nino": 0,
    }
    return snapshot


def write_state_aggregates(snapshot: dict, data_dir: Path) -> None:
    parsed = DashboardSnapshot.model_validate(snapshot)
    states = build_state_aggregates(parsed.reservoirs, generated_at=datetime.now(UTC))
    tmp = data_dir / "state_aggregates.json.tmp"
    with tmp.open("w") as handle:
        json.dump(states, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(data_dir / "state_aggregates.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reservoirs", nargs="*", help="reservoir IDs (default: all pending)")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_path = args.data_dir / "reservoirs.json"
    with snapshot_path.open() as handle:
        snapshot = json.load(handle)

    if args.reservoirs:
        ids = args.reservoirs
    else:
        ids = [
            r["id"]
            for r in snapshot["reservoirs"]
            if "awaiting_first_observation" in (r.get("flags") or [])
        ]

    print(f"will extract {len(ids)} reservoirs: {' '.join(ids)}", flush=True)
    cwc_latest = latest_cwc_by_reservoir()
    updates: dict[str, dict] = {}
    for rid in ids:
        try:
            updates[rid] = quick_extract(rid, args.as_of, cwc_latest)
        except Exception as exc:  # noqa: BLE001
            print(f"{rid}: FAILED — {exc}", file=sys.stderr, flush=True)
            continue

    snapshot = update_snapshot(snapshot, updates)
    snapshot = recompute_aggregates(snapshot)
    snapshot["generated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    DashboardSnapshot.model_validate(snapshot)
    tmp = snapshot_path.with_suffix(".json.tmp")
    with tmp.open("w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(snapshot_path)
    write_state_aggregates(snapshot, args.data_dir)
    print(f"wrote {len(updates)} updates → {snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Re-derive storage estimates in the dashboard CSVs without re-hitting GEE.

The Sentinel-2/JRC area observations in the per-reservoir CSVs are still valid;
only the area→volume calibration changed. This script rebuilds the curve from
the existing area observations + checked-in CWC bulletins and rewrites the
`estimated_storage_bcm` and `percent_full` columns in place.

Use it after changing calibration logic; for full Earth Engine refreshes, run
`python -m reservoirs.pipeline` instead.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from reservoirs.aois import load_aois
from reservoirs.config import DASHBOARD_DATA_DIR
from reservoirs.cwc_scraper import load_cwc_storage
from reservoirs.pipeline import _calibrate_curve, _full_pool_area_km2
from reservoirs.sentinel import RecentArea


def load_history_csv(reservoir_id: str, data_dir: Path) -> pd.DataFrame:
    path = data_dir / "reservoirs" / f"{reservoir_id}.csv"
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def rebuild_one(reservoir_id: str, data_dir: Path, cwc_storage: pd.DataFrame) -> dict:
    history = load_history_csv(reservoir_id, data_dir)
    aois = load_aois([reservoir_id])
    if not aois:
        raise SystemExit(f"reservoir id not found in master metadata: {reservoir_id}")
    aoi = aois[0]

    cwc_rows = cwc_storage[cwc_storage["reservoir_id"] == reservoir_id].sort_values("date")
    cwc_row = cwc_rows.iloc[-1] if not cwc_rows.empty else None

    jrc = history[history["data_source"] == "jrc"][["date", "area_km2"]].copy()
    jrc["month"] = jrc["date"].map(lambda d: d.strftime("%Y-%m"))

    latest_obs = history[history["area_km2"] > 0].sort_values("date").iloc[-1]
    current = RecentArea(
        area_km2=float(latest_obs["area_km2"]),
        as_of=latest_obs["date"],
        data_source=str(latest_obs["data_source"]),
    )

    full_pool_area = _full_pool_area_km2(aoi, jrc, current)
    if cwc_row is not None:
        full_capacity = float(cwc_row["live_capacity_at_frl_bcm"])
    else:
        full_capacity = aoi.full_pool_capacity_bcm
    curve, flags = _calibrate_curve(
        aoi,
        full_pool_area_km2=full_pool_area,
        full_capacity_bcm=full_capacity,
        history=history[["date", "area_km2", "data_source"]],
        cwc_row=cwc_row,
    )

    def storage_for(area: float) -> float:
        if area <= 0:
            return 0.0
        if curve is not None:
            return max(0.0, curve.area_to_volume(area))
        if full_capacity and full_pool_area > 0:
            return max(0.0, (area / full_pool_area) * full_capacity)
        return 0.0

    history["estimated_storage_bcm"] = history["area_km2"].map(storage_for)
    history["percent_full"] = history["estimated_storage_bcm"].map(
        lambda v: round(max(0.0, (v / full_capacity) * 100), 6) if full_capacity else 0.0
    )

    path = data_dir / "reservoirs" / f"{reservoir_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    history.to_csv(tmp, index=False)
    tmp.replace(path)

    return {
        "reservoir_id": reservoir_id,
        "full_pool_area_km2": full_pool_area,
        "full_capacity_bcm": full_capacity,
        "cwc_as_of": cwc_row["date"] if cwc_row is not None else None,
        "cwc_reported_bcm": (
            float(cwc_row["live_storage_bcm"]) if cwc_row is not None else None
        ),
        "curve_a": curve.coefficient_a if curve else None,
        "curve_b": curve.exponent_b if curve else None,
        "flags": flags,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    parser.add_argument("--reservoir", action="append", dest="reservoirs", default=None)
    return parser.parse_args()


def update_snapshot_json(data_dir: Path, infos: dict[str, dict]) -> None:
    """Refresh the per-reservoir `current` block in `reservoirs.json` from the
    rebuilt CSV without re-running Earth Engine.

    Tier, projection, and aggregate values are deliberately left untouched here
    — they depend on the depletion fit which a full pipeline run will redo. The
    `current.estimated_storage_bcm` / `percent_full` are the user-visible
    headline numbers, so we keep those consistent with the CSV.
    """

    path = data_dir / "reservoirs.json"
    if not path.exists():
        return
    with path.open() as handle:
        snapshot = json.load(handle)

    by_id = {r["id"]: r for r in snapshot.get("reservoirs", [])}
    for rid, info in infos.items():
        reservoir = by_id.get(rid)
        if reservoir is None:
            continue
        history = pd.read_csv(data_dir / "reservoirs" / f"{rid}.csv")
        history["date"] = pd.to_datetime(history["date"]).dt.date
        sat = history[history["data_source"].isin(["sentinel_2", "sentinel_1"])]
        if sat.empty:
            continue
        latest = sat.sort_values("date").iloc[-1]
        full_capacity = info["full_capacity_bcm"]
        storage = float(latest["estimated_storage_bcm"])
        percent_full = float(latest["percent_full"]) if full_capacity else 0.0
        reservoir["current"]["area_km2"] = round(float(latest["area_km2"]), 3)
        reservoir["current"]["as_of"] = latest["date"].isoformat()
        reservoir["current"]["estimated_storage_bcm"] = round(storage, 3)
        reservoir["current"]["percent_full"] = round(percent_full, 1)
        reservoir["current"]["data_source"] = str(latest["data_source"])
        cwc_as_of = info.get("cwc_as_of")
        reservoir["current"]["cwc_as_of"] = cwc_as_of.isoformat() if cwc_as_of else None
        cwc_reported = info.get("cwc_reported_bcm")
        reservoir["current"]["cwc_reported_bcm"] = (
            round(float(cwc_reported), 3) if cwc_reported is not None else None
        )
        reservoir["full_pool_area_km2"] = round(info["full_pool_area_km2"], 3)
        reservoir["full_pool_capacity_bcm"] = full_capacity
        current_flags = set(reservoir.get("flags", []))
        current_flags.difference_update(
            {
                "cwc_calibrated_single_point",
                "low_volume_confidence",
                "needs_cwc_calibration",
                "phase0_cwc_validation_incomplete",
                "volume_area_ratio_proxy",
            }
        )
        current_flags.update(info.get("flags") or [])
        current_flags.add("rebuilt_from_csv")
        reservoir["flags"] = sorted(current_flags)

    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def main() -> int:
    args = parse_args()
    reservoirs_dir = args.data_dir / "reservoirs"
    if args.reservoirs:
        ids = list(args.reservoirs)
    else:
        ids = sorted(p.stem for p in reservoirs_dir.glob("*.csv"))
    cwc_storage = load_cwc_storage()
    infos: dict[str, dict] = {}
    for rid in ids:
        info = rebuild_one(rid, args.data_dir, cwc_storage)
        infos[rid] = info
        b = info["curve_b"]
        b_str = f"{b:.3f}" if b is not None else "n/a"
        print(
            f"{rid}: full_pool={info['full_pool_area_km2']:.2f} km2, "
            f"capacity={info['full_capacity_bcm']:.3f} bcm, exponent b={b_str}"
        )
    update_snapshot_json(args.data_dir, infos)
    print("dashboard/public/data/reservoirs.json refreshed (current block + flags)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

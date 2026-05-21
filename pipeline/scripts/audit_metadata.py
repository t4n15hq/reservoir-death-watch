#!/usr/bin/env python
"""Audit the reservoir metadata in `docs/reservoirs.csv` against the live
pipeline snapshot, producing a per-reservoir provenance record and a
top-line count of what's verified vs unverified.

Writes `dashboard/public/data/data_provenance.json` for the UI to consume.

Definitions of "verified":
- lat/lon: marked verified iff `coord_verified_at` is present in the CSV
  (set by hand after a CWC bulletin or OSM cross-check).
- full-pool/live capacity: verified iff a matching CWC row provides
  `live_capacity_at_frl_bcm`.
- dead-storage capacity: unverified until an explicit source column is added.
- population: verified iff `population_source` is present in the CSV
  (set when a census reference is added).

Anything else is "approximate / unverified" — honestly labeled.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime

from reservoirs.config import DASHBOARD_DATA_DIR, RESERVOIRS_CSV
from reservoirs.cwc_scraper import load_cwc_storage


def build_provenance() -> dict:
    rows = list(csv.DictReader(RESERVOIRS_CSV.open()))
    try:
        cwc = load_cwc_storage()
        cwc_latest = _latest_cwc_by_reservoir(cwc)
    except Exception:
        cwc_latest = {}

    snapshot_path = DASHBOARD_DATA_DIR / "reservoirs.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text())
    else:
        snapshot = {"reservoirs": []}
    by_id = {r["id"]: r for r in snapshot.get("reservoirs", [])}

    per_reservoir = []
    for row in rows:
        entry = snapshot_entry_classification(row, by_id.get(row["id"]), cwc_latest)
        per_reservoir.append(entry)

    counts = aggregate_counts(per_reservoir)
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "counts": counts,
        "reservoirs": per_reservoir,
    }


def snapshot_entry_classification(
    row: dict, snapshot_entry: dict | None, cwc_latest: dict[str, dict]
) -> dict:
    rid = row["id"]
    flags = (snapshot_entry or {}).get("flags") or []
    current = (snapshot_entry or {}).get("current", {})
    cwc_row = cwc_latest.get(rid)
    cwc_live_capacity = _opt_float_from_value(
        cwc_row.get("live_capacity_at_frl_bcm") if cwc_row else None
    )

    cwc_reference_available = current.get("cwc_reported_bcm") is not None
    full_capacity_verified = cwc_live_capacity is not None
    coord_verified = bool(row.get("coord_verified_at"))
    population_verified = bool(row.get("population_source"))

    return {
        "id": rid,
        "name": row["name"],
        "lat_lon": {
            "value": [float(row["lat"]), float(row["lon"])],
            "verified": coord_verified,
            "source": row.get("coord_verified_at") or "approximate (training-data knowledge)",
        },
        "full_pool_capacity_bcm": {
            "value": cwc_live_capacity or _opt_float(row.get("full_pool_capacity_bcm")),
            "verified": full_capacity_verified,
            "source": (
                "CWC bulletin live_capacity_at_frl_bcm"
                if full_capacity_verified
                else "approximate (training-data knowledge)"
            ),
        },
        "dead_storage_capacity_bcm": {
            "value": _opt_float(row.get("dead_storage_capacity_bcm")),
            "verified": False,
            "source": "approximate (training-data knowledge)",
        },
        "population_served": {
            "value": _opt_int(row.get("population_served")),
            "verified": population_verified,
            "source": row.get("population_source") or "approximate (order-of-magnitude estimate)",
        },
        "city_served": {
            "value": row.get("city_served") or "",
            "verified": False,
            "source": "editorial label",
        },
        "aoi": {
            "verified": not any(
                f in flags
                for f in (
                    "awaiting_first_observation",
                    "first_pass_needs_manual_review",
                    "manual_bbox_needs_visual_check",
                    "needs_aoi_seeding",
                )
            ),
            "flag": next(
                (
                    f
                    for f in flags
                    if f
                    in (
                        "awaiting_first_observation",
                        "first_pass_needs_manual_review",
                        "manual_bbox_needs_visual_check",
                        "needs_aoi_seeding",
                    )
                ),
                None,
            ),
        },
        "storage_calibration": {
            "method": _storage_method(flags),
            "cwc_anchored": "cwc_calibrated_single_point" in flags,
        },
        "cwc_reference": {
            "available": cwc_reference_available,
            "as_of": current.get("cwc_as_of"),
            "reported_bcm": current.get("cwc_reported_bcm"),
        },
        "current_observation": {
            "as_of": current.get("as_of"),
            "data_source": current.get("data_source"),
        },
    }


def _storage_method(flags: list[str]) -> str:
    if "cwc_calibrated_single_point" in flags:
        return "cwc_calibrated_power_law"
    if "volume_area_ratio_proxy" in flags:
        return "area_ratio_proxy"
    if "awaiting_first_observation" in flags:
        return "pending"
    return "unknown"


def aggregate_counts(per_reservoir: list[dict]) -> dict:
    total = len(per_reservoir)
    coord_v = sum(1 for r in per_reservoir if r["lat_lon"]["verified"])
    full_capacity_cwc = sum(1 for r in per_reservoir if r["full_pool_capacity_bcm"]["verified"])
    dead_capacity_v = sum(1 for r in per_reservoir if r["dead_storage_capacity_bcm"]["verified"])
    cap_v = sum(
        1
        for r in per_reservoir
        if r["full_pool_capacity_bcm"]["verified"]
        and r["dead_storage_capacity_bcm"]["verified"]
    )
    pop_v = sum(1 for r in per_reservoir if r["population_served"]["verified"])
    aoi_v = sum(1 for r in per_reservoir if r["aoi"]["verified"])
    cwc_reference = sum(1 for r in per_reservoir if r["cwc_reference"]["available"])
    cwc_calibrated = sum(
        1 for r in per_reservoir if r["storage_calibration"]["cwc_anchored"]
    )
    observed = sum(
        1
        for r in per_reservoir
        if r["current_observation"]["as_of"]
        and r["current_observation"]["as_of"] != "1900-01-01"
    )

    return {
        "total_reservoirs": total,
        "observed_with_satellite": observed,
        "aoi_visually_reviewed": aoi_v,
        "cwc_reference_available": cwc_reference,
        "storage_cwc_calibrated": cwc_calibrated,
        "lat_lon_verified": coord_v,
        "full_pool_capacity_from_cwc": full_capacity_cwc,
        "dead_storage_capacity_verified": dead_capacity_v,
        "capacity_verified_against_cwc": cap_v,
        "population_verified_against_census": pop_v,
    }


def _latest_cwc_by_reservoir(cwc) -> dict[str, dict]:
    if cwc.empty:
        return {}
    latest: dict[str, dict] = {}
    for record in cwc.sort_values("date").to_dict("records"):
        latest[str(record["reservoir_id"])] = record
    return latest


def _opt_float(value: str | None) -> float | None:
    if not value:
        return None
    return _opt_float_from_value(value)


def _opt_float_from_value(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opt_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def main() -> int:
    provenance = build_provenance()
    path = DASHBOARD_DATA_DIR / "data_provenance.json"
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)

    counts = provenance["counts"]
    print(f"Wrote {path}")
    print(f"  total reservoirs:                       {counts['total_reservoirs']}")
    print(f"  observed (≥1 satellite obs):            {counts['observed_with_satellite']}")
    print(f"  AOI visually reviewed:                  {counts['aoi_visually_reviewed']}")
    print(f"  CWC reference rows loaded:              {counts['cwc_reference_available']}")
    print(f"  storage CWC-calibrated:                 {counts['storage_cwc_calibrated']}")
    print(f"  lat/lon verified against CWC/OSM:       {counts['lat_lon_verified']}")
    cap = counts["full_pool_capacity_from_cwc"]
    dead = counts["dead_storage_capacity_verified"]
    pop = counts["population_verified_against_census"]
    print(f"  FRL capacity loaded from CWC bulletin:  {cap}")
    print(f"  dead-storage capacity verified:         {dead}")
    print(f"  population verified against census:     {pop}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

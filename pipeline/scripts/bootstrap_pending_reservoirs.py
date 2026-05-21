#!/usr/bin/env python
"""Add placeholder entries to `reservoirs.json` for reservoirs in the master
list that don't have pipeline data yet.

This is an honesty-preserving stub: every placeholder is marked stale, carries
`awaiting_first_observation` in its flags, and has zero storage / no
projection. When the real pipeline runs against the reservoir its entry is
replaced with observed data; until then the dashboard shows the pin as
"no recent observation" rather than dropping it from the map entirely.

Use after editing `docs/reservoirs.csv` or before you've had a chance to seed
the AOIs.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from reservoirs.config import DASHBOARD_DATA_DIR, MODEL_VERSION, RESERVOIRS_CSV
from reservoirs.cwc_scraper import load_cwc_storage
from reservoirs.schemas import DashboardSnapshot
from reservoirs.state_aggregates import build_state_aggregates

PLACEHOLDER_AS_OF = "1900-01-01"
PLACEHOLDER_FLAGS = ["awaiting_first_observation", "needs_aoi_seeding"]


def make_placeholder(row: dict[str, str], cwc_row: dict | None = None) -> dict:
    """Build a schema-valid `reservoirs.json` entry for a reservoir we haven't
    actually observed yet. Storage values are zero (honest), tier is the
    lowest-severity bucket so it can't masquerade as a real critical signal,
    and `awaiting_first_observation` flags it explicitly.
    """

    def opt_float(value: str) -> float | None:
        return float(value) if value else None

    def opt_int(value: str) -> int | None:
        return int(value) if value else None

    cwc_reported = opt_float(str(cwc_row.get("live_storage_bcm", ""))) if cwc_row else None
    cwc_as_of = cwc_row.get("date").isoformat() if cwc_row else None
    cwc_capacity = (
        opt_float(str(cwc_row.get("live_capacity_at_frl_bcm", ""))) if cwc_row else None
    )
    scope = row.get("scope") or "core_city"
    flags = list(PLACEHOLDER_FLAGS)

    return {
        "id": row["id"],
        "name": row["name"],
        "river": row["river"],
        "state": row["state"],
        "city_served": row.get("city_served", ""),
        "population_served": opt_int(row.get("population_served") or ""),
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "full_pool_area_km2": None,
        "full_pool_capacity_bcm": (
            cwc_capacity or opt_float(row.get("full_pool_capacity_bcm") or "")
        ),
        "dead_storage_capacity_bcm": opt_float(row.get("dead_storage_capacity_bcm") or ""),
        "current": {
            "as_of": PLACEHOLDER_AS_OF,
            "area_km2": 0.0,
            "estimated_storage_bcm": 0.0,
            "cwc_reported_bcm": cwc_reported,
            "cwc_as_of": cwc_as_of,
            "percent_full": 0.0,
            "data_source": "stale",
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
        "tier": "stable",
        "model_version": MODEL_VERSION,
        "scope": scope,
        "flags": flags,
    }


def merge_placeholders(
    snapshot: dict,
    csv_rows: list[dict[str, str]],
    cwc_latest: dict[str, dict],
) -> dict:
    by_id = {r["id"]: r for r in snapshot.get("reservoirs", [])}
    for row in csv_rows:
        if row["id"] not in by_id:
            by_id[row["id"]] = make_placeholder(row, cwc_latest.get(row["id"]))
        else:
            by_id[row["id"]]["scope"] = row.get("scope") or by_id[row["id"]].get(
                "scope",
                "core_city",
            )
            flags = set(by_id[row["id"]].get("flags") or [])
            flags.difference_update({"core_city", "expanded_cwc"})
            by_id[row["id"]]["flags"] = sorted(flags)
    # Re-sort to follow priority order from CSV (so the JSON's reservoir list
    # is deterministic and matches what tier/aggregate computations expect).
    priority_index = {row["id"]: int(row["priority"]) for row in csv_rows}
    ordered = sorted(by_id.values(), key=lambda r: priority_index.get(r["id"], 9999))
    snapshot["reservoirs"] = ordered
    return snapshot


def recompute_aggregates(snapshot: dict) -> dict:
    """Recompute national_aggregate over only the observed reservoirs.

    Including placeholders in the denominator would drag percent-full down
    artificially (e.g. 4.2% national fill when 22 placeholders contribute 0
    storage but their full-pool capacity inflates the denominator). The
    honest framing is "of the X reservoirs we've actually observed, Y% is
    currently stored"; the observed-vs-master count is surfaced separately.
    """

    reservoirs = snapshot["reservoirs"]

    def is_observed(r: dict) -> bool:
        return "awaiting_first_observation" not in (r.get("flags") or [])

    observed = [r for r in reservoirs if is_observed(r)]
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

    percent_full = (
        round((current_storage / total_capacity * 100), 1) if total_capacity else 0.0
    )
    snapshot["national_aggregate"] = {
        "total_capacity_bcm": round(total_capacity, 3),
        "current_storage_bcm": round(current_storage, 3),
        "percent_full": percent_full,
        "reservoirs_critical": tiers["critical"],
        "reservoirs_warning": tiers["warning"],
        "reservoirs_watch": tiers["watch"],
        "reservoirs_stable": tiers["stable"],
        "people_at_risk_neutral": at_risk,
        "people_at_risk_el_nino": 0,
    }
    # The dashboard derives observed-vs-pending counts from the flags rather
    # than from a new schema field, so DashboardSnapshot's extra="forbid"
    # doesn't need to relax.
    return snapshot


def write_state_aggregates(snapshot: dict, data_dir: Path) -> None:
    # Validate via pydantic to be confident the JSON we wrote is schema-clean.
    parsed = DashboardSnapshot.model_validate(snapshot)
    states = build_state_aggregates(parsed.reservoirs, generated_at=datetime.now(UTC))
    tmp = data_dir / "state_aggregates.json.tmp"
    with tmp.open("w") as handle:
        json.dump(states, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(data_dir / "state_aggregates.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    parser.add_argument("--reservoirs-csv", type=Path, default=RESERVOIRS_CSV)
    return parser.parse_args()


def latest_cwc_by_reservoir() -> dict[str, dict]:
    try:
        cwc = load_cwc_storage()
    except Exception:  # noqa: BLE001
        return {}
    latest: dict[str, dict] = {}
    for record in cwc.sort_values("date").to_dict("records"):
        latest[str(record["reservoir_id"])] = record
    return latest


def main() -> int:
    args = parse_args()
    snapshot_path = args.data_dir / "reservoirs.json"
    with snapshot_path.open() as handle:
        snapshot = json.load(handle)
    csv_rows = list(csv.DictReader(args.reservoirs_csv.open()))
    cwc_latest = latest_cwc_by_reservoir()

    before = len(snapshot["reservoirs"])
    snapshot = merge_placeholders(snapshot, csv_rows, cwc_latest)
    snapshot = recompute_aggregates(snapshot)
    snapshot["generated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Validate before writing — catches schema drift before the dashboard hits it.
    DashboardSnapshot.model_validate(snapshot)

    tmp = snapshot_path.with_suffix(".json.tmp")
    with tmp.open("w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(snapshot_path)
    write_state_aggregates(snapshot, args.data_dir)

    after = len(snapshot["reservoirs"])
    added = after - before
    print(f"reservoirs.json: {before} → {after} entries ({added} placeholders added)")
    print("state_aggregates.json refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Run JRC history + S2 depletion fit + projection per reservoir, merge in.

Reuses `pipeline.build_reservoir_result` (the same logic the full pipeline
uses) but writes the resulting `ReservoirResult` into the existing
`reservoirs.json` instead of overwriting it. Use this when you've already
got the Phase 0 reservoirs populated and just want to backfill new ones
without redoing everything.

Also writes the per-reservoir CSV that the dashboard's history chart reads.

Slow — each reservoir does 42 years of monthly JRC reductions plus ~15
Sentinel-2 composite windows. Expect roughly 60–180 seconds per reservoir.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from reservoirs.aois import load_aois
from reservoirs.config import DASHBOARD_DATA_DIR
from reservoirs.cwc_scraper import load_cwc_storage
from reservoirs.jrc import extract_jrc_history
from reservoirs.pipeline import build_reservoir_result
from reservoirs.sentinel import extract_recent_area, extract_s2_area_series


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reservoirs", nargs="+", help="reservoir IDs to backfill")
    parser.add_argument("--as-of", default=None, help="ISO date for current observation")
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    parser.add_argument("--jrc-start", default="2000-01-01")
    return parser.parse_args()


def load_snapshot(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def write_snapshot(path: Path, snapshot: dict) -> None:
    snapshot["generated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def write_csv(data_dir: Path, reservoir_id: str, history_frame: pd.DataFrame) -> None:
    out_dir = data_dir / "reservoirs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{reservoir_id}.csv"
    tmp = path.with_suffix(".csv.tmp")
    history_frame.to_csv(tmp, index=False)
    tmp.replace(path)


def backfill_one(
    reservoir_id: str,
    *,
    as_of: date,
    jrc_start: str,
    cwc_storage: pd.DataFrame,
) -> tuple[dict, pd.DataFrame]:
    aois = load_aois([reservoir_id])
    aoi = aois[0]

    print(f"{reservoir_id}: JRC history from {jrc_start}", flush=True)
    jrc_history = extract_jrc_history(aoi, start=jrc_start, end=as_of)
    print(f"{reservoir_id}: Sentinel-2 series (150d)", flush=True)
    s2_series = extract_s2_area_series(aoi, as_of=as_of)
    print(f"{reservoir_id}: current Sentinel-2/1 observation", flush=True)
    current = extract_recent_area(aoi, as_of=as_of)

    result, history_frame = build_reservoir_result(
        aoi,
        jrc_history=jrc_history,
        s2_series=s2_series,
        current=current,
        as_of=as_of,
        cwc_storage=cwc_storage if not cwc_storage.empty else None,
    )
    return result.model_dump(mode="json"), history_frame


def main() -> int:
    args = parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    snapshot_path = args.data_dir / "reservoirs.json"
    snapshot = load_snapshot(snapshot_path)

    try:
        cwc_storage = load_cwc_storage()
    except Exception as exc:  # noqa: BLE001
        print(f"CWC storage unavailable: {exc}", file=sys.stderr, flush=True)
        cwc_storage = pd.DataFrame()

    by_id = {r["id"]: r for r in snapshot["reservoirs"]}
    written = 0
    failed: list[str] = []
    for rid in args.reservoirs:
        try:
            entry, history_frame = backfill_one(
                rid,
                as_of=as_of,
                jrc_start=args.jrc_start,
                cwc_storage=cwc_storage,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{rid}: FAILED — {exc}", file=sys.stderr, flush=True)
            failed.append(rid)
            continue
        by_id[rid] = entry
        write_csv(args.data_dir, rid, history_frame)
        snapshot["reservoirs"] = sorted(by_id.values(), key=lambda r: r["id"])
        write_snapshot(snapshot_path, snapshot)
        written += 1
        print(
            f"{rid}: tier={entry['tier']} "
            f"area={entry['current']['area_km2']} km² "
            f"days_to_dead={entry['projection']['neutral_monsoon']['days_to_dead_storage']}",
            flush=True,
        )

    print(f"\nbackfilled {written} reservoirs; {len(failed)} failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

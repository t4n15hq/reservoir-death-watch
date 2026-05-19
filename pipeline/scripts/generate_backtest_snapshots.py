#!/usr/bin/env python
"""Generate the four backtest snapshot JSONs the dashboard's `?backtest=`
mode reads.

For each case in `reservoirs.backtest.BACKTEST_CASES`, runs the full
pipeline against the historical `as_of` date and writes the snapshot
to `dashboard/public/data/backtest_<case_id>.json`. Skips re-export so
the live `reservoirs.json` is untouched.

Slow — ~3-7 min per case. Run when you've changed model logic or after
adding new backtest cases.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from reservoirs.backtest import BACKTEST_CASES
from reservoirs.config import DASHBOARD_DATA_DIR
from reservoirs.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="*", help="Case IDs (default: all four)")
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case_ids = args.cases or list(BACKTEST_CASES.keys())
    written = 0
    failed: list[str] = []

    for case_id in case_ids:
        if case_id not in BACKTEST_CASES:
            print(f"unknown case: {case_id}")
            failed.append(case_id)
            continue
        case = BACKTEST_CASES[case_id]
        print(f"\n=== {case_id} ({case['reservoir_id']} @ {case['as_of']}) ===")
        try:
            snapshot = run_pipeline(
                as_of=case["as_of"],
                reservoirs=[case["reservoir_id"]],
                export=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: {exc}")
            failed.append(case_id)
            continue

        # Note the historical context up-front so the dashboard banner can
        # render it without re-deriving the case from the URL.
        payload = snapshot.model_dump(mode="json")
        payload["backtest"] = {
            "case_id": case_id,
            "reservoir_id": case["reservoir_id"],
            "as_of": case["as_of"].isoformat(),
            "expected_tiers": sorted(case["tiers"]),
            "actual_tier": snapshot.reservoirs[0].tier,
            "passed": snapshot.reservoirs[0].tier in case["tiers"],
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

        out_path = args.data_dir / f"backtest_{case_id}.json"
        tmp = out_path.with_suffix(".json.tmp")
        with tmp.open("w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        tmp.replace(out_path)
        bt = payload["backtest"]
        print(f"wrote {out_path}: tier={bt['actual_tier']} pass={bt['passed']}")
        written += 1

    print(f"\n{written} snapshots written, {len(failed)} failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

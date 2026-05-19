#!/usr/bin/env python
"""Run the Phase 0 ±10% / six-month CWC validation gate.

Reads checked-in CWC bulletin CSVs and the latest pipeline export, compares
satellite-derived storage to CWC live storage per reservoir, and prints a
PASS/FAIL summary plus an optional CSV breakdown.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from reservoirs.config import (
    CWC_DIR,
    DASHBOARD_DATA_DIR,
    PHASE0_GATE_TOLERANCE,
    PHASE0_GATE_WINDOW_DAYS,
)
from reservoirs.validate import (
    format_phase0_gate_report,
    run_phase0_gate,
    write_phase0_gate_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--reservoir",
        action="append",
        dest="reservoirs",
        help="Limit to these reservoir IDs (default: every reservoir in the CWC CSVs).",
    )
    parser.add_argument("--tolerance", type=float, default=PHASE0_GATE_TOLERANCE)
    parser.add_argument("--window-days", type=int, default=PHASE0_GATE_WINDOW_DAYS)
    parser.add_argument("--data-dir", type=Path, default=DASHBOARD_DATA_DIR)
    parser.add_argument("--cwc-dir", type=Path, default=CWC_DIR)
    parser.add_argument(
        "--report-csv",
        type=Path,
        default=None,
        help="Optional path to write a per-comparison CSV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_phase0_gate(
        as_of=args.as_of,
        reservoir_ids=args.reservoirs,
        tolerance=args.tolerance,
        window_days=args.window_days,
        data_dir=args.data_dir,
        cwc_directory=args.cwc_dir,
    )
    print(format_phase0_gate_report(report))
    if args.report_csv:
        write_phase0_gate_csv(report, args.report_csv)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

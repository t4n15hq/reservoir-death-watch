"""Phase 0 gate: compare satellite-derived storage to CWC ground truth.

The gate in `docs/PHASES.md` requires every Phase 0 reservoir's satellite
trace to be within ±10% of CWC over the last six months. This module
implements that check from checked-in artifacts (per-reservoir CSVs and
CWC bulletin CSVs) so it can run without re-hitting Earth Engine.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from reservoirs.config import (
    CWC_BULLETINS_GLOB,
    CWC_DIR,
    CWC_PHASE0_STORAGE_CSV,
    DASHBOARD_DATA_DIR,
    PHASE0_GATE_TOLERANCE,
    PHASE0_GATE_WINDOW_DAYS,
)
from reservoirs.cwc_scraper import load_cwc_storage


@dataclass(frozen=True)
class BulletinComparison:
    reservoir_id: str
    cwc_date: date
    cwc_storage_bcm: float
    satellite_date: date
    satellite_storage_bcm: float
    days_apart: int
    relative_error: float


@dataclass(frozen=True)
class ReservoirGateReport:
    reservoir_id: str
    n_comparisons: int
    n_within_tolerance: int
    mean_absolute_error: float
    max_absolute_error: float
    passed: bool
    comparisons: list[BulletinComparison]


@dataclass(frozen=True)
class Phase0GateReport:
    as_of: date
    tolerance: float
    window_days: int
    reservoirs: list[ReservoirGateReport]

    @property
    def passed(self) -> bool:
        return bool(self.reservoirs) and all(r.passed for r in self.reservoirs)


def load_satellite_history(
    reservoir_id: str,
    *,
    data_dir: Path = DASHBOARD_DATA_DIR,
) -> pd.DataFrame:
    """Load the per-reservoir CSV the export step wrote."""

    path = data_dir / "reservoirs" / f"{reservoir_id}.csv"
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def compare_to_bulletins(
    cwc_rows: pd.DataFrame,
    satellite_history: pd.DataFrame,
    *,
    max_match_days: int = 14,
) -> list[BulletinComparison]:
    """For each CWC row, pick the nearest satellite obs and compare storages."""

    if cwc_rows.empty or satellite_history.empty:
        return []

    usable = satellite_history[
        (satellite_history["estimated_storage_bcm"].notna())
        & (satellite_history["estimated_storage_bcm"] > 0)
    ]
    if usable.empty:
        return []

    comparisons: list[BulletinComparison] = []
    for cwc_row in cwc_rows.itertuples(index=False):
        cwc_date = cwc_row.date
        deltas = usable["date"].map(lambda value, target=cwc_date: abs((value - target).days))
        nearest_index = deltas.idxmin()
        days_apart = int(deltas.loc[nearest_index])
        if days_apart > max_match_days:
            continue
        sat_row = usable.loc[nearest_index]
        sat_storage = float(sat_row["estimated_storage_bcm"])
        cwc_storage = float(cwc_row.live_storage_bcm)
        if cwc_storage <= 0:
            continue
        relative_error = (sat_storage - cwc_storage) / cwc_storage
        comparisons.append(
            BulletinComparison(
                reservoir_id=str(cwc_row.reservoir_id),
                cwc_date=cwc_row.date,
                cwc_storage_bcm=cwc_storage,
                satellite_date=sat_row["date"],
                satellite_storage_bcm=sat_storage,
                days_apart=days_apart,
                relative_error=relative_error,
            )
        )
    return comparisons


def report_for_reservoir(
    reservoir_id: str,
    comparisons: list[BulletinComparison],
    *,
    tolerance: float = PHASE0_GATE_TOLERANCE,
) -> ReservoirGateReport:
    if not comparisons:
        return ReservoirGateReport(
            reservoir_id=reservoir_id,
            n_comparisons=0,
            n_within_tolerance=0,
            mean_absolute_error=0.0,
            max_absolute_error=0.0,
            passed=False,
            comparisons=[],
        )

    abs_errors = [abs(c.relative_error) for c in comparisons]
    within = sum(1 for e in abs_errors if e <= tolerance)
    return ReservoirGateReport(
        reservoir_id=reservoir_id,
        n_comparisons=len(comparisons),
        n_within_tolerance=within,
        mean_absolute_error=sum(abs_errors) / len(abs_errors),
        max_absolute_error=max(abs_errors),
        passed=within == len(comparisons),
        comparisons=comparisons,
    )


def run_phase0_gate(
    *,
    as_of: date | None = None,
    reservoir_ids: list[str] | None = None,
    tolerance: float = PHASE0_GATE_TOLERANCE,
    window_days: int = PHASE0_GATE_WINDOW_DAYS,
    data_dir: Path = DASHBOARD_DATA_DIR,
    cwc_directory: Path = CWC_DIR,
    cwc_bulletin_glob: str = CWC_BULLETINS_GLOB,
    cwc_phase0_fallback: Path | None = CWC_PHASE0_STORAGE_CSV,
) -> Phase0GateReport:
    """Run the ±10% / six-month gate over all Phase 0 reservoirs."""

    cutoff = (as_of or date.today()) - timedelta(days=window_days)
    cwc_storage = load_cwc_storage(
        directory=cwc_directory,
        bulletin_glob=cwc_bulletin_glob,
        phase0_fallback=cwc_phase0_fallback,
    )
    cwc_window = cwc_storage[cwc_storage["date"] >= cutoff]

    reservoir_ids = reservoir_ids or sorted(cwc_window["reservoir_id"].unique().tolist())
    reservoirs: list[ReservoirGateReport] = []
    for reservoir_id in reservoir_ids:
        cwc_rows = cwc_window[cwc_window["reservoir_id"] == reservoir_id]
        try:
            history = load_satellite_history(reservoir_id, data_dir=data_dir)
        except FileNotFoundError:
            history = pd.DataFrame(columns=["date", "estimated_storage_bcm"])
        comparisons = compare_to_bulletins(cwc_rows, history)
        reservoirs.append(report_for_reservoir(reservoir_id, comparisons, tolerance=tolerance))

    return Phase0GateReport(
        as_of=as_of or date.today(),
        tolerance=tolerance,
        window_days=window_days,
        reservoirs=reservoirs,
    )


def format_phase0_gate_report(report: Phase0GateReport) -> str:
    lines = [
        f"Phase 0 gate (window={report.window_days}d, tolerance=±{report.tolerance:.0%})",
        f"  as of {report.as_of.isoformat()}",
    ]
    if not report.reservoirs:
        lines.append("  no reservoirs evaluated — no CWC bulletins found in window")
        return "\n".join(lines)

    for r in report.reservoirs:
        verdict = "PASS" if r.passed else "FAIL"
        if r.n_comparisons == 0:
            lines.append(f"  [{verdict}] {r.reservoir_id}: no comparable bulletins in window")
            continue
        lines.append(
            f"  [{verdict}] {r.reservoir_id}: {r.n_within_tolerance}/{r.n_comparisons} within "
            f"±{report.tolerance:.0%}; mean|err|={r.mean_absolute_error:.1%}, "
            f"max|err|={r.max_absolute_error:.1%}"
        )
        for c in r.comparisons:
            marker = "ok" if abs(c.relative_error) <= report.tolerance else "MISS"
            lines.append(
                f"      {marker:>4}  cwc {c.cwc_date}  {c.cwc_storage_bcm:.3f} bcm  "
                f"vs sat {c.satellite_date} {c.satellite_storage_bcm:.3f} bcm  "
                f"({c.relative_error:+.1%}, Δ{c.days_apart}d)"
            )

    summary = "PASS" if report.passed else "FAIL"
    lines.append(f"Overall: {summary}")
    return "\n".join(lines)


def write_phase0_gate_csv(report: Phase0GateReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "reservoir_id",
                "cwc_date",
                "cwc_storage_bcm",
                "satellite_date",
                "satellite_storage_bcm",
                "days_apart",
                "relative_error",
                "within_tolerance",
            ]
        )
        for r in report.reservoirs:
            for c in r.comparisons:
                writer.writerow(
                    [
                        c.reservoir_id,
                        c.cwc_date.isoformat(),
                        f"{c.cwc_storage_bcm:.6f}",
                        c.satellite_date.isoformat(),
                        f"{c.satellite_storage_bcm:.6f}",
                        c.days_apart,
                        f"{c.relative_error:.6f}",
                        "yes" if abs(c.relative_error) <= report.tolerance else "no",
                    ]
                )

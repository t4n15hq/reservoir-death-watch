from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from reservoirs.validate import (
    Phase0GateReport,
    compare_to_bulletins,
    format_phase0_gate_report,
    report_for_reservoir,
    run_phase0_gate,
    write_phase0_gate_csv,
)


def _cwc_frame(rows):
    return pd.DataFrame(rows)


def _sat_history(rows):
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def test_compare_to_bulletins_matches_nearest_within_window() -> None:
    cwc = _cwc_frame(
        [
            {
                "reservoir_id": "krs",
                "date": date(2026, 4, 9),
                "live_storage_bcm": 0.48,
            },
            {
                "reservoir_id": "krs",
                "date": date(2026, 5, 7),
                "live_storage_bcm": 0.30,
            },
        ]
    )
    sat = _sat_history(
        [
            {"date": "2026-04-05", "estimated_storage_bcm": 0.50},
            {"date": "2026-05-05", "estimated_storage_bcm": 0.28},
            {"date": "2026-05-15", "estimated_storage_bcm": 0.08},
        ]
    )

    comparisons = compare_to_bulletins(cwc, sat)

    assert len(comparisons) == 2
    first = comparisons[0]
    assert first.cwc_date == date(2026, 4, 9)
    assert first.satellite_date == date(2026, 4, 5)
    assert first.relative_error == (0.50 - 0.48) / 0.48
    second = comparisons[1]
    assert second.satellite_date == date(2026, 5, 5)
    assert second.days_apart == 2


def test_compare_to_bulletins_skips_when_no_match_in_window() -> None:
    cwc = _cwc_frame(
        [{"reservoir_id": "krs", "date": date(2026, 4, 9), "live_storage_bcm": 0.48}]
    )
    sat = _sat_history(
        [{"date": "2025-01-01", "estimated_storage_bcm": 0.7}]
    )

    assert compare_to_bulletins(cwc, sat, max_match_days=14) == []


def test_report_for_reservoir_passes_when_every_comparison_within_tolerance() -> None:
    cwc = _cwc_frame(
        [
            {"reservoir_id": "mettur", "date": date(2026, 3, 1), "live_storage_bcm": 1.00},
            {"reservoir_id": "mettur", "date": date(2026, 4, 1), "live_storage_bcm": 0.90},
        ]
    )
    sat = _sat_history(
        [
            {"date": "2026-03-01", "estimated_storage_bcm": 1.05},
            {"date": "2026-04-01", "estimated_storage_bcm": 0.83},
        ]
    )
    comparisons = compare_to_bulletins(cwc, sat)

    report = report_for_reservoir("mettur", comparisons, tolerance=0.10)

    assert report.passed is True
    assert report.n_within_tolerance == 2
    assert report.max_absolute_error <= 0.10


def test_report_for_reservoir_flags_a_miss() -> None:
    cwc = _cwc_frame(
        [{"reservoir_id": "indira_sagar", "date": date(2026, 4, 9), "live_storage_bcm": 4.0}]
    )
    sat = _sat_history(
        [{"date": "2026-04-10", "estimated_storage_bcm": 5.5}]
    )
    comparisons = compare_to_bulletins(cwc, sat)

    report = report_for_reservoir("indira_sagar", comparisons, tolerance=0.10)

    assert report.passed is False
    assert report.n_comparisons == 1
    assert abs(report.comparisons[0].relative_error) > 0.10


def test_run_phase0_gate_reads_directory_and_per_reservoir_csv(tmp_path: Path) -> None:
    cwc_dir = tmp_path / "cwc"
    cwc_dir.mkdir()
    bulletin = cwc_dir / "bulletin_2026_04_09.csv"
    bulletin.write_text(
        "reservoir_id,cwc_name,date,live_capacity_at_frl_bcm,live_storage_bcm,"
        "percent_frl,normal_storage_bcm,percent_normal,source_url,source_lines\n"
        "krs,KRS,2026-04-09,1.163,0.480,41.30,0.355,30.54,https://example/bulletin.pdf,L1\n"
    )

    data_dir = tmp_path / "data"
    (data_dir / "reservoirs").mkdir(parents=True)
    (data_dir / "reservoirs" / "krs.csv").write_text(
        "date,area_km2,data_source,cloud_coverage_percent,"
        "estimated_storage_bcm,cwc_storage_bcm,percent_full\n"
        "2026-04-07,40.0,sentinel_2,5.0,0.70,,60.0\n"
    )

    report = run_phase0_gate(
        as_of=date(2026, 5, 18),
        data_dir=data_dir,
        cwc_directory=cwc_dir,
        cwc_phase0_fallback=None,
    )

    assert isinstance(report, Phase0GateReport)
    assert [r.reservoir_id for r in report.reservoirs] == ["krs"]
    krs = report.reservoirs[0]
    assert krs.n_comparisons == 1
    assert krs.passed is False
    assert abs(krs.comparisons[0].relative_error - (0.70 - 0.48) / 0.48) < 1e-9

    rendered = format_phase0_gate_report(report)
    assert "krs" in rendered
    assert "FAIL" in rendered

    csv_path = tmp_path / "out.csv"
    write_phase0_gate_csv(report, csv_path)
    contents = csv_path.read_text()
    assert "reservoir_id" in contents.splitlines()[0]
    assert "krs," in contents

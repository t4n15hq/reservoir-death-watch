from __future__ import annotations

from datetime import date

import pytest

from reservoirs.cwc_scraper import (
    CWCFormatError,
    load_cwc_storage,
    load_cwc_storage_csv,
    parse_bulletin_text,
    parse_weekly_report_text,
)

ALIASES = {
    "Krishna Raja Sagar": "krs",
    "Mettur": "mettur",
    "Indira Sagar": "indira_sagar",
}


def test_parse_bulletin_text_extracts_known_reservoir_rows() -> None:
    text = """
    CENTRAL WATER COMMISSION RESERVOIR STORAGE POSITION AS ON 14/05/2026
    Sl No Reservoir Live Storage BCM Percent FRL Percent Normal
    1 Krishna Raja Sagar 0.81 56.9 72.4
    2 Mettur 1.10 41.5 63.0
    3 Indira Sagar 5.40 44.2 88.0
    """

    frame = parse_bulletin_text(text, reservoir_aliases=ALIASES)

    assert set(frame["reservoir_id"]) == {"krs", "mettur", "indira_sagar"}
    krs = frame[frame["reservoir_id"] == "krs"].iloc[0]
    assert krs["date"] == date(2026, 5, 14)
    assert krs["live_storage_bcm"] == pytest.approx(0.81)
    assert krs["percent_frl"] == pytest.approx(56.9)


def test_parse_bulletin_text_accepts_explicit_date() -> None:
    frame = parse_bulletin_text(
        "Mettur 1.10 41.5 63.0",
        reservoir_aliases=ALIASES,
        bulletin_date=date(2026, 5, 15),
    )

    assert frame.iloc[0]["date"] == date(2026, 5, 15)


def test_parse_bulletin_text_fails_loudly_without_matches() -> None:
    with pytest.raises(CWCFormatError):
        parse_bulletin_text("AS ON 14/05/2026 No reservoirs here", reservoir_aliases=ALIASES)


def test_parse_weekly_report_text_extracts_detailed_rows() -> None:
    text = """
    70 KRISHNARAJA
    SAGARA
    Karnataka 79.000 0.000 752.500 1.163 09.04.2026
    745.885 0.480 41.30 746.068 0.607 52.23 0.355 30.54 79.07 135.22
    92 METTUR Tamil Nadu 122.000 360.000 240.790 2.647 09.04.2026
    229.296 1.254 47.37 237.080 2.134 80.61 1.215 45.91 58.76 103.17
    46 INDIRA SAGAR Madhya Pradesh 123.000 1000.000 262.130 9.745
    09.04.2026 254.620 4.192 43.02 254.220 3.976 40.80 3.537 36.30
    105.43 118.51
    """

    frame = parse_weekly_report_text(
        text,
        reservoir_aliases={
            "Krishnaraja Sagara": "krs",
            "Mettur": "mettur",
            "Indira Sagar": "indira_sagar",
        },
        source_url="https://example.test/bulletin.pdf",
    )

    assert set(frame["reservoir_id"]) == {"krs", "mettur", "indira_sagar"}
    assert frame.loc[frame["reservoir_id"] == "krs", "live_storage_bcm"].iloc[0] == pytest.approx(
        0.480
    )
    assert frame.loc[frame["reservoir_id"] == "mettur", "percent_frl"].iloc[0] == pytest.approx(
        47.37
    )
    assert frame.loc[
        frame["reservoir_id"] == "indira_sagar", "normal_storage_bcm"
    ].iloc[0] == pytest.approx(3.537)


def test_load_cwc_storage_csv_validates_phase0_rows() -> None:
    frame = load_cwc_storage_csv()

    assert set(frame["reservoir_id"]) == {"krs", "mettur", "indira_sagar"}
    assert frame["source_url"].str.contains("rsms.cwc.gov.in").all()


def test_load_cwc_storage_merges_directory_bulletins(tmp_path):
    bulletin_a = tmp_path / "bulletin_2026_04_09.csv"
    bulletin_b = tmp_path / "bulletin_2026_04_16.csv"
    header = (
        "reservoir_id,cwc_name,date,live_capacity_at_frl_bcm,live_storage_bcm,"
        "percent_frl,normal_storage_bcm,percent_normal,source_url,source_lines\n"
    )
    bulletin_a.write_text(
        header + "krs,KRS,2026-04-09,1.163,0.48,41.30,0.355,30.54,https://example/a.pdf,L1\n"
    )
    bulletin_b.write_text(
        header + "krs,KRS,2026-04-16,1.163,0.45,38.69,0.330,28.40,https://example/b.pdf,L1\n"
    )

    frame = load_cwc_storage(
        directory=tmp_path,
        bulletin_glob="bulletin_*.csv",
        phase0_fallback=None,
    )

    assert sorted(frame["date"].astype(str).tolist()) == ["2026-04-09", "2026-04-16"]
    later = frame.loc[frame["date"] == date(2026, 4, 16), "live_storage_bcm"].iloc[0]
    assert later == pytest.approx(0.45)


def test_load_cwc_storage_dedupes_overlap(tmp_path):
    bulletin = tmp_path / "bulletin_2026_04_09.csv"
    header = (
        "reservoir_id,cwc_name,date,live_capacity_at_frl_bcm,live_storage_bcm,"
        "percent_frl,normal_storage_bcm,percent_normal,source_url,source_lines\n"
    )
    bulletin.write_text(
        header + "krs,KRS,2026-04-09,1.163,0.51,43.85,0.355,30.54,https://example/b.pdf,L1\n"
    )
    fallback = tmp_path / "phase0.csv"
    fallback.write_text(
        header + "krs,KRS,2026-04-09,1.163,0.48,41.30,0.355,30.54,https://example/a.pdf,L1\n"
    )

    frame = load_cwc_storage(
        directory=tmp_path,
        bulletin_glob="bulletin_*.csv",
        phase0_fallback=fallback,
    )

    assert len(frame) == 1
    # The directory bulletin loads last, so its value wins on overlap.
    assert frame.iloc[0]["live_storage_bcm"] == pytest.approx(0.51)


def test_load_cwc_storage_raises_when_nothing_available(tmp_path):
    with pytest.raises(CWCFormatError):
        load_cwc_storage(directory=tmp_path, phase0_fallback=None)

from __future__ import annotations

from datetime import date

import pytest

from reservoirs.cwc_scraper import CWCFormatError, parse_bulletin_text


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


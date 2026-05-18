from __future__ import annotations

import pandas as pd
import pytest

from reservoirs.oni import classify_enso, compute_el_nino_delta, latest_oni, parse_oni_table


def test_classify_enso_boundaries() -> None:
    assert classify_enso(0.51, 0.2) == "el_nino_developing"
    assert classify_enso(0.51, -0.1) == "el_nino"
    assert classify_enso(-0.51, -0.2) == "la_nina_developing"
    assert classify_enso(-0.51, 0.1) == "la_nina"
    assert classify_enso(0.5, 1.0) == "neutral"


def test_parse_oni_table_ignores_page_chrome() -> None:
    text = """
    SEAS  YR   TOTAL  ANOM
    DJF 2026  26.4  0.4
    JFM 2026  26.7  0.6
    FMA 2026  27.0  0.8
    footer
    """

    records = parse_oni_table(text)

    assert len(records) == 3
    assert records[-1].season == "FMA"
    assert records[-1].anomaly == pytest.approx(0.8)


def test_latest_oni_classifies_trend() -> None:
    records = parse_oni_table(
        """
        DJF 2026 26.4 0.4
        JFM 2026 26.7 0.6
        FMA 2026 27.0 0.8
        """
    )

    latest, state = latest_oni(records)

    assert latest == pytest.approx(0.8)
    assert state == "el_nino_developing"


def test_compute_el_nino_delta_uses_june_to_september_gain() -> None:
    frame = pd.DataFrame(
        [
            {"month": "2015-06", "area_km2": 100},
            {"month": "2015-09", "area_km2": 110},
            {"month": "2016-06", "area_km2": 100},
            {"month": "2016-09", "area_km2": 140},
        ]
    )

    assert compute_el_nino_delta(frame) == pytest.approx(-30)

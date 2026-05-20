from __future__ import annotations

from datetime import date

import pandas as pd

from reservoirs.pipeline import _cwc_row_for_reservoir, _latest_cwc_date


def _cwc_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "reservoir_id": "krs",
                "date": date(2023, 12, 28),
                "live_storage_bcm": 0.19,
            },
            {
                "reservoir_id": "krs",
                "date": date(2026, 4, 9),
                "live_storage_bcm": 0.48,
            },
            {
                "reservoir_id": "mettur",
                "date": date(2026, 4, 9),
                "live_storage_bcm": 1.254,
            },
        ]
    )


def test_cwc_row_for_reservoir_ignores_future_bulletins_in_backtests() -> None:
    row = _cwc_row_for_reservoir(_cwc_frame(), "krs", as_of=date(2023, 12, 31))

    assert row is not None
    assert row.date == date(2023, 12, 28)
    assert row.live_storage_bcm == 0.19


def test_cwc_row_for_reservoir_returns_none_when_only_future_data_exists() -> None:
    row = _cwc_row_for_reservoir(_cwc_frame(), "mettur", as_of=date(2019, 3, 31))

    assert row is None


def test_latest_cwc_date_uses_only_bulletins_available_as_of_snapshot() -> None:
    assert _latest_cwc_date(_cwc_frame(), as_of=date(2023, 12, 31)) == date(2023, 12, 28)
    assert _latest_cwc_date(_cwc_frame(), as_of=date(2019, 3, 31)) is None
    assert _latest_cwc_date(_cwc_frame(), as_of=date(2026, 4, 9)) == date(2026, 4, 9)

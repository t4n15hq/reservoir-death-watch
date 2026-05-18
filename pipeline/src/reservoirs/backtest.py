"""Historical validation cases for Phase 1."""

from __future__ import annotations

from datetime import date

BACKTEST_CASES = {
    "krs_2023_12_31": {"reservoir_id": "krs", "as_of": date(2023, 12, 31), "tiers": {"critical"}},
    "mettur_2019_03_31": {
        "reservoir_id": "mettur",
        "as_of": date(2019, 3, 31),
        "tiers": {"critical", "warning"},
    },
    "jayakwadi_2016_03_31": {
        "reservoir_id": "jayakwadi",
        "as_of": date(2016, 3, 31),
        "tiers": {"critical", "warning"},
    },
    "jayakwadi_2019_03_31": {
        "reservoir_id": "jayakwadi",
        "as_of": date(2019, 3, 31),
        "tiers": {"critical", "warning"},
    },
}


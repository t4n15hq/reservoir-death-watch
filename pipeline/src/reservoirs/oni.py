"""NOAA ONI parsing and ENSO classification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import requests

ONI_URL = "https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php"
EnsoState = Literal[
    "el_nino_developing",
    "el_nino",
    "la_nina_developing",
    "la_nina",
    "neutral",
]

EL_NINO_MONSOON_YEARS = {
    1986,
    1991,
    1997,
    2002,
    2009,
    2015,
    2018,
    2023,
}


@dataclass(frozen=True)
class OniRecord:
    season: str
    year: int
    total: float
    anomaly: float


def classify_enso(oni: float, trend_3mo: float) -> EnsoState:
    """Classify ENSO state using the threshold in docs/TDD.md."""

    if oni > 0.5:
        return "el_nino_developing" if trend_3mo > 0 else "el_nino"
    if oni < -0.5:
        return "la_nina_developing" if trend_3mo < 0 else "la_nina"
    return "neutral"


def parse_oni_table(text: str) -> list[OniRecord]:
    """Parse NOAA CPC ONI table text into records.

    NOAA serves this as an HTML-ish fixed-width table. This parser intentionally
    accepts only rows that look like data rows, so page chrome is ignored.
    """

    records: list[OniRecord] = []
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) < 4:
            continue
        season, year_text, total_text, anomaly_text = parts[:4]
        if len(season) != 3 or not year_text.isdigit():
            continue
        try:
            records.append(
                OniRecord(
                    season=season,
                    year=int(year_text),
                    total=float(total_text),
                    anomaly=float(anomaly_text),
                )
            )
        except ValueError:
            continue
    return records


def latest_oni(records: list[OniRecord]) -> tuple[float, EnsoState]:
    """Return latest anomaly and classified ENSO state."""

    if len(records) < 3:
        msg = "at least three ONI records are required to classify trend"
        raise ValueError(msg)
    latest = records[-1].anomaly
    trend = records[-1].anomaly - records[-3].anomaly
    return latest, classify_enso(latest, trend)


def fetch_oni(url: str = ONI_URL, timeout: int = 30) -> tuple[float, EnsoState]:
    """Fetch ONI data from NOAA and return latest anomaly plus state."""

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    records = parse_oni_table(response.text)
    return latest_oni(records)


def compute_el_nino_delta(jrc_history: pd.DataFrame) -> float | None:
    """Compute June-to-September area-gain delta for El Nino years.

    Negative values mean El Nino years gained less monsoon water area than the
    non-El-Nino baseline.
    """

    if jrc_history.empty:
        return None

    frame = jrc_history.copy()
    frame["date"] = pd.to_datetime(frame["month"] + "-01")
    frame["year"] = frame["date"].dt.year
    frame["month_number"] = frame["date"].dt.month

    gains = []
    for year, year_frame in frame.groupby("year"):
        june = year_frame[year_frame["month_number"] == 6]
        september = year_frame[year_frame["month_number"] == 9]
        if june.empty or september.empty:
            continue
        gains.append(
            {
                "year": int(year),
                "gain_km2": float(september.iloc[-1]["area_km2"] - june.iloc[-1]["area_km2"]),
            }
        )

    if not gains:
        return None

    gain_frame = pd.DataFrame(gains)
    el_nino = gain_frame[gain_frame["year"].isin(EL_NINO_MONSOON_YEARS)]
    neutral = gain_frame[~gain_frame["year"].isin(EL_NINO_MONSOON_YEARS)]
    if el_nino.empty or neutral.empty:
        return None
    return float(el_nino["gain_km2"].mean() - neutral["gain_km2"].mean())

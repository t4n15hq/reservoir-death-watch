"""JRC Global Surface Water extraction stage."""

from __future__ import annotations

from datetime import date, datetime
from time import sleep

import pandas as pd

from reservoirs.gee_auth import initialize_earth_engine
from reservoirs.schemas import ReservoirAOI

JRC_GEOMETRY_SIMPLIFY_M = {
    "indira_sagar": 2_000,
}
DEFAULT_GEOMETRY_SIMPLIFY_M = 100


def extract_jrc_history(
    aoi: ReservoirAOI,
    start: str | date = "1984-03-01",
    end: str | date | None = None,
) -> pd.DataFrame:
    """Return monthly JRC surface-water area for an AOI.

    Output columns: `month`, `area_km2`, `data_source`.
    """

    initialize_earth_engine()

    import ee

    geometry = ee.Geometry(aoi.polygon).simplify(
        JRC_GEOMETRY_SIMPLIFY_M.get(aoi.id, DEFAULT_GEOMETRY_SIMPLIFY_M)
    )
    start_date = _coerce_date(start)
    end_date = _coerce_date(end) if end else date.today()

    def image_to_feature(image):
        water = image.select("water").eq(2).rename("water")
        area_km2 = (
            water.multiply(ee.Image.pixelArea())
            .divide(1_000_000)
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=geometry,
                scale=30,
                maxPixels=1_000_000_000,
                tileScale=4,
            )
            .get("water")
        )
        return ee.Feature(
            None,
            {
                "month": ee.Date(image.get("system:time_start")).format("YYYY-MM"),
                "area_km2": area_km2,
                "data_source": "jrc",
            },
        )

    features = []
    for chunk_start, chunk_end in _year_chunks(start_date, end_date):
        collection = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterDate(
            chunk_start.isoformat(),
            chunk_end.isoformat(),
        )
        feature_collection = ee.FeatureCollection(collection.map(image_to_feature))
        try:
            features.extend(_get_features_with_retries(feature_collection))
        except Exception as exc:
            print(
                f"{aoi.id}: JRC yearly chunk {chunk_start:%Y-%m} failed, "
                f"falling back to monthly chunks: {exc}"
            )
            for month_start, month_end in _month_chunks(chunk_start, chunk_end):
                monthly_collection = ee.ImageCollection("JRC/GSW1_4/MonthlyHistory").filterDate(
                    month_start.isoformat(),
                    month_end.isoformat(),
                )
                monthly_features = ee.FeatureCollection(monthly_collection.map(image_to_feature))
                features.extend(_get_features_with_retries(monthly_features, retries=5))

    rows = [
        {
            "month": feature["properties"]["month"],
            "area_km2": float(feature["properties"].get("area_km2") or 0.0),
            "data_source": "jrc",
        }
        for feature in features
    ]
    frame = pd.DataFrame(rows, columns=["month", "area_km2", "data_source"])
    if frame.empty:
        return frame
    return frame.sort_values("month").reset_index(drop=True)


def _coerce_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _year_chunks(start: date, end: date):
    cursor = start
    while cursor < end:
        next_year = date(cursor.year + 1, 1, 1)
        chunk_end = min(next_year, end)
        yield cursor, chunk_end
        cursor = chunk_end


def _month_chunks(start: date, end: date):
    cursor = start
    while cursor < end:
        next_month = date(cursor.year + 1, 1, 1) if cursor.month == 12 else date(
            cursor.year,
            cursor.month + 1,
            1,
        )
        chunk_end = min(next_month, end)
        yield cursor, chunk_end
        cursor = chunk_end


def _get_features_with_retries(feature_collection, retries: int = 3) -> list[dict]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return feature_collection.getInfo()["features"]
        except Exception as exc:
            last_error = exc
            sleep(2**attempt)
    assert last_error is not None
    raise last_error

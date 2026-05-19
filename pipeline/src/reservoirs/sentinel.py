"""Sentinel-2 and Sentinel-1 live area extraction stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from reservoirs.gee_auth import initialize_earth_engine
from reservoirs.schemas import ReservoirAOI


@dataclass(frozen=True)
class RecentArea:
    area_km2: float
    as_of: date
    data_source: Literal["sentinel_2", "sentinel_1"]
    cloud_coverage_percent: float | None = None


class SentinelExtractionError(RuntimeError):
    """Raised when Sentinel extraction cannot produce a usable observation."""


SENTINEL_GEOMETRY_SIMPLIFY_M = {
    "indira_sagar": 2_000,
}
SENTINEL_SCALE_M = {
    "indira_sagar": 30,
}
DEFAULT_GEOMETRY_SIMPLIFY_M = 100
DEFAULT_SENTINEL_SCALE_M = 10

# Reservoirs do not lose >50% of their surface area in a single 10-day step.
# Drops beyond this are almost always cloud/SCL mask leakage, not real depletion.
MAX_PLAUSIBLE_STEP_DROP_RATIO = 0.50


def extract_recent_area(
    aoi: ReservoirAOI,
    *,
    as_of: date | None = None,
    days: int = 30,
) -> RecentArea:
    """Extract the best recent area observation, using S1 when S2 is too cloudy.

    Falls back to Sentinel-1 for both expected failures (no S2 images, too cloudy)
    and EE backend errors (some polygons reliably 500 out of S2 reduceRegion;
    radar still works for those).
    """

    try:
        area, observed_at, cloud_percent = extract_s2_recent(aoi, as_of=as_of, days=days)
        if cloud_percent <= 70:
            return RecentArea(area, observed_at, "sentinel_2", cloud_percent)
    except SentinelExtractionError:
        pass
    except Exception as exc:  # noqa: BLE001 — EE 500s surface as generic EEException
        print(f"{aoi.id}: Sentinel-2 unavailable ({exc}); trying Sentinel-1 SAR.")

    area, observed_at = extract_s1_recent(aoi, as_of=as_of, days=days)
    return RecentArea(area, observed_at, "sentinel_1", None)


def extract_s2_recent(
    aoi: ReservoirAOI,
    *,
    as_of: date | None = None,
    days: int = 30,
) -> tuple[float, date, float]:
    """Extract current reservoir area from a Sentinel-2 median composite."""

    initialize_earth_engine()

    import ee

    geometry = _geometry_for_aoi(aoi)
    scale = _scale_for_aoi(aoi)
    end_date = as_of or date.today()
    start_date = end_date - timedelta(days=days)
    collection = _s2_collection(geometry, start_date, end_date)
    if collection.size().getInfo() == 0:
        raise SentinelExtractionError(f"no Sentinel-2 images found for {aoi.id}")

    cloud_percent = float(collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 100.0)
    composite = collection.map(_mask_s2_clouds).median()
    water = _s2_water_mask(composite)
    area_km2 = _water_area_km2(water, geometry, scale=scale, band_name="water").getInfo()
    if area_km2 is None:
        raise SentinelExtractionError(f"Sentinel-2 produced no area for {aoi.id}")

    latest_ms = (
        collection.sort("system:time_start", False).first().get("system:time_start").getInfo()
    )
    observed_at = date.fromisoformat(ee.Date(latest_ms).format("YYYY-MM-dd").getInfo())
    return float(area_km2), observed_at, cloud_percent


def extract_s2_area_series(
    aoi: ReservoirAOI,
    *,
    as_of: date | None = None,
    days: int = 150,
    max_cloud_percent: float = 70,
    interval_days: int = 10,
) -> pd.DataFrame:
    """Return recent Sentinel-2 composite areas for regression fitting."""

    initialize_earth_engine()

    import ee

    geometry = _geometry_for_aoi(aoi)
    scale = _scale_for_aoi(aoi)
    end_date = as_of or date.today()
    start_date = end_date - timedelta(days=days)
    rows = []
    cursor = start_date
    while cursor <= end_date:
        window_end = min(cursor + timedelta(days=interval_days), end_date + timedelta(days=1))
        collection = _s2_collection(geometry, cursor, window_end - timedelta(days=1))
        if collection.size().getInfo() == 0:
            cursor = window_end
            continue

        cloud = float(collection.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 100.0)
        if cloud > max_cloud_percent:
            cursor = window_end
            continue

        composite = collection.map(_mask_s2_clouds).median()
        water = _s2_water_mask(composite)
        area = _water_area_km2(water, geometry, scale=scale, band_name="water").getInfo()
        if area is None:
            cursor = window_end
            continue

        latest_ms = (
            collection.sort("system:time_start", False).first().get("system:time_start").getInfo()
        )
        rows.append(
            {
                "date": date.fromisoformat(ee.Date(latest_ms).format("YYYY-MM-dd").getInfo()),
                "area_km2": float(area),
                "data_source": "sentinel_2",
                "cloud_coverage_percent": cloud,
            }
        )
        cursor = window_end

    frame = pd.DataFrame(
        rows,
        columns=["date", "area_km2", "data_source", "cloud_coverage_percent"],
    )
    if frame.empty:
        return frame
    deduped = (
        frame.groupby("date", as_index=False)
        .mean(numeric_only=True)
        .assign(data_source="sentinel_2")
    )
    return drop_implausible_cloud_artifacts(deduped)


def drop_implausible_cloud_artifacts(
    series: pd.DataFrame,
    *,
    max_drop_ratio: float = MAX_PLAUSIBLE_STEP_DROP_RATIO,
) -> pd.DataFrame:
    """Remove single-observation outliers where area collapses then recovers.

    Pattern we filter: prev=33 km², this=3.9 km², next=13 km². The middle
    reading is masked by clouds bleeding through the SCL filter. We keep the
    drop if the trend continues (sustained decline is real depletion); we
    only drop a single observation whose neighbours bracket a much higher
    value.
    """

    if len(series) < 3:
        return series
    sorted_series = series.sort_values("date").reset_index(drop=True)
    keep = [True] * len(sorted_series)
    areas = sorted_series["area_km2"].tolist()
    for i in range(1, len(sorted_series) - 1):
        prev_area = areas[i - 1]
        this_area = areas[i]
        next_area = areas[i + 1]
        if prev_area <= 0 or next_area <= 0:
            continue
        neighbour_floor = min(prev_area, next_area)
        if this_area < neighbour_floor * (1 - max_drop_ratio):
            keep[i] = False
    return sorted_series[keep].reset_index(drop=True)


def extract_s1_recent(
    aoi: ReservoirAOI,
    *,
    as_of: date | None = None,
    days: int = 30,
) -> tuple[float, date]:
    """Extract current reservoir area from Sentinel-1 SAR fallback."""

    initialize_earth_engine()

    import ee

    geometry = _geometry_for_aoi(aoi)
    scale = _scale_for_aoi(aoi)
    end_date = as_of or date.today()
    start_date = end_date - timedelta(days=days)
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geometry)
        .filterDate(start_date.isoformat(), (end_date + timedelta(days=1)).isoformat())
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )
    if collection.size().getInfo() == 0:
        raise SentinelExtractionError(f"no Sentinel-1 images found for {aoi.id}")

    composite = collection.median().focal_median(50, "circle", "meters")
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    water = composite.lt(-15).updateMask(slope.lt(10)).rename("water")
    area_km2 = _water_area_km2(water, geometry, scale=scale, band_name="water").getInfo()
    if area_km2 is None:
        raise SentinelExtractionError(f"Sentinel-1 produced no area for {aoi.id}")

    latest_ms = (
        collection.sort("system:time_start", False).first().get("system:time_start").getInfo()
    )
    observed_at = date.fromisoformat(ee.Date(latest_ms).format("YYYY-MM-dd").getInfo())
    return float(area_km2), observed_at


def _s2_collection(geometry, start_date: date, end_date: date):
    import ee

    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometry)
        .filterDate(start_date.isoformat(), (end_date + timedelta(days=1)).isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 90))
    )


def _geometry_for_aoi(aoi: ReservoirAOI):
    import ee

    return ee.Geometry(aoi.polygon).simplify(_simplify_for_aoi(aoi))


def _simplify_for_aoi(aoi: ReservoirAOI) -> int:
    """Pick a simplification tolerance proportional to AOI extent.

    A 3990-vertex polygon (Bhakra) at 100m simplify is still complex enough
    that GEE's reduceRegion runs out of resources. Coarser simplify for
    larger polygons keeps reduceRegion tractable; we lose a bit of boundary
    precision but only at edges of reservoirs that are already km across.
    """

    if aoi.id in SENTINEL_GEOMETRY_SIMPLIFY_M:
        return SENTINEL_GEOMETRY_SIMPLIFY_M[aoi.id]
    area = aoi.aoi_area_km2 or 0
    if area > 200:
        return 1_000
    if area > 100:
        return 500
    return DEFAULT_GEOMETRY_SIMPLIFY_M


def _scale_for_aoi(aoi: ReservoirAOI) -> int:
    if aoi.id in SENTINEL_SCALE_M:
        return SENTINEL_SCALE_M[aoi.id]
    # Polygons larger than ~100 km² blow GEE's per-call pixel budget at 10m,
    # which surfaces as an opaque "An internal error has occurred". Drop to
    # 30m for those — coarser but tractable in a single getInfo().
    if aoi.aoi_area_km2 and aoi.aoi_area_km2 > 100:
        return 30
    return DEFAULT_SENTINEL_SCALE_M


def _mask_s2_clouds(image):
    cloud = _s2_cloud_mask(image)
    return image.updateMask(cloud.Not())


def _s2_cloud_mask(image):
    scl = image.select("SCL")
    return (
        scl.eq(3)
        .Or(scl.eq(8))
        .Or(scl.eq(9))
        .Or(scl.eq(10))
        .Or(scl.eq(11))
    )


def _s2_water_mask(image):
    import ee

    mndwi = image.normalizedDifference(["B3", "B11"])
    slope = ee.Terrain.slope(ee.Image("USGS/SRTMGL1_003"))
    return mndwi.gt(0).updateMask(slope.lt(10)).rename("water")


def _water_area_km2(water, geometry, *, scale: int, band_name: str):
    import ee

    return (
        water.multiply(ee.Image.pixelArea())
        .divide(1_000_000)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=scale,
            maxPixels=1_000_000_000,
            tileScale=8,
        )
        .get(band_name)
    )

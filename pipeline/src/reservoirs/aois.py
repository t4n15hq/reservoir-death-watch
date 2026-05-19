"""Load reservoir metadata and AOI GeoJSON files."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from reservoirs.config import REPO_ROOT, RESERVOIRS_CSV
from reservoirs.schemas import ReservoirAOI


class AOILoadError(ValueError):
    """Raised when reservoir metadata or AOI files are missing or invalid."""


def load_aois(
    reservoir_ids: Iterable[str] | None = None,
    *,
    reservoirs_csv: Path = RESERVOIRS_CSV,
) -> list[ReservoirAOI]:
    """Read reservoir metadata and committed GeoJSON AOIs."""

    wanted = set(reservoir_ids) if reservoir_ids else None
    aois: list[ReservoirAOI] = []

    with reservoirs_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if wanted and row["id"] not in wanted:
                continue
            geometry, properties = _load_geojson_geometry(REPO_ROOT / row["aoi_file"])
            aois.append(
                ReservoirAOI(
                    id=row["id"],
                    name=row["name"],
                    river=row["river"],
                    state=row["state"],
                    cwc_name=row["cwc_name"],
                    city_served=row["city_served"],
                    population_served=_optional_int(row["population_served"]),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    full_pool_capacity_bcm=_optional_float(row["full_pool_capacity_bcm"]),
                    dead_storage_capacity_bcm=_optional_float(row["dead_storage_capacity_bcm"]),
                    priority=int(row["priority"]),
                    aoi_file=row["aoi_file"],
                    aoi_area_km2=_optional_float(str(properties.get("area_km2", ""))),
                    aoi_review_status=properties.get("review_status"),
                    polygon=geometry,
                    notes=row["notes"],
                )
            )

    if wanted:
        found = {aoi.id for aoi in aois}
        missing = sorted(wanted - found)
        if missing:
            raise AOILoadError(f"reservoir ids missing from metadata: {missing}")

    return sorted(aois, key=lambda aoi: aoi.priority)


def reservoirs_with_aois_on_disk(
    *,
    reservoirs_csv: Path = RESERVOIRS_CSV,
) -> list[str]:
    """Return reservoir IDs whose AOI GeoJSON files actually exist on disk.

    Lets the pipeline scale up phase-by-phase without editing the
    ``PHASE0_RESERVOIRS`` constant — drop a new AOI file in, and the
    next run picks the reservoir up automatically.
    """

    out: list[str] = []
    with reservoirs_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (REPO_ROOT / row["aoi_file"]).exists():
                out.append(row["id"])
    return out


def _load_geojson_geometry(path: Path) -> tuple[dict, dict]:
    if not path.exists():
        raise AOILoadError(f"AOI file is missing: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    if data.get("type") == "FeatureCollection":
        features = data.get("features") or []
        if len(features) != 1:
            raise AOILoadError(f"expected exactly one feature in {path}")
        return features[0]["geometry"], features[0].get("properties") or {}
    if data.get("type") == "Feature":
        return data["geometry"], data.get("properties") or {}
    if data.get("type") in {"Polygon", "MultiPolygon"}:
        return data, {}
    raise AOILoadError(f"unsupported GeoJSON shape in {path}")


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _optional_int(value: str) -> int | None:
    return int(value) if value else None

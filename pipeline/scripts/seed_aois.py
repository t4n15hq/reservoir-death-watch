#!/usr/bin/env python
"""Seed first-pass reservoir AOIs from JRC Global Surface Water.

These polygons are traceable satellite-derived starting points. They are not a
substitute for manual AOI review before Phase 0 is considered complete.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from reservoirs.config import AOI_DIR, RESERVOIRS_CSV
from reservoirs.gee_auth import initialize_earth_engine

PHASE0_IDS = ("krs", "mettur", "indira_sagar")

AOI_CONFIG = {
    "krs": {
        "radius_m": 18_000,
        "min_area_km2": 20,
        "nearby_buffer_m": 4_000,
        "simplify_m": 60,
        "occurrence_threshold": 5,
    },
    "mettur": {
        "radius_m": 38_000,
        "min_area_km2": 35,
        "nearby_buffer_m": 7_000,
        "simplify_m": 75,
        "occurrence_threshold": 5,
    },
    "indira_sagar": {
        "radius_m": 95_000,
        "min_area_km2": 120,
        "nearby_buffer_m": 12_000,
        "simplify_m": 120,
        "occurrence_threshold": 5,
    },
}


def main() -> None:
    args = parse_args()
    initialize_earth_engine()

    ids = tuple(args.reservoir_ids or PHASE0_IDS)
    metadata = read_reservoir_metadata(ids)
    AOI_DIR.mkdir(parents=True, exist_ok=True)

    for reservoir_id in ids:
        row = metadata[reservoir_id]
        config = AOI_CONFIG.get(reservoir_id, default_config(row))
        feature = build_aoi_feature(row, config)
        output_path = AOI_DIR / f"{reservoir_id}.geojson"
        write_geojson(output_path, feature, overwrite=args.overwrite)
        print(
            f"{reservoir_id}: wrote {output_path} "
            f"area={feature['properties']['area_km2']:.2f} km2"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reservoir_ids", nargs="*", help="Reservoir IDs to seed")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing AOI files")
    return parser.parse_args()


def read_reservoir_metadata(reservoir_ids: tuple[str, ...]) -> dict[str, dict[str, str]]:
    wanted = set(reservoir_ids)
    rows: dict[str, dict[str, str]] = {}
    with RESERVOIRS_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["id"] in wanted:
                rows[row["id"]] = row

    missing = sorted(wanted - set(rows))
    if missing:
        raise ValueError(f"reservoir IDs not found in {RESERVOIRS_CSV}: {missing}")
    return rows


def default_config(row: dict[str, str]) -> dict[str, float]:
    full_capacity = float(row["full_pool_capacity_bcm"] or 1.0)
    return {
        "radius_m": max(15_000, min(100_000, full_capacity * 8_000)),
        "min_area_km2": max(5, full_capacity * 8),
        "nearby_buffer_m": 5_000,
        "simplify_m": 90,
        "occurrence_threshold": 5,
    }


def build_aoi_feature(row: dict[str, str], config: dict[str, float]) -> dict:
    import ee

    point = ee.Geometry.Point([float(row["lon"]), float(row["lat"])])
    search_area = point.buffer(config["radius_m"]).bounds()
    water = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("occurrence")
        .gte(config["occurrence_threshold"])
        .selfMask()
        .clip(search_area)
        .rename("water")
    )
    vectors = water.reduceToVectors(
        geometry=search_area,
        scale=30,
        geometryType="polygon",
        eightConnected=True,
        labelProperty="water",
        reducer=ee.Reducer.countEvery(),
        maxPixels=1_000_000_000,
        tileScale=4,
    )

    def add_metrics(feature):
        geometry = feature.geometry()
        return feature.set(
            {
                "area_km2": geometry.area(1).divide(1_000_000),
                "distance_m": geometry.centroid(1).distance(point, 1),
            }
        )

    candidates = (
        vectors.map(add_metrics)
        .filter(ee.Filter.gte("area_km2", config["min_area_km2"]))
        .sort("area_km2", False)
    )
    nearby = candidates.filterBounds(point.buffer(config["nearby_buffer_m"]))
    selected = nearby.sort("area_km2", False).first()
    if nearby.size().getInfo() == 0:
        selected = candidates.sort("distance_m").first()

    if selected.getInfo() is None:
        raise RuntimeError(f"no JRC water polygon found for {row['id']}")

    geometry = selected.geometry().simplify(config["simplify_m"]).getInfo()
    area_km2 = selected.get("area_km2").getInfo()
    distance_m = selected.get("distance_m").getInfo()

    return {
        "type": "Feature",
        "properties": {
            "id": row["id"],
            "name": row["name"],
            "source": "JRC/GSW1_4/GlobalSurfaceWater",
            "method": (
                "occurrence_threshold_connected_component;"
                f"occurrence_gte={config['occurrence_threshold']};"
                f"radius_m={config['radius_m']}"
            ),
            "area_km2": round(float(area_km2), 3),
            "centroid_distance_m": round(float(distance_m), 1),
            "generated_at": datetime.now(UTC).isoformat(),
            "review_status": "first_pass_needs_manual_review",
        },
        "geometry": geometry,
    }


def write_geojson(path: Path, feature: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; pass --overwrite to replace it")
    with path.open("w", encoding="utf-8") as handle:
        json.dump(feature, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()


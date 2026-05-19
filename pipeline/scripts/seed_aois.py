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

# Strategies for selecting the AOI mask band on JRC/GSW1_4/GlobalSurfaceWater.
# - "recurrence":  pixels wet in ≥ N% of years; best for full-pool boundary
#                  because FRL pixels recur during annual peak fill.
# - "occurrence":  pixels wet in ≥ N% of all monthly observations; stricter,
#                  under-counts the FRL boundary on reservoirs that rarely fill.
# - "max_extent":  pixels ever observed as water; most inclusive, can merge
#                  with upstream river segments.
SELECTION_STRATEGIES = ("recurrence", "occurrence", "max_extent")

DEFAULT_STRATEGY = "recurrence"
DEFAULT_RECURRENCE_THRESHOLD = 50
DEFAULT_OCCURRENCE_THRESHOLD = 5

AOI_CONFIG = {
    "krs": {
        "radius_m": 18_000,
        "min_area_km2": 20,
        "nearby_buffer_m": 4_000,
        "simplify_m": 60,
    },
    "mettur": {
        "radius_m": 38_000,
        "min_area_km2": 35,
        "nearby_buffer_m": 7_000,
        "simplify_m": 75,
    },
    "indira_sagar": {
        "radius_m": 95_000,
        "min_area_km2": 120,
        "nearby_buffer_m": 12_000,
        "simplify_m": 120,
    },
    "jayakwadi": {
        "radius_m": 35_000,
        "min_area_km2": 60,
        "nearby_buffer_m": 8_000,
        "simplify_m": 75,
    },
    # Nagarjuna Sagar and Srisailam are 67 km apart on the same river (Krishna),
    # connected by a continuous JRC water mask. A generous radius pulls the
    # connected component for one into the other's AOI. Tight radii pin each
    # reservoir to its own dam.
    "nagarjuna_sagar": {
        "radius_m": 25_000,
        "min_area_km2": 50,
        "nearby_buffer_m": 5_000,
        "simplify_m": 75,
    },
    "srisailam": {
        # Dam at (16.08, 78.90) is the SE corner; reservoir extends 60 km NW.
        # Seed from the reservoir centroid and use a tight radius so NS doesn't
        # bleed in via the Krishna river that connects them.
        "search_lat": 16.30,
        "search_lon": 78.65,
        "radius_m": 35_000,
        "min_area_km2": 50,
        "nearby_buffer_m": 12_000,
        "simplify_m": 90,
    },
}


def main() -> None:
    args = parse_args()
    initialize_earth_engine()

    ids = tuple(args.reservoir_ids or PHASE0_IDS)
    metadata = read_reservoir_metadata(ids)
    AOI_DIR.mkdir(parents=True, exist_ok=True)

    selection = build_selection(args)

    for reservoir_id in ids:
        row = metadata[reservoir_id]
        config = AOI_CONFIG.get(reservoir_id, default_config(row))
        feature = build_aoi_feature(row, config, selection)
        output_path = AOI_DIR / f"{reservoir_id}.geojson"
        write_geojson(output_path, feature, overwrite=args.overwrite)
        print(
            f"{reservoir_id}: wrote {output_path} "
            f"area={feature['properties']['area_km2']:.2f} km2 "
            f"(strategy={selection['strategy']}, threshold={selection['threshold']})"
        )


def build_selection(args: argparse.Namespace) -> dict[str, object]:
    """Resolve the band/threshold the JRC mask should use."""

    if args.strategy not in SELECTION_STRATEGIES:
        raise SystemExit(f"unknown strategy: {args.strategy}")
    threshold = args.threshold
    if threshold is None:
        if args.strategy == "recurrence":
            threshold = DEFAULT_RECURRENCE_THRESHOLD
        elif args.strategy == "occurrence":
            threshold = DEFAULT_OCCURRENCE_THRESHOLD
        else:  # max_extent uses no threshold
            threshold = 0
    return {"strategy": args.strategy, "threshold": int(threshold)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reservoir_ids", nargs="*", help="Reservoir IDs to seed")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing AOI files")
    parser.add_argument(
        "--strategy",
        choices=SELECTION_STRATEGIES,
        default=DEFAULT_STRATEGY,
        help=(
            "JRC band used to define the water mask. 'recurrence' (default) captures the "
            "FRL boundary because pixels recur during annual peak fill; 'occurrence' is "
            "stricter and under-counts; 'max_extent' is most inclusive."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help=(
            "Threshold for the selected band. Default 50 for recurrence, 5 for occurrence; "
            "ignored for max_extent."
        ),
    )
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
    }


def build_water_mask(search_area, selection: dict[str, object]):
    """Build a JRC water mask Image per the chosen selection strategy."""

    import ee

    asset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    strategy = selection["strategy"]
    threshold = int(selection["threshold"])

    if strategy == "max_extent":
        mask = asset.select("max_extent").eq(1)
    elif strategy == "recurrence":
        mask = asset.select("recurrence").gte(threshold)
    else:  # occurrence
        mask = asset.select("occurrence").gte(threshold)

    return mask.selfMask().clip(search_area).rename("water")


def build_aoi_feature(
    row: dict[str, str],
    config: dict[str, float],
    selection: dict[str, object],
) -> dict:
    import ee

    # The map pin lives at the dam. For reservoirs where the dam sits at the
    # downstream edge of a long impoundment (Srisailam: dam at SE corner of a
    # reservoir that extends 60 km NW), search from the reservoir centroid
    # instead so the connected-component grab catches the right water body.
    search_lat = config.get("search_lat", float(row["lat"]))
    search_lon = config.get("search_lon", float(row["lon"]))
    point = ee.Geometry.Point([search_lon, search_lat])
    search_area = point.buffer(config["radius_m"]).bounds()
    water = build_water_mask(search_area, selection)
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
    geometry = collapse_to_largest_ring(geometry)
    area_km2 = selected.get("area_km2").getInfo()
    distance_m = selected.get("distance_m").getInfo()

    return {
        "type": "Feature",
        "properties": {
            "id": row["id"],
            "name": row["name"],
            "source": "JRC/GSW1_4/GlobalSurfaceWater",
            "method": (
                f"{selection['strategy']}_connected_component;"
                f"threshold={selection['threshold']};"
                f"radius_m={config['radius_m']}"
            ),
            "area_km2": round(float(area_km2), 3),
            "centroid_distance_m": round(float(distance_m), 1),
            "generated_at": datetime.now(UTC).isoformat(),
            "review_status": "first_pass_needs_manual_review",
        },
        "geometry": geometry,
    }


def collapse_to_largest_ring(geometry: dict) -> dict:
    """Reduce multi-ring polygons to their largest connected ring.

    `reduceToVectors` can return hundreds of disconnected water polygons all
    bundled into a single GeoJSON "Polygon" — those secondary rings get
    treated as holes by Earth Engine's reduceRegion, which then 500s with an
    opaque "internal error". Keep only the outer boundary of the actual
    reservoir.
    """

    coords = geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        # Pick the largest sub-polygon, then its largest ring.
        coords = max(coords, key=lambda poly: _ring_shoelace(poly[0]))
    if len(coords) <= 1:
        return {"type": "Polygon", "coordinates": coords}
    largest = max(coords, key=_ring_shoelace)
    return {"type": "Polygon", "coordinates": [largest]}


def _ring_shoelace(ring: list[list[float]]) -> float:
    n = len(ring)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += (x2 - x1) * (y2 + y1)
    return abs(total) / 2


def write_geojson(path: Path, feature: dict, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists; pass --overwrite to replace it")
    with path.open("w", encoding="utf-8") as handle:
        json.dump(feature, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()


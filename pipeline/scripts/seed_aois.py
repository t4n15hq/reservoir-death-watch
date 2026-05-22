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
        # Srisailam reservoir extends ~50 km NW from its SE-corner dam, BUT it's
        # connected to Nagarjuna Sagar via a continuous Krishna river that JRC
        # marks as recurrent water — any radius-based seed merges the two
        # connected components. Force a manual bbox that contains the Srisailam
        # main body and stops well west of NS (which sits east of lon 79.08).
        # Bounds confirmed by querying JRC max_extent for the largest connected
        # component in the area: lon 78.20-78.90, lat 15.85-16.16. East bound
        # stays well west of Nagarjuna Sagar (lon >= 79.08).
        "manual_bbox": (78.18, 15.83, 78.92, 16.20),
        "min_area_km2": 50,
        "nearby_buffer_m": 30_000,
        "simplify_m": 120,
    },
    # Expanded CWC reservoirs below are first-pass boxes used to get honest
    # current Sentinel observations online. They are intentionally flagged
    # `manual_bbox_needs_visual_check` by `_build_bbox_aoi`.
    "lower_manair": {
        "manual_bbox": (79.15, 18.25, 79.45, 18.50),
        "min_area_km2": 5,
        "nearby_buffer_m": 10_000,
        "simplify_m": 90,
    },
    "nizam_sagar": {
        "manual_bbox": (77.83, 18.10, 78.08, 18.32),
        "min_area_km2": 5,
        "nearby_buffer_m": 10_000,
        "simplify_m": 90,
    },
    "ramganga": {
        "manual_bbox": (78.55, 29.42, 79.00, 29.72),
        "min_area_km2": 20,
        "nearby_buffer_m": 15_000,
        "simplify_m": 120,
    },
    "nanak_sagar": {
        "manual_bbox": (79.75, 28.88, 79.92, 29.00),
        "min_area_km2": 3,
        "nearby_buffer_m": 8_000,
        "simplify_m": 75,
    },
    "hirakud": {
        "manual_bbox": (83.25, 21.25, 84.15, 21.85),
        "min_area_km2": 50,
        "nearby_buffer_m": 25_000,
        "simplify_m": 150,
    },
    "rengali": {
        "manual_bbox": (84.75, 21.12, 85.25, 21.48),
        "min_area_km2": 25,
        "nearby_buffer_m": 15_000,
        "simplify_m": 120,
    },
    "upper_indravati": {
        "manual_bbox": (82.55, 19.15, 83.05, 19.55),
        "min_area_km2": 15,
        "nearby_buffer_m": 12_000,
        "simplify_m": 120,
    },
    "minimata_bango": {
        "manual_bbox": (82.40, 22.35, 82.90, 22.78),
        "min_area_km2": 25,
        "nearby_buffer_m": 15_000,
        "simplify_m": 120,
    },
    "mahanadi_chhattisgarh": {
        "manual_bbox": (81.35, 20.45, 81.75, 20.78),
        "min_area_km2": 8,
        "nearby_buffer_m": 10_000,
        "simplify_m": 90,
    },
    "tandula": {
        "manual_bbox": (81.16, 20.56, 81.42, 20.82),
        "min_area_km2": 5,
        "nearby_buffer_m": 10_000,
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
    if config.get("manual_bbox"):
        # bbox = (min_lon, min_lat, max_lon, max_lat). For reservoirs that
        # fragment under recurrence>=50 (large reservoirs with seasonal bays;
        # or that are connected to a neighbour via a continuous river that
        # JRC marks as recurrent water), skip the connected-component step
        # entirely — use the bbox as the AOI, and let the downstream
        # Sentinel-2 water mask count actual water inside it.
        min_lon, min_lat, max_lon, max_lat = config["manual_bbox"]
        return _build_bbox_aoi(row, min_lon, min_lat, max_lon, max_lat, config, selection)
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
    if config.get("manual_bbox"):
        # bbox is the spatial constraint; just take the largest candidate inside it.
        selected = candidates.sort("area_km2", False).first()
    else:
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


def _build_bbox_aoi(
    row: dict[str, str],
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    config: dict[str, float],
    selection: dict[str, object],
) -> dict:
    """Build an AOI whose polygon IS the bbox itself (no water-mask selection)."""

    area_km2 = _bbox_area_km2(min_lon, min_lat, max_lon, max_lat)
    return {
        "type": "Feature",
        "properties": {
            "id": row["id"],
            "name": row["name"],
            "source": "manual_bbox",
            "method": (
                f"manual_bbox;lon={min_lon}-{max_lon};lat={min_lat}-{max_lat};"
                f"strategy={selection['strategy']}"
            ),
            "area_km2": round(area_km2, 3),
            "centroid_distance_m": 0.0,
            "generated_at": datetime.now(UTC).isoformat(),
            "review_status": "manual_bbox_needs_visual_check",
            "ring_cleanup_applied": True,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]],
        },
    }


def _bbox_area_km2(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> float:
    # Equirectangular approximation, accurate enough for "is this the right reservoir" sanity.
    import math
    mid_lat = (min_lat + max_lat) / 2
    width_km = (max_lon - min_lon) * 111.32 * math.cos(math.radians(mid_lat))
    height_km = (max_lat - min_lat) * 110.57
    return width_km * height_km


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

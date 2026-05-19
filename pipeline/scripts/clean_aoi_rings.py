#!/usr/bin/env python
"""Collapse multi-ring AOI polygons to their largest connected ring.

`reduceToVectors` in `seed_aois.py` sometimes returns hundreds of disconnected
water polygons all bundled into a single GeoJSON "Polygon" — the additional
rings get treated as holes, which Earth Engine's reduceRegion then chokes on
with opaque "internal errors" even when the polygon has reasonable total
area. Inspection showed Bhakra had 254 rings, Bisalpur 452.

This script rewrites each AOI to keep only the largest ring (the actual
reservoir's outer boundary) and drop the spurious holes/satellite ponds.
Safe to re-run; the original area is recorded under `original_area_km2`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reservoirs.config import AOI_DIR


def polygon_area_steradians(ring: list[list[float]]) -> float:
    """Cheap shoelace-on-the-sphere proxy; used only to find the largest ring.

    We don't need true spherical area — just a relative ordering — so the
    planar shoelace in degree-space is good enough.
    """

    n = len(ring)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += (x2 - x1) * (y2 + y1)
    return abs(total) / 2


def clean_polygon(coords: list, geometry_type: str) -> tuple[list, str]:
    if geometry_type == "MultiPolygon":
        # Take the largest sub-polygon, then its largest ring.
        largest = max(coords, key=lambda poly: polygon_area_steradians(poly[0]))
        coords = largest
    # `coords` is now a list of rings; first is outer, rest are holes.
    if len(coords) <= 1:
        return coords, "Polygon"
    largest_ring = max(coords, key=polygon_area_steradians)
    return [largest_ring], "Polygon"


def clean_aoi_file(path: Path) -> dict:
    with path.open() as handle:
        data = json.load(handle)
    if data.get("type") == "FeatureCollection":
        feature = data["features"][0]
    else:
        feature = data

    geom = feature["geometry"]
    before_rings = (
        sum(len(p) for p in geom["coordinates"])
        if geom["type"] == "MultiPolygon"
        else len(geom["coordinates"])
    )
    if before_rings <= 1:
        return {"id": path.stem, "rings_before": before_rings, "rings_after": before_rings}

    new_coords, new_type = clean_polygon(geom["coordinates"], geom["type"])
    feature["geometry"] = {"type": new_type, "coordinates": new_coords}
    props = feature.setdefault("properties", {})
    props.setdefault("original_area_km2", props.get("area_km2"))
    props["ring_cleanup_applied"] = True

    tmp = path.with_suffix(".geojson.tmp")
    with tmp.open("w") as handle:
        json.dump(
            {"type": "FeatureCollection", "features": [feature]}
            if data.get("type") == "FeatureCollection"
            else feature,
            handle,
            indent=2,
        )
        handle.write("\n")
    tmp.replace(path)
    return {"id": path.stem, "rings_before": before_rings, "rings_after": 1}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reservoirs", nargs="*", help="reservoir IDs (default: all)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = sorted(AOI_DIR.glob("*.geojson"))
    if args.reservoirs:
        paths = [p for p in paths if p.stem in args.reservoirs]
    for path in paths:
        info = clean_aoi_file(path)
        if info["rings_before"] != info["rings_after"]:
            print(f"{info['id']}: rings {info['rings_before']} → {info['rings_after']}")
        else:
            print(f"{info['id']}: ok (rings={info['rings_before']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# AOI Review Queue

Manual AOI review means opening the GeoJSON against a satellite or OSM water
reference and confirming the polygon tracks the reservoir water body without
major upstream-river bleed, land spill, or neighbouring-reservoir merge. Do not
mark a row reviewed from data counts alone.

## Priority 1 — critical core rows

These drive the public hero/risk narrative first.

| Priority | Reservoir | Current issue | Action |
|---:|---|---|---|
| 1 | Srisailam | Manual bbox AOI; useful for extraction but not a launch-ready map polygon | Replace with a hand-traced reservoir polygon before marking reviewed |
| 2 | KRS | JRC first-pass connected component; area is close to dashboard FRL area | Visual shoreline check in QGIS/geojson.io |
| 3 | Panchet | JRC first-pass connected component; storage still area-ratio proxy | Visual shoreline check, then wait for non-100%-full CWC anchor |
| 4 | Maithon | JRC first-pass connected component; area is close to dashboard FRL area | Visual shoreline check in QGIS/geojson.io |
| 5 | Vaigai | JRC first-pass connected component; small reservoir, higher edge-error risk | Visual shoreline check in QGIS/geojson.io |

Keep `aoi_visually_reviewed` at `0` until the corresponding GeoJSON
`review_status` is changed after a real visual pass.

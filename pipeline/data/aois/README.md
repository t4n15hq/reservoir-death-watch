# Reservoir AOIs

Committed AOIs live here as one GeoJSON polygon or multipolygon per reservoir:

```text
pipeline/data/aois/{id}.geojson
```

Do not add centroid buffers or approximate placeholder polygons. The pipeline
loads these files as source data, so every polygon must be hand-digitized or
otherwise traceable to a real reservoir boundary.

Phase 0 requires:

- `krs.geojson`
- `mettur.geojson`
- `indira_sagar.geojson`


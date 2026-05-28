# Data Schemas

The data contracts between pipeline stages and between pipeline → dashboard. Use Pydantic models for validation in code; this doc is the prose source-of-truth.

When changing any schema, bump the `model_version` in the output and update this doc.

---

## Pipeline-internal schemas

### `ReservoirAOI`

Input: loaded from `pipeline/data/aois/{id}.geojson` + row in `docs/reservoirs.csv`.

```python
class ReservoirAOI(BaseModel):
    id: str                       # short identifier, e.g. "krs"
    name: str                     # display name, e.g. "Krishnaraja Sagar"
    river: str
    state: str
    cwc_name: str                 # name as it appears in CWC bulletin
    city_served: str
    population_served: int
    lat: float                    # centroid for map pin
    lon: float
    full_pool_capacity_bcm: float | None
    dead_storage_capacity_bcm: float | None
    aoi_area_km2: float | None       # optional GeoJSON-derived area metadata
    aoi_review_status: str | None    # e.g. "first_pass_needs_manual_review"
    polygon: GeoJSONPolygon       # full-pool boundary
    scope: Literal["core_city", "expanded_cwc"]
```

### `AreaObservation`

One observation of reservoir surface area at a point in time.

```python
class AreaObservation(BaseModel):
    date: date
    area_km2: float
    data_source: Literal["jrc", "sentinel_2", "sentinel_1"]
    cloud_coverage_percent: float | None  # for S2; None for JRC/S1
```

### `AreaVolumeCurve`

Fitted hypsometric curve per reservoir. Persisted; computed once during Phase 1 and recalibrated if r² degrades.

```python
class AreaVolumeCurve(BaseModel):
    reservoir_id: str
    coefficient_a: float          # V = a * A^b
    exponent_b: float
    r_squared: float
    n_calibration_points: int
    calibrated_at: datetime
    confidence_flag: Literal["high", "medium", "low"]  # based on r²

    def area_to_volume(self, area_km2: float) -> float:
        return self.coefficient_a * (area_km2 ** self.exponent_b)
```

### `DepletionFit`

Output of Stage 7 (linear regression).

```python
class DepletionFit(BaseModel):
    reservoir_id: str
    slope_km2_per_day: float       # negative for depletion
    intercept: float
    std_error: float
    r_squared: float
    n_observations: int
    window_days: int
    fit_quality: Literal["good", "low_confidence", "rejected"]
```

### `Projection`

Output of Stage 8.

```python
class Projection(BaseModel):
    scenario: Literal["neutral_monsoon", "el_nino_monsoon"]
    days_to_dead_storage: int | None       # None if not projected to deplete
    dead_storage_date: date | None
    confidence_interval_days: tuple[int, int] | None
    method: Literal["linear_extrapolation", "chirps_augmented"]
```

### `ReservoirResult`

Final per-reservoir output of the pipeline.

```python
class ReservoirResult(BaseModel):
    id: str
    metadata: ReservoirAOI
    current_area_km2: float
    current_as_of: date
    current_data_source: Literal["sentinel_2", "sentinel_1", "stale"]
    estimated_storage_bcm: float
    cwc_reported_bcm: float | None
    cwc_as_of: date | None
    percent_full: float
    history_monthly: list[AreaObservation]   # JRC + S2 stitched
    fit: DepletionFit
    projection_neutral: Projection
    projection_el_nino: Projection
    tier: Literal["critical", "warning", "watch", "stable"]
    scope: Literal["core_city", "expanded_cwc"]
    flags: list[str]                          # e.g. ["low_volume_confidence", "monsoon_cloud_cover"]
```

---

## Output schemas (what the dashboard reads)

### `dashboard/public/data/reservoirs.json`

The primary artifact. Single file, ~200KB gzipped.

```json
{
  "generated_at": "2026-05-17T03:14:22Z",
  "model_version": "1.0.0",
  "data_sources_used": {
    "jrc_through": "2021-12",
    "s2_latest": "2026-05-15",
    "cwc_bulletin": "2026-05-14",
    "oni_month": "2026-04"
  },
  "enso": {
    "state": "el_nino_developing",
    "oni_latest": 0.7,
    "imd_monsoon_forecast": "below_normal"
  },
  "national_aggregate": {
    "total_capacity_bcm": 257.812,
    "current_storage_bcm": 99.84,
    "percent_full": 38.72,
    "reservoirs_critical": 12,
    "reservoirs_warning": 28,
    "reservoirs_watch": 35,
    "reservoirs_stable": 91,
    "people_at_risk_neutral": 32000000,
    "people_at_risk_el_nino": 87000000
  },
  "reservoirs": [ /* array of ReservoirResult */ ]
}
```

`enso.oni_latest` may be `null` when the NOAA endpoint is temporarily unavailable. Do not
substitute a stale or guessed ONI value.

### `dashboard/public/data/reservoirs/{id}.csv`

Per-reservoir long history. Columns:

| Column | Type | Notes |
|---|---|---|
| `date` | YYYY-MM-DD | Monthly for JRC, weekly for recent S2 |
| `area_km2` | float | |
| `data_source` | string | `jrc` / `sentinel_2` / `sentinel_1` |
| `estimated_storage_bcm` | float | Derived via area-volume curve; Phase 0 may use flagged area-ratio proxy |
| `cwc_storage_bcm` | float \| empty | Where matching CWC date exists |
| `percent_full` | float | |

### `dashboard/public/data/state_aggregates.json`

Pre-computed state rollups.

```json
{
  "generated_at": "2026-05-17T03:14:22Z",
  "states": [
    {
      "state": "Karnataka",
      "reservoir_count": 14,
      "observed_count": 10,
      "modeled_count": 8,
      "total_capacity_bcm": 31.2,
      "current_storage_bcm": 12.4,
      "percent_full": 39.7,
      "tier_counts": {"critical": 2, "warning": 5, "watch": 3, "stable": 4},
      "reservoir_ids": ["krs", "almatti", "bhadra", "..."]
    }
  ]
}
```

`tier_counts` counts full-history/non-`current_only_no_history` rows only, so
current-only expanded rows do not inflate projected critical/warning claims.

### `dashboard/public/data/data_provenance.json`

Per-field trust metadata consumed by the Data Quality panel.

```json
{
    "counts": {
    "total_reservoirs": 53,
    "observed_with_satellite": 53,
    "aoi_available": 53,
    "aoi_visually_reviewed": 0,
    "cwc_reference_available": 52,
    "storage_cwc_calibrated": 23,
    "lat_lon_verified": 0,
    "full_pool_capacity_from_cwc": 52,
    "dead_storage_capacity_verified": 0,
    "population_verified_against_census": 0
  },
  "reservoirs": [
    {
      "id": "srisailam",
      "scope": "core_city",
      "aoi": {"available": true, "verified": false},
      "lat_lon": {"verified": false},
      "population_served": {"verified": false}
    }
  ]
}
```

`aoi.available` means a GeoJSON polygon artifact exists and can be rendered on
the map. `aoi.verified` is stricter: it only becomes true after manual visual
review.

### `dashboard/public/data/backtest_{case}.json`

Same shape as `reservoirs.json`, but `as_of` rewound. One file per case:

- `backtest_krs_2023_12_31.json`
- `backtest_mettur_2019_03_31.json`
- `backtest_jayakwadi_2016_03_31.json`
- `backtest_jayakwadi_2019_03_31.json`

Computed once during Phase 1, regenerated only when the model changes.

---

## CSV: `docs/reservoirs.csv`

The master list. Columns:

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Short snake_case, e.g. `krs` |
| `name` | string | yes | Display name |
| `river` | string | yes | |
| `state` | string | yes | |
| `cwc_name` | string | yes | Name in CWC bulletin |
| `city_served` | string | no | Comma-separated if multiple |
| `population_served` | int | no | Estimate; if unknown, leave blank |
| `lat` | float | yes | Centroid for map pin |
| `lon` | float | yes | |
| `full_pool_capacity_bcm` | float | no | From CWC where published |
| `dead_storage_capacity_bcm` | float | no | From CWC where published |
| `priority` | int | yes | Contiguous display/backfill order |
| `aoi_file` | string | yes | Path to GeoJSON: `pipeline/data/aois/{id}.geojson` |
| `scope` | string | yes | `core_city` for the 25 city-serving rows; `expanded_cwc` for broader CWC state coverage |
| `notes` | string | no | Free text |
| `coord_source` | string | no | Source URL/citation for dam lat/lon; marks coordinates verified when populated |
| `coord_verified_at` | string | no | ISO date or short source label for coordinate verification |
| `dead_storage_source` | string | no | Source URL/citation for dead-storage capacity; marks dead-storage capacity verified when populated |
| `population_source` | string | no | Source URL/citation for population-served estimate; marks population verified when populated |

---

## Versioning policy

- `model_version` in output JSON tracks the pipeline's model logic.
- Bump minor (1.0.0 → 1.1.0) when model logic changes in a way that changes tier classifications for backtests.
- Bump patch (1.0.0 → 1.0.1) for non-substantive changes (e.g. UI-only).
- Never bump major; this is a single-project tool, not a library.
- The dashboard checks the loaded JSON's `model_version` and refuses to render if it's incompatible.

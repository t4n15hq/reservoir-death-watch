# Data Provenance

Every value displayed on the Reservoir Death Watch dashboard, with its source
and verification status. This file exists because AGENT.md non-negotiable #4
("No fabricated data") needs more than a promise — it needs an auditable
catalogue.

Fields are grouped by confidence tier. The dashboard surfaces this in the
"Data quality" card, and each reservoir detail panel exposes whether a CWC
live-storage reference is loaded for that row.

---

## Tier 1 — Genuinely measured

Pipeline-computed values traceable to a peer-reviewed satellite product or
an authoritative public feed. These are the "real" numbers.

| Dashboard field | Source | Notes |
|---|---|---|
| `current.area_km2` (surface area) | Sentinel-2 SR Harmonized via Earth Engine | MNDWI threshold > 0, SCL cloud mask, SRTM slope < 10° |
| `current.area_km2` (when cloudy) | Sentinel-1 GRD via Earth Engine | VV backscatter < -15 dB; flagged `data_source = sentinel_1` |
| `history` (JRC monthly) | JRC Global Surface Water 1.4 (Pekel et al. 2016 *Nature*) | Static, peer-reviewed; 1984–2021 |
| `history` (Sentinel-2 weekly recent) | Sentinel-2 via Earth Engine | 10-day composites, last 150 days |
| `fit` (depletion slope) | Linear regression on `history` window | r² and std error included |
| `projection.*.days_to_dead_storage` | Linear extrapolation from fit | Honest extrapolation, not modelled |
| `enso.oni_latest` | NOAA CPC ONI ASCII mirror | https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt |
| `enso.state` | Threshold rule on `oni_latest` | docs/DATASETS.md §NOAA ONI |
| `national_aggregate.*` | Sum over observed reservoirs | Derived from above |
| `state_aggregates.*` | Group-by-state of observed reservoirs | Derived from above |

---

## Tier 2 — Real but caveated

Pipeline outputs that depend on assumptions. Each surfaces a `flags` entry
that the UI displays in the detail panel.

| Field | Caveat | Flag |
|---|---|---|
| AOI polygon | Auto-derived from JRC `recurrence ≥ 50` seed, not visually reviewed | `first_pass_needs_manual_review` |
| AOI polygon (manual bbox rows) | Manual bbox; downstream extraction counts water inside | `manual_bbox_needs_visual_check` |
| `current.estimated_storage_bcm` (30 observed rows) | Computed via `area / full_pool_area × capacity` instead of a calibrated power-law curve | `volume_area_ratio_proxy`, `needs_cwc_calibration` or `needs_full_pipeline_run` |
| `current.estimated_storage_bcm` (23 observed rows) | Power-law calibrated, but only one usable CWC anchor point per reservoir | `cwc_calibrated_single_point`, `phase0_cwc_validation_incomplete` |
| `current.cwc_reported_bcm` (52 of 53) | Latest matching local CWC bulletin row from 02.04.2026-14.05.2026 — six-month validation pending | `phase0_cwc_validation_incomplete` where calibrated |
| `current.cwc_reported_bcm` (1 of 53) | No defensible matching CWC row is loaded into this snapshot yet | `needs_cwc_calibration` |
| Dead-storage area used in projection | Power-law conversion with default b=2.0 when no calibrated curve exists | `dead_storage_area_proxy` |
| `projection.el_nino_monsoon` | El Niño delta from static historical year list, not per-year ONI conditioning | `el_nino_delta_static_years` |
| `fit.fit_quality` | `low_confidence` when r² ∈ [0.7, 0.85) | embedded in `fit` object |
| `fit` missing | Insufficient observations (n < 6) or rejected (r² < 0.7) | `depletion_fit_unavailable` |

---

## Tier 3 — Metadata I supplied, not externally verified

These values came from training-data knowledge during the PRD v2 scope pivot
and have **not** been cross-checked against CWC's published register.

| Field | Where it shows | Confidence | Action needed |
|---|---|---|---|
| `lat` / `lon` | Map pin location | Approximate (±5 km plausible) | Cross-check against CWC bulletin or OSM `way:` for each dam |
| `full_pool_capacity_bcm` (52 of 53) | "of X BCM" in storage line | CWC `live_capacity_at_frl_bcm` loaded from local bulletin rows | Continue six-month bulletin collection |
| `full_pool_capacity_bcm` (1 of 53) | "of X BCM" in storage line | Approximate (±10%) | Needs a defensible CWC row match |
| `dead_storage_capacity_bcm` | Drives `dead_storage_area` calculation | Approximate | Add an explicit dead-storage source; the current Phase 0 CSV does not carry it |
| `population_served` | At-risk headline + detail byline | Rough estimate (order of magnitude) | Census 2011 + 2024 estimates for the named cities |
| `city_served` (free-text) | "Supplies X" in detail byline | Editorial label | Verify the *primary* drinking water source per city's water utility |
| `priority` | Sort order in list | Editorial; based on city population × CWC inclusion | n/a — internal ordering only |

**Note:** if any Tier 3 row is wrong by more than the noted tolerance, the
flag on that reservoir does not currently say so. The UI's "Data quality"
card lists this gap.

---

## How to verify a row in Tier 3

Standard workflow when you fetch a CWC bulletin or have time for a manual check:

1. Open the CWC weekly bulletin PDF (e.g. via `pipeline/data/cwc/raw_pdfs/`).
2. Match each reservoir's row by name; CWC publishes:
   - Live capacity at FRL (BCM)
   - Dead storage capacity (BCM)
   - Lat/long (degrees minutes seconds)
3. Update `docs/reservoirs.csv` for any field whose value differs by > 5%.
4. If `lat`/`lon` shift by > 2 km, re-run `python scripts/seed_aois.py <id> --overwrite`
   then `python scripts/backfill_history.py <id>` so the AOI follows the dam.
5. The provenance script (`scripts/audit_metadata.py`) re-validates after.

---

## Counts at last audit

Generated at the time of the most recent pipeline run. See `data_provenance.json`
for the machine-readable form.

| Class | Count |
|---|---|
| Reservoirs in dashboard scope | 53 of 53 |
| Reservoirs with satellite observation | 53 of 53 |
| Reservoirs with CWC live-storage reference loaded | 52 of 53 |
| Reservoirs with CWC-calibrated curve | 23 of 53 |
| Reservoirs with `volume_area_ratio_proxy` flag | 30 of 53 |
| Reservoirs with AOI GeoJSON available | 53 of 53 |
| Reservoirs with AOI seeded but unreviewed | 53 of 53 |
| Reservoirs awaiting AOI seeding | 0 of 53 |
| Reservoirs with verified `lat/lon` against CWC bulletin | **0 of 53** |
| Reservoirs with FRL capacity loaded from CWC | 52 of 53 |
| Reservoirs with verified `dead_storage_capacity_bcm` | **0 of 53** |
| Reservoirs with verified `population_served` against census | **0 of 53** |

The dashboard separates **operational coverage** from **manual source checks**:
all 53 reservoirs have current satellite observations and AOI polygons, while
the 28 expanded reservoirs are current-only rows awaiting historical backfill
and full area-to-volume calibration. The "0 of 53" rows are the next milestone
for Tier 3 confidence. They require manual cross-checks against CWC/OSM/census
sources; until then those metadata fields stay "approximate" in the dashboard.

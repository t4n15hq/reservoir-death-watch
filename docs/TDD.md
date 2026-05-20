# Technical Design Document

**Project:** Reservoir Death Watch
**Version:** 1.0
**Date:** May 18, 2026
**Status:** Active spec

This document is the source of truth for HOW we build. The PRD (`PRD.md`) is the source of truth for WHAT and WHY. When they conflict, fix the docs to agree — the spec should not be ambiguous.

---

## 1. Repository structure

```
reservoir-death-watch/
├── AGENT.md                    # constitution; agents read first
├── README.md                   # public-facing, links to dashboard + writeup
├── docs/
│   ├── PRD.md                  # product requirements
│   ├── TDD.md                  # this file
│   ├── PHASES.md               # phase-gated plan
│   ├── BACKTESTS.md            # validation cases
│   ├── DATASETS.md             # dataset matrix
│   ├── SCHEMAS.md              # data contracts
│   ├── reservoirs.csv          # reservoir metadata
│   ├── QUESTIONS.md            # open questions for Tanishq
│   ├── IDEAS.md                # deferred scope expansions
│   └── CHANGELOG.md            # phase completion log
├── pipeline/                   # Python: GEE pipeline + scrapers
│   ├── pyproject.toml
│   ├── src/
│   │   └── reservoirs/
│   │       ├── __init__.py
│   │       ├── config.py       # paths, constants, env
│   │       ├── aois.py         # reservoir AOI definitions
│   │       ├── gee_auth.py     # service account auth
│   │       ├── jrc.py          # JRC monthly history extraction
│   │       ├── sentinel.py     # S2 + S1 extraction
│   │       ├── area_volume.py  # SRTM hypsometric curves
│   │       ├── cwc_scraper.py  # CWC bulletin PDF scraper
│   │       ├── oni.py          # NOAA ONI fetcher
│   │       ├── chirps.py       # catchment rainfall
│   │       ├── model.py        # depletion regression + projection
│   │       ├── backtest.py     # KRS / Mettur / Jayakwadi cases
│   │       ├── export.py       # writes GEE Asset + CSV
│   │       └── pipeline.py     # top-level orchestrator
│   ├── tests/
│   │   ├── test_model.py
│   │   ├── test_backtest.py
│   │   ├── test_area_volume.py
│   │   └── test_cwc_scraper.py
│   └── scripts/
│       ├── run_weekly.sh       # entry point for cron
│       └── seed_aois.py        # one-time AOI digitization helper
├── dashboard/                  # JS: frontend
│   ├── package.json
│   ├── index.html
│   ├── src/
│   │   ├── main.js
│   │   ├── map.js              # leaflet/maplibre map of India
│   │   ├── detail.js           # per-reservoir detail panel
│   │   ├── rollup.js           # state-level rollups
│   │   ├── backtest.js         # backtest mode toggle
│   │   ├── data.js             # fetches GEE Asset + CSVs
│   │   └── styles/
│   └── public/
│       └── data/               # synced from GEE export, weekly
├── site/                       # the writeup + methodology pages
│   ├── astro.config.mjs        # or similar SSG
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.astro     # blog post / launch
│   │   │   ├── methodology.astro
│   │   │   └── data.astro      # per-reservoir CSV downloads
│   │   └── components/
│   └── public/
└── infra/                      # Hetzner deployment
    ├── cron.tab
    ├── run.sh
    ├── healthcheck.sh
    └── README.md               # Hetzner setup instructions
```

The pipeline, dashboard, and site are intentionally separate. The pipeline writes to `dashboard/public/data/` and that's the only contract between them.

---

## 2. Tech stack

### Pipeline (Python)

- **Python 3.12** managed via `uv`
- `earthengine-api` for GEE access
- `pandas`, `numpy`, `scipy` for analysis
- `requests`, `pypdf` for CWC scraping
- `pydantic` for schema enforcement on outputs
- `pytest` for tests
- `ruff` for lint + format

### Dashboard (JS)

- **Vanilla JS + Vite** (no React, no framework — pages are simple, lifetime is long)
- `maplibre-gl` for the map of India (open, no Mapbox token needed)
- `chart.js` for sparklines and projection charts
- Hosted on **GitHub Pages** at a custom domain

### Site (Astro)

- **Astro** for the writeup site (SSG, fast, friendly to markdown content)
- Content in markdown, components in Astro for charts
- Hosted on the same custom domain as dashboard via subpath or subdomain — decide in §6

### Infra

- **Hetzner VPS** (the existing one, the Hermes box)
- `cron` for weekly scheduling
- `healthchecks.io` free tier for failure alerts
- GitHub Actions for site/dashboard CI (build + deploy)

---

## 3. Data contracts

Schemas are formalized in `docs/SCHEMAS.md` with Pydantic models. The summary:

### 3.1 `dashboard/public/data/reservoirs.json`

The single artifact the dashboard reads. Updated weekly.

```json
{
  "generated_at": "2026-05-17T03:14:22Z",
  "ENSO_state": "el_nino_developing",
  "ONI_latest": 0.7,
  "national_aggregate": {
    "total_capacity_bcm": 257.812,
    "current_storage_bcm": 99.84,
    "percent_full": 38.72,
    "reservoirs_critical": 12,
    "reservoirs_warning": 28,
    "people_at_risk_el_nino": 87000000
  },
  "reservoirs": [
    {
      "id": "krs",
      "name": "Krishnaraja Sagar",
      "river": "Kaveri",
      "state": "Karnataka",
      "city_served": "Bengaluru, Mysuru",
      "population_served": 13500000,
      "full_pool_area_km2": 130.5,
      "full_pool_capacity_bcm": 1.37,
      "dead_storage_capacity_bcm": 0.13,
      "lat": 12.4244,
      "lon": 76.5719,
      "current": {
        "as_of": "2026-05-14",
        "area_km2": 78.2,
        "estimated_storage_bcm": 0.78,
        "cwc_reported_bcm": 0.81,
        "cwc_as_of": "2026-05-14",
        "percent_full": 56.9,
        "data_source": "sentinel_2"
      },
      "history": [
        {"month": "2024-01", "area_km2": 92.1},
        {"month": "2024-02", "area_km2": 88.4}
      ],
      "projection": {
        "neutral_monsoon": {
          "days_to_dead_storage": 142,
          "dead_storage_date": "2026-10-07",
          "confidence_interval_days": [118, 168]
        },
        "el_nino_monsoon": {
          "days_to_dead_storage": 89,
          "dead_storage_date": "2026-08-15",
          "confidence_interval_days": [71, 109]
        }
      },
      "tier": "warning",
      "model_version": "1.0.0"
    }
  ]
}
```

### 3.2 `dashboard/public/data/reservoirs/{id}.csv`

Per-reservoir long-history CSV for download. Columns: `date`, `area_km2`, `data_source`, `cwc_storage_bcm` (nullable), `estimated_storage_bcm`.

### 3.3 `dashboard/public/data/backtest.json`

Pre-computed backtest results. Same structure as `reservoirs.json` but with `as_of` rewound. One snapshot per backtest case (2024-01-01 for KRS, 2019-03-31 for Mettur, etc).

### 3.4 Tiers (criticality)

Computed at pipeline time. Definitions:

| Tier | Condition |
|---|---|
| critical | `projection.neutral_monsoon.days_to_dead_storage < 60` |
| warning | `60 <= projection.neutral_monsoon.days_to_dead_storage < 120` OR `projection.el_nino_monsoon.days_to_dead_storage < 60` |
| watch | `current.percent_full < 5_year_average_for_month` |
| stable | otherwise |

---

## 4. Pipeline stages

The orchestrator (`pipeline/src/reservoirs/pipeline.py`) runs these in order. Each stage is independently testable and idempotent.

### Stage 1: Load AOIs

```python
def load_aois() -> list[ReservoirAOI]:
    """Read AOI GeoJSON polygons + metadata from docs/reservoirs.csv."""
```

AOIs live in `pipeline/data/aois/{id}.geojson`. One-time digitization, committed.

### Stage 2: Fetch JRC monthly history

```python
def extract_jrc_history(aoi: ReservoirAOI, start: str, end: str) -> pd.DataFrame:
    """Returns DataFrame with columns: month, area_km2."""
```

Uses `JRC/GSW1_4/MonthlyHistory`. Pixel-count over the AOI per month. Convert to km² using pixel area.

### Stage 3: Fetch Sentinel-2 live area

```python
def extract_s2_recent(aoi: ReservoirAOI, days: int = 30) -> tuple[float, date, float]:
    """Returns (area_km2, as_of_date, cloud_coverage_percent)."""
```

- Build a 30-day cloud-masked median composite from `COPERNICUS/S2_SR_HARMONIZED`.
- Compute MNDWI: `(GREEN - SWIR1) / (GREEN + SWIR1)`. Threshold > 0.
- Mask hillshade artifacts using SRTM slope (`slope < 10°`).
- Count water pixels in AOI, convert to km².
- If composite has >70% cloud cover over AOI, fall back to Stage 3b.

### Stage 3b: Sentinel-1 SAR fallback

```python
def extract_s1_recent(aoi: ReservoirAOI, days: int = 30) -> tuple[float, date]:
    """SAR-based water extraction for monsoon cloud cover."""
```

- Use `COPERNICUS/S1_GRD`, VV polarization.
- Threshold backscatter < -15 dB → water.
- Apply same slope mask as S2.
- Lower spatial precision than S2; accept it, flag in `data_source`.

### Stage 4: Build area-to-volume curve

```python
def calibrate_area_volume(reservoir_id: str, cwc_history: pd.DataFrame) -> AreaVolumeCurve:
    """Fit a power-law curve V = a * A^b using CWC volumes as anchor points."""
```

- Match dates where we have both satellite area and CWC volume.
- Fit `V = a * A^b` (typical for reservoir geometry).
- If r² < 0.85, log a warning and widen confidence intervals downstream.

### Stage 5: Fetch CWC bulletin

```python
def fetch_cwc_bulletin() -> pd.DataFrame:
    """Scrape the latest weekly bulletin, return per-reservoir storage."""
```

- Source: `http://cwc.gov.in/reservoir-bulletin/latest`
- PDF parsing with `pypdf`, then regex for the reservoir-rows table.
- Schema-validate; if format changed, raise a clear error (don't silently produce garbage).

### Stage 6: Fetch ONI

```python
def fetch_oni() -> tuple[float, str]:
    """Returns (latest_oni, enso_state)."""
```

- Source: NOAA CPC ONI CSV.
- Classify: `oni > 0.5` → `el_nino`; `oni < -0.5` → `la_nina`; else `neutral`.
- Sub-state: `el_nino_developing` if trending upward over 3 months.

### Stage 7: Fit depletion regression

```python
def fit_depletion(area_series: pd.DataFrame, window_days: int = 90) -> DepletionFit:
    """Linear regression on the last N days of daily area observations."""
```

- Interpolate area series to daily (or use available monthly + S2 obs).
- Linear regression: `area = m * t + c`.
- Return slope (km²/day), intercept, std error, r².
- Reject if r² < 0.7 or if fewer than 6 observations in window — return `None` and flag.

### Stage 8: Project forward

```python
def project_to_dead_storage(
    fit: DepletionFit,
    current_area: float,
    dead_storage_area: float,
    el_nino_inflow_delta: float = 0.0
) -> Projection:
    """Returns (days_to_dead_storage, dead_storage_date, ci_low, ci_high)."""
```

- Straight extrapolation: `days = (current_area - dead_storage_area) / -slope`.
- El Niño scenario applies the historical inflow delta during the projected monsoon months.
- CI from regression std error, widened by 50% below 20% fill.

### Stage 9: El Niño conditioning

```python
def compute_el_nino_delta(reservoir_id: str, jrc_history: pd.DataFrame, oni_history: pd.DataFrame) -> float:
    """Historical monsoon inflow during El Niño years vs neutral years."""
```

- For each year with available JRC monthly history, classify monsoon-season ENSO state.
- Compute area gain (June area → September area) per year.
- Average for El Niño years vs neutral years.
- Return the delta in km²-gained terms.

### Stage 10: Compute tier and aggregate

```python
def compute_tiers(reservoirs: list[ReservoirResult]) -> list[ReservoirResult]:
    """Assign critical/warning/watch/stable per the table in §3.4."""

def aggregate_national(reservoirs: list[ReservoirResult]) -> NationalAggregate:
    """Sum capacity, storage, count tiers, population at risk."""
```

### Stage 11: Export

```python
def export_dashboard_data(reservoirs, aggregate, oni) -> None:
    """Write reservoirs.json + per-reservoir CSVs to dashboard/public/data/."""
```

Atomic write: write to `.tmp`, fsync, rename. Never partial state.

### Stage 12: Healthcheck ping

```python
def ping_healthcheck() -> None:
    """curl to healthchecks.io. Skip on local dev runs."""
```

---

## 5. The model (technical detail)

### 5.1 Why linear regression

Empirically, surface area decline in the 60–90 days before a reservoir hits dead storage is approximately linear. The departure from linearity is mostly governed by upstream releases for irrigation — which we treat as observed, not modeled. A more complex model would overfit this noise.

### 5.2 Window selection

- Default 90-day window.
- If recent observations show a slope inflection (Chow test p < 0.05), shorten to the most recent regime.
- Floor of 30 days; below this, surface a `low_confidence` flag.

### 5.3 El Niño delta calculation

Per reservoir:

```
neutral_inflow = mean(monsoon_area_gain[year] for year in neutral_years)
el_nino_inflow = mean(monsoon_area_gain[year] for year in el_nino_years)
el_nino_delta = el_nino_inflow - neutral_inflow  # negative if El Niño suppresses
```

Apply this delta as a shift in the projected June-Sept area curve, then re-derive days-to-dead-storage.

### 5.4 Dead storage proxy

If we have CWC's published dead storage capacity for the reservoir, use it (convert via area-volume curve to area).

If not (true for many smaller reservoirs), use 10% of full-pool area as proxy. Flag this in the UI footer for that reservoir.

### 5.5 Confidence intervals

- Base CI from regression standard error → ±1.28σ for 80% CI.
- Widen by 50% when projected fill < 20% (area-volume curve degrades).
- Widen by 30% when relying on Sentinel-1 (lower spatial precision).
- Widen by 100% on projections >120 days (extrapolation, not forecast).

---

## 6. Frontend architecture

### 6.1 Pages

| Path | Purpose | Tech |
|---|---|---|
| `/` | Landing: national map | dashboard (vanilla JS + maplibre) |
| `/state/{state}` | State rollup | dashboard |
| `/reservoir/{id}` | Detail page | dashboard |
| `/methodology` | Technical writeup | site (Astro) |
| `/blog/launch` | Launch post | site (Astro) |
| `/data` | CSV download index | site (Astro) |

### 6.2 Hosting

Single domain (e.g. `reservoirs.tanishq.dev`).

- Site (Astro SSG) served at root.
- Dashboard JS app served at `/app` or as embedded components within Astro pages.

Decide before Phase 3 (writeup): are dashboard and site one Astro project with islands, or two projects? **Recommend: one Astro project, with the interactive dashboard as Astro islands.** Simpler deploy, single domain, no auth-domain shenanigans.

### 6.3 Data fetching

- Dashboard loads `reservoirs.json` once on page load (~200KB gzipped est).
- Per-reservoir history CSVs loaded on-demand when detail panel opens.
- All data static; no API.

### 6.4 Map

- maplibre-gl with OpenMapTiles or similar open style.
- India bounding box on load.
- Reservoirs as circle markers, color by tier.
- Hover → tooltip with name + percent full.
- Click → opens detail panel.

### 6.5 Backtest mode

- URL param: `?backtest=krs_2024_01_01` loads `backtest.json` snapshot.
- Banner: "Showing model as of Jan 1, 2024 (backtest)."
- Same UI, different data file.

---

## 7. Hetzner deployment

### 7.1 Directory layout

```
/opt/reservoirs/
├── repo/                       # git checkout
├── venv/                       # uv-managed Python env
├── secrets/
│   └── gee_service_account.json  # mode 600
├── logs/
│   └── run-YYYY-MM-DD.log
└── data/
    └── reservoirs.json         # latest output (synced to GH Pages)
```

### 7.2 Cron

```
# /etc/cron.d/reservoirs
0 3 * * 0 reservoirs /opt/reservoirs/repo/infra/run.sh
```

User `reservoirs` is a non-login service user. No root.

### 7.3 `run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /opt/reservoirs/repo
source /opt/reservoirs/venv/bin/activate

LOG="/opt/reservoirs/logs/run-$(date -u +%Y-%m-%d).log"

{
  echo "=== Run start: $(date -u) ==="
  uv run python -m reservoirs.pipeline
  echo "=== Run end: $(date -u) ==="
} >> "$LOG" 2>&1

# Commit + push the updated data to GH Pages branch
cd /opt/reservoirs/repo/dashboard
git add public/data/
git commit -m "data: weekly rebuild $(date -u +%Y-%m-%d)" || true
git push origin data-branch

# Healthcheck ping (only on success — set -e ensures we don't get here on failure)
curl -fsS --retry 3 "$HEALTHCHECK_URL" > /dev/null
```

### 7.4 Failure handling

- Cron sets `MAILTO=""` to suppress email.
- If `run.sh` exits non-zero, no healthcheck ping happens.
- healthchecks.io alerts to Discord (existing Hermes webhook) after 24h of silence.
- Tanishq investigates from the log file.

### 7.5 First-time setup

Documented in `infra/README.md`. Estimated time: 2–3 hours.

1. Create GCP project, enable Earth Engine API.
2. Create service account, download JSON.
3. Register service account in GEE Code Editor.
4. Create `reservoirs` system user on Hetzner.
5. Clone repo to `/opt/reservoirs/repo`.
6. `uv venv && uv pip install -e ./pipeline`.
7. Copy service account JSON to `/opt/reservoirs/secrets/`, `chmod 600`.
8. Set env vars in `/opt/reservoirs/.env` (HEALTHCHECK_URL, etc).
9. Test manual run: `./infra/run.sh`. Verify output JSON exists.
10. Install cron entry.
11. Verify next Sunday's run.

---

## 8. Testing

### 8.1 Unit tests (must pass before merge)

- `test_area_volume.py`: hypsometric fit yields r² > 0.85 on synthetic data.
- `test_model.py`: linear regression returns expected slope on known input; CI widening logic.
- `test_cwc_scraper.py`: parse a checked-in PDF fixture; assert correct schema.
- `test_oni.py`: ENSO classification at boundary values.

### 8.2 Backtest suite (must pass before "shipped")

`test_backtest.py`:

```python
def test_krs_2024_flagged_critical():
    snapshot = run_pipeline(as_of="2023-12-31", reservoirs=["krs"])
    assert snapshot.reservoirs[0].tier == "critical"

def test_mettur_2019_flagged():
    snapshot = run_pipeline(as_of="2019-03-31", reservoirs=["mettur"])
    assert snapshot.reservoirs[0].tier in ("critical", "warning")

def test_jayakwadi_2016_2019_flagged():
    s2016 = run_pipeline(as_of="2016-03-31", reservoirs=["jayakwadi"])
    s2019 = run_pipeline(as_of="2019-03-31", reservoirs=["jayakwadi"])
    assert s2016.reservoirs[0].tier in ("critical", "warning")
    assert s2019.reservoirs[0].tier in ("critical", "warning")
```

These tests are Earth Engine-bound and opt in with `RDW_RUN_BACKTESTS=1`.
Run them before claiming Phase 1 or "shipped" status. If they ever fail
after being made passing, the model has regressed.

### 8.3 Integration test

`test_pipeline_e2e.py`: full pipeline run against a fixed test date, compares output JSON against a checked-in golden file. Updated deliberately when model changes.

---

## 9. Performance budget

- Full pipeline run (25 city-serving reservoirs, current scope): target < 30 minutes on GEE free tier. Measured: ~22 min for 22 reservoirs in the May 2026 backfill, scales linearly.
- JSON output: < 2 MB uncompressed, < 400 KB gzipped. Measured: 860 KB uncompressed, 76 KB gzipped — well under budget.
- Dashboard initial load: < 3 seconds on 4G.
- Detail panel open: < 1 second.

If we blow these, investigate before adding features.

---

## 10. Things to defer (write to `docs/IDEAS.md`)

- ML-based area extraction (current threshold-based is fine).
- Per-reservoir custom rainfall-runoff model.
- Inter-state allocation modeling.
- Real-time alerting.
- Mobile-native app.
- API server.
- User accounts.
- Anything involving GRACE before Phase 5.

If you encounter any of these and feel the urge, write the idea down in IDEAS.md with a one-line rationale and move on.

---

## 11. Versioning

- Pipeline: SemVer in `pipeline/pyproject.toml`. Bump minor on model changes that break backtest goldens. Bump major never (this isn't a library).
- Dashboard: tag releases on the GH Pages branch.
- Data: every output JSON includes `generated_at` and `model_version`.

---

## 12. Open questions

These need Tanishq's decision before Phase 3 (public writeup):

- Domain: `reservoirs.tanishq.dev`? `indiawater.live`? Other? **(Required by Phase 3)**
- Repo visibility: public from day 0, or private until Phase 3? **(Defaults to public — say so if you disagree)**
- Astro vs separate site/dashboard projects: **(Recommended: one Astro project, islands for interactive)**

Log answers in `docs/QUESTIONS.md` as they're decided.

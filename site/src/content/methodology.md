---
title: Methodology
slug: methodology
description: How Reservoir Death Watch turns Sentinel-2 surface-area observations into days-to-dead-storage projections for 25 city-serving Indian reservoirs.
---

# Methodology

This is a public dashboard for the 25 reservoirs that supply India's major
cities. It tracks them weekly via satellite, anchors the satellite-derived
storage estimates to the Central Water Commission's published volumes where
available, and projects forward to a "days to dead storage" number under two
monsoon scenarios.

Everything here is reproducible from the open-source code at
[`reservoir-death-watch`](https://github.com/t4n15hq/reservoir-death-watch).
No proprietary feeds, no manual smoothing, no fabricated values.

If something on the dashboard surprises you, this page is where to look.

## What we observe vs what we derive

**Observed** (counted in satellite pixels):

- Reservoir water-surface area in km², per reservoir, weekly.

**Derived** (from the observation plus a hypsometric assumption):

- Live storage in BCM.
- Percent of full pool.
- Days-to-dead-storage under neutral-monsoon and El Niño-monsoon scenarios.
- Tier classification (critical / warning / watch / stable).

The distinction is enforced in code and in the dashboard's UI labels —
"satellite area (observed)" vs "estimated storage (derived)" appear on every
reservoir's detail panel.

## Data sources

| Source | Coverage | Latency | Role |
|---|---|---|---|
| Sentinel-2 SR Harmonized | 10 m, 5-day revisit | 2–5 days | Live surface area |
| Sentinel-1 GRD (SAR) | 10 m, 6–12 day revisit | 3–6 days | Monsoon-cloud fallback |
| JRC Global Surface Water 1.4 | 30 m, monthly, 1984–2021 | static | Historical trace |
| SRTM DEM | 30 m | static | Slope mask for water classification |
| Central Water Commission (CWC) weekly bulletin | 166 reservoirs, weekly | Thursdays | Ground-truth storage; calibration anchor |
| NOAA CPC ONI | monthly | 1 month | ENSO conditioning of the El Niño projection |

Sentinel-2 and JRC are peer-reviewed datasets accessed via Google Earth
Engine. CWC publishes a PDF; we parse it. NOAA serves a plain text ASCII
table.

## Pipeline

The full pipeline is twelve discrete stages in
[`pipeline/src/reservoirs/`](https://github.com/t4n15hq/reservoir-death-watch/tree/main/pipeline/src/reservoirs).
Summary:

1. **Load AOI.** Each reservoir has a polygon at
   `pipeline/data/aois/{id}.geojson`, seeded from JRC's `recurrence ≥ 50`
   band — i.e. pixels that have been water in at least half the years
   observed by Landsat since 1984. The first-pass seed is then collapsed to
   its largest connected ring to keep Earth Engine's `reduceRegion`
   tractable. Some AOIs (Srisailam) use a manual bounding box because the
   reservoir is connected by river to a neighbour.

2. **Fetch JRC monthly history** (1984–2021) over the AOI. Pixel counts of
   `water == 2` → area in km².

3. **Fetch Sentinel-2 recent series** (last 150 days, 10-day composites).
   MNDWI threshold `(B3 − B11) / (B3 + B11) > 0`, SCL cloud mask, SRTM
   slope mask < 10°. Composites with cloud cover > 50% are dropped before
   the depletion fit.

4. **Sentinel-1 SAR fallback** when Sentinel-2 fails or is too cloudy.
   VV polarisation, backscatter < −15 dB → water.

5. **Build area-to-volume curve.** For reservoirs with at least one CWC
   bulletin reading: fit `V = a · A^b` in log space using the (FRL area,
   FRL capacity) anchor and the (observation area near CWC date, CWC
   reported volume) anchor. The exponent `b` for our calibrated reservoirs
   sits in the 1.86–2.83 range — consistent with literature for
   narrow-deep impoundments. When no CWC anchor exists, the pipeline
   uses an area-ratio proxy and flags the reservoir
   `volume_area_ratio_proxy`.

6. **Fetch CWC bulletin.** Manual drop into
   `pipeline/data/cwc/raw_pdfs/`; one command converts each PDF to a
   bulletin CSV. (CWC's web endpoint is auth-walled.)

7. **Fetch NOAA ONI.** Live HTTP GET against the ASCII mirror; classify
   ENSO state (`el_nino`, `el_nino_developing`, `neutral`, `la_nina`,
   `la_nina_developing`) from the latest 3 months.

8. **Fit depletion regression.** Linear `area = m · t + c` over the last
   90 days. Reject if r² < 0.7 or fewer than 6 usable observations.
   Cloud-corrupted Sentinel-2 (> 50% cloud cover) is dropped before
   fitting.

9. **Project to dead storage.** Straight-line extrapolation:
   `days = (current_area − dead_area) / |slope|`. Dead-storage area is
   computed via the calibrated curve when available; otherwise as
   `full_pool_area × (V_dead / V_full)^(1/b)` with b = 2.0 default.
   El Niño scenario applies a historical inflow delta during projected
   monsoon months.

10. **Compute tier.**
    - `critical` if neutral-monsoon days < 60
    - `warning` if neutral-monsoon days < 120 or El Niño days < 60
    - `watch` if percent full < 5-year average for the month
    - `stable` otherwise

11. **Aggregate.** National and per-state rollups over only the
    *observed* reservoirs — placeholders for reservoirs we haven't run yet
    don't drag the totals down.

12. **Export.** Atomic write to
    `dashboard/public/data/reservoirs.json`,
    `dashboard/public/data/state_aggregates.json`, plus per-reservoir CSVs
    for download.

The full source for each stage is in `pipeline/src/reservoirs/`. There's a
runbook with concrete commands at
[`docs/RUNBOOK.md`](https://github.com/t4n15hq/reservoir-death-watch/blob/main/docs/RUNBOOK.md).

## Why linear regression?

Empirically, surface-area decline in the 60–90 days before a reservoir hits
dead storage is approximately linear. The departure from linearity is mostly
governed by upstream releases for irrigation — which we observe as part of
the data rather than try to model.

This is a deliberate design choice over fancier models. A random-forest or
LSTM would over-fit the noise in the satellite observations and lose the
explainability that lets a journalist write a story about *why* a number is
moving. The dashboard's projection is reproducible from the published CSVs
in a spreadsheet.

A non-linear model would also be hard to falsify. With linear regression,
the slope and r² are inspectable; the projection is an arithmetic
extrapolation. When it's wrong, you can see it.

## Validation: three historical backtests

The model has earned the right to be called useful when it would have
flagged each of these crises using only data available at the time:

1. **KRS / Bengaluru, late 2023** — KRS dropped to ~16% of capacity, the
   worst level in over a decade. Bengaluru's tanker mafia and IT-WFH order
   followed in early 2024. **Backtest status: still failing.** The
   satellite data in Nov–Dec 2023 had only 5 Sentinel-2 observations in
   the 90-day window, all with 47–64% cloud cover. With cloud-filtering,
   no usable depletion fit is possible from satellite alone. Documented as
   a model limitation, not a code bug.

2. **Mettur / Tamil Nadu, March 2019** — fed into the broader Chennai 2019
   crisis (four Chennai reservoirs essentially dry by June 2019). Mettur
   was below average from late 2018. **Backtest status: passes.** With
   power-law dead-storage area, the model flags Mettur as warning at
   ~102 days to dead storage from the March 31, 2019 snapshot.

3. **Jayakwadi / Marathwada, 2016 and 2019** — recurring near-dead-storage
   events driven by failed monsoons. **Backtest status: both pass.** 2016
   is flagged warning with 0 days (already at dead storage); 2019 flags
   warning at 69 days.

That's 3 of 4 historical cases. The KRS 2023 case is the most recent and
best-documented crisis, and we don't catch it — that's a real limit of
satellite-only monitoring during heavy cloud cover, not something to hide.

## Data quality

Of the 25 reservoirs on the dashboard:

- **25 have Sentinel-2 observations in the last week.**
- **3 have CWC-calibrated area-to-volume curves** (KRS, Mettur, Indira
  Sagar — Phase 0 calibration set).
- **22 are using an area-ratio proxy** for storage, flagged on each
  reservoir's detail panel.
- **0 reservoirs have lat/lon verified against CWC's published register
  or OpenStreetMap.** These came from training-data knowledge during
  scope definition; they're approximate but plausible (within ±5 km).
  Same goes for `full_pool_capacity_bcm` and `population_served`.

Full provenance per field is at
[`docs/PROVENANCE.md`](https://github.com/t4n15hq/reservoir-death-watch/blob/main/docs/PROVENANCE.md).
The "Data quality" card at the bottom of the dashboard shows these counts
live.

This is the work that's still pending on the path to a fully-validated
Phase 1 ship.

## What the dashboard does NOT claim

- Real-time data. Sentinel-2 has 2–5 day latency; we update weekly.
- Forecast accuracy beyond 90 days. Anything further is extrapolation, and
  the confidence interval widens accordingly.
- Modelled prediction of upstream releases. We observe depletion; we don't
  explain it.
- Authoritative status. CWC remains the authoritative ground truth.

## What's coming

- More CWC bulletins added, replacing the area-ratio proxy with proper
  calibration on the remaining 22 reservoirs.
- Manual visual review of every AOI.
- CHIRPS catchment rainfall as a secondary projection input during
  monsoon.
- Hetzner cron deployment for weekly automated refresh.
- The four backtest snapshots exposed via `?backtest=krs_2023_12_31` etc.

All tracked in [`docs/PHASES.md`](https://github.com/t4n15hq/reservoir-death-watch/blob/main/docs/PHASES.md).

## Source

Everything is at [github.com/t4n15hq/reservoir-death-watch](https://github.com/t4n15hq/reservoir-death-watch).
Per-reservoir CSV downloads are in `dashboard/public/data/reservoirs/`.

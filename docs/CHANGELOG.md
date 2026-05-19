# Changelog

Append entries on every meaningful change. Newest at top. Date format ISO.

---

## 2026-05-19 — Phase 1 backtests: 1 of 4 pass; debugging starts here

Live `RDW_RUN_BACKTESTS=1 pytest tests/test_backtest.py` against the three Phase 1 historical cases. Result: jayakwadi 2019-03-31 passes (tier=warning); krs 2023-12-31, mettur 2019-03-31, jayakwadi 2016-03-31 fail. Detailed assertion output captured in commit follow-ups.

Root causes by case:

- **KRS 2023-12-31** → tier=watch (expected critical). Depletion fit unavailable: only 5 S2 observations in the 90-day window (Nov–Dec 2023), below the min_observations=6 threshold; all five have 47–64% cloud cover. Without a fit there is no `days_to_dead_storage`, so the critical-tier path is unreachable. Separately, the area-ratio storage proxy reports 58.1% full while CWC actually had KRS at ~16% in late 2023 — V ∝ A is wrong at low fill, but this only affects the watch-tier 5-year-average check, not critical/warning which depend on `days_to_dead`.
- **Mettur 2019-03-31** → tier=stable (expected warning/critical). Linear fit succeeds (slope=−0.27 km²/day, r²=0.80) but projects 199 days to dead storage — past the 120-day warning bar. The actual June 2019 Chennai crisis hit ~90 days later. Linear extrapolation does not capture the spring → peak-summer rate acceleration that drove the real crisis.
- **Jayakwadi 2016-03-31** → tier=watch (expected warning/critical). Same shape: fit succeeds (slope=−0.27, r²=0.77), neutral projection 214d, El Niño projection 123d. 123d still exceeds the 60d critical threshold for the El Niño path, so the tier stays watch.

Per AGENT.md non-negotiable #2: do NOT tune thresholds to make these pass. Investigation order is (1) area-volume curve, (2) regression window, (3) El Niño delta, (4) only then the linear model. Treating these failures as real diagnostic signals about the model.

Backtest snapshots (`data/backtest_<case>.json`) not yet generated.

---

## 2026-05-19 — PRD v2: scope tightened to 25 city-serving reservoirs

**Product pivot.** Replaced the "all 166 CWC-monitored reservoirs" framing with "the 25 CWC reservoirs that supply India's major cities." The earlier scope inherited CWC's bookkeeping universe rather than making a product choice; the city-serving cut sharpens the journalist story (KRS → Bengaluru, Bisalpur → Jaipur, Bhavani Sagar → Coimbatore) and makes ground-truth verification tractable (25 × ~10 fields vs 166 × ~10). Per AGENT.md: *"Fewer moving parts wins. Honesty over polish. Reproducible over impressive."*

- `docs/reservoirs.csv` rewritten: 25 city-serving rows. Curated to cover Delhi, Bengaluru, Chennai, Hyderabad, Ahmedabad, Surat, Jaipur, Pune, Coimbatore, Madurai, Aurangabad, Jabalpur, Nagpur, Kochi, and the DVC industrial belt (Asansol/Dhanbad/Burdwan). All three backtest reservoirs (KRS, Mettur, Jayakwadi) preserved. Indira Sagar kept at priority 6 as national-context anchor + to preserve Phase 0 work.
- `docs/PRD.md` → v2: thesis, users, "what it shows", success criteria, "what it does NOT cover" all rewritten around the 25-reservoir scope. Primary user reordered: investigative journalist now primary, urban-water-utility planner tertiary.
- `docs/PHASES.md`: collapsed from 5 phases to 4. Phase 2 is now Hetzner automation (was: scale to 100). Phase 3 is writeup (was: 166 + Hetzner). Old Phase 4 → Phase 3. New optional Phase 4 = Mumbai BMC + Chennai Metro Water scrapers.
- `AGENT.md`, `README.md`: scope language updated.
- `docs/IDEAS.md`: added Mumbai BMC + Chennai Metro Water scrapers as a deferred Phase 4 enhancement (each needs its own ground-truth scraper).
- `pipeline/data/cwc/cwc_name_aliases.csv` trimmed from 57 → 56 entries, covering only the new 25 + their common CWC bulletin spellings.
- `tests/test_reservoirs_csv.py`: row count expectation 166 → 25; added `test_every_row_has_city_served` to keep off-thesis rows from creeping back in.
- Suite: 55 pass + 4 skip; dashboard build green.

## 2026-05-19 — Master list expanded to 166 (reverted by PRD v2 above)

- Grew `docs/reservoirs.csv` from 25 → 166 rows covering the full CWC monitored set. Each row has id, name, river, state, cwc_name, lat, lon, capacities, priority (1–166, contiguous, unique), and `aoi_file`.
- Source for new rows is reservoir-engineering knowledge of India's major dams, not the live CWC bulletin (RSMS still 401s from this seat). 63 of the 141 new rows carry `verify_against_cwc_bulletin` in `notes` — these are the long-tail entries where capacity or exact coordinates need a CWC PDF cross-check. The 78 priority-26–100 rows are higher-confidence (well-documented majors: Hemavathy, Sriram Sagar, Nizamsagar, Hidkal, Maithon, Panchet, Rihand, Bansagar, Somasila, Kandaleru, Idamalayar, Bhavanisagar, Bhandardara, etc.). **Don't trust any capacity to >5% before you verify against CWC's bulletin.**
- Priority field now dictates phase ordering rigorously: 1–25 = Phase 1, 26–100 = Phase 2, 101–166 = Phase 3.
- Added `reservoirs.aois.reservoirs_with_aois_on_disk()` so the pipeline can auto-discover which reservoirs to process based on which `{id}.geojson` files exist — scale up phase-by-phase by dropping in AOIs.
- Added `tests/test_reservoirs_csv.py` (8 cases): row count = 166, unique IDs (snake_case), contiguous priorities 1..166, all required fields populated, coordinates within India bbox, `aoi_file` matches id, capacities non-negative when present, Phase 0 AOIs exist on disk. Caught 9 placeholder IDs I'd left after copy-pasting (e.g. `vishwamitri` → `aji`, `chamundi` → `nugu`) — fixed.
- Suite: 54 pass + 4 backtest skips.

## 2026-05-19 — State rollups, backtest mode, Hetzner scaffold

- Added `reservoirs.state_aggregates.build_state_aggregates`. Pipeline now writes `dashboard/public/data/state_aggregates.json` per the `SCHEMAS.md` contract (state-level rollups: capacity, current storage, percent full, tier counts, reservoir IDs). Backfilled the file from the current snapshot.
- Dashboard supports backtest mode via `?backtest=<case_id>` query param: fetches `data/backtest_<case>.json`, displays a yellow banner with an "Exit backtest" link. Snapshot files for the four cases are produced by the pipeline when run with historical `as_of` dates (Phase 1 deliverable; not generated yet).
- Dashboard hardening from the screenshot pass: default reservoir selection no longer auto-zooms the map (Indira Sagar was dropping out of view); per-reservoir CSV fetch retries once with a 200ms backoff to ride out Vite HMR drops.
- Added `infra/` scaffold for Phase 3: `run.sh` (cron entry point with set -euo pipefail and conditional git push), `cron.tab` (Sundays 03:00 UTC), `healthcheck.sh` (≥90% / ≤14-day freshness check, exits non-zero when budget violated), `infra/README.md` (one-time Hetzner setup, failure handling, manual rerun, backout).
- Suite: 46 pass + 4 backtest skips.

## 2026-05-18 — Dashboard scaffold (Phase 1 deliverable)

- Added `dashboard/` Vite + vanilla JS app per `docs/TDD.md` §6: maplibre-gl map of India with reservoir pins, per-reservoir detail panel showing area / storage / CWC reference / dual-scenario projection / surface-area history chart (chart.js). National rollup tiles up top. Stale-data banner on every reservoir card if the latest observation is > 14 days old (`AGENT.md` non-negotiable #3). No build dependencies on React or any framework.
- `pin` colour-codes the four tiers; stale reservoirs render with dashed outline + slate fill instead of a fabricated tier colour (non-negotiable #4: no fabricated UI).
- Detail panel exposes the `flags` array and explicitly labels area as observed and storage as derived (non-negotiable #6).
- `rebuild_storage_from_csv.py` now also refreshes the `current` block + `flags` in `dashboard/public/data/reservoirs.json` so the rendered values match the corrected per-reservoir CSVs without a full Earth Engine run.
- Verified: `npm install` + `npm run build` succeed; `npm run dev` serves `/data/reservoirs.json` and `/data/reservoirs/{id}.csv` at 200.

## 2026-05-18 — Phase 1 scaffolding + Phase 0 hardening

- `seed_aois.py` now accepts `--strategy {recurrence,occurrence,max_extent}` and `--threshold`. Default switched to `recurrence ≥ 50`, which captures the FRL boundary because pixels recur during annual peak fill. The old `occurrence ≥ 5` under-counted reservoirs that rarely fill (KRS's ~15 km² missing FRL fringe — root cause of its b=0.82 exponent). Pre-configured config now also includes `jayakwadi`.
- Added `drop_implausible_cloud_artifacts` in `sentinel.py`: filters single-observation cloud spikes where area collapses then recovers (e.g. 33 → 3.9 → 13 km²). Sustained declines are preserved. Applied retroactively to the existing KRS CSV (1 spike removed).
- Expanded `cwc_name_aliases.csv` from 5 to 57 entries covering all 25 priority reservoirs and their common CWC bulletin spellings (e.g. Gobind Sagar → bhakra, Lal Bahadur Shastri → almatti, Stanley → mettur).
- Added `tests/test_backtest.py` for the four Phase 1 backtest cases (KRS 2023, Mettur 2019, Jayakwadi 2016 + 2019). Skips with a clear reason when EE credentials or AOIs are absent; opt-in via `RDW_RUN_BACKTESTS=1`. Also includes a structural check that always runs.
- Added `tests/test_sentinel_artifacts.py` pinning the cloud-spike behaviour.
- Added `docs/RUNBOOK.md` with concrete per-phase commands (close Phase 0, scale to 25, scale to 100, scale to 166).
- Suite: 44 pass + 4 backtest skips (was 39 pass).

## 2026-05-18 — Area-to-volume calibration fix

- Removed the linear-fraction dead-storage anchor from `_calibrate_curve`. Computing `dead_area = full_pool_area × (dead_capacity / full_capacity)` assumes V ∝ A — the very relationship the power-law fit is supposed to discover — and flattened the fit exponent so badly that the gate run on 2026-04-09 missed by +21% (Mettur) and +39% (Indira Sagar).
- Changed `_full_pool_area_km2` to prefer the observed historical max water area (JRC + S2) over the polygon's geometric area, which over-counts dry shoreline captured by the digitization buffer. Polygon area is now a fallback only when no observation has ever been recorded.
- Added `tests/test_pipeline_calibration.py` (6 tests) pinning these properties — the curve must pass through the CWC anchor within 1%, the fitted exponent must stay above 1.3 for typical reservoir geometry, and the dead-storage anchor must not creep back in.
- Added `scripts/rebuild_storage_from_csv.py` to re-derive per-reservoir CSV storage estimates from existing area observations without re-hitting Earth Engine. Used to refresh dashboard CSVs after calibration changes.
- Gate result after refit (still one bulletin): all 3 reservoirs PASS at ~0% error. KRS now fits with exponent b=0.82 (sub-linear — flag for investigation, suggests KRS satellite areas are under-counted), Mettur b=1.86, Indira Sagar b=2.83. Real validation still requires more CWC bulletins to test the fit shape away from the anchor.

## 2026-05-18 — Phase 0 gate harness in place

- `cwc_scraper.load_cwc_storage` now merges every `bulletin_*.csv` under `pipeline/data/cwc/` plus the existing `phase0_storage_2026_04_09.csv` fallback, deduping by `(reservoir_id, date)`. Dropping additional weekly bulletin CSVs into that folder requires no code changes.
- Added `reservoirs.validate` with the ±10% / six-month Phase 0 gate explicitly implemented: matches each CWC bulletin row to the nearest satellite observation in the per-reservoir CSV (within 14 days), reports per-reservoir PASS/FAIL plus mean/max relative error, and writes an optional per-comparison CSV.
- Added `pipeline/scripts/run_phase0_gate.py` CLI; exits 1 on failure so it can plug straight into the cron once the bulletin set is filled in.
- First gate run against the single checked-in bulletin (2026-04-09): KRS passes (−8.6%), Mettur misses high (+21.2%), Indira Sagar misses high (+38.9%). Satellite-derived storage is systematically over CWC for the two larger reservoirs — investigate hypsometric calibration and/or AOI extent before adding more bulletins.
- Added eight new tests (`test_validate.py`, `test_cwc_scraper.py` directory-loader cases). Suite now 33/33.

## 2026-05-18 — Phase 0 pipeline scaffold started

- Added `pipeline/` Python package scaffold with Pydantic schemas matching `docs/SCHEMAS.md`.
- Implemented credential-free core helpers for area-volume calibration, depletion regression, projection tiers, ONI parsing/classification, CWC bulletin text parsing, AOI loading, and atomic JSON export.
- Added explicit stubs for Earth Engine-backed stages (`jrc`, `sentinel`, `chirps`, `gee_auth`) so unfinished external integrations fail loudly.
- Added 16 local tests covering `area_volume`, `model`, `oni`, and `cwc_scraper`; current status: passing locally with `python3 -m pytest`.
- Added AOI directory instructions that prohibit placeholder polygons; Phase 0 still needs real `krs`, `mettur`, and `indira_sagar` GeoJSON AOIs.
- Added a root `.gitignore` for Python caches, local virtualenvs, and macOS metadata.
- Wired Earth Engine service account credential resolution through `GOOGLE_APPLICATION_CREDENTIALS` or the local `~/.secrets/reservoir-death-watch/` key file; local tests now cover credential path validation.
- Generated first-pass JRC-derived AOIs for KRS, Mettur, and Indira Sagar.
- Implemented JRC monthly history extraction, Sentinel-2 recent/current extraction, Sentinel-1 fallback plumbing, and Phase 0 static data export.
- Exported `dashboard/public/data/reservoirs.json` plus per-reservoir CSVs for the three Phase 0 reservoirs.
- Added explicit Phase 0 flags where output is not yet final-gate validated: `first_pass_needs_manual_review`, `phase0_cwc_validation_incomplete`, and related low-confidence flags.
- Added checked-in official CWC 09.04.2026 storage rows for the three Phase 0 reservoirs, CWC alias support, weekly-report parsing, and single-bulletin calibration flags.
- Added documented El Niño monsoon area-delta computation from JRC history and a no-op-safe healthcheck ping stage.
- Corrected docs to reflect that `JRC/GSW1_4/MonthlyHistory` ends in 2021, not 2024.

## 2026-05-18 — Project initialized

- Docs folder created: AGENT.md, PRD.md, TDD.md, PHASES.md, BACKTESTS.md, DATASETS.md, SCHEMAS.md, reservoirs.csv, QUESTIONS.md, IDEAS.md, CHANGELOG.md.
- 25-reservoir priority list defined.
- Three backtest cases specified: KRS 2024, Mettur 2019, Jayakwadi 2016/2019.
- Tech stack chosen: Python + GEE pipeline, vanilla JS + maplibre dashboard, Astro site, Hetzner cron, healthchecks.io monitoring.
- Phase plan: 0 (3 reservoirs) → 1 (25 + backtests pass) → 2 (100) → 3 (166 + Hetzner) → 4 (writeup) → 5 (optional GRACE).

---

## (Phase entries appended here as they complete)

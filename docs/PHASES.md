# Phases

Each phase ships something usable. Each phase has a hard gate. **Do not start Phase N+1 until Phase N's gate passes.**

Since this project is built with agents on auto, "phase" here is a logical checkpoint, not a time budget. The whole thing could finish in a day; the phases still matter because each gate prevents a class of bug from propagating into the next.

---

## Phase 0 — Pipeline-as-code on 3 reservoirs

**Goal:** Prove the full pipeline works end-to-end on a small set.

**Reservoirs:** KRS, Mettur, Indira Sagar.

**Deliverables:**
- `pipeline/` package with all 12 stages from `TDD.md` §4 implemented.
- Working `pipeline.py` orchestrator that produces a valid `reservoirs.json` for the 3 reservoirs.
- Unit tests for `area_volume`, `model`, `oni`, and `cwc_scraper`.
- AOI GeoJSON files committed for the 3 reservoirs.
- Manual local run produces a sensible output.

**Gate:**
- All 3 reservoirs produce a time series that matches CWC reported live storage within ±10% over the last 6 months.
- Pipeline runs end-to-end without manual intervention.
- Unit tests pass.

**Failure handling:**
- If area-to-volume calibration is off, investigate hypsometric fit, not the model.
- If CWC scraping is fragile, check fixture against the latest PDF format.

---

## Phase 1 — Foundation, 25 reservoirs

**Goal:** Validate the pipeline on the CWC headline-bulletin reservoirs and pass all three backtests.

**Reservoirs:** All 25 from `reservoirs.csv` rows 1–25 (priority order).

**Deliverables:**
- Pipeline runs across 25 reservoirs.
- All AOIs digitized and committed.
- First version of GEE App / dashboard reading the JSON output (static, manual rebuild).
- Backtest suite implemented and passing (KRS 2024, Mettur 2019, Jayakwadi 2016/2019).

**Gate:**
- All three backtests pass with no threshold-tuning.
- Pipeline output validated against CWC for all 25.
- Dashboard loads, renders all 25 pins, detail panel works for each.

**Failure handling:**
- **If backtests fail**: STOP. Do not proceed to Phase 2. Debug in this order:
  1. Area-to-volume curve for the failing reservoir.
  2. Regression window (try 60-day, 120-day variants).
  3. El Niño delta computation.
  4. Only then question the linear model itself.
- Document the debugging in `CHANGELOG.md`.

---

## Phase 2 — Scale to 100

**Goal:** Trust the pipeline. Add the long tail of medium reservoirs.

**Reservoirs:** First 100 from `reservoirs.csv`.

**Deliverables:**
- 100 reservoirs in the dashboard.
- State-level rollups added to UI.
- Sentinel-1 SAR fallback fully working (test against a known monsoon-cloud month).
- CHIRPS catchment rainfall integration as a secondary projection input.

**Gate:**
- Random sample of 10 reservoirs hand-checked, all within ±15% of CWC.
- State rollups match sum-of-parts.
- At least one monsoon-month test case verifies S1 fallback worked.

---

## Phase 3 — All 166 + Hetzner automation

**Goal:** Full CWC coverage. Zero-manual operations.

**Reservoirs:** All 166.

**Deliverables:**
- All 166 in the dashboard.
- Hetzner deployment per `TDD.md` §7.
- Cron running every Sunday 3am UTC.
- healthchecks.io configured with Discord webhook to existing Hermes setup.
- `infra/README.md` complete and reproducible.

**Gate:**
- Pipeline runs successfully on Hetzner for 4 consecutive Sundays with no manual intervention.
- Dashboard data freshness: ≥90% of reservoirs with `as_of` ≤ 14 days.

---

## Phase 4 — Writeup and distribution

**Goal:** Make the project findable. Personal projects without a writeup are invisible.

**Deliverables:**
- Long-form launch blog post at `/blog/launch`.
- Methodology page at `/methodology`.
- Per-reservoir CSV downloads page at `/data`.
- Twitter / X thread drafted.
- Three journalist cold-email drafts.
- Hacker News submission ready.

**Gate (the real "shipped" gate):**
- Writeup published.
- 8 consecutive weeks of stable cron runs.
- At least one journalist emailed.
- Tanishq is satisfied with what's public.

---

## Phase 5 (optional) — GRACE groundwater overlay

Only if Tanishq isn't bored and wants to keep going. This is a separate technical project; treat it as such. New Phase 0–4 structure inside this phase.

---

## Phase gates summary table

| Phase | Hard gate | Failure means |
|---|---|---|
| 0 | E2E pipeline on 3 reservoirs, within ±10% of CWC | Fix data extraction |
| 1 | All 3 backtests pass, dashboard renders 25 | Debug model, do NOT proceed |
| 2 | Random 10 within ±15%, state rollups correct | Find the systematic bug at scale |
| 3 | 4 consecutive Sunday runs on Hetzner, ≥90% fresh | Fix infra before claiming live |
| 4 | Writeup + 8 weeks stable + journalist email | Project is shipped |

---

## Notes for agents

- **Phase gates are not optional.** They exist to prevent bugs from cascading.
- **The Phase 1 gate is the most important.** If backtests don't pass, everything downstream is built on sand. Spend time here.
- **Tanishq reviews at every gate.** Surface results clearly. Don't silently lower thresholds.

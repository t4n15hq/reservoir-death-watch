# Reservoir Death Watch

A satellite-driven early warning system for India's draining reservoirs.

---

## What this is

A live public dashboard covering a 25-reservoir city-serving core plus an expanded CWC state-coverage watchlist. The core set covers Delhi, Bengaluru, Chennai, Hyderabad, Ahmedabad, Surat, Jaipur, Pune, Coimbatore, Madurai, Aurangabad, Jabalpur, Nagpur, Kochi, and the DVC industrial belt. Expanded rows add CWC-backed reservoirs so each covered state has broader context. Current observations use Sentinel-2/Sentinel-1 satellite imagery; projected days-to-dead-storage uses JRC Global Surface Water history, CWC bulletins, and NOAA ONI where the full pipeline has been run.

Updated weekly via a cron job. Validated against three historical water crises (Bengaluru 2024, Chennai/Mettur 2019, Marathwada/Jayakwadi 2016 & 2019).

**Dashboard:** (URL TBD, Phase 3)
**Methodology writeup:** drafts at `site/src/content/methodology.md` and `site/src/content/launch-post.md`
**Source data:** Per-reservoir CSVs at `dashboard/public/data/reservoirs/`

---

## Status

**Phase 1B — expanded, current-observed, not closed.** All 53 dashboard reservoirs have AOIs + at least one current Sentinel observation. The 25 core city-serving reservoirs have full history/projection coverage; the 28 expanded CWC reservoirs are current-only rows with CWC storage/capacity loaded, awaiting historical backfill and full calibration. 3 of 4 historical backtests pass.

Implemented:
- Full pipeline: JRC monthly history, Sentinel-2 area, Sentinel-1 SAR fallback, area-to-volume calibration (power-law where CWC anchor available), depletion regression, dual-scenario projection, tier classification.
- Dashboard: editorial hero + ranked reservoir list + maplibre map of India + per-reservoir detail panel with history chart + data-quality provenance card + state/search/scope filters.
- Hetzner infra scaffold (`infra/run.sh`, cron entry, freshness check, README).
- CWC bulletin auto-fetcher with graceful manual fallback.
- Python unit/integration tests and ruff checks passing.

**Not yet Phase 1 closed** — blockers before public distribution:
- **Expanded coverage gap:** 53 of 53 reservoirs have current satellite observations, but the 28 expanded rows are intentionally flagged `current_only_no_history` / `needs_full_pipeline_run` until JRC/Sentinel histories are backfilled and calibrated.
- **CWC validation gap:** 23 observed reservoirs have usable CWC-calibrated storage curves. Mullaperiyar still has no defensible matched CWC row; Panchet has a CWC row but remains on the area-ratio proxy because the current CWC anchor is exactly 100% full and cannot fit a power-law curve. Six-month ±10% validation still requires more bulletins. See `docs/RUNBOOK.md`.
- **KRS 2023 backtest fails:** 5 Sentinel-2 observations in the 90-day window all have 47–64% cloud cover; no usable depletion fit possible.
- **0 of 53 manual AOI reviews / coordinate checks / dead-storage capacity checks** — see `docs/PROVENANCE.md` for the trust catalogue.

See `docs/PHASES.md` for the full plan and `docs/PROVENANCE.md` for honest counts.

---

## For agents working on this project

**Read `AGENT.md` first.** It is the constitution.

Then read `docs/PRD.md` (the why), `docs/TDD.md` (the how), and `docs/PHASES.md` (the order).

Reference docs:
- `docs/BACKTESTS.md` — validation cases (these must pass before "shipped")
- `docs/DATASETS.md` — every dataset, why it's here
- `docs/SCHEMAS.md` — data contracts
- `docs/reservoirs.csv` — 25 core city-serving reservoirs + expanded CWC state coverage
- `docs/PROVENANCE.md` — every dashboard field, its source, and verification status

Write to:
- `docs/QUESTIONS.md` when you hit a fork the docs don't cover
- `docs/IDEAS.md` when tempted by scope expansion
- `docs/CHANGELOG.md` on phase completion or user-visible change

---

## Repo layout

```
.
├── AGENT.md             # agents read first
├── README.md            # this file
├── docs/                # all the docs
├── pipeline/            # Python: GEE pipeline + scrapers
├── dashboard/           # JS: frontend
├── site/                # Astro: writeup + methodology
└── infra/               # Hetzner deployment
```

Build it out per `docs/TDD.md` §1.

---

## License

TBD before Phase 3 (public release / writeup).

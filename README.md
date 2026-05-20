# Reservoir Death Watch

A satellite-driven early warning system for India's draining reservoirs.

---

## What this is

A live public dashboard covering the 25 CWC-monitored reservoirs that supply India's major cities — Delhi, Bengaluru, Chennai, Hyderabad, Ahmedabad, Surat, Jaipur, Pune, Coimbatore, Madurai, Aurangabad, Jabalpur, Nagpur, Kochi, and the DVC industrial belt. For each reservoir, the system projects days-to-dead-storage under two scenarios — neutral monsoon and El Niño-suppressed monsoon — using Sentinel-2 satellite imagery for live extent, JRC Global Surface Water for multi-decade historical context, CWC bulletins as ground truth, and NOAA ONI for El Niño conditioning.

Updated weekly via a cron job. Validated against three historical water crises (Bengaluru 2024, Chennai/Mettur 2019, Marathwada/Jayakwadi 2016 & 2019).

**Dashboard:** (URL TBD, Phase 3)
**Methodology writeup:** drafts at `site/src/content/methodology.md` and `site/src/content/launch-post.md`
**Source data:** Per-reservoir CSVs at `dashboard/public/data/reservoirs/`

---

## Status

**Phase 1 — mostly done, not closed.** All 25 city-serving reservoirs have AOIs + at least one satellite observation; 3 of 4 historical backtests pass.

Implemented:
- Full pipeline: JRC monthly history, Sentinel-2 area, Sentinel-1 SAR fallback, area-to-volume calibration (power-law where CWC anchor available), depletion regression, dual-scenario projection, tier classification.
- Dashboard: editorial hero + ranked reservoir list + maplibre map of India + per-reservoir detail panel with history chart + data-quality provenance card.
- Hetzner infra scaffold (`infra/run.sh`, cron entry, freshness check, README).
- CWC bulletin auto-fetcher with graceful manual fallback.
- 72 unit/integration tests passing; ruff clean.

**Not yet Phase 1 closed** — blockers before public distribution:
- **CWC ground truth gap:** only 3 of 25 reservoirs have loaded CWC live-storage references and CWC-calibrated storage curves. The other 22 use area-ratio proxy (flagged `volume_area_ratio_proxy`). Six-month ±10% validation requires more bulletins. See `docs/RUNBOOK.md`.
- **KRS 2023 backtest fails:** 5 Sentinel-2 observations in the 90-day window all have 47–64% cloud cover; no usable depletion fit possible. Investigation steps 2 and 3 (per AGENT.md non-negotiable #2 failure handling) still pending — may end up as spec reframe in `docs/QUESTIONS.md`.
- **0 of 25 manual AOI reviews** — see `docs/PROVENANCE.md` for the trust catalogue.
- **0 of 25 coordinates / dead-storage capacities verified against CWC's published register** — FRL capacity is loaded from CWC for the same 3 reservoirs, but the rest of the metadata still needs cross-check.

See `docs/PHASES.md` for the full plan and `docs/PROVENANCE.md` for honest counts.

---

## For agents working on this project

**Read `AGENT.md` first.** It is the constitution.

Then read `docs/PRD.md` (the why), `docs/TDD.md` (the how), and `docs/PHASES.md` (the order).

Reference docs:
- `docs/BACKTESTS.md` — validation cases (these must pass before "shipped")
- `docs/DATASETS.md` — every dataset, why it's here
- `docs/SCHEMAS.md` — data contracts
- `docs/reservoirs.csv` — the 25 city-serving reservoirs (PRD v2 scope)
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

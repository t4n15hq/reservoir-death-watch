# Reservoir Death Watch

A satellite-driven early warning system for India's draining reservoirs.

---

## What this is

A live public dashboard covering all 166 reservoirs monitored by the Central Water Commission (CWC). For each reservoir, the system projects days-to-dead-storage under two scenarios — neutral monsoon and El Niño-suppressed monsoon — using Sentinel-2 satellite imagery for live extent, JRC Global Surface Water for 40 years of historical context, CWC bulletins as ground truth, and NOAA ONI for El Niño conditioning.

Updated weekly via a cron job. Validated against three historical water crises (Bengaluru 2024, Chennai/Mettur 2019, Marathwada/Jayakwadi 2016 & 2019).

**Dashboard:** (URL TBD, Phase 4)
**Methodology writeup:** (URL TBD, Phase 4)
**Source data:** (CSV per reservoir, Phase 2)

---

## Status

Pre-Phase-0. Specs in `docs/`. No code yet.

See `docs/PHASES.md` for the build plan.

---

## For agents working on this project

**Read `AGENT.md` first.** It is the constitution.

Then read `docs/PRD.md` (the why), `docs/TDD.md` (the how), and `docs/PHASES.md` (the order).

Reference docs:
- `docs/BACKTESTS.md` — validation cases (these must pass before "shipped")
- `docs/DATASETS.md` — every dataset, why it's here
- `docs/SCHEMAS.md` — data contracts
- `docs/reservoirs.csv` — the 25 priority reservoirs (expand to 166 in Phase 3)

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

TBD before Phase 4 (public release).

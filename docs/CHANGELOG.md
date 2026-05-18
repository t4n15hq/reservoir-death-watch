# Changelog

Append entries on every meaningful change. Newest at top. Date format ISO.

---

## 2026-05-18 — Phase 0 pipeline scaffold started

- Added `pipeline/` Python package scaffold with Pydantic schemas matching `docs/SCHEMAS.md`.
- Implemented credential-free core helpers for area-volume calibration, depletion regression, projection tiers, ONI parsing/classification, CWC bulletin text parsing, AOI loading, and atomic JSON export.
- Added explicit stubs for Earth Engine-backed stages (`jrc`, `sentinel`, `chirps`, `gee_auth`) so unfinished external integrations fail loudly.
- Added 16 local tests covering `area_volume`, `model`, `oni`, and `cwc_scraper`; current status: passing locally with `python3 -m pytest`.
- Added AOI directory instructions that prohibit placeholder polygons; Phase 0 still needs real `krs`, `mettur`, and `indira_sagar` GeoJSON AOIs.
- Added a root `.gitignore` for Python caches, local virtualenvs, and macOS metadata.
- Wired Earth Engine service account credential resolution through `GOOGLE_APPLICATION_CREDENTIALS` or `~/.secrets/reservoir-death-watch/gee_service_account.json`; local tests now cover credential path validation.

## 2026-05-18 — Project initialized

- Docs folder created: AGENT.md, PRD.md, TDD.md, PHASES.md, BACKTESTS.md, DATASETS.md, SCHEMAS.md, reservoirs.csv, QUESTIONS.md, IDEAS.md, CHANGELOG.md.
- 25-reservoir priority list defined.
- Three backtest cases specified: KRS 2024, Mettur 2019, Jayakwadi 2016/2019.
- Tech stack chosen: Python + GEE pipeline, vanilla JS + maplibre dashboard, Astro site, Hetzner cron, healthchecks.io monitoring.
- Phase plan: 0 (3 reservoirs) → 1 (25 + backtests pass) → 2 (100) → 3 (166 + Hetzner) → 4 (writeup) → 5 (optional GRACE).

---

## (Phase entries appended here as they complete)

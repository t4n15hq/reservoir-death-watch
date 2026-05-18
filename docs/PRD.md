# Product Requirements Document

**Project:** Reservoir Death Watch
**Version:** 1.0
**Date:** May 18, 2026

This is the WHY and WHAT. The HOW lives in `TDD.md`. The phase plan lives in `PHASES.md`. The constitution lives in `../AGENT.md`.

---

## 1. Thesis

India has 166 large reservoirs monitored by the Central Water Commission. They hold most of the country's interannual freshwater buffer. When they empty before the monsoon refills them — as happened to Bengaluru in 2024 (KRS at 16%), Chennai in 2019 (four reservoirs dry), and is now visibly happening to the Krishna and Kaveri basins — millions of people lose access to drinking water and irrigation.

As of the CWC's April 30, 2026 bulletin: 166 reservoirs at 38.72% of live capacity. Krishna at 22.55%. Kaveri at 35.74%. Eight states below normal. The WMO has just confirmed El Niño conditions forming May–July 2026, with a meaningful chance of suppressing the southwest monsoon by 10–20%.

CWC publishes the data weekly as a 30-page PDF. ISRO Bhuvan hosts imagery. Nobody fuses the satellite history, the live observations, the ground-truth volumes, and the El Niño signal into a single, public-facing answer to the question every state water board is privately asking:

**Which reservoirs run dry first, and when?**

This project is that answer.

---

## 2. Users

### Primary: state water board analyst

Wants to know, before the press does, which reservoir under their jurisdiction is on track for emergency-level depletion. Needs to defend the projection to political leadership. **Lands first on the state rollup view.**

### Secondary: investigative journalist

Wants a chartable, citable data point for a story on the water crisis. Needs the methodology to be defensible. **Lands first on a specific reservoir's detail page, downloads CSV.**

### Tertiary: concerned resident

Lives in a reservoir-dependent city. Wants a single plain-English answer: how worried should I be? **Lands on a search-by-city flow (Phase 2+).**

---

## 3. The product

### What it shows

- **National map** of India with 166 reservoirs, color-coded by criticality tier.
- **State rollups**: per-state aggregate capacity, current storage, count of critical reservoirs.
- **Reservoir detail pages**: 40-year history, current surface area, two-scenario projection (neutral monsoon vs El Niño monsoon), CSV download, methodology link.
- **Backtest mode**: rewind the model to a historical date and reproduce findings.

### What it claims

> "Satellite-derived early-warning signal that flags reservoir-level water stress 30–90 days before the equivalent CWC bulletin reads as critical. Updated weekly. Backed by 40 years of JRC Global Surface Water history."

### What it does NOT claim

- Real-time data. (Sentinel-2 has 2–5 day latency; we update weekly.)
- Forecast accuracy beyond 90 days. (Anything further is extrapolation, labeled as such.)
- Modeled prediction of upstream releases. (We observe depletion; we don't explain it.)
- Authoritative status. (CWC remains the authoritative ground truth.)

---

## 4. Success criteria

The project is "shipped" when all of these are true (also in `AGENT.md` §Definition of "shipped"):

1. Dashboard live at a permanent public URL, no auth required.
2. All 166 reservoirs render with `as_of` dates ≤ 14 days for ≥ 90% of them.
3. All three backtests (KRS 2024, Mettur 2019, Jayakwadi 2016/2019) pass on the live model.
4. Weekly Hetzner cron has run successfully for 8 consecutive Sundays.
5. Writeup published at `/methodology` and `/blog/launch-post`.
6. Three journalists cold-emailed.

After "shipped," further work is optional, not obligatory.

---

## 5. Out of scope (the explicit no-list)

- Other hazards (air quality, heat, landslides) — separate projects.
- Real-time/streaming updates — weekly is enough.
- Sub-reservoir spatial detail (which inlet, which gate) — operational, not strategic.
- User accounts, auth, notifications — public read-only.
- Mobile app — responsive web is sufficient.
- ML models — linear regression is more defensible.
- Inter-state allocation modeling — political modeling, not water modeling.
- A backend API — the data JSON IS the API.

When tempted by any of these, write to `IDEAS.md` and move on. See `AGENT.md` §Things to refuse.

---

## 6. Why this gap exists

CWC publishes raw data; nobody synthesizes it. State water boards have internal models but no public versions. Global products (GRanD, HydroLAKES) are static inventories. Most climate-data work in India focuses on rainfall, not the storage layer that buffers it. Stacking JRC + Sentinel-2 + CWC + ONI together is the entire technical insight; everything else is engineering.

---

## 7. The distribution plan

A live dashboard that nobody finds is worse than a writeup that nobody reads. The writeup is the project's moat.

### Channels

- **Long-form post** at `/blog/launch` — 1500–2500 words.
- **Twitter / X thread** — 8–12 tweets, leads with a striking visual.
- **Hacker News** — "Show HN" submission Tuesday/Wednesday morning IST.
- **Reddit** — r/india, r/IndiaTech, r/dataisbeautiful.
- **Cold email** to 3–5 journalists at Down To Earth, Mongabay India, Indian Express climate desk, Scroll, The Wire Science.

### Not doing

- SEO optimization, newsletter, podcast pitches, academic paper.

---

## 8. Risks

Catalogued in detail in `TDD.md` §8 and `PHASES.md`. The big ones:

1. **Backtests fail.** Phase 1 gate. Debug area-volume, then regression window. Do not tune thresholds to pass.
2. **Monsoon cloud cover.** Sentinel-1 SAR fallback handles this.
3. **CWC PDF format changes.** Scrape script has clear error mode; manual update for 1–2 weeks is acceptable.
4. **Project loses momentum.** Phase gates exist for this. After Phase 3, automate and stop touching.

---

## 9. Stopping conditions

The project ends when shipped (§4) OR when sunsetted gracefully:

**Sunset triggers:**
- Dashboard breaks and isn't fixed within 4 weeks.
- Tanishq stops caring (legitimate, not a failure mode).
- A more authoritative version of this is published by someone else.

**Sunset process:**
- Banner on writeup: "Data last updated [date]. Project no longer actively maintained."
- Disable cron.
- Archive GitHub repo.
- Leave dashboard up but stale-warned.

Sunsetting is a valid ending. See `AGENT.md` §Definition of "sunsetted".

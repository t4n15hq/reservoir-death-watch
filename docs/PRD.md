# Product Requirements Document

**Project:** Reservoir Death Watch
**Version:** 2.0
**Date:** May 19, 2026

This is the WHY and WHAT. The HOW lives in `TDD.md`. The phase plan lives in `PHASES.md`. The constitution lives in `../AGENT.md`.

**v2 change:** Scope tightened from "all 166 CWC-monitored reservoirs" to "the 25 reservoirs supplying India's major cities." The earlier 166-universe framing inherited CWC's bookkeeping choice rather than making a product choice; the city-serving cut sharpens the story (KRS dead in 89 days → Bengaluru). **v2.1 expansion:** keep that 25-reservoir core as the default view, but add an `expanded_cwc` watchlist so covered states have broader CWC context. Mumbai's BMC-managed system is still deferred to `IDEAS.md` since it requires a separate data scraper.

---

## 1. Thesis

When the reservoirs supplying India's major cities empty before the monsoon refills them — as happened to Bengaluru in 2024 (KRS at 16%), Chennai in 2019 (four reservoirs dry), and is now visibly happening to the Krishna and Kaveri basins — tens of millions of urban Indians lose reliable drinking water.

Twenty-five CWC-monitored reservoirs anchor the drinking-water supply for roughly two-thirds of India's metro population: Delhi (Bhakra, Tehri), Bengaluru (KRS, Kabini, Hemavathy, Harangi), Chennai (Mettur via the Veeranam transfer), Hyderabad (Nagarjuna Sagar, Srisailam, Singur), Ahmedabad (Sardar Sarovar), Surat (Ukai), Jaipur (Bisalpur), Pune (Khadakwasla), Coimbatore (Bhavani Sagar), Madurai (Vaigai), Aurangabad (Jayakwadi), Jabalpur (Bargi), Nagpur (Totladoh/Pench), Kochi (Idamalayar, Idukki), and the DVC industrial belt (Maithon, Panchet). A second tier of expanded CWC rows adds state context without changing the default core story. The full list lives in `reservoirs.csv`.

CWC publishes weekly storage data as a 30-page PDF. ISRO Bhuvan hosts imagery. Nobody fuses the satellite history, the live observations, the ground-truth volumes, and the El Niño signal into a single, public-facing answer to the question every urban water utility is privately asking:

**Which of our cities' reservoirs runs dry first, and when?**

This project is that answer.

---

## 2. Users

### Primary: investigative journalist or urban-affairs reporter

Wants a chartable, citable data point for a story on the water crisis. Needs the methodology to be defensible. **Lands first on a specific city's reservoir page, downloads CSV.** "Bengaluru's water source dead in 89 days" is the headline; the dashboard provides the receipts.

### Secondary: concerned urban resident

Lives in a reservoir-dependent city. Wants a single plain-English answer: how worried should I be about my city's water? **Lands on the city-search flow.**

### Tertiary: urban water-utility planner (BMC, BWSSB, CMWSSB, etc.)

Wants advance warning of which of their feeder reservoirs is on track for emergency depletion, before the press picks it up. **Lands on the per-reservoir detail page; treats it as a public second-opinion check on their internal model.**

---

## 3. The product

### What it shows

- **National map** of India with the 25 city-serving core reservoirs by default, plus an expanded CWC scope toggle.
- **Filters** for Core / Expanded / All, state, and reservoir/city search.
- **City view**: each major city's primary feeders grouped, with an aggregate "days of water under each monsoon scenario."
- **Reservoir detail pages**: multi-decade history, current surface area, two-scenario projection (neutral monsoon vs El Niño monsoon), CSV download, methodology link.
- **Backtest mode**: rewind the model to a historical date and reproduce findings.

### What it claims

> "Satellite-derived early-warning signal for the 25 reservoirs that supply India's major cities. Flags water stress 30–90 days before the equivalent CWC bulletin reads as critical. Updated weekly. Backed by multi-decade JRC Global Surface Water history."

### What it does NOT cover

- Mumbai (BMC-managed reservoirs sit outside CWC's monitoring set; deferred to `IDEAS.md`).
- Smaller Chennai reservoirs (Poondi/Cholavaram/Red Hills/Chembarambakkam — Chennai Metro Water-managed; Mettur represents the Cauvery transfer upstream).
- Hyderabad's HMWS&SB internal reservoirs (Osman Sagar, Himayat Sagar) — Singur covers the CWC-side Manjira contribution.
- Smaller-city reservoirs (anything below ~1M population unless geopolitically significant like Mullaperiyar).

### What it does NOT claim

- Real-time data. (Sentinel-2 has 2–5 day latency; we update weekly.)
- Forecast accuracy beyond 90 days. (Anything further is extrapolation, labeled as such.)
- Modeled prediction of upstream releases. (We observe depletion; we don't explain it.)
- Authoritative status. (CWC remains the authoritative ground truth.)

---

## 4. Success criteria

The project is "shipped" when all of these are true (also in `AGENT.md` §Definition of "shipped"):

1. Dashboard live at a permanent public URL, no auth required.
2. All 25 city-serving reservoirs render with `as_of` dates ≤ 14 days for ≥ 90% of them.
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

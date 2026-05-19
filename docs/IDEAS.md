# Deferred Ideas

When you have an idea that would expand scope, write it here instead of building it. Tanishq reviews periodically.

**Format:**

```
## YYYY-MM-DD: Short title

One-line description.
Why it's interesting: ...
Why it's deferred: ...
Estimated scope: small | medium | large project
```

---

## 2026-05-19: Mumbai BMC + Chennai Metro Water reservoirs

The largest gap in the city-serving scope after the v2 PRD pivot: Mumbai and most of Chennai's drinking water comes from reservoirs **not on CWC's monitored list**. Adding them would let us claim "every major Indian city's primary reservoirs" instead of "every major city except Mumbai."

- Mumbai BMC system: Bhatsa, Upper Vaitarna, Middle Vaitarna, Modak Sagar (Lower Vaitarna), Tansa, Tulsi, Vihar. Daily levels published at `portal.mcgm.gov.in`.
- Chennai Metro Water: Chembarambakkam, Poondi (Sathyamoorthy Sagar), Red Hills (Puzhal), Cholavaram. Daily levels at `chennaimetrowater.tn.gov.in`.
- Why interesting: Mumbai's 22M and Chennai's 11M people are the headline omission today.
- Why deferred: each source needs its own ground-truth scraper. AOI seeding works the same way (JRC). The pipeline calibration logic supports an arbitrary `cwc_row` so swapping in BMC/CMWSSB data is a refactor, not a redesign.
- Estimated scope: small-to-medium per source. Phase 4 candidate after the core 25 ship and the cron is stable.

---

## 2026-05-18: GRACE groundwater overlay

Layering GRACE/GRACE-FO water storage anomalies over the reservoir map.

- Why interesting: Surface water + groundwater = complete India freshwater picture. Nobody publishes this combined view.
- Why deferred: GRACE is coarse (25,000 km²) — needs a fundamentally different visualization. Separate technical project.
- Estimated scope: medium project (Phase 5 if pursued).

---

## 2026-05-18: Sediment loss over multiple decades per reservoir

Using JRC's permanent vs seasonal water classification to show how reservoirs have lost effective full-pool area to silt accumulation.

- Why interesting: Nobody visualizes this at scale for Indian reservoirs. Original-finding territory.
- Why deferred: Not deferred actually — flag for Phase 2 inclusion as a chart on detail pages.
- Estimated scope: small extension to existing pipeline.

---

## 2026-05-18: State-by-state news feed

Pull news mentions of each reservoir into a sidebar on detail pages.

- Why interesting: Adds journalism layer; "this reservoir is in the news right now."
- Why deferred: Requires news API or scraper, ongoing maintenance burden. Scope creep.
- Estimated scope: medium project, defer indefinitely.

---

## 2026-05-18: Email alerts when a reservoir crosses a threshold

Users subscribe to a reservoir, get an email when it crosses warning/critical.

- Why interesting: Useful.
- Why deferred: Adds auth, email infrastructure, ongoing maintenance. Violates the read-only-public principle. Users can build their own alerts off our CSVs.
- Estimated scope: medium project. Don't.

---

## (template for future entries)

```
## YYYY-MM-DD: Title

Description.
Why interesting: ...
Why deferred: ...
Estimated scope: small | medium | large
```

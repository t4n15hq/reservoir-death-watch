---
purpose: Hacker News "Show HN" submission draft
slug: distribution/hacker-news
status: draft — not posted
---

# Hacker News: Show HN draft

## Title (HN-friendly)

> Show HN: Reservoir Death Watch – satellite-derived early warning for India's reservoirs

Alternative titles:

- `Show HN: Tracking India's 25 city-serving reservoirs via Sentinel-2 + CWC`
- `Show HN: A days-to-dead-storage dashboard for India's reservoirs`

Lead with "Show HN: ", keep under ~75 chars, no emoji, no buzzwords.

## First comment (post immediately after submission)

> Hi HN — I built this because India's water data is technically public but
> nobody fuses it.
>
> CWC publishes a weekly PDF for 166 reservoirs. ISRO Bhuvan hosts the
> satellite imagery. NOAA tracks the El Niño signal. None of these talk
> to each other in a way that lets a journalist or a state water-board
> analyst answer "which of our reservoirs runs dry first, and when?"
>
> The dashboard tracks the 25 CWC reservoirs that supply India's major
> cities. For each one:
>
> - Surface area observed from Sentinel-2 (10m, weekly)
> - Storage estimated via CWC-calibrated hypsometric curve where I have
>   ground-truth bulletins (3 of 25 so far), or a clearly-labelled
>   area-ratio proxy otherwise (22 of 25)
> - Days-to-dead-storage projected via linear regression on the recent
>   90-day series
> - Validated against three historical crises (KRS 2024, Mettur 2019,
>   Jayakwadi 2016/2019); 3 of 4 backtests pass, the failure is
>   honestly documented
>
> The model is deliberately simple — linear regression, not LSTM or RF.
> If a number on the dashboard surprises you, you can reproduce the math
> in a spreadsheet from the per-reservoir CSV downloads.
>
> Stack: Python + Earth Engine for the pipeline, vanilla JS + Vite +
> maplibre for the dashboard, Hetzner cron for the weekly refresh. AI-
> assisted construction; the AGENT.md "constitution" governing how I
> built it is in the repo.
>
> Honest about gaps in the "Data quality" card at the bottom of the
> dashboard:
>
> - 22 of 25 reservoirs use area-ratio proxy (need more CWC bulletins)
> - 0 of 25 lat/lon coordinates verified against CWC's register
> - KRS Dec 2023 backtest fails — no usable cloud-free satellite obs
>
> Code, methodology, AGENT.md, all open:
> github.com/t4n15hq/reservoir-death-watch
>
> Happy to answer Qs about the model, the data, or the build process.

## Posting strategy

- Submit Tuesday or Wednesday morning IST (~07:30 UTC) — catches both
  Indian morning and US-East-Coast late evening
- DON'T submit on Friday (weekend kills traction) or Monday (HN traffic
  spikes hard from the weekend backlog)
- DON'T cross-post immediately to /r/india etc. — let HN cycle for ~24h
  first
- Be present in the thread for 4–6 hours after posting to answer
  questions; HN front-page time is the only thing that matters

## Likely HN questions to prepare for

| Question | Pre-baked answer |
|---|---|
| "Why not just use CWC's data directly?" | CWC is the ground truth and credited in the methodology. The contribution is the satellite-derived 30-90 day early warning signal *before* the CWC bulletin reads as critical. |
| "Why linear regression, not ML?" | Linked answer in methodology. Short version: explainability matters more than fit quality for a public-trust tool, and the noise in satellite area observations would over-fit anything fancier. |
| "Why only 25?" | PRD v2 pivot in May 2026. 166 was inheriting CWC's bookkeeping universe; 25 city-serving makes the journalist story land + ground-truth verification tractable. Mumbai is the headline omission — its BMC reservoirs aren't on CWC's list. Documented in IDEAS.md as Phase 4 candidate. |
| "How do you handle clouds?" | Sentinel-1 SAR fallback when S2 > 70% cloud. Plus a single-observation cloud-spike filter (drops 33→3.9→13 km² pattern). >50% cloud cover observations are dropped at depletion-fit time. |
| "Did you fabricate any data?" | No. There's a `docs/PROVENANCE.md` catalogue of every field's source. The dashboard's "Data quality" card surfaces verified vs unverified counts. Some metadata (population_served estimates, capacity figures) is my training-data knowledge pending CWC cross-check; flagged as such. |
| "AI-assisted, what does that mean?" | I worked through this with Claude over ~one week. The AGENT.md "constitution" in the repo records the non-negotiables I gave it (no model swaps, no fabricated data, no threshold tuning, etc.). It's an interesting artifact in itself. |

## What NOT to do on HN

- Don't oversell. The 22-of-25 proxy gap is a real limitation; lead
  with it, don't bury it
- Don't argue back at skeptical commenters — they're usually right about
  *some* part of their critique
- Don't link to Twitter. HN discounts cross-promotional content
- Don't post a second "Show HN" if the first one flops; HN frowns on
  reposting

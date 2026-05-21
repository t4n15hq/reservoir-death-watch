---
title: Launching Reservoir Death Watch
slug: blog/launch
description: A satellite-derived early warning dashboard for the 25 reservoirs that supply India's major cities.
date: 2026-05-19
---

# Launching Reservoir Death Watch

India has a freshwater problem that nobody fuses into a single picture.

The Central Water Commission publishes a 30-page PDF every Thursday with
storage levels at 166 reservoirs. ISRO hosts the satellite imagery.
NOAA tracks the El Niño signal that determines whether the southwest
monsoon will refill those reservoirs or not. None of these talk to each
other in a way that lets you answer the question every state water board
is privately asking: *which of our reservoirs runs dry first, and when?*

[Reservoir Death Watch](https://reservoirs.tanishq.dev) is my answer.

## What it shows

A live dashboard tracking the 25 CWC-monitored reservoirs that supply
India's major cities — Delhi, Bengaluru, Chennai (indirect), Hyderabad,
DVC industrial belt, Ahmedabad, Surat, Jaipur, Pune,
Coimbatore, Madurai, Aurangabad, Jabalpur, Nagpur, Kochi.

For each reservoir, the dashboard shows:

- Current surface area, observed from Sentinel-2 satellite in the last
  week.
- Estimated storage, derived from area via a calibrated hypsometric curve
  where ground-truth CWC bulletins exist, or a clearly-labelled area-ratio
  proxy otherwise.
- Days to "dead storage" — the regulatory minimum below which the
  reservoir can't supply water — under both a neutral monsoon and an El
  Niño-suppressed monsoon scenario.
- 15+ years of monthly surface-area history from JRC Global Surface
  Water, stitched with recent Sentinel-2 weekly observations.

## What the numbers say today

Of the 25 reservoirs, **5 are critical, 5 warning** as of this week:

- **KRS (Bengaluru)** — 16.9% full, model flags as already at dead
  storage.
- **Panchet & Maithon (DVC industrial belt)** — 27% and 32% full, ~30
  days to dead storage.
- **Vaigai (Madurai)** — 20.5% full, 32 days to dead.
- **Srisailam (Hyderabad)** — 22.7% full, already at dead per the model.
- **Tehri (Delhi)** — 19.4% of capacity, watch tier.
- **Indira Sagar (MP/Maharashtra)** — 21.1% full, warning.

About 66.5 million people live downstream of these critical and warning
reservoirs.

## Why I built it

Every monsoon season, a handful of Indian cities make the international
news for water rationing — Cape Town-style crises in slow motion.
Journalists at Down To Earth, Mongabay India, and the Indian Express
climate desk write good single-city stories about them, but there's no
public dataset that lets you compare across cities or check whether the
"Bengaluru is running out" headline is a leading or lagging indicator.

The data exists. CWC is open. JRC is open. NOAA is open. Earth Engine
is free for non-commercial use. The technical insight is fusing them;
the engineering is the dashboard.

## How the model works (briefly)

Linear regression on the last 90 days of satellite surface-area
observations, extrapolated to the dead-storage area for each reservoir.

It's deliberately simple. Anything more complex would over-fit the noise
in the satellite observations and lose the property I care about most:
if a number on the dashboard surprises you, you can reproduce the math
from the published CSV in a spreadsheet.

Full methodology, the historical backtest status, and the things it doesn't
claim, are at [/methodology](/methodology).

## What it doesn't do

- Real-time data. Sentinel-2 has 2–5 day latency; the dashboard updates
  weekly.
- Predict more than 90 days out. Anything further is extrapolation, and
  the confidence interval widens accordingly.
- Replace CWC. CWC remains the authoritative ground truth. The
  dashboard's contribution is the satellite-derived early warning signal,
  typically visible 30–90 days before the equivalent CWC bulletin reads
  as critical.

## What's open

Everything. Code, data, methodology, even the AGENT.md constitution that
governed how I built this with AI assistance:
[github.com/t4n15hq/reservoir-death-watch](https://github.com/t4n15hq/reservoir-death-watch).

Per-reservoir CSV downloads for the multi-decade history are at
`/data` — usable directly in any analysis tool. Citations are
appreciated; reuse is encouraged.

## What's missing

I'm honest about this in the dashboard's "Data quality" card at the
bottom of the page. As of the latest CWC ingest:

- 2 of 25 reservoirs are still using an area-ratio storage proxy:
  Mullaperiyar needs a defensible CWC name match, and Panchet needs a
  non-100%-full CWC anchor before the power-law fit is meaningful.
- 24 of 25 reservoirs have a loaded CWC live-storage reference and FRL
  capacity from local April-May 2026 bulletins.
- 0 of 25 lat/long coordinates have been verified against CWC's
  published register — they're from my training-data knowledge and could
  be off by a couple of km.
- 0 of 25 dead-storage capacities or population-served numbers have an
  external source attached yet.

These are the next milestones. The system architecture supports drop-in
verification: drop a CWC PDF into the right folder, run one command, and
the calibration switches from proxy to power-law automatically when the
row provides a usable anchor.

## What I'd love help with

If you're at a state water utility, a journalist, or a researcher who
has cross-checked Indian reservoir capacities against CWC's published
register — open a PR or email me. Same for AOI polygon corrections, or
city-served estimates from census data.

If you're an engineer who finds a bug in the model, open an issue. I
care more about being correct than being defended.

## Cold-emailing the press

If you're a journalist who's written about Indian water stress in the
last 12 months, you'll get a friendly email from me this week.

If you'd rather find me first: **tanishq@example.com**.

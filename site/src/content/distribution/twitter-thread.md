---
purpose: Twitter / X thread draft for launch day
slug: distribution/twitter-thread
status: draft — not posted
---

# Twitter / X launch thread

**Tweet 1** (with map screenshot — the 5 red pins prominently visible):

🧵 Five of the 25 reservoirs that supply India's major cities are now at critical levels.

KRS (Bengaluru), Vaigai (Madurai), Srisailam (Hyderabad), and the Maithon/Panchet pair (DVC industrial belt) are 0–32 days from dead storage under a neutral monsoon.

Live dashboard: [link]

---

**Tweet 2** (with dashboard hero screenshot — at-risk stat + tier counts):

About **66.5 million people** live downstream of reservoirs currently flagged critical or warning.

The dashboard tracks 25 reservoirs weekly via Sentinel-2 satellite + CWC bulletins + NOAA's El Niño index, and projects forward.

---

**Tweet 3** (with KRS detail panel screenshot — the days-to-dead block):

KRS is the headline. Bengaluru's primary water source is at 16.9% of capacity — the worst level since the 2024 crisis.

The model says it's already at dead storage. CWC's last bulletin confirmed 41% in early April; satellite says it's gone further down since.

---

**Tweet 4** (with surface-area history chart screenshot):

This isn't a model that requires you to trust it. The depletion projection is a linear regression on satellite area observations from the last 90 days. You can reproduce the math from the published CSV in a spreadsheet.

That's deliberate. Per the methodology:

> "If a number on the dashboard surprises you, you can reproduce it."

---

**Tweet 5** (with provenance "Data quality" card screenshot):

Honest about gaps:
- 2 of 25 reservoirs still use a storage proxy; 24 now have CWC reference rows
- 0 of 25 lat/lon coordinates have been verified against CWC's published register
- KRS 2023 backtest fails — Dec 2023 had no usable cloud-free satellite obs

These are listed on every page.

---

**Tweet 6** (closer):

Methodology, source code, per-reservoir CSV downloads — all at:
github.com/t4n15hq/reservoir-death-watch

Built solo with AI assistance over ~one week. The AGENT.md "constitution" that governed how I built it is in the repo too.

🌧️ /end

---

## Hashtags / tagging strategy

- Primary: #WaterCrisisIndia #Bengaluru #Chennai #Hyderabad (city tags
  surface to local urban planning communities)
- Avoid: #BigData, #AI — they pull engineering audiences not water people
- Tag: @CWC_Official, @MoEFCC, the climate desks at @indianexpress
  @scroll_in @mongabayindia

## Timing

- Post Tuesday or Wednesday morning IST (peak Twitter India hours)
- Aim for ~09:30 — catches morning-news rounds
- Cross-post to LinkedIn (slightly longer; lead with the headline number)

---
purpose: Cold-email drafts to investigative journalists / climate desks
slug: distribution/journalist-emails
status: draft — not sent
---

# Journalist cold-email drafts

Three templates, each tuned to the recipient's beat. Send one per
publication; pick the version closest to what they already cover. Keep
under 200 words.

---

## Template A: climate-desk reporter

**Subject:** Satellite data for an India water-crisis story (free; live
dashboard)

Hi [name],

I built a satellite-derived early-warning dashboard for the 25 reservoirs
that supply India's major cities. As of today, **5 are at critical
levels**, including KRS (Bengaluru), Vaigai (Madurai), Srisailam
(Hyderabad), and the Maithon/Panchet pair serving the DVC industrial
belt. Together they're upstream of ~66.5M people.

The data and methodology are open: live dashboard at [link], code at
github.com/t4n15hq/reservoir-death-watch, per-reservoir CSVs downloadable
from the dashboard.

Each reservoir has a "days to dead storage" projection under two monsoon
scenarios (neutral / El Niño), plus historical context from JRC Global
Surface Water back to 1984. The model is linear regression on satellite
area observations — deliberately simple, reproducible from the CSV in a
spreadsheet.

Three historical backtests (KRS 2024, Mettur 2019, Jayakwadi 2016/2019)
documented in the methodology, with the one that the model misses
honestly flagged.

Happy to walk through it if useful. No expectation of attribution if you
end up using a single chart; full citation appreciated for anything
larger.

— Tanishq
[tanishq@example.com]

---

## Template B: data-journalism reporter

**Subject:** 25-reservoir Indian water-stress dataset, public + weekly

Hi [name],

This may be relevant to your beat: I've put up a dashboard tracking the
25 CWC-monitored reservoirs that supply India's major cities, with
weekly satellite refresh and per-reservoir CSV download.

Headline: 5 of 25 currently critical, 5 warning. KRS (Bengaluru) at
16.9% of capacity. Methodology is at [link]/methodology.

I think you'll find the data-quality card at the bottom of the
dashboard interesting — it's an honest itemisation of which fields are
measured satellite observations vs my unverified metadata. Of 25
reservoirs, 22 are using a storage proxy because I only have one CWC
bulletin loaded; the path to fixing that is documented.

Source data: Sentinel-2 (10m, weekly), JRC Global Surface Water (30m,
monthly, 1984–2021), CWC weekly bulletins, NOAA ONI.

Everything is at github.com/t4n15hq/reservoir-death-watch. The
per-reservoir history CSVs are pure data — no smoothing, no
interpolation, with `data_source` column so you can filter Sentinel-2 vs
JRC vs Sentinel-1.

If a specific reservoir is interesting for a story, let me know — I
can pull a clean export.

— Tanishq

---

## Template C: investigative reporter (skeptical lede)

**Subject:** "Cape Town in slow motion" — open data for the cities at
risk

Hi [name],

The Bengaluru 2024 water crisis wasn't a surprise to anyone watching the
satellite imagery from late 2023. KRS reservoir was visibly low for
months before the tanker mafia stories ran in March 2024. Same pattern
in Chennai 2019, Marathwada 2016, etc.

I built a public dashboard that does this watching, weekly, for the 25
CWC-monitored reservoirs serving India's major cities. As of today:

- 5 critical reservoirs upstream of ~66.5M people
- KRS at 16.9% — model says already at dead storage
- Vaigai (Madurai) at 20.5%, 32 days to dead
- Maithon + Panchet (DVC industrial belt) at 27% and 32% full,
  ~30 days to dead

Live: [link]. Code, data, methodology all open at
github.com/t4n15hq/reservoir-death-watch.

The dashboard's purpose is to be the public version of what state water
boards already see internally — and ideally to flag stress 30–90 days
before the equivalent CWC bulletin reads as critical.

If you'd like an early read on any specific reservoir, the
per-reservoir CSV downloads have 15+ years of monthly history. I'm happy
to email you the cleaned series for any reservoir you're interested in.

— Tanishq

---

## Target list (cold-email triage)

| Publication | Beat | Why | Send |
|---|---|---|---|
| Down To Earth | Environment, water | Strong India climate audience; runs reservoir-level stories | Template C |
| Mongabay India | Environment, conservation | Open-data friendly; long-form | Template C |
| Indian Express climate desk | Climate, urban infra | Bengaluru / Chennai readership | Template A |
| Scroll.in | Investigative, urban | Skeptical lede works here | Template C |
| The Wire Science | Environment, data | Data-journalism friendly | Template B |
| Hindustan Times environment desk | Mainstream climate | Template A | Template A |
| Quint | Data-journalism, video-friendly | Template B + offer to package | Template B |

Send 1 per day max. Follow up once after 7 days, then drop.

## Etiquette notes

- Lead with the headline number, not the project.
- Offer the data, not the dashboard. The dashboard is for them to verify;
  the CSVs are for their work.
- No "groundbreaking", no "AI-powered", no "first-of-its-kind". Just
  describe what it does.
- Be explicit about what it doesn't do (no real-time, no >90d forecast).
- Don't ask for coverage. Ask if they want the data.

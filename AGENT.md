# AGENT.md

You are working on **Reservoir Death Watch**, a personal project by Tanishq. This file is your constitution. Read it first. Re-read it when you feel the urge to expand scope.

---

## What this project is

A live public dashboard covering the 25 CWC-monitored reservoirs that supply India's major cities, projecting days-to-dead-storage under neutral-monsoon and El Niño-suppressed-monsoon scenarios. Updated weekly via a Hetzner cron. Backed by Sentinel-2/1 imagery, JRC Global Surface Water history, CWC bulletin ground truth, and NOAA ONI for El Niño conditioning.

(Scope was tightened from "all 166 CWC reservoirs" to "25 city-serving" in May 2026 — see `docs/PRD.md` v2 for the why. The 166-universe was CWC's bookkeeping choice; 25 city-serving is the product choice.)

The full product requirements live in `docs/PRD.md`. The engineering spec lives in `docs/TDD.md`. The phase plan lives in `docs/PHASES.md`. The reservoir list lives in `docs/reservoirs.csv`. The validation cases live in `docs/BACKTESTS.md`. Read all of these before writing code.

---

## What this project is NOT

- Not a research paper. No novel ML. No deep learning models.
- Not a real-time system. Weekly cadence is honest and sufficient.
- Not a multi-hazard platform. Reservoirs only. Groundwater (GRACE) is explicitly Phase 5, optional.
- Not a tool that requires authentication, user accounts, or notifications.
- Not a mobile app.
- Not a SaaS. Public read-only.

---

## Non-negotiables (the things you must not violate)

1. **Linear regression for depletion projection.** Not random forests, not LSTMs, not Prophet. If you find yourself wanting to swap the model: stop, write the suggestion as a comment in `docs/IDEAS.md`, and continue with linear regression. The transparency of the model is a feature, not a constraint to overcome.

2. **The three backtests must pass before the dashboard is considered shipped.**
   - KRS / Bengaluru: model run on data ending Dec 31, 2023 must flag KRS as Critical.
   - Mettur / Tamil Nadu: model run on data ending Mar 31, 2019 must flag Mettur.
   - Jayakwadi / Marathwada: model should flag the 2016 and 2019 drought cycles.

   Write assertions for these into the test suite. Do not tune thresholds to make them pass — debug the underlying model. If a backtest fails, surface it loudly. Do not silently lower the bar.

3. **Show "as of" dates prominently on every reservoir card.** Earth observation is never real-time. The dashboard must be honest about staleness. If Sentinel-2 is more than 14 days stale for a reservoir, show a "stale data" indicator.

4. **No fabricated data.** If a reservoir has no usable Sentinel-2 observation in the last 30 days due to cloud cover, fall back to Sentinel-1 SAR. If both fail, show "no recent observation" — never interpolate to make the UI look complete.

5. **The CWC bulletin is ground truth.** When satellite-derived estimates disagree with CWC, CWC wins for displayed volume. Satellite-derived area can still be shown.

6. **Surface area is the satellite-observable quantity.** Volume is derived. Always be clear which is which in code, comments, and UI.

7. **Catchment rainfall (CHIRPS) refines forward projections, it does not replace them.** Keep the pure depletion-rate projection visible alongside any CHIRPS-augmented version. The user should be able to see both.

8. **Methodology must be reproducible.** Every chart on the dashboard should be reproducible from the public datasets + the code in this repo. No hidden parameters, no manual interventions beyond the AOI digitization.

---

## Things to refuse, even if asked

- Adding ML models "just to see if they're better." They're not better for this problem. If you want to try, do it in a branch called `experiments/` and do not merge.
- Expanding to other hazards (air quality, heatwaves, landslides). Each is a separate project. Add to `docs/IDEAS.md` and move on.
- Adding auth, accounts, or user-specific features. Public read-only.
- Adding email alerts, push notifications, or any messaging integration. Users can build their own alerts off our CSV exports.
- Adding a backend API server. The GEE Asset is the API surface. Static CSVs are the bulk download path.
- Generating fake/seed data for empty states. Show "no data" honestly.

---

## Decision-making heuristics

When you face a fork in the road and the docs don't cover it:

- **Boring tech wins.** PostgreSQL over a vector DB. Cron over Kubernetes. Plain JS over a framework. The boring choice is the one Tanishq can debug at 2am.
- **Fewer moving parts wins.** If you can do it with one fewer service, dependency, or config file — do it with fewer.
- **Honesty over polish.** A dashboard that says "no recent observation" is better than one that smoothly interpolates a fake number.
- **Reproducible over impressive.** A simple chart with a clear methodology beats a complex chart that nobody can recreate.

When in doubt, ask before you build. Write the question into `docs/QUESTIONS.md` with your proposed answer, and continue with the proposed answer marked as provisional.

---

## How to communicate

- **Commits should be small and atomic.** One concern per commit. Conventional commits format: `feat(pipeline): add Sentinel-1 fallback for monsoon clouds`.
- **PR descriptions explain the why.** The diff explains the what. The description explains the why and any trade-offs taken.
- **In-line comments only where the code is non-obvious.** Don't narrate.
- **Update `docs/CHANGELOG.md`** when you ship a phase or make a user-visible change.
- **If you find a bug in the spec itself, fix the spec.** Don't work around a wrong doc.

---

## Definition of "shipped"

The project is shipped when ALL of these are true:

1. Dashboard live at a permanent public URL, no auth required.
2. All 25 city-serving reservoirs render with `as_of` dates ≤ 14 days for at least 90% of them.
3. All three backtests pass on the live model.
4. Weekly Hetzner cron has run successfully for 8 consecutive Sundays.
5. Writeup published at `/methodology` and `/blog/launch-post`.
6. Three journalists cold-emailed.

After "shipped," further work is optional, not obligatory. Default to NOT adding features.

---

## Definition of "sunsetted"

If at any point Tanishq stops actively maintaining this:

1. Add a banner to the writeup: "Data last updated [date]. Project no longer actively maintained."
2. Disable the Hetzner cron.
3. Archive the GitHub repo.
4. Leave the dashboard up but with a stale-data warning.

Sunsetting is a valid ending. Most personal projects deserve this ending.

---

## Files you will look at most often

- `docs/PRD.md` — what we're building and why
- `docs/TDD.md` — engineering spec, the source of truth for HOW
- `docs/PHASES.md` — phase-gated plan with definition-of-done per phase
- `docs/BACKTESTS.md` — exact validation cases
- `docs/DATASETS.md` — every dataset, what it's for, how stale it is
- `docs/reservoirs.csv` — the 25 city-serving reservoirs and their metadata
- `docs/SCHEMAS.md` — data contracts between pipeline stages
- `docs/PROVENANCE.md` — every dashboard field, its source, and verification status
- `docs/QUESTIONS.md` — open questions for Tanishq (you write to this)
- `docs/IDEAS.md` — scope-expansion ideas to defer (you write to this)
- `docs/CHANGELOG.md` — phase-completion log (you write to this)

---

## The user

Tanishq is a founding engineer at Luminari (regulatory/clinical platform). He's comfortable in TypeScript, Python, and infra. He runs a Hetzner VPS for personal projects (Hermes). He doesn't need hand-holding on tech choices but does want to be in the loop on:

- Backtest results before claiming success
- Any data quality issue that changes the project's claims
- Any architectural decision that adds an ongoing maintenance burden
- Anything that touches Hermes' existing setup (don't break what's already running)

Default to acting; surface for review at phase gates and at the items above.

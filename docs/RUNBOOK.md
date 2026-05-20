# Runbook

Concrete commands per phase. Read `docs/PHASES.md` for the *why* before running these.

---

## Phase 0 close-out

What's still required:

1. Drop more CWC bulletin CSVs into `pipeline/data/cwc/` named `bulletin_YYYY_MM_DD.csv`.
   The directory loader picks them up automatically. Target: at least 26 weekly bulletins (~6 months).
   Each CSV must include the columns enforced by `CWC_STORAGE_REQUIRED_COLUMNS`.

2. Re-seed AOIs with the inclusive `recurrence` strategy so KRS picks up its
   missing ~15 km² along the FRL boundary (the old `occurrence ≥ 5` was the
   reason its fit exponent came out at b=0.82):

   ```bash
   cd pipeline
   uv run python scripts/seed_aois.py --overwrite
   ```

   To compare strategies on a single reservoir without overwriting the others:

   ```bash
   uv run python scripts/seed_aois.py krs --strategy recurrence --threshold 50 --overwrite
   ```

3. Run the gate. Exits 0 on PASS, 1 on FAIL:

   ```bash
   uv run python scripts/run_phase0_gate.py --as-of $(date +%F) --report-csv /tmp/gate.csv
   ```

4. If gate FAILs, debug in this order per `docs/PHASES.md`:
   - Area-to-volume curve (read `flags` in `reservoirs.json`).
   - Regression window (try 60-day / 120-day variants).
   - El Niño delta.
   - Only then question the linear model.

---

## Phase 1 — scale to 25

Prerequisites (these can run in any order):

1. **Add the 22 missing AOIs.** Every reservoir in `docs/reservoirs.csv` needs
   a polygon at `pipeline/data/aois/{id}.geojson`. The seeder handles the
   priority-1 reservoirs already configured (KRS, Mettur, Indira Sagar,
   Jayakwadi). For the rest:

   ```bash
   uv run python scripts/seed_aois.py jayakwadi hirakud bhakra tehri nagarjuna_sagar \
     almatti tungabhadra sardar_sarovar srisailam ukai pong gandhi_sagar \
     rana_pratap_sagar harangi bhadra linganamakki idukki mullaperiyar \
     bargi tawa koyna ujjani --overwrite
   ```

   Each first-pass polygon is flagged `first_pass_needs_manual_review`. Open
   each one in QGIS / geojson.io and trim shorelines that bleed onto land or
   merge with upstream rivers. `seed_aois.py` writes one feature per file —
   the pipeline's loader enforces that.

2. **Extract the full CWC bulletin (all 25 rows) into `pipeline/data/cwc/`.**
   The parser supports it via `parse_bulletin_pdf`:

   ```bash
   uv run python -c "
   from pathlib import Path
   from reservoirs.cwc_scraper import load_cwc_name_aliases, parse_bulletin_pdf
   aliases = load_cwc_name_aliases()
   frame = parse_bulletin_pdf(
       Path('/path/to/bulletin-DD-MM-YYYY.pdf'),
       reservoir_aliases=aliases,
       source_url='https://rsms.cwc.gov.in/.../bulletin.pdf',
   )
   frame['source_lines'] = ''
   frame.to_csv('pipeline/data/cwc/bulletin_YYYY_MM_DD.csv', index=False)
   "
   ```

   Aliases for all 25 priority reservoirs are pre-loaded in
   `pipeline/data/cwc/cwc_name_aliases.csv`.

3. **Run the pipeline against all 25:**

   ```bash
   uv run python -m reservoirs.pipeline \
     $(awk -F, 'NR>1 {printf "--reservoir %s ", $1}' ../docs/reservoirs.csv)
   ```

4. **Run the backtest suite** (requires Earth Engine creds + Jayakwadi AOI):

   ```bash
   RDW_RUN_BACKTESTS=1 uv run pytest tests/test_backtest.py -v
   ```

   All four cases must pass. Per `AGENT.md`: *do not tune thresholds to make
   them pass.*

5. **Gate check:** the ±10% / six-month gate must pass for all 25 reservoirs
   with the accumulated CWC bulletin set.

---

## Phase 2 — Hetzner automation

`docs/reservoirs.csv` is now scoped to the 25 city-serving reservoirs.
Phase 2 is about getting the weekly cron stable on Hermes — no scope growth.

- Build out `infra/` per `docs/TDD.md` §7. Files already exist in `infra/`;
  follow `infra/README.md` for the one-time Hetzner setup.
- Wire `/etc/cron.d/reservoirs` and confirm 4 consecutive Sunday runs with
  ≥90% of reservoirs fresh (≤14 days old).
- Wire CHIRPS catchment rainfall (`reservoirs.chirps` is still stubbed) as a
  secondary projection input.
- Verify Sentinel-1 SAR fallback against a monsoon-month test case.

Run the pipeline against everything that has an AOI file present:

```bash
uv run python -m reservoirs.pipeline $(python -c "
from reservoirs.aois import reservoirs_with_aois_on_disk
print(' '.join(f'--reservoir {r}' for r in reservoirs_with_aois_on_disk()))
")
```

---

## Phase 3 — writeup + distribution

See `docs/PHASES.md`. Writeup, three journalist cold-emails, Hacker News post.

---

## CWC bulletin ingest

Adds proper power-law area-to-volume calibration for the 22 reservoirs
currently using the area-ratio storage proxy.

> **Dead end:** `rsms.cwc.gov.in/admin/storage/bulletins/...` returns
> HTTP 401 from every network we tested (laptop, Azure runners,
> Anthropic egress, in-browser). It was never a stable public path.
> The old `fetch_cwc_bulletin.py` is now a deprecated stub pointing
> at the replacement below.

### Canonical path: data.gov.in API

The CWC daily reservoir feed is published as resource
`1fc2148c-fc41-46f5-a364-bdc03f77053f` on
[data.gov.in](https://www.data.gov.in/resource/daily-data-reservoir-level-central-water-commission-cwc).
JSON, stable, free, daily-resolution. One-time setup:

1. Register at <https://www.data.gov.in/>.
2. Generate a key from your profile (Resources → API key, or similar).
3. Store the key in **one** of:
   - `~/.secrets/reservoir-death-watch/data_gov_in.key` (recommended)
   - `$DATA_GOV_IN_API_KEY` env var
   - the `--api-key` flag

Run it:

```bash
cd pipeline
uv run python scripts/fetch_data_gov_in.py --days-back 14 --verbose
```

It paginates the resource, filters to our 25 tracked reservoirs via
`pipeline/data/cwc/cwc_name_aliases.csv`, and writes
`bulletin_YYYY_MM_DD.csv` files in the same schema as the PDF parser
output. Existing CSVs are preserved unless the API has strictly more
rows.

### Automated: GitHub Actions

`.github/workflows/fetch-cwc-bulletin.yml` runs every Friday 03:30 UTC
and on manual dispatch. It reads `DATA_GOV_IN_API_KEY` from a repo
secret (Settings → Secrets and variables → Actions → New repository
secret). On any new CSVs it opens a PR with label `automated, data`.

### Manual fallback: weekly bulletin PDFs

The data.gov.in resource carries `live_storage` and `capacity_at_frl`
but **not** `normal_storage` or `percent_normal` (long-period averages).
Those only come from the weekly bulletin PDF. If you need them, grab
a PDF in a browser when `cwc.gov.in` is reachable, drop it into
`pipeline/data/cwc/raw_pdfs/`, and run:

```bash
uv run python scripts/parse_local_cwc_pdfs.py
```

That CSV is strictly richer and will supersede the data.gov.in row for
the same date.

### After either path, refresh the snapshot

Fast path — refresh storage from existing CSVs without re-hitting GEE:

```bash
uv run python scripts/rebuild_storage_from_csv.py
```

Or, full path — re-run the depletion fit for specific reservoirs that
now have CWC calibration:

```bash
uv run python scripts/backfill_history.py --as-of $(date +%F) <ids...>
```

Then run the gate:

```bash
uv run python scripts/run_phase0_gate.py --report-csv /tmp/gate.csv
```

---

## Dashboard

```bash
cd dashboard
npm install         # one-time
npm run dev         # local dev server at http://localhost:5173
npm run build       # static bundle in dashboard/dist/
```

The dashboard reads `dashboard/public/data/reservoirs.json` and the per-reservoir
CSVs. Re-running `python scripts/rebuild_storage_from_csv.py` (no GEE needed)
or `python -m reservoirs.pipeline` (full refresh) updates these files.

---

## Operational commands

Regenerate dashboard storage CSVs after a calibration change (no GEE needed):

```bash
uv run python scripts/rebuild_storage_from_csv.py
```

Run the gate against checked-in artifacts:

```bash
uv run python scripts/run_phase0_gate.py --report-csv /tmp/gate.csv
```

Full pipeline (requires Earth Engine):

```bash
uv run python -m reservoirs.pipeline --as-of $(date +%F)
```

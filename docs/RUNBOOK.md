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

1. Fetch the weekly bulletin PDF from CWC. Any path that works for you —
   browser, VPN, IndiaWRIS export, etc. (the rsms.cwc.gov.in endpoint
   is auth-walled from at least some networks; assume it might be
   inaccessible from your CI/agent seat).

2. Drop the PDF into `pipeline/data/cwc/raw_pdfs/` (filename ignored).

3. Convert all PDFs in that folder to bulletin CSVs:

   ```bash
   cd pipeline
   uv run python scripts/parse_local_cwc_pdfs.py
   ```

   Each PDF becomes `bulletin_YYYY_MM_DD.csv` in `pipeline/data/cwc/`
   (the directory `cwc_scraper.load_cwc_storage` watches). Use
   `--overwrite` to replace existing files when re-parsing.

4. Rebuild snapshots for the affected reservoirs so they pick up the
   new CWC calibration anchor:

   ```bash
   uv run python scripts/backfill_history.py --as-of $(date +%F) <ids...>
   ```

   Or, faster, just refresh storage from existing CSVs without re-hitting
   Earth Engine:

   ```bash
   uv run python scripts/rebuild_storage_from_csv.py
   ```

5. Run the gate:

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

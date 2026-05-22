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

## Phase 1 — scale core to 25

Prerequisites (these can run in any order):

1. **Add the missing core AOIs.** Every `core_city` reservoir in
   `docs/reservoirs.csv` needs a polygon at `pipeline/data/aois/{id}.geojson`.
   For a batch run:

   ```bash
   uv run python scripts/seed_aois.py \
     $(uv run python -c "import csv; print(' '.join(r['id'] for r in csv.DictReader(open('../docs/reservoirs.csv')) if r['scope']=='core_city'))") \
     --overwrite
   ```

   Each first-pass polygon is flagged `first_pass_needs_manual_review`. Open
   each one in QGIS / geojson.io and trim shorelines that bleed onto land or
   merge with upstream rivers. `seed_aois.py` writes one feature per file —
   the pipeline's loader enforces that.

2. **Extract CWC bulletin rows into `pipeline/data/cwc/`.**
   The current local parser handles all aliases in `docs/reservoirs.csv`:

   ```bash
   uv run python scripts/parse_local_cwc_pdfs.py --overwrite
   ```

3. **Run the pipeline against the 25 core rows:**

   ```bash
   uv run python -m reservoirs.pipeline \
     $(uv run python -c "import csv; print(' '.join('--reservoir '+r['id'] for r in csv.DictReader(open('../docs/reservoirs.csv')) if r['scope']=='core_city'))")
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

## Phase 1B — expanded CWC rows

Expanded rows now have first-pass AOIs and current Sentinel observations. To
rebuild that current-observed layer, run:

```bash
uv run python scripts/seed_aois.py \
  $(uv run python -c "import csv; print(' '.join(r['id'] for r in csv.DictReader(open('../docs/reservoirs.csv')) if r['scope']=='expanded_cwc'))") \
  --overwrite

uv run python scripts/quick_extract_current.py \
  $(uv run python -c "import csv; print(' '.join(r['id'] for r in csv.DictReader(open('../docs/reservoirs.csv')) if r['scope']=='expanded_cwc'))")
```

To close Phase 1B, run the slower historical backfill for expanded rows:

```bash
uv run python scripts/backfill_history.py --as-of $(date +%F) \
  $(uv run python -c "import csv; print(' '.join(r['id'] for r in csv.DictReader(open('../docs/reservoirs.csv')) if r['scope']=='expanded_cwc'))")
```

After any metadata or AOI change, keep the dashboard honest with:

```bash
uv run python scripts/audit_metadata.py
```

---

## Phase 2 — Hetzner automation

The dashboard scope includes current-observed expanded rows, but Phase 2 is
about getting the weekly cron stable on Hermes — no further scope growth.

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

Adds or extends CWC-grounded area-to-volume calibration. As of the
2026-05-20 local ingest, 23 reservoirs have usable CWC-calibrated curves,
Panchet has a CWC reference but still needs a non-100%-full anchor, and
Mullaperiyar still needs a defensible CWC row match.

### What we know about CWC access

Official path, in order of preference:

1. CWC's public reservoir bulletin listing:
   `https://www.cwc.gov.in/reservoir-level-storage-bulletin`
2. RSMS public portal launched by CWC:
   `https://rsms.cwc.gov.in/frameWork/web/public-dashboard`
3. Direct RSMS PDFs:
   `https://rsms.cwc.gov.in/admin/storage/bulletins/bulletin-DD-MM-YYYY-NN.pdf`

PIB confirms CWC issues the storage bulletin weekly on Thursdays and that the
public can download bulletins from the RSMS portal. In practice, some networks
still receive HTTP 401 from `rsms.cwc.gov.in`, so the fetcher tries the CWC
listing page first, then falls back to direct RSMS URL guesses.

### Automated path A: official listing + RSMS URL fetch

Run locally from any network that can reach CWC:

```bash
cd pipeline
uv run python scripts/fetch_cwc_bulletin.py --weeks-back 8 --verbose
```

The script now:

1. Scans CWC's official reservoir bulletin listing for PDF download links.
2. For missing dates, tries direct RSMS `bulletin-DD-MM-YYYY-NN.pdf` URLs.
3. Estimates `NN` from known public anchors:
   - `26.02.2026` -> `84`
   - `09.04.2026` -> `91`
4. Saves PDFs into `pipeline/data/cwc/raw_pdfs/`.
5. Parses PDFs into `pipeline/data/cwc/bulletin_YYYY_MM_DD.csv`.

If this succeeds, run:

```bash
uv run python scripts/rebuild_storage_from_csv.py
```

That is the fastest path to update the dashboard without re-hitting Earth
Engine.

### Automated path B: GitHub Actions (no machine required)

`.github/workflows/fetch-cwc-bulletin.yml` runs every Friday 03:30 UTC
on a GitHub-hosted runner. The runner egresses from Azure IPs — a
completely different IP space from your laptop or Hermes, so if CWC
doesn't block Azure ranges this is fully automated.

- On success: opens a PR titled "Weekly CWC bulletin pull" containing
  the new PDF + parsed CSV. Merge → run `python scripts/rebuild_storage_from_csv.py`
  → done.
- On failure: the workflow records "no bulletin pulled" in its summary
  but does NOT fail with a red ✗ (this is a best-effort task; we don't
  want it to spam Actions noise).

You can also fire it manually via Actions → "fetch-cwc-bulletin" →
"Run workflow", with optional `hint_index` (NN guess for
`bulletin-DD-MM-YYYY-NN.pdf`) and `weeks_back` inputs.

If the PR opens consistently every Friday, the runner has CWC access —
turn on auto-merge for the `automated` label and walk away.

If it never opens a PR, Azure IPs are blocked too — fall through to
path B or C.

### Automated path C: local cron (when your network has CWC access)

```bash
cd pipeline
uv run python scripts/fetch_cwc_bulletin.py --weeks-back 4
```

Tries the last four Thursdays' bulletins from `rsms.cwc.gov.in`, drops
any PDFs that come back into `pipeline/data/cwc/raw_pdfs/`, then
auto-runs the parser to produce `bulletin_*.csv`. Exit code 0 means at
least one bulletin landed; non-zero means none did.

The `infra/run.sh` cron entry calls this on every Sunday run, before
the main pipeline. If the fetch fails (CWC's RSMS is auth-walled from
some networks), the cron pings the configured Discord webhook so you
get a manual-action notice; the rest of the pipeline still runs against
whatever bulletins are already cached.

### Automated path D: manual fallback when auto paths fail

If `fetch_cwc_bulletin.py` reports `no candidate URL worked`, the
network the script is running on doesn't have access (CWC blocks some
IP ranges). Download in a browser from any working network and:

1. Drop the PDF into `pipeline/data/cwc/raw_pdfs/` (filename ignored).

2. Parse:

   ```bash
   uv run python scripts/parse_local_cwc_pdfs.py
   ```

   Each PDF becomes `bulletin_YYYY_MM_DD.csv` in `pipeline/data/cwc/`
   where the directory loader picks it up.

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

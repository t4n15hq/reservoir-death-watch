#!/usr/bin/env bash
# Weekly pipeline run for Reservoir Death Watch on the Hermes Hetzner VPS.
# Per docs/TDD.md §7.3. Exits non-zero (no healthcheck ping) on any failure.

set -euo pipefail

REPO="${RDW_REPO:-/opt/reservoirs/repo}"
VENV="${RDW_VENV:-/opt/reservoirs/venv}"
LOG_DIR="${RDW_LOG_DIR:-/opt/reservoirs/logs}"
DATA_BRANCH="${RDW_DATA_BRANCH:-data-branch}"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run-$(date -u +%Y-%m-%d).log"

{
  echo "=== Run start: $(date -u) ==="
  cd "$REPO"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"

  # Try to grab this week's CWC bulletin BEFORE the main pipeline runs.
  # Failure here is non-fatal — the pipeline can still produce satellite-
  # only output. If the fetch fails we ping a Discord webhook (if
  # configured) so the on-call knows to grab the PDF manually.
  echo "--- CWC bulletin fetch ---"
  if python pipeline/scripts/fetch_cwc_bulletin.py --weeks-back 2 --timeout 20; then
    echo "CWC fetch ok"
  else
    echo "CWC fetch failed; continuing with previously-loaded bulletins"
    if [[ -n "${RDW_DISCORD_WEBHOOK:-}" ]]; then
      curl -fsS -X POST -H "Content-Type: application/json" \
        -d '{"content":"⚠️ Reservoir Death Watch: weekly CWC bulletin auto-fetch failed. Please download manually from rsms.cwc.gov.in and drop into pipeline/data/cwc/raw_pdfs/, then run scripts/parse_local_cwc_pdfs.py."}' \
        "$RDW_DISCORD_WEBHOOK" > /dev/null || true
    fi
  fi

  echo "--- main pipeline ---"
  python -m reservoirs.pipeline --as-of "$(date -u +%F)"
  echo "=== Run end: $(date -u) ==="
} >> "$LOG" 2>&1

# Commit + push the updated data so GitHub Pages picks it up.
cd "$REPO/dashboard"
if [[ -n "$(git status --porcelain public/data)" ]]; then
  git add public/data/
  git commit -m "data: weekly rebuild $(date -u +%Y-%m-%d)" >> "$LOG" 2>&1
  git push origin "$DATA_BRANCH" >> "$LOG" 2>&1
else
  echo "no data changes to commit" >> "$LOG"
fi

# Healthcheck ping fires only on success — set -e above guarantees we don't get here on failure.
if [[ -n "${HEALTHCHECK_URL:-}" ]]; then
  curl -fsS --retry 3 "$HEALTHCHECK_URL" > /dev/null
fi

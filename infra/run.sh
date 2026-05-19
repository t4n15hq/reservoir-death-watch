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

#!/usr/bin/env bash
# Independent freshness check the cron does NOT block on — run from a
# secondary host (or a separate cron entry) to confirm the data on disk
# matches the freshness budget in `docs/PHASES.md` (≥ 90% of reservoirs
# ≤ 14 days old). Exits non-zero when budget is violated; the healthchecks.io
# alert chain handles escalation.

set -euo pipefail

DATA="${RDW_DATA_FILE:-/opt/reservoirs/repo/dashboard/public/data/reservoirs.json}"
THRESHOLD_PCT="${RDW_FRESH_PCT:-90}"
THRESHOLD_DAYS="${RDW_FRESH_DAYS:-14}"

python3 - "$DATA" "$THRESHOLD_PCT" "$THRESHOLD_DAYS" <<'PY'
import json, sys
from datetime import date, datetime

path, threshold_pct, threshold_days = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with open(path) as handle:
    snapshot = json.load(handle)

reservoirs = snapshot.get("reservoirs", [])
if not reservoirs:
    print("no reservoirs in snapshot", file=sys.stderr)
    sys.exit(2)

today = date.today()
fresh = 0
for r in reservoirs:
    as_of = r.get("current", {}).get("as_of")
    if not as_of:
        continue
    age = (today - date.fromisoformat(as_of)).days
    if age <= threshold_days:
        fresh += 1

pct = round((fresh / len(reservoirs)) * 100, 1)
print(f"freshness: {fresh}/{len(reservoirs)} ({pct}%) <= {threshold_days}d old")
sys.exit(0 if pct >= threshold_pct else 1)
PY

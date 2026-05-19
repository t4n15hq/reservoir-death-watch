# infra/ — Hetzner cron deployment

Documents the one-time setup on Hermes (Tanishq's existing Hetzner VPS) and the
weekly cron that refreshes the dashboard data. Spec lives in `docs/TDD.md` §7.

## One-time setup

Estimated time: 2–3 hours. **Do not break anything Hermes is already running.**

```bash
# 1. As root on Hermes:
useradd --system --create-home --shell /bin/bash reservoirs
mkdir -p /opt/reservoirs/{repo,venv,secrets,logs,data}
chown -R reservoirs:reservoirs /opt/reservoirs
chmod 700 /opt/reservoirs/secrets

# 2. As the reservoirs user:
sudo -iu reservoirs
cd /opt/reservoirs
git clone git@github.com:<owner>/reservoir-death-watch.git repo
python3.12 -m venv venv
source venv/bin/activate
pip install -e ./repo/pipeline

# 3. Drop the GEE service account key in place (mode 600):
cp /path/to/gee_service_account.json /opt/reservoirs/secrets/
chmod 600 /opt/reservoirs/secrets/gee_service_account.json

# 4. Configure environment:
cat > /opt/reservoirs/.env <<'EOF'
GOOGLE_APPLICATION_CREDENTIALS=/opt/reservoirs/secrets/gee_service_account.json
HEALTHCHECK_URL=https://hc-ping.com/<uuid>
RDW_DATA_BRANCH=data-branch
EOF
chmod 600 /opt/reservoirs/.env

# 5. Smoke test:
set -a && source /opt/reservoirs/.env && set +a
bash /opt/reservoirs/repo/infra/run.sh
tail -n 50 /opt/reservoirs/logs/run-*.log

# 6. Install the cron entry (as root):
install -m 644 /opt/reservoirs/repo/infra/cron.tab /etc/cron.d/reservoirs
systemctl reload cron
```

## Files

- `cron.tab` — installs as `/etc/cron.d/reservoirs`. Sundays 03:00 UTC.
- `run.sh` — entry point. Activates the venv, runs the pipeline, commits the
  updated data to `data-branch`, pings healthchecks.io on success.
- `healthcheck.sh` — independent freshness check (≥ 90% of reservoirs ≤ 14 days
  old). Run from a separate schedule; alerts via the existing Hermes Discord
  webhook on the healthchecks.io account.

## Failure handling

`run.sh` is `set -euo pipefail`. Any non-zero exit aborts the script before the
healthcheck ping, so a silent miss in the cron drops the next scheduled
healthchecks.io check and pages within ~24h.

When the on-call sees a miss:

1. SSH to Hermes, `sudo -iu reservoirs`.
2. Open the latest log: `ls -t /opt/reservoirs/logs/ | head -1`.
3. Common causes in order of frequency:
   - CWC PDF format changed → parser raises `CWCFormatError`. See
     `docs/QUESTIONS.md` and bump the alias table or fixture.
   - Earth Engine quota hit → wait until next day, re-run manually.
   - NOAA ONI timeout → snapshot is still valid; `enso.state` will be
     `unavailable` and the dashboard renders that honestly.
   - Git push rejected (force-push to data-branch from elsewhere) → resolve in
     git and re-run.

Never `--no-verify` or `--force` from this box. If you cannot resolve in 4
weeks, the project switches to sunset mode per `AGENT.md`.

## Manual rerun

```bash
sudo -iu reservoirs
set -a && source /opt/reservoirs/.env && set +a
bash /opt/reservoirs/repo/infra/run.sh
```

## Backout

Disable the cron, leave the dashboard's last successful data in place:

```bash
sudo rm /etc/cron.d/reservoirs
sudo systemctl reload cron
```

The static dashboard keeps serving the last good `reservoirs.json`. Add a stale
banner if the gap exceeds 4 weeks per `AGENT.md` §sunset.

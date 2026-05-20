#!/usr/bin/env python
"""Fetch CWC reservoir data from data.gov.in's Open Government Data API.

This replaces the old `fetch_cwc_bulletin.py` PDF scraper. CWC's RSMS
endpoint (rsms.cwc.gov.in/admin/...) returns HTTP 401 unconditionally
as of May 2026 — the `/admin/` path was never a stable public URL.
data.gov.in mirrors the same CWC daily reservoir feed as a versioned
JSON resource, requires a free API key, and is the canonical path for
automated ingest.

Resource: "Daily data of reservoir level of Central Water Commission (CWC)"
Resource ID: 1fc2148c-fc41-46f5-a364-bdc03f77053f

Auth: `--api-key` flag OR `DATA_GOV_IN_API_KEY` env var OR
      `~/.secrets/reservoir-death-watch/data_gov_in.key` file.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from reservoirs.config import CWC_DIR
from reservoirs.cwc_scraper import CWC_STORAGE_REQUIRED_COLUMNS, load_cwc_name_aliases

RESOURCE_ID = "1fc2148c-fc41-46f5-a364-bdc03f77053f"
API_ROOT = "https://api.data.gov.in/resource"
PAGE_SIZE = 1000  # data.gov.in caps individual page size; we paginate.
SECRET_PATH = Path.home() / ".secrets" / "reservoir-death-watch" / "data_gov_in.key"

# Column name candidates — data.gov.in resource schemas drift over time and
# this resource has had at least three different casings historically. We
# look up each logical field across the candidates we've seen.
COLUMN_CANDIDATES = {
    "reservoir_name": ["reservoir_name", "Reservoir_Name", "RESERVOIR", "dam_name", "Dam_Name"],
    "state": ["state", "State", "STATE"],
    "date": ["date", "Date", "level_date", "Level_Date", "as_on", "As_On"],
    "current_storage": [
        "current_live_storage", "Current_Live_Storage",
        "live_storage", "Live_Storage",
        "current_storage", "Current_Storage",
        "storage", "Storage",
    ],
    "capacity_at_frl": [
        "live_capacity_at_frl", "Live_Capacity_At_FRL",
        "live_capacity_frl", "Live_Capacity_FRL",
        "capacity_frl", "Capacity_FRL",
        "full_reservoir_level_capacity", "Full_Reservoir_Level_Capacity",
    ],
    "percent_full": [
        "percentage_storage", "Percentage_Storage",
        "percent_frl", "Percent_FRL",
        "storage_percentage", "Storage_Percentage",
    ],
}


def resolve_api_key(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("DATA_GOV_IN_API_KEY")
    if env:
        return env
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()
    sys.exit(
        "No data.gov.in API key found. Provide one via --api-key, "
        f"$DATA_GOV_IN_API_KEY, or {SECRET_PATH}."
    )


def pick(record: dict, logical: str) -> str | None:
    """Return the first non-empty value across the candidate column names
    for a logical field, or None if nothing matched."""
    for candidate in COLUMN_CANDIDATES[logical]:
        if candidate in record and record[candidate] not in (None, "", "NA"):
            return record[candidate]
    return None


def fetch_page(api_key: str, offset: int, *, timeout: int, verbose: bool) -> dict:
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    resp = requests.get(f"{API_ROOT}/{RESOURCE_ID}", params=params, timeout=timeout)
    if verbose:
        # Don't log the key.
        safe_url = resp.url.replace(api_key, "***")
        print(f"  GET {safe_url} → HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp.json()


def fetch_all(api_key: str, *, timeout: int, max_records: int | None, verbose: bool) -> list[dict]:
    records: list[dict] = []
    offset = 0
    while True:
        page = fetch_page(api_key, offset, timeout=timeout, verbose=verbose)
        chunk = page.get("records") or []
        if not chunk:
            break
        records.extend(chunk)
        total = page.get("total")
        if verbose:
            print(f"  page offset={offset} got {len(chunk)} records (total reported: {total})")
        if total is not None and len(records) >= total:
            break
        if max_records is not None and len(records) >= max_records:
            records = records[:max_records]
            break
        offset += PAGE_SIZE
    return records


def to_bulletin_rows(
    records: list[dict],
    *,
    aliases: dict[str, str],
    since: date | None,
) -> pd.DataFrame:
    """Transform raw API records into the bulletin CSV schema we already
    use. Unknown reservoirs (no alias match) are dropped silently — the
    pipeline only cares about the 25 we're tracking."""
    rows: list[dict] = []
    dropped_no_alias = 0
    dropped_no_date = 0
    dropped_no_numbers = 0
    for r in records:
        name_raw = pick(r, "reservoir_name")
        if not name_raw:
            continue
        reservoir_id = aliases.get(str(name_raw).strip())
        if reservoir_id is None:
            # Also try case-insensitive
            for alias_name, rid in aliases.items():
                if alias_name.lower() == str(name_raw).strip().lower():
                    reservoir_id = rid
                    break
        if reservoir_id is None:
            dropped_no_alias += 1
            continue

        date_str = pick(r, "date")
        if not date_str:
            dropped_no_date += 1
            continue
        try:
            row_date = pd.to_datetime(date_str).date()
        except (ValueError, TypeError):
            dropped_no_date += 1
            continue
        if since is not None and row_date < since:
            continue

        # All numeric fields on data.gov.in CWC daily come as MCM
        # (million cubic metres). We store BCM (billion m³) =  MCM / 1000.
        try:
            cap_mcm = float(pick(r, "capacity_at_frl"))
            stor_mcm = float(pick(r, "current_storage"))
        except (TypeError, ValueError):
            dropped_no_numbers += 1
            continue

        try:
            pct = float(pick(r, "percent_full"))
        except (TypeError, ValueError):
            pct = (stor_mcm / cap_mcm * 100.0) if cap_mcm else None

        rows.append(
            {
                "reservoir_id": reservoir_id,
                "cwc_name": str(name_raw).strip(),
                "date": row_date,
                "live_capacity_at_frl_bcm": cap_mcm / 1000.0,
                "live_storage_bcm": stor_mcm / 1000.0,
                "percent_frl": pct,
                # data.gov.in daily feed doesn't carry "normal storage"
                # (long-period average) — those come from the weekly
                # bulletin PDF only. Leave NaN; downstream code already
                # tolerates this.
                "normal_storage_bcm": None,
                "percent_normal": None,
                "source_url": f"https://api.data.gov.in/resource/{RESOURCE_ID}",
                "source_lines": "data_gov_in",
            }
        )

    if dropped_no_alias or dropped_no_date or dropped_no_numbers:
        print(
            f"  dropped: no_alias={dropped_no_alias} no_date={dropped_no_date} "
            f"no_numbers={dropped_no_numbers}"
        )

    frame = pd.DataFrame(rows, columns=list(CWC_STORAGE_REQUIRED_COLUMNS))
    return frame


def write_per_date_csvs(frame: pd.DataFrame, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for day, group in frame.groupby("date"):
        # `bulletin_YYYY_MM_DD.csv` — same filename pattern the loader watches.
        path = out_dir / f"bulletin_{day:%Y_%m_%d}.csv"
        # Don't clobber a more-complete existing CSV. data.gov.in's daily
        # rows are a subset of what the weekly bulletin carries (no
        # normal_storage column), so a pre-existing CSV from a parsed
        # bulletin PDF is strictly better — keep it.
        if path.exists():
            existing = pd.read_csv(path)
            if len(existing) >= len(group):
                continue
        group.to_csv(path, index=False)
        written.append(path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-key",
        default=None,
        help=(
            "data.gov.in API key. Falls back to $DATA_GOV_IN_API_KEY "
            "then ~/.secrets/.../data_gov_in.key."
        ),
    )
    parser.add_argument("--days-back", type=int, default=14,
                        help="Filter records to the last N days. Default 14.")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Stop after this many raw records (debug helper).")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--out-dir", type=Path, default=CWC_DIR,
                        help=f"Where to write bulletin_YYYY_MM_DD.csv files. Default: {CWC_DIR}")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = resolve_api_key(args.api_key)
    aliases = load_cwc_name_aliases()
    since = date.today() - timedelta(days=args.days_back)

    print(f"Fetching CWC data from data.gov.in (resource {RESOURCE_ID})")
    print(f"  Window: since {since:%Y-%m-%d} ({args.days_back} days back)")
    print(f"  Aliases loaded: {len(aliases)} name → reservoir_id mappings")

    try:
        records = fetch_all(
            api_key,
            timeout=args.timeout,
            max_records=args.max_records,
            verbose=args.verbose,
        )
    except requests.HTTPError as exc:
        print(f"\nAPI request failed: {exc}", file=sys.stderr)
        if exc.response is not None and exc.response.status_code in (401, 403):
            print(
                "  Check your API key — register at https://www.data.gov.in/ to get one.",
                file=sys.stderr,
            )
        return 2
    except requests.RequestException as exc:
        print(f"\nAPI request failed: {exc}", file=sys.stderr)
        return 2

    print(f"\nFetched {len(records)} raw records")
    frame = to_bulletin_rows(records, aliases=aliases, since=since)
    n_reservoirs = frame["reservoir_id"].nunique() if not frame.empty else 0
    print(f"Matched {len(frame)} records across {n_reservoirs} reservoirs")

    if frame.empty:
        print("No matching reservoir rows. Either:")
        print("  - This window had no observations for our 25 tracked reservoirs")
        print("  - The API column names have changed — check the raw record dump with --verbose")
        return 1

    written = write_per_date_csvs(frame, args.out_dir)
    if written:
        print(f"\nWrote {len(written)} new bulletin CSV(s):")
        for path in written:
            print(f"  {path}")
    else:
        print("\nNo new CSVs written (existing files were more complete or up to date).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

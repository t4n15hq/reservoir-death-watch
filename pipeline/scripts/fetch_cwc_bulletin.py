#!/usr/bin/env python
"""Automated CWC weekly bulletin fetcher.

Tries multiple known URL patterns with realistic browser headers, validates
the response is an actual PDF, and saves to `pipeline/data/cwc/raw_pdfs/`.
After a successful download, optionally chains into
`parse_local_cwc_pdfs.py` so the new bulletin lands in the right CSV form
and the next pipeline run picks it up automatically.

CWC publishes weekly on Thursdays. The script auto-derives candidate URLs
for the last `--weeks-back` Thursdays (default 4) so it can backfill any
missed week.

Known constraints — read these before deploying:

- `rsms.cwc.gov.in` returns HTTP 401 from at least two networks (this
  agent seat + assorted US/EU egress). The block appears to be IP-based,
  not browser-detection-based — even with realistic User-Agent and
  Referer headers the response is the same 401 JSON blob. Run from an
  Indian-IP-egressing host (your laptop on a domestic connection, or a
  VPS with Indian transit) for the actual fetch to succeed.

- The script does NOT bypass auth. If the seat doesn't have access, every
  candidate URL returns 401 / timeout and the script exits non-zero. The
  cron / wrapper can hook into that — `infra/run.sh` can ping a Discord
  webhook for manual follow-up.

- On success the new PDF is dropped in `pipeline/data/cwc/raw_pdfs/` and
  `scripts/parse_local_cwc_pdfs.py` converts it to the `bulletin_*.csv`
  format the directory loader watches. After that, the next
  `python -m reservoirs.pipeline` (or `scripts/backfill_history.py <ids>`)
  picks up CWC calibration automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

from reservoirs.config import CWC_DIR

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# CWC's RSMS bulletin URL pattern is `bulletin-DD-MM-YYYY-NN.pdf` where NN
# is an internal index that increments roughly monotonically. We don't know
# NN ahead of time so we try a window of likely values.
RSMS_TEMPLATE = "https://rsms.cwc.gov.in/admin/storage/bulletins/bulletin-{date}-{idx}.pdf"
NN_SEARCH_WIDTH = 10  # how many NN values to probe around the last-known


def thursdays_in_window(weeks_back: int) -> list[date]:
    """Return the last N Thursdays (most recent first)."""

    today = date.today()
    # Python's weekday(): Monday=0 ... Thursday=3
    days_since_thu = (today.weekday() - 3) % 7
    most_recent_thu = today - timedelta(days=days_since_thu)
    return [most_recent_thu - timedelta(weeks=i) for i in range(weeks_back)]


def candidate_urls_for(bulletin_date: date, hint_index: int | None) -> list[str]:
    """All URLs we're willing to try for one bulletin date."""

    ymd = bulletin_date.strftime("%d-%m-%Y")
    urls: list[str] = []
    if hint_index is not None:
        for delta in range(-NN_SEARCH_WIDTH, NN_SEARCH_WIDTH + 1):
            idx = hint_index + delta
            if idx > 0:
                urls.append(RSMS_TEMPLATE.format(date=ymd, idx=idx))
    else:
        # Without a hint we try a coarse spread of likely indices.
        for idx in (91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 90, 80, 70, 60):
            urls.append(RSMS_TEMPLATE.format(date=ymd, idx=idx))
    return urls


def looks_like_pdf(content: bytes) -> bool:
    """Magic-byte check: real PDFs start with `%PDF-`. The 401 JSON blob
    that CWC returns instead does not."""

    return content[:5] == b"%PDF-"


def try_fetch(
    url: str,
    *,
    session: requests.Session,
    timeout: int,
) -> bytes | None:
    """Return PDF bytes if successful, None otherwise."""

    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"  request error: {exc}", file=sys.stderr)
        return None
    if resp.status_code != 200:
        return None
    if not looks_like_pdf(resp.content):
        return None
    return resp.content


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9,en-US;q=0.8",
            "Referer": "https://cwc.gov.in/",
        }
    )
    return session


def save_pdf(content: bytes, bulletin_date: date, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"bulletin_{bulletin_date.strftime('%Y_%m_%d')}.pdf"
    path = out_dir / name
    # If we already have this exact bulletin (byte-for-byte), don't rewrite.
    if path.exists():
        existing_hash = hashlib.sha256(path.read_bytes()).digest()
        if existing_hash == hashlib.sha256(content).digest():
            print(f"  already have {name} (identical content)")
            return path
    path.write_bytes(content)
    return path


def run_parser(pdf_path: Path) -> int:
    """Invoke the local PDF parser to produce the bulletin CSV."""

    import subprocess  # noqa: PLC0415

    cmd = [
        sys.executable,
        str(Path(__file__).parent / "parse_local_cwc_pdfs.py"),
        "--pdf-dir",
        str(pdf_path.parent),
        "--overwrite",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"parser failed: {result.stderr}", file=sys.stderr)
    else:
        print(result.stdout, end="")
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weeks-back", type=int, default=4)
    parser.add_argument(
        "--hint-index",
        type=int,
        default=None,
        help=(
            "Best guess at the RSMS bulletin index "
            "(NN in bulletin-DD-MM-YYYY-NN.pdf). If omitted, tries a spread."
        ),
    )
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--out-dir", type=Path, default=CWC_DIR / "raw_pdfs")
    parser.add_argument("--no-parse", action="store_true",
                        help="Skip auto-parsing the downloaded PDFs to CSV.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = build_session(args.user_agent)
    targets = thursdays_in_window(args.weeks_back)

    print(f"Trying bulletins for last {args.weeks_back} Thursdays:")
    for d in targets:
        print(f"  {d:%Y-%m-%d}")

    downloaded: list[Path] = []
    for bulletin_date in targets:
        print(f"\n→ {bulletin_date:%Y-%m-%d}")
        urls = candidate_urls_for(bulletin_date, args.hint_index)
        for url in urls:
            content = try_fetch(url, session=session, timeout=args.timeout)
            if content is not None:
                path = save_pdf(content, bulletin_date, args.out_dir)
                print(f"  ✓ {url} → {path.name} ({len(content)} bytes)")
                downloaded.append(path)
                break
        else:
            print(f"  ✗ no candidate URL worked for {bulletin_date:%Y-%m-%d}")

    if not downloaded:
        print("\nNo bulletins fetched. Likely causes:")
        print("  - This network can't reach rsms.cwc.gov.in (auth-walled / geo-blocked).")
        print("    Try running from a host with Indian-IP transit.")
        print("  - The bulletin index pattern has changed. Inspect manually.")
        print("Workaround: download the PDF in a browser, drop it into")
        print(f"  {args.out_dir}")
        print("then run  python scripts/parse_local_cwc_pdfs.py")
        return 1

    print(f"\n{len(downloaded)} bulletin(s) downloaded.")
    if args.no_parse:
        return 0
    return run_parser(downloaded[0])


if __name__ == "__main__":
    raise SystemExit(main())

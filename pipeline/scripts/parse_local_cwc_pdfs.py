#!/usr/bin/env python
"""Convert any local CWC bulletin PDF into a bulletin_*.csv the pipeline reads.

Workflow:
  1. Download the PDF from CWC (any way you can — browser, VPN, manual fetch).
  2. Drop it into pipeline/data/cwc/raw_pdfs/ (any filename).
  3. Run this script. Each PDF turns into a bulletin_YYYY_MM_DD.csv next to it,
     matching the schema enforced by reservoirs.cwc_scraper.

Subsequent `python scripts/backfill_history.py <reservoir_ids>` runs (or
the next full pipeline run) pick up the new CSVs automatically — no edits.

The parser uses parse_bulletin_pdf which already handles both the
weekly-report tabular format and the older free-text format with the same
alias map. Reservoirs in the alias map but missing from the PDF are
skipped silently; reservoirs in the PDF but not in the alias map are
ignored (extend pipeline/data/cwc/cwc_name_aliases.csv if you add them).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reservoirs.config import CWC_DIR
from reservoirs.cwc_scraper import (
    CWCFormatError,
    load_cwc_name_aliases,
    parse_bulletin_pdf,
)

DEFAULT_PDF_DIR = CWC_DIR / "raw_pdfs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing CWC bulletin PDFs (default: pipeline/data/cwc/raw_pdfs/).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=CWC_DIR,
        help="Where to write bulletin_*.csv files (default: pipeline/data/cwc/).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing CSVs of the same name.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_dir: Path = args.pdf_dir
    if not pdf_dir.exists():
        print(f"PDF dir missing: {pdf_dir}", file=sys.stderr)
        print(f"Create it with: mkdir -p {pdf_dir}", file=sys.stderr)
        return 1

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}", file=sys.stderr)
        return 1

    aliases = load_cwc_name_aliases()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    parsed = 0
    failed: list[str] = []
    for pdf_path in pdfs:
        try:
            frame = parse_bulletin_pdf(
                pdf_path,
                reservoir_aliases=aliases,
                source_url=f"local://{pdf_path.name}",
            )
        except CWCFormatError as exc:
            print(f"FAIL {pdf_path.name}: {exc}", file=sys.stderr)
            failed.append(pdf_path.name)
            continue

        if frame.empty:
            print(f"SKIP {pdf_path.name}: no reservoir rows matched", file=sys.stderr)
            failed.append(pdf_path.name)
            continue

        bulletin_date = frame["date"].iloc[0]
        if "source_lines" not in frame.columns:
            frame["source_lines"] = ""
        out_name = f"bulletin_{bulletin_date:%Y_%m_%d}.csv"
        out_path = args.out_dir / out_name
        if out_path.exists() and not args.overwrite:
            print(f"SKIP {out_name}: exists (use --overwrite to replace)")
            continue
        frame.to_csv(out_path, index=False)
        print(f"OK   {pdf_path.name} -> {out_name} ({len(frame)} reservoirs)")
        parsed += 1

    print(f"\nparsed {parsed} PDFs; {len(failed)} failed: {failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

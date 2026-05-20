#!/usr/bin/env python
"""DEPRECATED. Use `fetch_data_gov_in.py` instead.

This script targeted `rsms.cwc.gov.in/admin/storage/bulletins/...` —
that URL returns HTTP 401 unconditionally as of May 2026 from every
network we've tested (laptop, Azure GitHub Actions runners, Anthropic
WebFetch). The `/admin/` segment was never a stable public path; CWC
appears to have either always required auth on it or tightened the WAF
recently.

The canonical machine-readable source for CWC daily reservoir data is
data.gov.in's open data API. Use the replacement script.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(__doc__, file=sys.stderr)
    print(
        "\n  Replacement: python scripts/fetch_data_gov_in.py --verbose\n"
        "  See docs/RUNBOOK.md for the API key setup.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

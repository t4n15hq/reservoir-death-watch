"""Tests for the offline parts of `scripts/fetch_cwc_bulletin.py`.

We don't try to mock the actual HTTP calls — the value of the script is
in (a) URL pattern generation, (b) PDF magic-byte detection, (c) the
Thursday-window date logic. Those are all pure functions.
"""

from __future__ import annotations

# Importable as a module via PYTHONPATH=scripts (pytest.ini_options.pythonpath
# in pyproject.toml is set to ["src"], so we need an explicit path adjustment).
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch_cwc_bulletin import (  # noqa: E402
    NN_SEARCH_WIDTH,
    RSMS_TEMPLATE,
    candidate_urls_for,
    looks_like_pdf,
    thursdays_in_window,
)


def test_looks_like_pdf_accepts_pdf_magic_bytes() -> None:
    assert looks_like_pdf(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n...") is True


def test_looks_like_pdf_rejects_html_error_pages() -> None:
    err_blob = b'{"status":"401","message":"Unauthorized"}'
    assert looks_like_pdf(err_blob) is False
    assert looks_like_pdf(b"<html><body>Not Found</body></html>") is False


def test_thursdays_in_window_returns_thursdays_most_recent_first() -> None:
    days = thursdays_in_window(4)
    assert len(days) == 4
    for d in days:
        assert d.weekday() == 3, f"{d} is not a Thursday"
    # Strictly descending — most recent first.
    for i in range(len(days) - 1):
        assert days[i] > days[i + 1]
    # Span should be exactly 3 weeks (4 Thursdays = 3 gaps of 7 days each).
    assert (days[0] - days[-1]).days == 21


def test_candidate_urls_for_uses_hint_index_window() -> None:
    sample_date = date(2026, 4, 9)  # Thursday — matches our existing bulletin
    urls = candidate_urls_for(sample_date, hint_index=91)

    expected_count = 2 * NN_SEARCH_WIDTH + 1
    assert len(urls) == expected_count
    # All should use the same date format CWC uses.
    for url in urls:
        assert "09-04-2026" in url
        assert url.startswith(RSMS_TEMPLATE.split("{")[0])


def test_candidate_urls_for_no_hint_uses_default_spread() -> None:
    sample_date = date(2026, 4, 9)
    urls = candidate_urls_for(sample_date, hint_index=None)
    # Default spread should at least include the known-good index 91.
    assert any("-91.pdf" in u for u in urls)
    assert all("09-04-2026" in u for u in urls)


def test_candidate_urls_skip_non_positive_indices() -> None:
    sample_date = date(2026, 4, 9)
    # hint_index=2 would produce some negative indices in the -NN_SEARCH_WIDTH
    # neighbourhood; those should be filtered out.
    urls = candidate_urls_for(sample_date, hint_index=2)
    indices = [int(u.rsplit("-", 1)[1].split(".")[0]) for u in urls]
    assert all(i > 0 for i in indices)


@pytest.mark.parametrize("weeks_back", [1, 2, 4, 8])
def test_thursdays_window_arbitrary_lengths(weeks_back: int) -> None:
    days = thursdays_in_window(weeks_back)
    assert len(days) == weeks_back
    assert all(d.weekday() == 3 for d in days)

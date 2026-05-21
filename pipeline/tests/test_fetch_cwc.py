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
    date_from_text,
    dated_pdf_urls_from_html,
    estimated_indices_for,
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


def test_candidate_urls_for_no_hint_uses_known_index_anchors() -> None:
    urls = candidate_urls_for(date(2026, 2, 26), hint_index=None)

    assert any("-84.pdf" in u for u in urls)
    assert all("26-02-2026" in u for u in urls)


def test_estimated_indices_project_future_weeks_from_nearest_anchor() -> None:
    # 2026-05-14 is five Thursdays after the known 2026-04-09 index 91.
    assert 96 in estimated_indices_for(date(2026, 5, 14))


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


def test_date_from_text_extracts_cwc_publication_date() -> None:
    assert date_from_text("LIVE STORAGE STATUS AS ON 14.05.2026") == date(2026, 5, 14)
    assert date_from_text("bulletin-14-05-2026-96.pdf") is None


def test_dated_pdf_urls_from_html_extracts_listing_downloads() -> None:
    html = """
    <tr>
      <td>LIVE STORAGE STATUS OF 166 RESERVOIRS IN THE COUNTRY AS ON 14.05.2026</td>
      <td><a href="/sites/default/files/bulletin-14-05-2026.pdf">Download</a></td>
    </tr>
    <tr>
      <td>Not a PDF</td>
      <td><a href="/about">About</a></td>
    </tr>
    """

    links = dated_pdf_urls_from_html(html, "https://www.cwc.gov.in/reservoir-level-storage-bulletin")

    assert links == [
        (
            date(2026, 5, 14),
            "https://www.cwc.gov.in/sites/default/files/bulletin-14-05-2026.pdf",
        )
    ]

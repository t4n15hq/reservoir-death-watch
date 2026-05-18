"""CWC reservoir bulletin parsing.

The live PDF format is allowed to be fragile, but failure must be obvious.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd


class CWCFormatError(ValueError):
    """Raised when a CWC bulletin cannot be parsed into the expected schema."""


@dataclass(frozen=True)
class CWCStorageRow:
    reservoir_id: str
    cwc_name: str
    date: date
    live_storage_bcm: float
    percent_frl: float
    percent_normal: float | None


_DATE_PATTERNS = (
    re.compile(r"as\s+on\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.IGNORECASE),
    re.compile(r"as\s+on\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE),
)


def parse_bulletin_text(
    text: str,
    *,
    reservoir_aliases: dict[str, str],
    bulletin_date: date | None = None,
) -> pd.DataFrame:
    """Parse extracted CWC bulletin text into a storage DataFrame."""

    parsed_date = bulletin_date or _parse_bulletin_date(text)
    aliases = [
        (name, _normalize_name(name), reservoir_id)
        for name, reservoir_id in reservoir_aliases.items()
    ]
    rows: list[CWCStorageRow] = []

    for line in text.splitlines():
        normalized_line = " ".join(line.split())
        if not normalized_line:
            continue
        for cwc_name, cwc_name_normalized, reservoir_id in aliases:
            if cwc_name_normalized not in _normalize_name(normalized_line):
                continue
            numbers = _numbers_in_line(_suffix_after_name(normalized_line, cwc_name))
            if len(numbers) < 2:
                raise CWCFormatError(f"matched {reservoir_id} but found too few numeric columns")
            rows.append(
                CWCStorageRow(
                    reservoir_id=reservoir_id,
                    cwc_name=cwc_name,
                    date=parsed_date,
                    live_storage_bcm=numbers[0],
                    percent_frl=numbers[1],
                    percent_normal=numbers[2] if len(numbers) >= 3 else None,
                )
            )
            break

    if not rows:
        raise CWCFormatError("no reservoir rows matched the alias map")

    frame = pd.DataFrame([row.__dict__ for row in rows])
    required = {"reservoir_id", "date", "live_storage_bcm", "percent_frl", "percent_normal"}
    missing = required.difference(frame.columns)
    if missing:
        raise CWCFormatError(f"parsed frame missing required columns: {sorted(missing)}")
    return frame


def extract_pdf_text(path: Path) -> str:
    """Extract text from a CWC PDF using pypdf."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        msg = "pypdf is required to parse CWC bulletin PDFs"
        raise CWCFormatError(msg) from exc

    reader = PdfReader(str(path))
    page_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(page_text).strip()
    if not text:
        raise CWCFormatError(f"no extractable text found in {path}")
    return text


def parse_bulletin_pdf(
    path: Path,
    *,
    reservoir_aliases: dict[str, str],
    bulletin_date: date | None = None,
) -> pd.DataFrame:
    """Extract and parse a local CWC bulletin PDF."""

    return parse_bulletin_text(
        extract_pdf_text(path),
        reservoir_aliases=reservoir_aliases,
        bulletin_date=bulletin_date,
    )


def _parse_bulletin_date(text: str) -> date:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        first, second, year = match.groups()
        if second.isdigit():
            return date(int(year), int(second), int(first))
        return datetime.strptime(f"{first} {second} {year}", "%d %B %Y").date()
    raise CWCFormatError("could not find bulletin date in text")


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _numbers_in_line(line: str) -> list[float]:
    return [float(match) for match in re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", line)]


def _suffix_after_name(line: str, cwc_name: str) -> str:
    words = [re.escape(word) for word in cwc_name.split()]
    pattern = re.compile(r"\b" + r"\s+".join(words) + r"\b(.*)$", re.IGNORECASE)
    match = pattern.search(line)
    return match.group(1) if match else line

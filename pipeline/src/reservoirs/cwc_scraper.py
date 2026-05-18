"""CWC reservoir bulletin parsing.

The live PDF format is allowed to be fragile, but failure must be obvious.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from reservoirs.config import CWC_NAME_ALIASES_CSV, CWC_PHASE0_STORAGE_CSV, RESERVOIRS_CSV


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
    live_capacity_at_frl_bcm: float | None = None
    normal_storage_bcm: float | None = None
    source_url: str | None = None
    source_lines: str | None = None


_DATE_PATTERNS = (
    re.compile(r"as\s+on\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.IGNORECASE),
    re.compile(r"as\s+on\s+(\d{1,2})\.(\d{1,2})\.(\d{4})", re.IGNORECASE),
    re.compile(r"as\s+on\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE),
)
_DATE_TOKEN = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}")


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


def parse_weekly_report_text(
    text: str,
    *,
    reservoir_aliases: dict[str, str],
    source_url: str | None = None,
) -> pd.DataFrame:
    """Parse the detailed CWC weekly report table from extracted PDF text."""

    normalized_text = " ".join(text.split())
    aliases = [
        (name, _normalize_name(name), reservoir_id)
        for name, reservoir_id in reservoir_aliases.items()
    ]
    rows: list[CWCStorageRow] = []
    seen: set[str] = set()

    for cwc_name, cwc_name_normalized, reservoir_id in aliases:
        if reservoir_id in seen:
            continue
        match = _find_normalized_alias(normalized_text, cwc_name_normalized)
        if not match:
            continue
        row = _parse_weekly_report_row(
            normalized_text[match.end() : match.end() + 700],
            reservoir_id=reservoir_id,
            cwc_name=cwc_name,
            source_url=source_url,
        )
        rows.append(row)
        seen.add(reservoir_id)

    if not rows:
        raise CWCFormatError("no CWC weekly report rows matched the alias map")
    return pd.DataFrame([row.__dict__ for row in rows])


def load_cwc_name_aliases(
    *,
    aliases_csv: Path = CWC_NAME_ALIASES_CSV,
    reservoirs_csv: Path = RESERVOIRS_CSV,
) -> dict[str, str]:
    """Load CWC-name-to-reservoir-id aliases from metadata plus overrides."""

    aliases: dict[str, str] = {}
    if reservoirs_csv.exists():
        metadata = pd.read_csv(reservoirs_csv).fillna("")
        for row in metadata.itertuples(index=False):
            aliases[str(row.cwc_name)] = str(row.id)
            aliases[str(row.name)] = str(row.id)

    if aliases_csv.exists():
        alias_frame = pd.read_csv(aliases_csv)
        for row in alias_frame.itertuples(index=False):
            aliases[str(row.cwc_name)] = str(row.reservoir_id)
    return aliases


def load_cwc_storage_csv(path: Path = CWC_PHASE0_STORAGE_CSV) -> pd.DataFrame:
    """Load checked-in CWC storage rows with strict column validation."""

    frame = pd.read_csv(path)
    required = {
        "reservoir_id",
        "cwc_name",
        "date",
        "live_capacity_at_frl_bcm",
        "live_storage_bcm",
        "percent_frl",
        "normal_storage_bcm",
        "percent_normal",
        "source_url",
        "source_lines",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise CWCFormatError(f"CWC storage CSV missing columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def parse_bulletin_pdf(
    path: Path,
    *,
    reservoir_aliases: dict[str, str],
    bulletin_date: date | None = None,
    source_url: str | None = None,
) -> pd.DataFrame:
    """Extract and parse a local CWC bulletin PDF."""

    text = extract_pdf_text(path)
    try:
        return parse_weekly_report_text(
            text,
            reservoir_aliases=reservoir_aliases,
            source_url=source_url,
        )
    except CWCFormatError:
        return parse_bulletin_text(
            text,
            reservoir_aliases=reservoir_aliases,
            bulletin_date=bulletin_date,
        )


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


def _find_normalized_alias(text: str, normalized_alias: str) -> re.Match[str] | None:
    words = [re.escape(word) for word in normalized_alias.split()]
    pattern = re.compile(r"\b" + r"\s+".join(words) + r"\b", re.IGNORECASE)
    return pattern.search(text)


def _parse_weekly_report_row(
    text_after_name: str,
    *,
    reservoir_id: str,
    cwc_name: str,
    source_url: str | None,
) -> CWCStorageRow:
    date_match = _DATE_TOKEN.search(text_after_name)
    if not date_match:
        raise CWCFormatError(f"matched {reservoir_id} but found no row date")

    row_date = _parse_date_token(date_match.group(0))
    before_numbers = _numbers_in_line(text_after_name[: date_match.start()])
    after_numbers = _numbers_in_line(text_after_name[date_match.end() :])

    if len(before_numbers) < 2 or len(after_numbers) < 3:
        raise CWCFormatError(f"matched {reservoir_id} but row has too few numeric columns")

    if after_numbers[0] <= 100 and before_numbers[-1] <= before_numbers[-2]:
        live_capacity = before_numbers[-2]
        live_storage = before_numbers[-1]
        percent_frl = after_numbers[0]
        percent_normal = after_numbers[2] if len(after_numbers) >= 3 else None
        normal_storage = None
    else:
        live_capacity = before_numbers[-1]
        live_storage = after_numbers[1]
        percent_frl = after_numbers[2]
        normal_storage = after_numbers[6] if len(after_numbers) >= 7 else None
        percent_normal = after_numbers[7] if len(after_numbers) >= 8 else None

    return CWCStorageRow(
        reservoir_id=reservoir_id,
        cwc_name=cwc_name,
        date=row_date,
        live_storage_bcm=live_storage,
        percent_frl=percent_frl,
        percent_normal=percent_normal,
        live_capacity_at_frl_bcm=live_capacity,
        normal_storage_bcm=normal_storage,
        source_url=source_url,
    )


def _parse_date_token(token: str) -> date:
    separator = "." if "." in token else "/" if "/" in token else "-"
    day, month, year = token.split(separator)
    return date(int(year), int(month), int(day))

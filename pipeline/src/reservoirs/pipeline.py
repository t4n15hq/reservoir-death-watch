"""Top-level pipeline orchestrator."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from reservoirs.aois import load_aois
from reservoirs.schemas import DashboardSnapshot


def run_pipeline(
    *,
    as_of: date | None = None,
    reservoirs: Iterable[str] | None = None,
) -> DashboardSnapshot:
    """Run the full pipeline.

    The credential-free scaffold loads metadata first, then stops before any
    external data access. This keeps the failure mode honest until AOIs and GEE
    credentials are available.
    """

    _ = as_of
    load_aois(reservoirs)
    raise NotImplementedError("full pipeline requires AOIs plus Earth Engine/CWC integrations")


if __name__ == "__main__":
    run_pipeline()


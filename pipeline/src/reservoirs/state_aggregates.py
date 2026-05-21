"""Aggregate per-reservoir results into state-level rollups.

Matches the contract in `docs/SCHEMAS.md` §`state_aggregates.json`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from reservoirs.schemas import ReservoirResult, Tier


def build_state_aggregates(
    reservoirs: list[ReservoirResult],
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    """Group reservoirs by state and roll up capacity, storage, and tier counts."""

    buckets: dict[str, list[ReservoirResult]] = defaultdict(list)
    for reservoir in reservoirs:
        buckets[reservoir.state].append(reservoir)

    states = []
    for state in sorted(buckets):
        members = buckets[state]
        observed = [
            member
            for member in members
            if "awaiting_first_observation" not in (member.flags or [])
        ]
        total_capacity = sum(m.full_pool_capacity_bcm or 0 for m in observed)
        current_storage = sum(m.current.estimated_storage_bcm for m in observed)
        percent_full = round((current_storage / total_capacity) * 100, 1) if total_capacity else 0.0
        states.append(
            {
                "state": state,
                "reservoir_count": len(members),
                "observed_count": len(observed),
                "total_capacity_bcm": round(total_capacity, 3),
                "current_storage_bcm": round(current_storage, 3),
                "percent_full": percent_full,
                "tier_counts": _tier_counts(observed),
                "reservoir_ids": sorted(m.id for m in members),
            }
        )
    return {
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "states": states,
    }


def _tier_counts(members: list[ReservoirResult]) -> dict[Tier, int]:
    counts: dict[str, int] = {"critical": 0, "warning": 0, "watch": 0, "stable": 0}
    for member in members:
        counts[member.tier] += 1
    return counts  # type: ignore[return-value]

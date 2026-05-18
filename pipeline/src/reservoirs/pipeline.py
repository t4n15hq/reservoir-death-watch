"""Top-level pipeline orchestrator."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from reservoirs.aois import load_aois
from reservoirs.area_volume import fit_power_law_curve
from reservoirs.config import DASHBOARD_DATA_DIR, MODEL_VERSION
from reservoirs.cwc_scraper import load_cwc_storage_csv
from reservoirs.export import write_json_atomic
from reservoirs.healthcheck import ping_healthcheck
from reservoirs.jrc import extract_jrc_history
from reservoirs.model import compute_tier, fit_depletion, project_to_dead_storage
from reservoirs.oni import compute_el_nino_delta, fetch_oni
from reservoirs.schemas import (
    AreaObservation,
    DashboardSnapshot,
    DataSourcesUsed,
    EnsoSummary,
    NationalAggregate,
    Projection,
    ReservoirAOI,
    ReservoirCurrent,
    ReservoirResult,
)
from reservoirs.sentinel import RecentArea, extract_recent_area, extract_s2_area_series

PHASE0_RESERVOIRS = ("krs", "mettur", "indira_sagar")


def run_pipeline(
    *,
    as_of: date | None = None,
    reservoirs: Iterable[str] | None = None,
    output_dir: Path = DASHBOARD_DATA_DIR,
    export: bool = True,
) -> DashboardSnapshot:
    """Run the Phase 0 pipeline for the requested reservoirs."""

    run_as_of = as_of or date.today()
    reservoir_ids = tuple(reservoirs or PHASE0_RESERVOIRS)
    aois = load_aois(reservoir_ids)

    results: list[ReservoirResult] = []
    csv_frames: dict[str, pd.DataFrame] = {}
    cwc_storage = _load_cwc_storage_or_empty()

    for aoi in aois:
        print(f"{aoi.id}: extracting JRC history")
        jrc_history = extract_jrc_history(aoi, end=run_as_of)
        print(f"{aoi.id}: extracting recent Sentinel-2 series")
        s2_series = extract_s2_area_series(aoi, as_of=run_as_of)
        print(f"{aoi.id}: extracting current Sentinel observation")
        current = extract_recent_area(aoi, as_of=run_as_of)

        result, history_frame = build_reservoir_result(
            aoi,
            jrc_history=jrc_history,
            s2_series=s2_series,
            current=current,
            as_of=run_as_of,
            cwc_storage=cwc_storage,
        )
        results.append(result)
        csv_frames[aoi.id] = history_frame

    snapshot = DashboardSnapshot(
        generated_at=datetime.now(UTC),
        model_version=MODEL_VERSION,
        data_sources_used=DataSourcesUsed(
            jrc_through=_latest_jrc_month(results),
            s2_latest=max(result.current.as_of for result in results),
            cwc_bulletin=_latest_cwc_date(cwc_storage),
            oni_month=None,
        ),
        enso=_fetch_enso_summary(),
        national_aggregate=aggregate_national(results),
        reservoirs=results,
    )

    if export:
        export_dashboard_data(snapshot, csv_frames, output_dir)
    ping_healthcheck()

    return snapshot


def build_reservoir_result(
    aoi: ReservoirAOI,
    *,
    jrc_history: pd.DataFrame,
    s2_series: pd.DataFrame,
    current: RecentArea,
    as_of: date,
    cwc_storage: pd.DataFrame | None = None,
) -> tuple[ReservoirResult, pd.DataFrame]:
    full_pool_area_km2 = _full_pool_area_km2(aoi, jrc_history, current)
    cwc_row = _cwc_row_for_reservoir(cwc_storage, aoi.id)
    full_capacity = _full_capacity_bcm(aoi, cwc_row)
    cwc_reported = _optional_cwc_value(cwc_row, "live_storage_bcm")
    cwc_as_of = _optional_cwc_date(cwc_row)
    curve, curve_flags = _calibrate_curve(
        aoi,
        full_pool_area_km2=full_pool_area_km2,
        full_capacity_bcm=full_capacity,
        history=_merge_history(jrc_history, s2_series, current),
        cwc_row=cwc_row,
    )
    estimated_storage = _storage_from_area(
        current.area_km2,
        full_pool_area_km2=full_pool_area_km2,
        capacity_bcm=full_capacity,
        curve=curve,
    )
    percent_full = _storage_percent_full(estimated_storage, full_capacity)
    flags = curve_flags
    if aoi.aoi_review_status:
        flags.append(aoi.aoi_review_status)

    history = _merge_history(jrc_history, s2_series, current)
    observations = [
        AreaObservation(
            date=row.date,
            area_km2=row.area_km2,
            data_source=row.data_source,
            cloud_coverage_percent=getattr(row, "cloud_coverage_percent", None),
        )
        for row in history.itertuples(index=False)
    ]
    fit_observations = [observation for observation in observations if observation.area_km2 > 0]
    fit = fit_depletion(aoi.id, fit_observations, as_of=as_of)

    if fit:
        dead_area = _dead_storage_area_proxy(aoi, full_pool_area_km2)
        el_nino_delta = compute_el_nino_delta(jrc_history)
        neutral = project_to_dead_storage(
            fit,
            current_area_km2=current.area_km2,
            dead_storage_area_km2=dead_area,
            as_of=current.as_of,
            scenario="neutral_monsoon",
            sentinel_1=current.data_source == "sentinel_1",
        )
        if el_nino_delta is not None:
            el_nino = project_to_dead_storage(
                fit,
                current_area_km2=current.area_km2,
                dead_storage_area_km2=dead_area,
                as_of=current.as_of,
                scenario="el_nino_monsoon",
                el_nino_area_delta_km2=min(0.0, el_nino_delta),
                sentinel_1=current.data_source == "sentinel_1",
            )
            flags.append("el_nino_delta_static_years")
        else:
            el_nino = Projection(
                scenario="el_nino_monsoon",
                days_to_dead_storage=None,
                dead_storage_date=None,
                confidence_interval_days=None,
            )
            flags.append("el_nino_delta_not_computed")
        flags.append("dead_storage_area_proxy")
    else:
        neutral = Projection(
            scenario="neutral_monsoon",
            days_to_dead_storage=None,
            dead_storage_date=None,
            confidence_interval_days=None,
        )
        el_nino = Projection(
            scenario="el_nino_monsoon",
            days_to_dead_storage=None,
            dead_storage_date=None,
            confidence_interval_days=None,
        )
        flags.append("depletion_fit_unavailable")

    five_year_average = _five_year_average_percent(jrc_history, full_pool_area_km2, as_of.month)
    tier = compute_tier(
        neutral_projection=neutral,
        el_nino_projection=el_nino,
        current_percent_full=percent_full,
        five_year_average_for_month=five_year_average,
    )

    history_for_csv = history.copy()
    history_for_csv["estimated_storage_bcm"] = history_for_csv["area_km2"].map(
        lambda area: _storage_from_area(
            area,
            full_pool_area_km2=full_pool_area_km2,
            capacity_bcm=full_capacity,
            curve=curve,
        )
    )
    history_for_csv["cwc_storage_bcm"] = None
    if cwc_row is not None:
        cwc_date = _optional_cwc_date(cwc_row)
        history_for_csv.loc[history_for_csv["date"] == cwc_date, "cwc_storage_bcm"] = (
            _optional_cwc_value(cwc_row, "live_storage_bcm")
        )
    history_for_csv["percent_full"] = history_for_csv["area_km2"].map(
        lambda area: _storage_percent_full(
            _storage_from_area(
                area,
                full_pool_area_km2=full_pool_area_km2,
                capacity_bcm=full_capacity,
                curve=curve,
            ),
            full_capacity,
        )
    )

    result = ReservoirResult(
        id=aoi.id,
        name=aoi.name,
        river=aoi.river,
        state=aoi.state,
        city_served=aoi.city_served,
        population_served=aoi.population_served,
        full_pool_area_km2=round(full_pool_area_km2, 3),
        full_pool_capacity_bcm=full_capacity,
        dead_storage_capacity_bcm=aoi.dead_storage_capacity_bcm,
        lat=aoi.lat,
        lon=aoi.lon,
        current=ReservoirCurrent(
            as_of=current.as_of,
            area_km2=round(current.area_km2, 3),
            estimated_storage_bcm=round(estimated_storage, 3),
            cwc_reported_bcm=round(cwc_reported, 3) if cwc_reported is not None else None,
            cwc_as_of=cwc_as_of,
            percent_full=round(percent_full, 1),
            data_source=current.data_source,
        ),
        history=observations,
        fit=fit,
        projection={
            "neutral_monsoon": neutral,
            "el_nino_monsoon": el_nino,
        },
        tier=tier,
        model_version=MODEL_VERSION,
        flags=sorted(set(flags)),
    )
    return result, history_for_csv


def aggregate_national(results: list[ReservoirResult]) -> NationalAggregate:
    total_capacity = sum(result.full_pool_capacity_bcm or 0 for result in results)
    current_storage = sum(result.current.estimated_storage_bcm for result in results)
    tier_counts = {tier: sum(1 for result in results if result.tier == tier) for tier in _tiers()}
    at_risk = sum(
        result.population_served or 0
        for result in results
        if result.tier in {"critical", "warning"}
    )
    return NationalAggregate(
        total_capacity_bcm=round(total_capacity, 3),
        current_storage_bcm=round(current_storage, 3),
        percent_full=round((current_storage / total_capacity) * 100, 1) if total_capacity else 0,
        reservoirs_critical=tier_counts["critical"],
        reservoirs_warning=tier_counts["warning"],
        reservoirs_watch=tier_counts["watch"],
        reservoirs_stable=tier_counts["stable"],
        people_at_risk_neutral=at_risk,
        people_at_risk_el_nino=0,
    )


def export_dashboard_data(
    snapshot: DashboardSnapshot,
    csv_frames: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    write_json_atomic(output_dir / "reservoirs.json", snapshot)
    reservoir_dir = output_dir / "reservoirs"
    reservoir_dir.mkdir(parents=True, exist_ok=True)
    for reservoir_id, frame in csv_frames.items():
        csv_path = reservoir_dir / f"{reservoir_id}.csv"
        tmp_path = csv_path.with_suffix(".csv.tmp")
        frame.to_csv(tmp_path, index=False)
        tmp_path.replace(csv_path)


def _merge_history(
    jrc_history: pd.DataFrame,
    s2_series: pd.DataFrame,
    current: RecentArea,
) -> pd.DataFrame:
    jrc = pd.DataFrame(
        {
            "date": pd.to_datetime(jrc_history["month"] + "-01").dt.date,
            "area_km2": jrc_history["area_km2"],
            "data_source": "jrc",
            "cloud_coverage_percent": None,
        }
    )
    s2 = s2_series.copy()
    if s2.empty:
        s2 = pd.DataFrame(columns=["date", "area_km2", "data_source", "cloud_coverage_percent"])
    current_frame = pd.DataFrame(
        [
            {
                "date": current.as_of,
                "area_km2": current.area_km2,
                "data_source": current.data_source,
                "cloud_coverage_percent": current.cloud_coverage_percent,
            }
        ]
    )
    history = pd.concat([jrc, s2, current_frame], ignore_index=True)
    history = history.sort_values(["date", "data_source"]).drop_duplicates("date", keep="last")
    return history.reset_index(drop=True)


def _load_cwc_storage_or_empty() -> pd.DataFrame:
    try:
        return load_cwc_storage_csv()
    except Exception as exc:
        print(f"CWC storage unavailable: {exc}")
        return pd.DataFrame()


def _latest_cwc_date(cwc_storage: pd.DataFrame) -> date | None:
    if cwc_storage.empty:
        return None
    return max(cwc_storage["date"])


def _cwc_row_for_reservoir(cwc_storage: pd.DataFrame | None, reservoir_id: str):
    if cwc_storage is None or cwc_storage.empty:
        return None
    matches = cwc_storage[cwc_storage["reservoir_id"] == reservoir_id].sort_values("date")
    if matches.empty:
        return None
    return matches.iloc[-1]


def _calibrate_curve(
    aoi: ReservoirAOI,
    *,
    full_pool_area_km2: float,
    full_capacity_bcm: float | None,
    history: pd.DataFrame,
    cwc_row,
):
    flags: list[str] = []
    if not full_capacity_bcm:
        return None, ["needs_cwc_calibration", "volume_area_ratio_proxy"]

    points = [(full_pool_area_km2, full_capacity_bcm)]
    if cwc_row is not None:
        cwc_date = _optional_cwc_date(cwc_row)
        cwc_storage = _optional_cwc_value(cwc_row, "live_storage_bcm")
        nearest_area, days_apart = _nearest_area_for_date(history, cwc_date)
        if nearest_area is not None and cwc_storage and days_apart <= 14:
            points.append((nearest_area, cwc_storage))
            flags.extend(["cwc_calibrated_single_point", "phase0_cwc_validation_incomplete"])
        else:
            flags.extend(["needs_cwc_calibration", "volume_area_ratio_proxy"])
    else:
        flags.extend(["needs_cwc_calibration", "volume_area_ratio_proxy"])

    if aoi.dead_storage_capacity_bcm and aoi.full_pool_capacity_bcm:
        dead_area = full_pool_area_km2 * (
            aoi.dead_storage_capacity_bcm / aoi.full_pool_capacity_bcm
        )
        points.append((dead_area, aoi.dead_storage_capacity_bcm))

    if len(points) < 2:
        return None, sorted(set(flags))

    try:
        curve = fit_power_law_curve(aoi.id, points)
    except Exception:
        flags.extend(["needs_cwc_calibration", "volume_area_ratio_proxy"])
        return None, sorted(set(flags))

    if curve.r_squared < 0.85:
        flags.append("low_volume_confidence")
    return curve, sorted(set(flags))


def _nearest_area_for_date(
    history: pd.DataFrame,
    target_date: date | None,
) -> tuple[float | None, int]:
    if target_date is None or history.empty:
        return None, 9999
    frame = history.copy()
    frame["date_delta"] = frame["date"].map(lambda value: abs((value - target_date).days))
    frame = frame[frame["area_km2"] > 0].sort_values("date_delta")
    if frame.empty:
        return None, 9999
    row = frame.iloc[0]
    return float(row["area_km2"]), int(row["date_delta"])


def _fetch_enso_summary() -> EnsoSummary:
    try:
        oni_latest, state = fetch_oni(timeout=10)
    except Exception as exc:
        print(f"ONI fetch unavailable: {exc}")
        return EnsoSummary(state="unavailable", oni_latest=None, imd_monsoon_forecast=None)
    return EnsoSummary(state=state, oni_latest=oni_latest, imd_monsoon_forecast=None)


def _full_pool_area_km2(
    aoi: ReservoirAOI,
    jrc_history: pd.DataFrame,
    current: RecentArea,
) -> float:
    if aoi.aoi_area_km2:
        return aoi.aoi_area_km2
    historical_max = float(jrc_history["area_km2"].max()) if not jrc_history.empty else 0.0
    return max(historical_max, current.area_km2)


def _area_ratio_storage(
    area_km2: float,
    full_pool_area_km2: float,
    capacity_bcm: float | None,
) -> float:
    if not capacity_bcm or full_pool_area_km2 <= 0:
        return 0.0
    return max(0.0, (area_km2 / full_pool_area_km2) * capacity_bcm)


def _storage_from_area(
    area_km2: float,
    *,
    full_pool_area_km2: float,
    capacity_bcm: float | None,
    curve,
) -> float:
    if curve is not None and area_km2 > 0:
        return max(0.0, curve.area_to_volume(area_km2))
    return _area_ratio_storage(area_km2, full_pool_area_km2, capacity_bcm)


def _storage_percent_full(storage_bcm: float, capacity_bcm: float | None) -> float:
    if not capacity_bcm:
        return 0.0
    return max(0.0, (storage_bcm / capacity_bcm) * 100)


def _full_capacity_bcm(aoi: ReservoirAOI, cwc_row) -> float | None:
    cwc_capacity = _optional_cwc_value(cwc_row, "live_capacity_at_frl_bcm")
    return cwc_capacity or aoi.full_pool_capacity_bcm


def _optional_cwc_value(cwc_row, field: str) -> float | None:
    if cwc_row is None:
        return None
    value = cwc_row.get(field) if hasattr(cwc_row, "get") else getattr(cwc_row, field, None)
    if pd.isna(value):
        return None
    return float(value)


def _optional_cwc_date(cwc_row) -> date | None:
    if cwc_row is None:
        return None
    value = cwc_row.get("date") if hasattr(cwc_row, "get") else getattr(cwc_row, "date", None)
    if pd.isna(value):
        return None
    return value


def _dead_storage_area_proxy(aoi: ReservoirAOI, full_pool_area_km2: float) -> float:
    if aoi.dead_storage_capacity_bcm and aoi.full_pool_capacity_bcm:
        return full_pool_area_km2 * (aoi.dead_storage_capacity_bcm / aoi.full_pool_capacity_bcm)
    return full_pool_area_km2 * 0.10


def _five_year_average_percent(
    jrc_history: pd.DataFrame,
    full_pool_area_km2: float,
    month: int,
) -> float | None:
    if jrc_history.empty or full_pool_area_km2 <= 0:
        return None
    frame = jrc_history.copy()
    frame["date"] = pd.to_datetime(frame["month"] + "-01")
    same_month = frame[frame["date"].dt.month == month].tail(5)
    if same_month.empty:
        return None
    return float((same_month["area_km2"] / full_pool_area_km2 * 100).mean())


def _latest_jrc_month(results: list[ReservoirResult]) -> str | None:
    months = [
        observation.date.strftime("%Y-%m")
        for result in results
        for observation in result.history
        if observation.data_source == "jrc"
    ]
    return max(months) if months else None


def _tiers() -> tuple[str, str, str, str]:
    return "critical", "warning", "watch", "stable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--reservoir", action="append", dest="reservoirs")
    parser.add_argument("--output-dir", type=Path, default=DASHBOARD_DATA_DIR)
    parser.add_argument("--no-export", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        as_of=args.as_of,
        reservoirs=args.reservoirs,
        output_dir=args.output_dir,
        export=not args.no_export,
    )

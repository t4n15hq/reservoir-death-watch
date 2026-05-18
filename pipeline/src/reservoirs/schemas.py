"""Pydantic models for pipeline inputs and dashboard outputs."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AreaSource = Literal["jrc", "sentinel_2", "sentinel_1"]
CurrentSource = Literal["sentinel_2", "sentinel_1", "stale"]
Tier = Literal["critical", "warning", "watch", "stable"]
FitQuality = Literal["good", "low_confidence", "rejected"]
ConfidenceFlag = Literal["high", "medium", "low"]
Scenario = Literal["neutral_monsoon", "el_nino_monsoon"]
ProjectionMethod = Literal["linear_extrapolation", "chirps_augmented"]


class ReservoirAOI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    river: str
    state: str
    cwc_name: str
    city_served: str = ""
    population_served: int | None = None
    lat: float
    lon: float
    full_pool_capacity_bcm: float | None = None
    dead_storage_capacity_bcm: float | None = None
    priority: int
    aoi_file: str
    aoi_area_km2: float | None = None
    aoi_review_status: str | None = None
    polygon: dict[str, Any]
    notes: str = ""

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, value: dict[str, Any]) -> dict[str, Any]:
        geometry_type = value.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            msg = "AOI geometry must be a GeoJSON Polygon or MultiPolygon"
            raise ValueError(msg)
        if not value.get("coordinates"):
            msg = "AOI geometry has no coordinates"
            raise ValueError(msg)
        return value


class AreaObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    area_km2: float = Field(ge=0)
    data_source: AreaSource
    cloud_coverage_percent: float | None = Field(default=None, ge=0, le=100)


class AreaVolumeCurve(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservoir_id: str
    coefficient_a: float = Field(gt=0)
    exponent_b: float = Field(gt=0)
    r_squared: float = Field(ge=0, le=1)
    n_calibration_points: int = Field(ge=2)
    calibrated_at: datetime
    confidence_flag: ConfidenceFlag

    def area_to_volume(self, area_km2: float) -> float:
        if area_km2 <= 0:
            msg = "area_km2 must be positive"
            raise ValueError(msg)
        return self.coefficient_a * (area_km2**self.exponent_b)

    def volume_to_area(self, volume_bcm: float) -> float:
        if volume_bcm <= 0:
            msg = "volume_bcm must be positive"
            raise ValueError(msg)
        return (volume_bcm / self.coefficient_a) ** (1 / self.exponent_b)


class DepletionFit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservoir_id: str
    slope_km2_per_day: float
    intercept: float
    std_error: float = Field(ge=0)
    r_squared: float = Field(ge=0, le=1)
    n_observations: int = Field(ge=0)
    window_days: int = Field(gt=0)
    fit_quality: FitQuality


class Projection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    days_to_dead_storage: int | None
    dead_storage_date: date | None
    confidence_interval_days: tuple[int, int] | None
    method: ProjectionMethod = "linear_extrapolation"


class ReservoirCurrent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    area_km2: float = Field(ge=0)
    estimated_storage_bcm: float = Field(ge=0)
    cwc_reported_bcm: float | None = Field(default=None, ge=0)
    percent_full: float = Field(ge=0)
    data_source: CurrentSource


class ReservoirResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    river: str
    state: str
    city_served: str = ""
    population_served: int | None = None
    full_pool_area_km2: float | None = None
    full_pool_capacity_bcm: float | None = None
    dead_storage_capacity_bcm: float | None = None
    lat: float
    lon: float
    current: ReservoirCurrent
    history: list[AreaObservation]
    fit: DepletionFit | None
    projection: dict[Scenario, Projection]
    tier: Tier
    model_version: str
    flags: list[str] = Field(default_factory=list)


class NationalAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_capacity_bcm: float = Field(ge=0)
    current_storage_bcm: float = Field(ge=0)
    percent_full: float = Field(ge=0)
    reservoirs_critical: int = Field(ge=0)
    reservoirs_warning: int = Field(ge=0)
    reservoirs_watch: int = Field(ge=0)
    reservoirs_stable: int = Field(ge=0)
    people_at_risk_neutral: int = Field(ge=0)
    people_at_risk_el_nino: int = Field(ge=0)


class DataSourcesUsed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jrc_through: str | None = None
    s2_latest: date | None = None
    cwc_bulletin: date | None = None
    oni_month: str | None = None


class EnsoSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    oni_latest: float | None
    imd_monsoon_forecast: str | None = None


class DashboardSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    model_version: str
    data_sources_used: DataSourcesUsed
    enso: EnsoSummary
    national_aggregate: NationalAggregate
    reservoirs: list[ReservoirResult]

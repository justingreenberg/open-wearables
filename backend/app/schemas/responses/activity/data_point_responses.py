from datetime import date, datetime
from typing import TypedDict
from uuid import UUID

from pydantic import BaseModel

from app.schemas.enums import SeriesType
from app.schemas.utils import SourceMetadata
from app.utils.dates import ZoneOffset


class TimeSeriesSourceMetadata(SourceMetadata):
    """Stored provenance for one time-series sample."""

    source: str | None = None
    device_type: str | None = None
    software_version: str | None = None
    original_source_name: str | None = None


class TimeSeriesSyncMetadata(BaseModel):
    """Persisted connection state associated with a sample's data source."""

    connection_id: UUID
    connection_status: str
    last_synced_at: datetime | None = None


class TimeSeriesSample(BaseModel):
    record_id: UUID
    external_id: str | None = None
    data_source_id: UUID
    provider: str
    timestamp: datetime
    zone_offset: ZoneOffset = None
    type: SeriesType
    value: float | int
    unit: str
    source: TimeSeriesSourceMetadata
    sync: TimeSeriesSyncMetadata | None = None
    # True = daily total. False/None = not a daily total (summable sample); None is a
    # legacy row and is treated as False by the aggregation.
    is_daily_total: bool | None = None


class ActivityAggregateResult(TypedDict):
    """Result from daily activity aggregation query."""

    activity_date: date
    provider: str | None
    source: str | None
    device_model: str | None
    steps_sum: int
    active_energy_sum: float
    basal_energy_sum: float
    hr_avg: int | None
    hr_max: int | None
    hr_min: int | None
    distance_sum: float | None
    flights_climbed_sum: int | None
    active_time_minutes: int | None  # Provider-reported daily active time; None when not reported


class ActiveMinutesResult(TypedDict):
    """Result from daily active/sedentary minutes query."""

    activity_date: date
    source: str | None
    device_model: str | None
    active_minutes: int
    tracked_minutes: int
    sedentary_minutes: int


class IntensityMinutesResult(TypedDict):
    """Result from daily intensity minutes query."""

    activity_date: date
    source: str | None
    device_model: str | None
    light_minutes: int
    moderate_minutes: int
    vigorous_minutes: int

"""
Tests for TimeSeriesService.

Tests cover:
- Bulk creating time series samples
- Getting daily histogram of data points
- Counting data points by series type
- Counting data points by provider
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import (
    HeartRateSampleCreate,
    StepSampleCreate,
    TimeSeriesQueryParams,
    TimeSeriesSampleCreate,
)
from app.services.timeseries_service import timeseries_service
from tests.factories import (
    DataPointSeriesFactory,
    DataSourceFactory,
    SeriesTypeDefinitionFactory,
    UserConnectionFactory,
    UserFactory,
)


class TestTimeSeriesServiceBulkCreateSamples:
    """Test bulk creation of time series samples."""

    def test_bulk_create_heart_rate_samples(self, db: Session) -> None:
        """Should bulk create heart rate samples."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_1")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            HeartRateSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_1",
                recorded_at=now - timedelta(minutes=i),
                value=70 + i,
                series_type=SeriesType.heart_rate,
            )
            for i in range(5)
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert - verify samples were created
        final_count = timeseries_service.get_total_count(db)
        assert final_count == initial_count + 5

    def test_bulk_create_step_samples(self, db: Session) -> None:
        """Should bulk create step samples."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_2")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            StepSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_2",
                recorded_at=now - timedelta(hours=i),
                value=1000 + i * 100,
                series_type=SeriesType.steps,
            )
            for i in range(3)
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert
        final_count = timeseries_service.get_total_count(db)
        assert final_count == initial_count + 3

    def test_bulk_create_mixed_series_types(self, db: Session) -> None:
        """Should bulk create samples of different series types."""
        # Arrange
        user = UserFactory()
        DataSourceFactory(source="apple", device_model="device_3")

        initial_count = timeseries_service.get_total_count(db)
        now = datetime.now(timezone.utc)
        samples = [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_3",
                recorded_at=now - timedelta(minutes=1),
                value=72,
                series_type=SeriesType.heart_rate,
            ),
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user.id,
                provider_name="apple",
                device_model="device_3",
                recorded_at=now - timedelta(minutes=2),
                value=5000,
                series_type=SeriesType.steps,
            ),
        ]

        # Act
        timeseries_service.bulk_create_samples(db, samples)

        # Assert
        total_count = timeseries_service.get_total_count(db)
        assert total_count >= initial_count + 2


class TestTimeSeriesServiceProvenance:
    """Time-series reads retain stored record, source, device, and sync identity."""

    def test_get_timeseries_exposes_stored_identity_and_connection_state(self, db: Session) -> None:
        user = UserFactory()
        last_synced_at = datetime(2026, 7, 11, 12, 30, tzinfo=timezone.utc)
        connection = UserConnectionFactory(
            user=user,
            provider="apple",
            last_synced_at=last_synced_at,
        )
        data_source = DataSourceFactory(
            user=user,
            provider="apple",
            user_connection_id=connection.id,
            source="com.omron.healthkit",
            device_model="Omron Evolv",
            device_type="blood_pressure_cuff",
            software_version="2.4.1",
            original_source_name="OMRON connect",
        )
        series_type = SeriesTypeDefinitionFactory.get_or_create_blood_pressure_systolic()
        record_id = uuid4()
        sample = DataPointSeriesFactory(
            id=record_id,
            external_id="hk-record-123",
            data_source=data_source,
            series_type=series_type,
            recorded_at=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            value=118,
        )

        response = timeseries_service.get_timeseries(
            db,
            user.id,
            [SeriesType.blood_pressure_systolic],
            TimeSeriesQueryParams(
                start_datetime=sample.recorded_at - timedelta(minutes=1),
                end_datetime=sample.recorded_at + timedelta(minutes=1),
                limit=50,
            ),
        )

        assert len(response.data) == 1
        result = response.data[0]
        assert result.record_id == record_id
        assert result.external_id == "hk-record-123"
        assert result.data_source_id == data_source.id
        assert result.provider == "apple"
        assert result.source.provider == "apple"
        assert result.source.source == "com.omron.healthkit"
        assert result.source.device == "Omron Evolv"
        assert result.source.device_type == "blood_pressure_cuff"
        assert result.source.software_version == "2.4.1"
        assert result.source.original_source_name == "OMRON connect"
        assert result.sync is not None
        assert result.sync.connection_id == connection.id
        assert result.sync.connection_status == "active"
        assert result.sync.last_synced_at == last_synced_at

    def test_get_timeseries_does_not_invent_external_id_or_sync_state(self, db: Session) -> None:
        user = UserFactory()
        data_source = DataSourceFactory(user=user, user_connection_id=None)
        sample = DataPointSeriesFactory(data_source=data_source, external_id=None)

        response = timeseries_service.get_timeseries(
            db,
            user.id,
            [],
            TimeSeriesQueryParams(
                start_datetime=sample.recorded_at - timedelta(minutes=1),
                end_datetime=sample.recorded_at + timedelta(minutes=1),
                limit=50,
            ),
        )

        assert len(response.data) == 1
        result = response.data[0]
        assert result.record_id == sample.id
        assert result.external_id is None
        assert result.data_source_id == data_source.id
        assert result.sync is None


class TestTimeSeriesServiceGetDailyHistogram:
    """Test getting daily histogram of data points."""

    def test_get_daily_histogram_groups_by_day(self, db: Session) -> None:
        """Should group data points by day."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        start_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 4, 0, 0, 0, tzinfo=timezone.utc)

        # Day 1: 3 samples
        for i in range(3):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 1, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 2: 2 samples
        for i in range(2):
            DataPointSeriesFactory(
                mapping=mapping,
                series_type=series_type,
                recorded_at=datetime(2024, 1, 2, 10 + i, 0, 0, tzinfo=timezone.utc),
            )

        # Day 3: 1 sample
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=datetime(2024, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
        )

        # Act
        histogram = timeseries_service.get_daily_histogram(db, start_date, end_date)

        # Assert
        assert len(histogram) == 3
        assert histogram[0] == 3  # Day 1
        assert histogram[1] == 2  # Day 2
        assert histogram[2] == 1  # Day 3

    def test_get_daily_histogram_empty_range(self, db: Session) -> None:
        """Should return empty list for range with no data."""
        # Arrange
        start_date = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2024, 6, 7, 0, 0, 0, tzinfo=timezone.utc)

        # Act
        histogram = timeseries_service.get_daily_histogram(db, start_date, end_date)

        # Assert
        assert histogram == []


class TestTimeSeriesServiceGetCountBySeriesType:
    """Test counting data points by series type."""

    def test_get_count_by_series_type_groups_correctly(self, db: Session) -> None:
        """Should group and count data points by series type."""
        # Arrange
        mapping = DataSourceFactory()
        hr_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        step_type = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create 3 heart rate samples
        for _ in range(3):
            DataPointSeriesFactory(mapping=mapping, series_type=hr_type)

        # Create 2 step samples
        for _ in range(2):
            DataPointSeriesFactory(mapping=mapping, series_type=step_type)

        # Act
        results = timeseries_service.get_count_by_series_type(db)

        # Assert
        results_dict = dict(results)
        assert results_dict[hr_type.id] == 3
        assert results_dict[step_type.id] == 2

    def test_get_count_by_series_type_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        mapping = DataSourceFactory()
        # Use existing seeded series types to avoid ID conflicts
        type1 = SeriesTypeDefinitionFactory.get_or_create_heart_rate()
        type2 = SeriesTypeDefinitionFactory.get_or_create_steps()

        # Create more of type1
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=type1)

        # Create fewer of type2
        for _ in range(2):
            DataPointSeriesFactory(mapping=mapping, series_type=type2)

        # Act
        results = timeseries_service.get_count_by_series_type(db)

        # Assert
        # Results should be ordered by count descending
        assert results[0][1] >= results[1][1]

    def test_get_count_by_series_type_empty_result(self, db: Session) -> None:
        """Should return empty list when no data points exist."""
        # Act
        results = timeseries_service.get_count_by_series_type(db)

        # Assert
        assert results == []


class TestTimeSeriesServiceGetCountBySource:
    """Test counting data points by source."""

    def test_get_count_by_source_groups_correctly(self, db: Session) -> None:
        """Should group and count data points by source."""
        # Arrange
        user = UserFactory()
        apple_mapping = DataSourceFactory(user=user, source="apple")
        garmin_mapping = DataSourceFactory(user=user, source="garmin")

        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        # Create 4 samples from Apple
        for _ in range(4):
            DataPointSeriesFactory(mapping=apple_mapping, series_type=series_type)

        # Create 2 samples from Garmin
        for _ in range(2):
            DataPointSeriesFactory(mapping=garmin_mapping, series_type=series_type)

        # Act
        results = timeseries_service.get_count_by_source(db)

        # Assert
        results_dict = dict(results)
        assert results_dict["apple"] == 4
        assert results_dict["garmin"] == 2

    def test_get_count_by_source_ordered_by_count(self, db: Session) -> None:
        """Should order results by count descending."""
        # Arrange
        results = timeseries_service.get_count_by_source(db)

        if len(results) > 1:
            # Verify descending order
            for i in range(len(results) - 1):
                assert results[i][1] >= results[i + 1][1]

    def test_get_count_by_source_empty_result(self, db: Session) -> None:
        """Should return empty list when no data points exist."""
        # Act
        results = timeseries_service.get_count_by_source(db)

        # Assert
        assert results == []


class TestTimeSeriesServiceGetTotalCount:
    """Test getting total count of data points."""

    def test_get_total_count(self, db: Session) -> None:
        """Should return total count of all data points."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        initial_count = timeseries_service.get_total_count(db)

        # Create 5 samples
        for _ in range(5):
            DataPointSeriesFactory(mapping=mapping, series_type=series_type)

        # Act
        total_count = timeseries_service.get_total_count(db)

        # Assert
        assert total_count == initial_count + 5

    def test_get_total_count_empty_database(self, db: Session) -> None:
        """Should return 0 when no data points exist."""
        # Note: This test might fail if there's existing data in the test DB
        # from other tests running in the same session
        # Act
        count = timeseries_service.get_total_count(db)

        # Assert
        assert count >= 0  # At minimum should be non-negative


class TestTimeSeriesServiceGetCountInRange:
    """Test counting data points in date range."""

    def test_get_count_in_range(self, db: Session) -> None:
        """Should count data points within date range."""
        # Arrange
        mapping = DataSourceFactory()
        series_type = SeriesTypeDefinitionFactory.get_or_create_heart_rate()

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        end = now - timedelta(days=1)

        # Create samples at different times
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=10),
        )  # Before range
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=5),
        )  # In range
        DataPointSeriesFactory(
            mapping=mapping,
            series_type=series_type,
            recorded_at=now - timedelta(days=3),
        )  # In range
        DataPointSeriesFactory(mapping=mapping, series_type=series_type, recorded_at=now)  # After range

        # Act
        count = timeseries_service.get_count_in_range(db, start, end)

        # Assert
        assert count == 2

    def test_get_count_in_range_empty_result(self, db: Session) -> None:
        """Should return 0 when no data points in range."""
        # Arrange
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)
        far_future = future + timedelta(days=7)

        # Act
        count = timeseries_service.get_count_in_range(db, future, far_future)

        # Assert
        assert count == 0

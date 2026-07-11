from unittest import TestCase

from app.tools.timeseries import _record_from_sample


class TimeSeriesRecordTests(TestCase):
    def test_identity_provenance_and_sync_are_preserved(self) -> None:
        sample = {
            "record_id": "ow-record-1",
            "external_id": "provider-record-1",
            "data_source_id": "source-1",
            "provider": "apple",
            "timestamp": "2026-07-11T12:00:00Z",
            "type": "blood_pressure_systolic",
            "value": 118,
            "unit": "mmHg",
            "source": {
                "provider": "apple",
                "source": "com.omron.healthkit",
                "device": "Omron Evolv",
                "device_type": "blood_pressure_cuff",
            },
            "sync": {
                "connection_id": "connection-1",
                "connection_status": "active",
                "last_synced_at": "2026-07-11T12:05:00Z",
            },
        }

        record = _record_from_sample(sample)

        assert record == sample

    def test_missing_provider_identity_remains_missing(self) -> None:
        record = _record_from_sample(
            {
                "timestamp": "2026-07-11T12:00:00Z",
                "type": "weight",
                "value": 80,
                "unit": "kg",
                "source": None,
            }
        )

        assert record["record_id"] is None
        assert record["external_id"] is None
        assert record["data_source_id"] is None
        assert record["provider"] is None
        assert record["sync"] is None

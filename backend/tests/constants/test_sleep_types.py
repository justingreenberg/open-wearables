"""Unit tests for SDK sleep-phase normalization.

Covers app.constants.series_types.sdk.sleep_types.get_apple_sleep_phase — the function
the mobile-SDK ingest path (sleep_service.handle_sleep_data) uses to map an incoming
stage label to a canonical SleepPhase. Anything that returns None is dropped at ingest,
so a regression here silently loses the deep/REM/light breakdown while total sleep
duration survives.

Pure-Python logic only — no database, no factories.
"""

import pytest

from app.constants.series_types.sdk.sleep_types import SleepPhase, get_apple_sleep_phase


class TestGetAppleSleepPhase:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # canonical values still map to themselves (no regression)
            ("in_bed", SleepPhase.IN_BED),
            ("sleeping", SleepPhase.SLEEPING),
            ("awake", SleepPhase.AWAKE),
            ("light", SleepPhase.ASLEEP_LIGHT),
            ("deep", SleepPhase.ASLEEP_DEEP),
            ("rem", SleepPhase.ASLEEP_REM),
            ("unknown", SleepPhase.UNKNOWN),
        ],
    )
    def test_canonical_values_unchanged(self, raw: str, expected: SleepPhase) -> None:
        assert get_apple_sleep_phase(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # Apple "Core" is the dominant Apple Watch stage and maps to LIGHT,
            # mirroring the XML importer's SLEEP_VALUE_TO_STAGE.
            ("core", SleepPhase.ASLEEP_LIGHT),
            ("asleepCore", SleepPhase.ASLEEP_LIGHT),
            ("HKCategoryValueSleepAnalysisAsleepCore", SleepPhase.ASLEEP_LIGHT),
            ("asleepDeep", SleepPhase.ASLEEP_DEEP),
            ("HKCategoryValueSleepAnalysisAsleepDeep", SleepPhase.ASLEEP_DEEP),
            ("asleepREM", SleepPhase.ASLEEP_REM),
            ("HKCategoryValueSleepAnalysisAsleepREM", SleepPhase.ASLEEP_REM),
            ("asleepUnspecified", SleepPhase.SLEEPING),
            ("HKCategoryValueSleepAnalysisAsleepUnspecified", SleepPhase.SLEEPING),
            ("HKCategoryValueSleepAnalysisInBed", SleepPhase.IN_BED),
            ("HKCategoryValueSleepAnalysisAwake", SleepPhase.AWAKE),
        ],
    )
    def test_apple_healthkit_spellings_normalized(self, raw: str, expected: SleepPhase) -> None:
        """These previously returned None and were dropped at ingest (the bug)."""
        assert get_apple_sleep_phase(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("CORE", SleepPhase.ASLEEP_LIGHT),
            ("  Deep  ", SleepPhase.ASLEEP_DEEP),
            ("Rem", SleepPhase.ASLEEP_REM),
        ],
    )
    def test_case_and_whitespace_insensitive(self, raw: str, expected: SleepPhase) -> None:
        assert get_apple_sleep_phase(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "garbage", "not_a_stage"])
    def test_unrecognized_returns_none(self, raw: str | None) -> None:
        assert get_apple_sleep_phase(raw) is None

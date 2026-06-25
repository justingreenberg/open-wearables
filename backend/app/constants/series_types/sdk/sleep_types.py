from enum import StrEnum

from app.constants.sleep import SleepStageType


class SleepPhase(StrEnum):
    IN_BED = SleepStageType.IN_BED
    SLEEPING = "sleeping"
    AWAKE = SleepStageType.AWAKE
    ASLEEP_LIGHT = SleepStageType.LIGHT
    ASLEEP_DEEP = SleepStageType.DEEP
    ASLEEP_REM = SleepStageType.REM
    UNKNOWN = SleepStageType.UNKNOWN


# Normalizes the several spellings of Apple Watch / HealthKit (and provider) sleep
# stages to canonical SleepPhase values. The mobile SDK and providers emit stage
# labels in different forms: raw HKCategoryValueSleepAnalysis identifiers
# ("...AsleepCore"), short Apple names ("asleepCore" / "core"), or already-canonical
# values ("light"). Apple's "Core" stage maps to LIGHT, matching the XML importer's
# SLEEP_VALUE_TO_STAGE (app/services/apple/apple_xml/xml_service.py).
#
# Without this map, any non-canonical label fails the strict SleepPhase() parse and the
# stage sample is silently dropped at ingest (sleep_service.handle_sleep_data) — total
# sleep duration survives but the deep/REM/light breakdown is lost. Apple Watch's
# dominant stage is "Core", so in practice the whole breakdown disappears.
_SLEEP_PHASE_ALIASES: dict[str, SleepPhase] = {
    # in bed
    "in_bed": SleepPhase.IN_BED,
    "inbed": SleepPhase.IN_BED,
    "hkcategoryvaluesleepanalysisinbed": SleepPhase.IN_BED,
    # awake
    "awake": SleepPhase.AWAKE,
    "hkcategoryvaluesleepanalysisawake": SleepPhase.AWAKE,
    # unspecified / generic asleep
    "sleeping": SleepPhase.SLEEPING,
    "asleep": SleepPhase.SLEEPING,
    "asleepunspecified": SleepPhase.SLEEPING,
    "hkcategoryvaluesleepanalysisasleep": SleepPhase.SLEEPING,
    "hkcategoryvaluesleepanalysisasleepunspecified": SleepPhase.SLEEPING,
    # light / core (Apple "Core" == light)
    "light": SleepPhase.ASLEEP_LIGHT,
    "core": SleepPhase.ASLEEP_LIGHT,
    "asleeplight": SleepPhase.ASLEEP_LIGHT,
    "asleepcore": SleepPhase.ASLEEP_LIGHT,
    "hkcategoryvaluesleepanalysisasleepcore": SleepPhase.ASLEEP_LIGHT,
    # deep
    "deep": SleepPhase.ASLEEP_DEEP,
    "asleepdeep": SleepPhase.ASLEEP_DEEP,
    "hkcategoryvaluesleepanalysisasleepdeep": SleepPhase.ASLEEP_DEEP,
    # rem
    "rem": SleepPhase.ASLEEP_REM,
    "asleeprem": SleepPhase.ASLEEP_REM,
    "hkcategoryvaluesleepanalysisasleeprem": SleepPhase.ASLEEP_REM,
    # unknown
    "unknown": SleepPhase.UNKNOWN,
}


def get_apple_sleep_phase(apple_sleep_phase: str | None) -> SleepPhase | None:
    if apple_sleep_phase is None:
        return None
    normalized = _SLEEP_PHASE_ALIASES.get(apple_sleep_phase.strip().lower())
    if normalized is not None:
        return normalized
    try:
        return SleepPhase(apple_sleep_phase)
    except ValueError:
        return None

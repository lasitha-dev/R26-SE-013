"""Transparent, documented data-quality dimensions for normalized records.

Every component below is a categorical judgment (HIGH / MEDIUM / LOW /
UNKNOWN) derived from explicit, stated rules over fields that already
exist on the record — never a fitted or tuned score. The optional
composite DQS is a plain equal-weighted average of the six components,
declared and fixed here; per the Checkpoint 2 rule, it is NEVER adjusted
using future model performance or validation results, and the
component-level values are always kept alongside it (never discarded once
a composite exists).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import AvailabilityQuality, GpsQuality, NormalizedOutbreakRecord

HIGH, MEDIUM, LOW, UNKNOWN = "HIGH", "MEDIUM", "LOW", "UNKNOWN"

_CATEGORY_SCORE = {HIGH: 1.0, MEDIUM: 0.6, LOW: 0.3, UNKNOWN: 0.0}

# Declared equal weighting across the six components — a documented,
# fixed starting point for transparency, not a tuned parameter.
_COMPONENT_WEIGHT = 1.0 / 6.0

# Fields counted toward completeness_quality. Deliberately excludes
# identifiers/provenance metadata (source_record_id, source_file, ...) and
# the derived quality/availability columns themselves, so completeness
# measures the epidemiological content, not bookkeeping.
_COMPLETENESS_FIELDS = [
    "country",
    "event_id",
    "outbreak_id",
    "admin1",
    "admin2",
    "admin3",
    "locality",
    "latitude",
    "longitude",
    "species",
    "susceptible",
    "cases",
    "deaths",
    "killed_disposed",
    "vaccinated",
    "diagnostic_method",
    "diagnostic_result",
    "event_status",
]


def gps_quality_component(r: NormalizedOutbreakRecord) -> str:
    if r.latitude is None or r.longitude is None:
        return UNKNOWN
    return {
        GpsQuality.EXACT.value: HIGH,
        GpsQuality.APPROXIMATE.value: MEDIUM,
        GpsQuality.COARSE.value: LOW,
        GpsQuality.UNKNOWN.value: LOW,
    }.get(r.gps_quality, UNKNOWN)


def date_quality_component(r: NormalizedOutbreakRecord) -> str:
    if r.outbreak_start_date or r.onset_date:
        return HIGH
    if r.event_start_date or r.confirmation_date:
        return MEDIUM
    if r.report_date:
        return LOW
    return UNKNOWN


def diagnostic_quality_component(r: NormalizedOutbreakRecord) -> str:
    has_method = bool(r.diagnostic_method)
    has_result = bool(r.diagnostic_result)
    if has_method and has_result:
        return HIGH
    if has_method or has_result:
        return MEDIUM
    return UNKNOWN


def identifier_quality_component(r: NormalizedOutbreakRecord) -> str:
    has_event_id = bool(r.event_id)
    has_outbreak_id = bool(r.outbreak_id)
    if has_event_id and has_outbreak_id:
        return HIGH
    if has_event_id or has_outbreak_id:
        return MEDIUM
    return UNKNOWN


def completeness_quality_component(r: NormalizedOutbreakRecord) -> str:
    filled = sum(1 for name in _COMPLETENESS_FIELDS if getattr(r, name) not in (None, ""))
    fraction = filled / len(_COMPLETENESS_FIELDS)
    if fraction >= 0.75:
        return HIGH
    if fraction >= 0.5:
        return MEDIUM
    if fraction >= 0.25:
        return LOW
    return UNKNOWN


def availability_quality_component(r: NormalizedOutbreakRecord) -> str:
    if r.operational_availability_quality == AvailabilityQuality.ACTUAL.value:
        return HIGH
    if r.proxy_availability_quality in (
        AvailabilityQuality.EVENT_DATE_PROXY.value,
        AvailabilityQuality.OBSERVATION_DATE_PROXY.value,
        AvailabilityQuality.CONFIRMATION_PROXY.value,
    ):
        return MEDIUM
    if r.proxy_availability_quality == AvailabilityQuality.REPORT_PROXY.value:
        return LOW
    return UNKNOWN


@dataclass
class QualityComponents:
    source_record_id: str
    gps_quality: str
    date_quality: str
    diagnostic_quality: str
    identifier_quality: str
    completeness_quality: str
    availability_quality: str
    dqs: float

    def as_dict(self) -> dict:
        return {
            "source_record_id": self.source_record_id,
            "gps_quality": self.gps_quality,
            "date_quality": self.date_quality,
            "diagnostic_quality": self.diagnostic_quality,
            "identifier_quality": self.identifier_quality,
            "completeness_quality": self.completeness_quality,
            "availability_quality": self.availability_quality,
            "dqs": self.dqs,
        }


def compute_quality(r: NormalizedOutbreakRecord) -> QualityComponents:
    components = {
        "gps_quality": gps_quality_component(r),
        "date_quality": date_quality_component(r),
        "diagnostic_quality": diagnostic_quality_component(r),
        "identifier_quality": identifier_quality_component(r),
        "completeness_quality": completeness_quality_component(r),
        "availability_quality": availability_quality_component(r),
    }
    dqs = round(sum(_CATEGORY_SCORE[v] * _COMPONENT_WEIGHT for v in components.values()), 4)
    return QualityComponents(source_record_id=r.source_record_id, dqs=dqs, **components)

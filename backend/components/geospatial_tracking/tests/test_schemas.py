"""Tests for RawOutbreakRecord's availability-date invariants.

These guard the checkpoint-1 correction: operational availability (C) must
stay separate from biological (A) and source-document (B) chronology, and
ACTUAL must never be assignable without real evidence.
"""

import pytest

from components.geospatial_tracking.schemas import (
    AvailabilityQuality,
    RawOutbreakRecord,
    SourceSystem,
    ValidationMode,
)


def _record(**overrides) -> RawOutbreakRecord:
    fields = dict(source_file="fixture.csv", source_system=SourceSystem.FAO_EMPRESI_CSV.value)
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def test_defaults_are_unknown_and_none():
    r = _record()
    assert r.operational_availability_date is None
    assert r.operational_availability_quality == AvailabilityQuality.UNKNOWN.value
    assert r.proxy_availability_date is None
    assert r.proxy_availability_quality == AvailabilityQuality.UNKNOWN.value


def test_operational_actual_requires_a_date():
    with pytest.raises(ValueError, match="ACTUAL requires"):
        _record(
            operational_availability_quality=AvailabilityQuality.ACTUAL.value,
            operational_availability_date=None,
        )


def test_operational_actual_with_date_is_allowed():
    r = _record(
        operational_availability_quality=AvailabilityQuality.ACTUAL.value,
        operational_availability_date="2024/01/09",
    )
    assert r.operational_availability_quality == AvailabilityQuality.ACTUAL.value


def test_proxy_quality_can_never_be_actual_even_with_a_date():
    # Proxy fields are RETROSPECTIVE_PROXY-mode substitutes only — no
    # amount of evidence makes them real operational availability.
    with pytest.raises(ValueError, match="never be ACTUAL"):
        _record(
            proxy_availability_quality=AvailabilityQuality.ACTUAL.value,
            proxy_availability_date="2021/03/10",
        )


def test_availability_quality_enum_has_both_proxy_labels():
    assert AvailabilityQuality.EVENT_DATE_PROXY.value == "EVENT_DATE_PROXY"
    assert AvailabilityQuality.OBSERVATION_DATE_PROXY.value == "OBSERVATION_DATE_PROXY"


def test_validation_mode_enum_has_both_future_modes():
    assert ValidationMode.STRICT_OPERATIONAL.value == "STRICT_OPERATIONAL"
    assert ValidationMode.RETROSPECTIVE_PROXY.value == "RETROSPECTIVE_PROXY"


def test_original_dates_are_never_overwritten_by_a_proxy_field():
    # Preserve original A/B chronology fields even when proxy fields are set.
    r = _record(
        event_start_date="2020/09/01",
        outbreak_start_date="2020/09/15",
        confirmation_date="2020/12/18",
        report_date="2023/07/28",
        proxy_availability_date="2020/09/15",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
    )
    assert r.event_start_date == "2020/09/01"
    assert r.outbreak_start_date == "2020/09/15"
    assert r.confirmation_date == "2020/12/18"
    assert r.report_date == "2023/07/28"

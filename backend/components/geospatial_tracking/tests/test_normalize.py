import copy

from components.geospatial_tracking.data_processing.normalize import (
    assign_spatial_independence,
    make_source_record_id,
    normalize_raw_records,
)
from components.geospatial_tracking.schemas import AvailabilityQuality, GpsQuality, RawOutbreakRecord, SourceSystem


def _csv_record(**overrides):
    fields = dict(
        source_file="fixture.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        event_id="UNFAO-LEG-1",
        onset_date="2020-09-07",
        report_date="2021-01-19",
        latitude=9.71517,
        longitude=80.066849,
        species="Domestic - Cattle",
        proxy_availability_date="2020-09-07",
        proxy_availability_quality=AvailabilityQuality.OBSERVATION_DATE_PROXY.value,
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _wahis_record(**overrides):
    fields = dict(
        source_file="fixture.pdf",
        source_system=SourceSystem.WAHIS_PDF.value,
        country="Sri Lanka",
        outbreak_id="OB_1",
        outbreak_start_date="2020/09/07",
        report_date="2023/07/28",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        species="cattle (domestic)",
        proxy_availability_date="2020/09/07",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def test_source_record_id_is_deterministic():
    assert make_source_record_id("FAO_EMPRESI_CSV", "a.csv", 3) == make_source_record_id(
        "FAO_EMPRESI_CSV", "a.csv", 3
    )
    assert make_source_record_id("FAO_EMPRESI_CSV", "a.csv", 3) != make_source_record_id(
        "FAO_EMPRESI_CSV", "a.csv", 4
    )


def test_normalize_is_deterministic_across_runs():
    raw = [_csv_record(), _wahis_record()]
    ids_run1 = [r.source_record_id for r in normalize_raw_records(raw)]
    ids_run2 = [r.source_record_id for r in normalize_raw_records(raw)]
    assert ids_run1 == ids_run2


def test_normalize_does_not_mutate_raw_records():
    raw = [_csv_record()]
    raw_before = copy.deepcopy(raw[0])
    normalize_raw_records(raw)
    assert raw[0] == raw_before


def test_normalize_does_not_invent_missing_values():
    raw = [_csv_record(admin1=None, diagnostic_method=None)]
    normalized = normalize_raw_records(raw)[0]
    assert normalized.admin1 is None
    assert normalized.diagnostic_method is None
    # this source has no susceptible/cases/deaths columns at all
    assert normalized.susceptible is None
    assert normalized.cases is None


def test_proxy_availability_source_field_inferred_for_wahis():
    raw = [_wahis_record()]
    normalized = normalize_raw_records(raw)[0]
    assert normalized.proxy_availability_source_field == "outbreak_start_date"


def test_proxy_availability_source_field_inferred_for_csv():
    raw = [_csv_record()]
    normalized = normalize_raw_records(raw)[0]
    assert normalized.proxy_availability_source_field == "observation_date"


def test_proxy_availability_source_field_none_when_no_proxy_set():
    raw = [
        _csv_record(
            proxy_availability_date=None,
            proxy_availability_quality=AvailabilityQuality.UNKNOWN.value,
        )
    ]
    normalized = normalize_raw_records(raw)[0]
    assert normalized.proxy_availability_source_field is None


def test_spatial_independence_true_for_unique_exact_coordinate():
    raw = [_wahis_record(outbreak_id="OB_1", locality="Kopay")]
    normalized = normalize_raw_records(raw)
    assign_spatial_independence(normalized)
    assert normalized[0].spatial_independence is True


def test_spatial_independence_false_for_shared_approximate_coordinate():
    raw = [
        _wahis_record(
            outbreak_id="OB_A",
            locality="Village A",
            latitude=18.689547,
            longitude=98.994437,
            gps_quality=GpsQuality.APPROXIMATE.value,
            approximate_location=True,
        ),
        _wahis_record(
            outbreak_id="OB_B",
            locality="Village B",
            latitude=18.689547,
            longitude=98.994437,
            gps_quality=GpsQuality.APPROXIMATE.value,
            approximate_location=True,
        ),
    ]
    normalized = normalize_raw_records(raw)
    assign_spatial_independence(normalized)
    assert normalized[0].spatial_independence is False
    assert normalized[1].spatial_independence is False


def test_spatial_independence_none_when_coordinates_missing():
    raw = [_csv_record(latitude=None, longitude=None)]
    normalized = normalize_raw_records(raw)
    assign_spatial_independence(normalized)
    assert normalized[0].spatial_independence is None

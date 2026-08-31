from components.geospatial_tracking.data_processing.normalize import normalize_raw_records
from components.geospatial_tracking.data_processing.quality import HIGH, LOW, MEDIUM, UNKNOWN, compute_quality
from components.geospatial_tracking.schemas import AvailabilityQuality, GpsQuality, RawOutbreakRecord, SourceSystem


def _rich_wahis_record():
    raw = RawOutbreakRecord(
        source_file="Event_3473.pdf",
        source_system=SourceSystem.WAHIS_PDF.value,
        country="Sri Lanka",
        event_id="3473",
        outbreak_id="OB_80063",
        admin1=None,
        locality="Kopay",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        outbreak_start_date="2020/09/07",
        species="cattle (domestic)",
        susceptible=10,
        cases=3,
        deaths=1,
        vaccinated=0,
        diagnostic_method="Clinical, Diagnostic test",
        diagnostic_result="Confirmed",
        event_status="Stable",
        operational_availability_date="2020/09/10",
        operational_availability_quality=AvailabilityQuality.ACTUAL.value,
    )
    return normalize_raw_records([raw])[0]


def _sparse_csv_record():
    raw = RawOutbreakRecord(
        source_file="events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        event_id="UNFAO-LEG-1",
        report_date="2021-01-19",
    )
    return normalize_raw_records([raw])[0]


def test_rich_record_scores_high_on_most_components():
    q = compute_quality(_rich_wahis_record())
    assert q.gps_quality == HIGH
    assert q.date_quality == HIGH
    assert q.diagnostic_quality == HIGH
    assert q.identifier_quality == HIGH
    assert q.availability_quality == HIGH
    assert q.dqs > 0.9


def test_sparse_record_scores_low_or_unknown():
    q = compute_quality(_sparse_csv_record())
    assert q.gps_quality == UNKNOWN
    assert q.diagnostic_quality == UNKNOWN
    assert q.identifier_quality == MEDIUM  # event_id present, outbreak_id absent
    assert q.date_quality == LOW  # only report_date present
    assert q.dqs < 0.5


def test_component_level_values_are_always_present_alongside_composite():
    q = compute_quality(_sparse_csv_record()).as_dict()
    for key in (
        "gps_quality",
        "date_quality",
        "diagnostic_quality",
        "identifier_quality",
        "completeness_quality",
        "availability_quality",
        "dqs",
    ):
        assert key in q


def test_availability_quality_component_distinguishes_actual_from_proxy():
    actual_record = _rich_wahis_record()
    assert compute_quality(actual_record).availability_quality == HIGH

    proxy_raw = RawOutbreakRecord(
        source_file="events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        proxy_availability_date="2020-09-07",
        proxy_availability_quality=AvailabilityQuality.OBSERVATION_DATE_PROXY.value,
    )
    proxy_record = normalize_raw_records([proxy_raw])[0]
    assert compute_quality(proxy_record).availability_quality == MEDIUM

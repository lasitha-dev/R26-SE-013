"""DATE-04/05/06/07."""

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.services.historical_event_date import derive_historical_event_date


def test_date_04_wahis_outbreak_start_date_becomes_event_date_with_provenance():
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        outbreak_start_date="2020/09/07",
        event_start_date="2020/09/01",
        report_date="2023/07/28",
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date == "2020/09/07"
    assert result.historical_event_date_quality == "HIGH"
    assert result.historical_event_date_source_field == "outbreak_start_date"


def test_wahis_falls_back_to_event_start_date_when_outbreak_start_date_missing():
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_9999.pdf:000001",
        outbreak_start_date=None,
        event_start_date="2020/09/01",
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date == "2020/09/01"
    assert result.historical_event_date_quality == "MEDIUM"
    assert result.historical_event_date_source_field == "event_start_date"


def test_date_05_csv_onset_date_preserved_with_provenance():
    record = HistoricalOutbreakRecord(
        source_record_id="FAO_EMPRESI_CSV:events.csv:000001",
        onset_date="2020-09-07",
        report_date="2021-01-19",
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date == "2020-09-07"
    assert result.historical_event_date_quality == "HIGH"
    assert result.historical_event_date_source_field == "onset_date"


def test_fmd05_bigquery_csv_onset_date_preserved_with_provenance():
    """FMD-05: FAO_EMPRESI_BIGQUERY_CSV (FMD-03's source system) must get
    the same HIGH-confidence treatment as FAO_EMPRESI_CSV's onset_date —
    previously fell through to the generic MEDIUM-confidence fallback
    branch because this source system had no dedicated branch."""
    record = HistoricalOutbreakRecord(
        source_record_id="FAO_EMPRESI_BIGQUERY_CSV:EMPRES-i_FMD_events_2002-2026.csv:000001",
        onset_date="2026-08-07",
        report_date="2026-08-09",
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date == "2026-08-07"
    assert result.historical_event_date_quality == "HIGH"
    assert result.historical_event_date_source_field == "onset_date"


def test_date_06_report_date_can_never_become_historical_event_date():
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        outbreak_start_date=None,
        event_start_date=None,
        report_date="2023/07/28",  # the only date present — must NOT be used
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date is None
    assert result.historical_event_date != "2023/07/28"
    assert result.historical_event_date_quality == "UNKNOWN"


def test_date_06_csv_report_date_also_never_used():
    record = HistoricalOutbreakRecord(
        source_record_id="FAO_EMPRESI_CSV:events.csv:000001",
        onset_date=None,
        report_date="2021-01-19",
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date is None
    assert result.historical_event_date_quality == "UNKNOWN"


def test_proxy_availability_date_never_used_even_when_convenient():
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        outbreak_start_date=None,
        event_start_date=None,
        proxy_availability_date="2020/09/07",  # documented, easy to grab — but wrong concept
    )
    result = derive_historical_event_date(record)
    assert result.historical_event_date is None
    assert result.historical_event_date_quality == "UNKNOWN"


def test_date_07_unknown_occurrence_date_remains_unknown():
    record = HistoricalOutbreakRecord(source_record_id="H1")
    result = derive_historical_event_date(record)
    assert result.historical_event_date is None
    assert result.historical_event_date_quality == "UNKNOWN"
    assert result.historical_event_date_source_field is None


def test_original_date_fields_are_never_mutated():
    record = HistoricalOutbreakRecord(
        source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
        outbreak_start_date="2020/09/07",
        event_start_date="2020/09/01",
        confirmation_date="2020/12/18",
        report_date="2023/07/28",
    )
    derive_historical_event_date(record)
    assert record.outbreak_start_date == "2020/09/07"
    assert record.event_start_date == "2020/09/01"
    assert record.confirmation_date == "2020/12/18"
    assert record.report_date == "2023/07/28"

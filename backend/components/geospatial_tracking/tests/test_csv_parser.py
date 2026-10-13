"""Tests for the FAO EMPRES-i CSV parser.

Fixtures are synthetic (fabricated coordinates/IDs modeled on the real
column layout) rather than copies of local_data/pistes_raw, which must
never be committed.
"""

import csv

import pytest

from components.geospatial_tracking.data_processing.csv_parser import parse_csv_file, parse_csv_row
from components.geospatial_tracking.schemas import AvailabilityQuality, GpsQuality, SourceSystem

HEADER = [
    "Event ID",
    "Disease",
    "Serotype",
    "latitude",
    "longitude",
    "Locality",
    "Country",
    "Region",
    "observation date",
    "report date",
    "Species",
    "Diagnosis Source",
    "Humans Affected",
    "Human Deaths",
    "Diagnosis Status",
]

SAMPLE_ROW = {
    "Event ID": "UNFAO-LEG-999999",
    "Disease": "Lumpy skin disease",
    "Serotype": "",
    "latitude": "7.123456",
    "longitude": "81.654321",
    "Locality": "12345TESTVILLE",
    "Country": "Sri Lanka",
    "Region": "Asia",
    "observation date": "2022-05-01",
    "report date": "2022-05-10",
    "Species": "Domestic - Cattle",
    "Diagnosis Source": "WOAH (former OIE)",
    "Humans Affected": "",
    "Human Deaths": "",
    "Diagnosis Status": "Confirmed",
}


def test_parse_csv_row_maps_canonical_fields():
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")

    assert record.source_system == SourceSystem.FAO_EMPRESI_CSV.value
    assert record.country == "Sri Lanka"
    assert record.event_id == "UNFAO-LEG-999999"
    assert record.latitude == pytest.approx(7.123456)
    assert record.longitude == pytest.approx(81.654321)
    assert record.species == "Domestic - Cattle"
    assert record.diagnostic_result == "Confirmed"


def test_csv_source_never_fabricates_animal_counts():
    # This CSV source has no susceptible/cases/deaths/vaccinated columns at all —
    # the parser must not invent zeros or copy human-health fields into them.
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")
    assert record.susceptible is None
    assert record.cases is None
    assert record.deaths is None
    assert record.killed_disposed is None
    assert record.vaccinated is None


def test_csv_gps_quality_is_unknown_not_exact():
    # This source never states GPS precision explicitly, so it must not be
    # marked EXACT just because a coordinate is present.
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")
    assert record.gps_quality == GpsQuality.UNKNOWN.value
    assert record.approximate_location is False


def test_csv_operational_availability_is_unknown_not_inferred_from_report_date():
    # This source has no true "system knew by" timestamp. report_date must
    # never be silently promoted into operational_availability_date.
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")
    assert record.operational_availability_date is None
    assert record.operational_availability_quality == AvailabilityQuality.UNKNOWN.value
    assert record.report_date == "2022-05-10"


def test_csv_proxy_availability_uses_observation_date_and_is_labeled():
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")
    assert record.proxy_availability_date == "2022-05-01"
    assert record.proxy_availability_quality == AvailabilityQuality.OBSERVATION_DATE_PROXY.value
    # onset/observation date must stay separate from the availability proxy
    assert record.onset_date == "2022-05-01"


def test_csv_proxy_availability_unknown_when_observation_date_missing():
    row = dict(SAMPLE_ROW, **{"observation date": ""})
    record = parse_csv_row(row, source_file="fixture.csv")
    assert record.proxy_availability_date is None
    assert record.proxy_availability_quality == AvailabilityQuality.UNKNOWN.value


def test_csv_region_is_not_mapped_to_admin1():
    # "Region" in this source is a continent grouping (Europe/Asia/Africa),
    # not an administrative subdivision — collapsing it into admin1 would
    # misrepresent it as a district/province.
    record = parse_csv_row(SAMPLE_ROW, source_file="fixture.csv")
    assert record.admin1 is None
    assert record.extra["region_continent"] == "Asia"


def test_parse_csv_file_missing_column_raises(tmp_path):
    bad_header = [c for c in HEADER if c != "latitude"]
    path = tmp_path / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=bad_header)
        writer.writeheader()
    with pytest.raises(ValueError, match="missing expected columns"):
        parse_csv_file(path)


def test_parse_csv_file_round_trip(tmp_path):
    path = tmp_path / "sample.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow(SAMPLE_ROW)
    records = parse_csv_file(path)
    assert len(records) == 1
    assert records[0].source_file == "sample.csv"
    assert records[0].event_id == "UNFAO-LEG-999999"

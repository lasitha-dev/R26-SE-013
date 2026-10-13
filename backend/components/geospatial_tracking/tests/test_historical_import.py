import csv

from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.historical_import import (
    import_conservative_csv,
    load_conservative_csv,
    parse_conservative_row,
)

HEADER = [
    "source_record_id", "country", "disease", "event_id", "outbreak_id",
    "event_start_date", "outbreak_start_date", "onset_date", "confirmation_date", "report_date",
    "operational_availability_date", "operational_availability_quality",
    "proxy_availability_date", "proxy_availability_quality", "proxy_availability_source_field",
    "latitude", "longitude", "gps_quality", "species",
    "dedup_status", "dedup_confidence", "model_candidate", "duplicate_group_id", "member_record_ids",
]

ROW_MODEL_CANDIDATE = {
    "source_record_id": "H1", "country": "Thailand", "disease": "Lumpy skin disease",
    "event_id": "", "outbreak_id": "OB_1",
    "event_start_date": "", "outbreak_start_date": "2026/01/05", "onset_date": "", "confirmation_date": "", "report_date": "",
    "operational_availability_date": "", "operational_availability_quality": "UNKNOWN",
    "proxy_availability_date": "2026/01/05", "proxy_availability_quality": "EVENT_DATE_PROXY",
    "proxy_availability_source_field": "outbreak_start_date",
    "latitude": "15.0", "longitude": "101.0", "gps_quality": "EXACT", "species": "cattle",
    "dedup_status": "AUTO_MERGED_HIGH", "dedup_confidence": "HIGH", "model_candidate": "True",
    "duplicate_group_id": "DUPGRP:1", "member_record_ids": "H1;H2",
}

ROW_NOT_MODEL_CANDIDATE = dict(
    ROW_MODEL_CANDIDATE,
    source_record_id="H3",
    dedup_status="REVIEW_MEDIUM",
    dedup_confidence="MEDIUM",
    model_candidate="False",
    duplicate_group_id="DUPGRP:2",
    member_record_ids="H3",
)


def _write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_parse_conservative_row_maps_all_fields():
    record = parse_conservative_row(ROW_MODEL_CANDIDATE)
    assert record.source_record_id == "H1"
    assert record.country == "Thailand"
    assert record.disease == "Lumpy skin disease"
    assert record.outbreak_start_date == "2026/01/05"
    assert record.proxy_availability_date == "2026/01/05"
    assert record.proxy_availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value
    assert record.proxy_availability_source_field == "outbreak_start_date"
    assert record.operational_availability_quality == AvailabilityQuality.UNKNOWN.value
    assert record.latitude == 15.0
    assert record.longitude == 101.0
    assert record.gps_quality == GpsQuality.EXACT.value
    assert record.dedup_status == DedupStatus.AUTO_MERGED_HIGH.value
    assert record.model_candidate is True
    assert record.duplicate_group_id == "DUPGRP:1"
    assert record.member_record_ids == "H1;H2"


def test_parse_conservative_row_supports_canonical_modelling_eligible_and_legacy_precedence():
    canonical_row = dict(ROW_MODEL_CANDIDATE)
    canonical_row.pop("model_candidate")
    canonical_row["modelling_eligible"] = "True"
    assert parse_conservative_row(canonical_row).model_candidate is True

    legacy_row = dict(ROW_MODEL_CANDIDATE, model_candidate="False", modelling_eligible="True")
    assert parse_conservative_row(legacy_row).model_candidate is False


def test_import_preserves_full_corpus_including_non_model_candidates(tmp_path):
    # CRITICAL: import must NOT silently drop REVIEW_MEDIUM/LOW rows —
    # they must still exist in storage so the source-selector gate has
    # something real to prove it excludes (see test_source_selector.py
    # SOURCE-09/10/11).
    csv_path = tmp_path / "conservative.csv"
    _write_csv(csv_path, [ROW_MODEL_CANDIDATE, ROW_NOT_MODEL_CANDIDATE])

    repo = SQLiteOutbreakRepository(tmp_path / "test.db")
    repo.init_schema()
    count = import_conservative_csv(repo, csv_path)
    assert count == 2

    all_records = repo.list_historical_records()
    assert {r.source_record_id for r in all_records} == {"H1", "H3"}
    excluded = repo.get_historical_record("H3")
    assert excluded.model_candidate is False
    assert excluded.dedup_status == DedupStatus.REVIEW_MEDIUM.value
    repo.close()


def test_load_conservative_csv_never_mutates_the_source_file(tmp_path):
    csv_path = tmp_path / "conservative.csv"
    _write_csv(csv_path, [ROW_MODEL_CANDIDATE])
    before = csv_path.read_text(encoding="utf-8")
    load_conservative_csv(csv_path)
    after = csv_path.read_text(encoding="utf-8")
    assert before == after


def test_blank_optional_fields_become_none_not_empty_string(tmp_path):
    row = dict(ROW_MODEL_CANDIDATE, event_id="", outbreak_id="")
    csv_path = tmp_path / "conservative.csv"
    _write_csv(csv_path, [row])
    records = load_conservative_csv(csv_path)
    assert records[0].event_id is None
    assert records[0].outbreak_id is None

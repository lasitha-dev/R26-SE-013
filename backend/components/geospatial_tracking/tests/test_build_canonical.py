from components.geospatial_tracking.data_processing.build_canonical import (
    build_canonical_rows,
    build_dedup_report_rows,
    build_quality_report_rows,
)
from components.geospatial_tracking.data_processing.normalize import (
    assign_spatial_independence,
    normalize_raw_records,
)
from components.geospatial_tracking.schemas import GpsQuality, RawOutbreakRecord, SourceSystem


def _csv(**overrides):
    fields = dict(
        source_file="events.csv",
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country="Sri Lanka",
        event_id="UNFAO-LEG-1",
        onset_date="2020-09-07",
        locality="Kopay",
        latitude=9.71517,
        longitude=80.066849,
        species="Domestic - Cattle",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _wahis(**overrides):
    fields = dict(
        source_file="Event_3473.pdf",
        source_system=SourceSystem.WAHIS_PDF.value,
        country="Sri Lanka",
        outbreak_id="OB_80063",
        outbreak_start_date="2020/09/07",
        locality="Kopay",
        latitude=9.7151701,
        longitude=80.0668497,
        gps_quality=GpsQuality.EXACT.value,
        species="cattle (domestic)",
    )
    fields.update(overrides)
    return RawOutbreakRecord(**fields)


def _normalize(raw_records):
    normalized = normalize_raw_records(raw_records)
    assign_spatial_independence(normalized)
    return normalized


def test_merged_group_produces_one_canonical_row():
    norm = _normalize([_csv(), _wahis()])
    rows, groups = build_canonical_rows(norm)
    assert len(rows) == 1
    assert rows[0]["member_count"] == 2
    assert rows[0]["duplicate_group_id"] == groups[0].duplicate_group_id


def test_singleton_record_produces_its_own_row_unmodified():
    norm = _normalize([_wahis(country="Vietnam", locality="Solo Village")])
    rows, groups = build_canonical_rows(norm)
    assert len(rows) == 1
    assert rows[0]["duplicate_group_id"] == ""
    assert rows[0]["member_count"] == 1
    assert rows[0]["country"] == "Vietnam"
    assert groups == []


def test_low_confidence_candidates_stay_as_separate_canonical_rows():
    raw = [
        _wahis(
            outbreak_id="OB_A",
            locality="Village A",
            outbreak_start_date="2024/03/01",
            latitude=18.689547,
            longitude=98.994437,
            gps_quality=GpsQuality.APPROXIMATE.value,
            approximate_location=True,
            country="Thailand",
        ),
        _wahis(
            outbreak_id="OB_B",
            locality="Village B",
            outbreak_start_date="2024/03/02",
            latitude=18.689547,
            longitude=98.994437,
            gps_quality=GpsQuality.APPROXIMATE.value,
            approximate_location=True,
            country="Thailand",
        ),
    ]
    norm = _normalize(raw)
    rows, groups = build_canonical_rows(norm)
    # LOW confidence -> NOT merged: both members remain as separate rows
    assert len(rows) == 2
    assert all(r["member_count"] == 1 for r in rows)
    assert all(r["dedup_confidence"] == "LOW" for r in rows)
    assert all(r["review_required"] is True for r in rows)
    assert len(groups) == 1
    assert groups[0].merged is False


def test_canonical_row_preserves_source_provenance():
    norm = _normalize([_csv(), _wahis()])
    rows, _ = build_canonical_rows(norm)
    row = rows[0]
    # canonical row is one real member's own fields (WAHIS, richer record)
    assert row["source_system"] == SourceSystem.WAHIS_PDF.value
    assert row["source_file"] == "Event_3473.pdf"


def test_dedup_report_rows_have_required_columns():
    norm = _normalize([_csv(), _wahis()])
    _, groups = build_canonical_rows(norm)
    report = build_dedup_report_rows(groups)
    assert len(report) == 1
    row = report[0]
    for key in (
        "duplicate_group_id",
        "canonical_record_id",
        "member_record_ids",
        "match_rule",
        "match_features",
        "dedup_confidence",
        "review_required",
        "notes",
    ):
        assert key in row


def test_quality_report_covers_every_normalized_record_not_just_canonical():
    norm = _normalize([_csv(), _wahis()])
    quality_rows = build_quality_report_rows(norm)
    assert len(quality_rows) == 2  # pre-dedup — both source records get a quality row

"""COORD-01..07."""

from components.geospatial_tracking.domain.enums import CoordinateCollisionStatus
from components.geospatial_tracking.schemas import DedupStatus, GpsQuality
from components.geospatial_tracking.services.coordinate_collision import compute_coordinate_collision_status


def _row(**overrides):
    fields = dict(
        source_record_id="H1",
        latitude="9.71517",
        longitude="80.066849",
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
    )
    fields.update(overrides)
    return fields


def test_coord_01_auto_merged_high_row_does_not_count_against_itself():
    # An AUTO_MERGED_HIGH group is already ONE conservative row (its raw
    # pre-dedup members never reach this function) — with nothing else at
    # that coordinate, it must come back unique.
    rows = [
        _row(source_record_id="WAHIS_PDF:Event_3473.pdf:000002", latitude="9.7151701", longitude="80.0668497"),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0"),  # unrelated, distant
    ]
    results = compute_coordinate_collision_status(rows)
    kopay = next(r for r in results if r.source_record_id == "WAHIS_PDF:Event_3473.pdf:000002")
    assert kopay.coordinate_collision_status == CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
    assert kopay.resolved_shared_count == 0
    assert kopay.unresolved_shared_count == 0


def test_coord_02_two_resolved_outbreaks_sharing_coordinate_labeled_shared_with_resolved():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0", dedup_status=DedupStatus.AUTO_MERGED_HIGH.value),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0", dedup_status=DedupStatus.SINGLETON.value),
    ]
    results = compute_coordinate_collision_status(rows)
    for r in results:
        assert r.coordinate_collision_status == CoordinateCollisionStatus.SHARED_WITH_RESOLVED.value
        assert r.resolved_shared_count == 1
        assert r.unresolved_shared_count == 0


def test_coord_03_resolved_outbreak_sharing_only_with_review_low_is_shared_with_unresolved():
    # The exact Sri Lanka Chavakachcheri pattern.
    rows = [
        _row(
            source_record_id="WAHIS_PDF:Event_3473.pdf:000002",
            latitude="9.6579014", longitude="80.1643076",
            dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        ),
        _row(
            source_record_id="FAO_EMPRESI_CSV:events.csv:000066",
            latitude="9.6579014", longitude="80.1643076",
            dedup_status=DedupStatus.REVIEW_LOW.value,
        ),
    ]
    results = compute_coordinate_collision_status(rows)
    resolved_row = next(r for r in results if r.source_record_id == "WAHIS_PDF:Event_3473.pdf:000002")
    assert resolved_row.coordinate_collision_status == CoordinateCollisionStatus.SHARED_WITH_UNRESOLVED.value
    assert resolved_row.resolved_shared_count == 0
    assert resolved_row.unresolved_shared_count == 1
    # NOT treated as definitively non-independent — this status is
    # explicitly the ambiguous/preserved-for-review one, distinct from
    # SHARED_WITH_RESOLVED.
    assert resolved_row.coordinate_collision_status != CoordinateCollisionStatus.SHARED_WITH_RESOLVED.value


def test_coord_04_resolved_outbreak_sharing_both_resolved_and_unresolved_gets_shared_with_both():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0", dedup_status=DedupStatus.AUTO_MERGED_HIGH.value),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0", dedup_status=DedupStatus.SINGLETON.value),
        _row(source_record_id="H3", latitude="15.0", longitude="100.0", dedup_status=DedupStatus.REVIEW_LOW.value),
    ]
    results = compute_coordinate_collision_status(rows)
    h1 = next(r for r in results if r.source_record_id == "H1")
    assert h1.coordinate_collision_status == CoordinateCollisionStatus.SHARED_WITH_BOTH.value
    assert h1.resolved_shared_count == 1
    assert h1.unresolved_shared_count == 1


def test_coord_05_unique_resolved_outbreak_gets_unique_among_resolved():
    rows = [_row(source_record_id="H1", latitude="9.0", longitude="80.0")]
    results = compute_coordinate_collision_status(rows)
    assert results[0].coordinate_collision_status == CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value


def test_coord_06_approximate_gps_never_becomes_exact_due_to_uniqueness():
    rows = [_row(source_record_id="H1", latitude="15.0", longitude="100.0", gps_quality=GpsQuality.APPROXIMATE.value)]
    results = compute_coordinate_collision_status(rows)
    r = results[0]
    assert r.gps_quality == GpsQuality.APPROXIMATE.value  # never upgraded
    assert r.coordinate_collision_status == CoordinateCollisionStatus.UNIQUE_AMONG_RESOLVED.value
    assert "APPROXIMATE" in r.reason  # caution explicitly noted


def test_coord_07_raw_pre_dedup_spatial_flag_untouched():
    # This module must never touch Checkpoint 2's raw
    # `spatial_independence` column, and must never emit the superseded
    # `canonical_spatial_independence` field as one of its own output
    # keys (docstring prose referencing the old name for context is fine).
    from components.geospatial_tracking.services.coordinate_collision import CoordinateCollisionRow
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(CoordinateCollisionRow)}
    assert "spatial_independence" not in field_names
    assert "canonical_spatial_independence" not in field_names


def test_missing_coordinates_get_missing_coordinate_status():
    rows = [_row(source_record_id="H1", latitude="", longitude="")]
    results = compute_coordinate_collision_status(rows)
    assert results[0].coordinate_collision_status == CoordinateCollisionStatus.MISSING_COORDINATE.value


def test_shared_coordinate_group_id_deterministic_across_runs():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0"),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0"),
        _row(source_record_id="H3", latitude="9.0", longitude="80.0"),
    ]
    r1 = compute_coordinate_collision_status(rows)
    r2 = compute_coordinate_collision_status(rows)
    assert [x.shared_coordinate_group_id for x in r1] == [x.shared_coordinate_group_id for x in r2]

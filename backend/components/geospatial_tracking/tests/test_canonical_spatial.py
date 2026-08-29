"""SPATIAL-01/02/03."""

from components.geospatial_tracking.schemas import DedupStatus, GpsQuality
from components.geospatial_tracking.services.canonical_spatial import compute_canonical_spatial_independence


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


def test_spatial_01_high_merged_canonical_row_is_independent_despite_raw_duplicate_history():
    # After HIGH merging, the group is represented by ONE conservative
    # row with ONE coordinate — even though its raw pre-dedup members
    # (2 CSV rows + 1 WAHIS outbreak) shared that coordinate across
    # sources, that never even reaches this function's input.
    rows = [
        _row(source_record_id="WAHIS_PDF:Event_3473.pdf:000002", latitude="9.7151701", longitude="80.0668497"),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0"),  # unrelated, distant
    ]
    results = compute_canonical_spatial_independence(rows)
    kopay = next(r for r in results if r.source_record_id == "WAHIS_PDF:Event_3473.pdf:000002")
    assert kopay.canonical_spatial_independence is True
    assert kopay.shared_coordinate_count == 1


def test_spatial_02_two_distinct_canonical_outbreaks_sharing_a_coordinate_are_flagged():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0"),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0"),
    ]
    results = compute_canonical_spatial_independence(rows)
    assert all(r.canonical_spatial_independence is False for r in results)
    assert all(r.shared_coordinate_count == 2 for r in results)
    assert results[0].shared_coordinate_group_id == results[1].shared_coordinate_group_id


def test_spatial_03_approximate_gps_is_preserved_and_not_upgraded():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0", gps_quality=GpsQuality.APPROXIMATE.value),
    ]
    results = compute_canonical_spatial_independence(rows)
    r = results[0]
    assert r.gps_quality == GpsQuality.APPROXIMATE.value  # not silently changed to EXACT
    assert r.canonical_spatial_independence is True  # unique, but...
    assert "APPROXIMATE" in r.reason  # ...caution explicitly noted, not silently asserted with full confidence


def test_missing_coordinates_cannot_be_assessed():
    rows = [_row(source_record_id="H1", latitude="", longitude="")]
    results = compute_canonical_spatial_independence(rows)
    assert results[0].canonical_spatial_independence is None
    assert "missing coordinates" in results[0].reason


def test_shared_coordinate_group_id_deterministic_across_runs():
    rows = [
        _row(source_record_id="H1", latitude="15.0", longitude="100.0"),
        _row(source_record_id="H2", latitude="15.0", longitude="100.0"),
        _row(source_record_id="H3", latitude="9.0", longitude="80.0"),
    ]
    r1 = compute_canonical_spatial_independence(rows)
    r2 = compute_canonical_spatial_independence(rows)
    assert [x.shared_coordinate_group_id for x in r1] == [x.shared_coordinate_group_id for x in r2]


def test_raw_spatial_independence_column_not_referenced_or_overwritten():
    # This module must never touch the pre-dedup `spatial_independence`
    # column at all — it only ever reads latitude/longitude/gps_quality.
    import inspect

    from components.geospatial_tracking.services import canonical_spatial

    src = inspect.getsource(canonical_spatial)
    assert '"spatial_independence"' not in src
    assert "row['spatial_independence']" not in src

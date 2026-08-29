"""Parameter-candidate registry tests (Part 17) — pure, synthetic, no network."""

from __future__ import annotations

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.stdbscan.parameter_candidates import (
    ACTIVE_WINDOW_DAY_CANDIDATES,
    build_legacy_parameter_candidate_report,
)


def _historical(**overrides) -> HistoricalOutbreakRecord:
    fields = dict(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2021/06/01",
        proxy_availability_date="2021/06/01",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def test_active_window_candidates_are_fixed_not_derived():
    assert ACTIVE_WINDOW_DAY_CANDIDATES == (7, 14, 21, 28)


def test_sri_lanka_records_excluded_from_candidate_geometry():
    records = [
        _historical(source_record_id="SL1", country="Sri Lanka", latitude=9.0, longitude=80.0, outbreak_start_date="2020/06/01"),
        _historical(source_record_id="TH1", country="Thailand", latitude=15.0, longitude=101.0, outbreak_start_date="2021/06/01"),
        _historical(source_record_id="TH2", country="Thailand", latitude=15.01, longitude=101.0, outbreak_start_date="2021/06/03"),
    ]
    report = build_legacy_parameter_candidate_report(records)
    # only the 2 Thailand records are usable -- Sri Lanka is excluded
    # regardless of its real pre-cutoff date
    assert report.n_fit_development_usable_records == 2


def test_held_out_2024_records_excluded_from_candidate_geometry():
    records = [
        _historical(source_record_id="OLD1", outbreak_start_date="2021/06/01", latitude=15.0, longitude=101.0),
        _historical(source_record_id="NEW1", outbreak_start_date="2024/06/01", latitude=15.01, longitude=101.0),
    ]
    report = build_legacy_parameter_candidate_report(records)
    assert report.n_fit_development_usable_records == 1


def test_quantiles_computed_from_real_synthetic_distances():
    records = [
        _historical(source_record_id=f"T{i}", latitude=15.0 + i * 0.01, longitude=101.0, outbreak_start_date=f"2021/06/{i+1:02d}")
        for i in range(5)
    ]
    report = build_legacy_parameter_candidate_report(records)
    assert report.n_fit_development_usable_records == 5
    q = report.nearest_neighbor_distance_km_quantiles
    assert q["p25"] is not None and q["p50"] is not None and q["p75"] is not None
    assert q["p25"] <= q["p50"] <= q["p75"]

    tq = report.positive_temporal_gap_days_quantiles
    assert tq["p50"] == 1.0  # consecutive days


def test_pathological_case_reported_not_hidden():
    records = [_historical(source_record_id="ONLY1")]
    report = build_legacy_parameter_candidate_report(records)
    assert report.pathological_note is not None
    assert report.nearest_neighbor_distance_km_quantiles["p50"] is None


def test_no_positive_gaps_reported_when_all_same_date():
    records = [
        _historical(source_record_id="A", latitude=15.0, longitude=101.0, outbreak_start_date="2021/06/01"),
        _historical(source_record_id="B", latitude=15.01, longitude=101.0, outbreak_start_date="2021/06/01"),
    ]
    report = build_legacy_parameter_candidate_report(records)
    assert report.positive_temporal_gap_days_quantiles["p50"] is None
    assert report.pathological_note is not None

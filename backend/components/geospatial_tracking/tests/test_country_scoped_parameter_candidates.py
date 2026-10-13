"""Checkpoint 6B.5 Parts 7-11: country-scoped parameter-candidate
registry — PARAM-COUNTRY-01..05, MINPTS-01."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.stdbscan.candidate_constants import MIN_CORE_SUPPORT_CANDIDATES
from components.geospatial_tracking.services.stdbscan.development_source_universe import DevelopmentSource
from components.geospatial_tracking.services.stdbscan.parameter_candidates import build_country_scoped_parameter_candidates


def _source(**overrides) -> DevelopmentSource:
    fields = dict(
        source_id="S1",
        country="Thailand",
        first_fit_origin_t0_seen="2021-06-01",
        last_fit_origin_t0_seen="2021-06-01",
        effective_availability_date="2021-06-01",
        availability_quality="EVENT_DATE_PROXY",
        cluster_event_date="2021/06/01",
        cluster_event_date_quality="HIGH",
        cluster_event_date_source_field="outbreak_start_date",
        latitude=15.0,
        longitude=101.0,
        gps_quality="EXACT",
        dedup_status="SINGLETON",
        model_candidate=True,
    )
    fields.update(overrides)
    return DevelopmentSource(**fields)


def test_param_country_01_nn_never_uses_another_country():
    # Thailand: two sources ~1.1km apart. Vietnam: one source placed
    # essentially on top of a Thailand source (near-zero cross-country
    # distance) -- if cross-country contamination occurred, Thailand's
    # nearest-neighbor distance would collapse toward ~0.
    sources = [
        _source(source_id="TH1", country="Thailand", latitude=15.000, longitude=101.000),
        _source(source_id="TH2", country="Thailand", latitude=15.010, longitude=101.000),
        _source(source_id="VN1", country="Vietnam", latitude=15.0001, longitude=101.0001),
    ]
    report = build_country_scoped_parameter_candidates(sources)
    th_stats = next(c for c in report.per_country_nn_distance if c["country"] == "Thailand")
    # TH1<->TH2 real geodesic distance is ~1.1km -- must not be near-zero
    assert th_stats["p50"] > 1.0


def test_param_country_02_temporal_gaps_never_bridge_countries():
    sources = [
        _source(source_id="TH1", country="Thailand", cluster_event_date="2021/06/01"),
        _source(source_id="TH2", country="Thailand", cluster_event_date="2021/06/10"),
        _source(source_id="VN1", country="Vietnam", cluster_event_date="2021/06/02"),
    ]
    report = build_country_scoped_parameter_candidates(sources)
    th_stats = next(c for c in report.per_country_temporal_gap if c["country"] == "Thailand")
    # only TH1/TH2 exist in Thailand -- gap must be exactly 9 days, never
    # shrunk by the Vietnam record's date
    assert th_stats["p50"] == 9.0


def test_param_country_03_sparse_single_record_country_reported():
    sources = [
        _source(source_id="TH1", country="Thailand", latitude=15.0, longitude=101.0),
        _source(source_id="TH2", country="Thailand", latitude=15.01, longitude=101.0),
        _source(source_id="LK1", country="Laos"),
    ]
    report = build_country_scoped_parameter_candidates(sources)
    countries = {c["country"] for c in report.per_country_nn_distance}
    assert "Laos" in countries
    laos_stats = next(c for c in report.per_country_nn_distance if c["country"] == "Laos")
    assert laos_stats["n_unique_sources"] == 1
    assert laos_stats["p50"] is None


def test_param_country_04_pooled_distribution_only_within_country():
    sources = [
        _source(source_id="TH1", country="Thailand", latitude=15.000, longitude=101.000, cluster_event_date="2021/06/01"),
        _source(source_id="TH2", country="Thailand", latitude=15.010, longitude=101.000, cluster_event_date="2021/06/10"),
        _source(source_id="VN1", country="Vietnam", latitude=15.0001, longitude=101.0001, cluster_event_date="2021/06/02"),
        _source(source_id="VN2", country="Vietnam", latitude=15.020, longitude=101.000, cluster_event_date="2021/06/03"),
    ]
    report = build_country_scoped_parameter_candidates(sources)
    # pooled NN distances = {TH1-TH2 dist, VN1-VN2 dist} only, never any
    # cross-country pairing -- exactly 2 contributing values
    pooled_p50 = report.pooled_within_country_nn_distance_km_quantiles["p50"]
    assert pooled_p50 is not None
    # pooled gaps = {9 (Thailand), 1 (Vietnam)} only
    assert report.pooled_within_country_temporal_gap_days_quantiles["p50"] is not None


def test_param_country_05_temporally_local_nn_audit_respects_28_day_window():
    sources = [
        # S1's spatially-nearest same-country neighbor (S2, ~1.1km) is 40
        # days away (outside the 28-day audit window); S3 is farther
        # (~5.5km) but only 10 days away -- the audit must pick S3.
        _source(source_id="S1", country="Thailand", latitude=15.000, longitude=101.000, cluster_event_date="2021/06/01"),
        _source(source_id="S2", country="Thailand", latitude=15.010, longitude=101.000, cluster_event_date="2021/07/11"),
        _source(source_id="S3", country="Thailand", latitude=15.050, longitude=101.000, cluster_event_date="2021/06/11"),
    ]
    report = build_country_scoped_parameter_candidates(sources)
    audit_p50 = report.temporally_local_nn_distance_audit_km_quantiles["p50"]
    assert audit_p50 is not None
    assert audit_p50 > 3.0  # reflects the ~5.5km S1<->S3 pair, not the ~1.1km S1<->S2 pair
    assert report.temporally_local_nn_audit_max_window_days == 28


def test_minpts_01_min_core_support_candidates_registry():
    assert MIN_CORE_SUPPORT_CANDIDATES == (2, 3, 4)
    report = build_country_scoped_parameter_candidates([_source()])
    assert report.min_core_support_candidates == [2, 3, 4]


def test_pathological_empty_universe_reported():
    report = build_country_scoped_parameter_candidates([])
    assert report.pathological_note is not None
    assert report.n_sources_considered == 0


def test_legacy_st_01_safe_path_cannot_consume_raw_historical_records():
    """Checkpoint 6C Part 0/39: the real, safe scientific parameter path
    must not silently accept an arbitrary raw `HistoricalOutbreakRecord`
    row. It is duck-typed on `DevelopmentSource`'s shape
    (`.source_id`/`.cluster_event_date`), which a raw historical record
    does not have (`.source_record_id`, no `.cluster_event_date` at
    all) — so passing one in fails loudly (AttributeError) rather than
    silently computing unsafe statistics."""
    from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
    from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality

    raw_record = HistoricalOutbreakRecord(
        source_record_id="H1",
        country="Thailand",
        disease="Lumpy skin disease",
        outbreak_start_date="2021/06/01",
        proxy_availability_date="2021/06/01",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        latitude=15.0,
        longitude=101.0,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
        model_candidate=True,
    )
    with pytest.raises(AttributeError):
        build_country_scoped_parameter_candidates([raw_record])

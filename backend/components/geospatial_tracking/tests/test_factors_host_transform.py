"""Checkpoint 6D Part 34 (HOST-01..08) / Checkpoint 6D.5 Part 24
(HOSTSAFE-01..08): host transform tests — corrected identity/safety API.

SUPERSEDED_BY_6D5_INDEX_CORRECTION: rewritten for
`compute_host_density_total`'s new unit-safety/NaN/negative checks and
`FactorReferenceProfile`'s new required fields.
"""

from __future__ import annotations

import math

from components.geospatial_tracking.services.factors.contracts import (
    BLOCKED,
    DEGENERATE_REFERENCE_DISTRIBUTION,
    MISSING,
    RAW_REAL_COMPONENT,
    REAL_TRANSFORMED_CANDIDATE,
    UNIT_MISMATCH,
)
from components.geospatial_tracking.services.factors.host_transform import (
    build_host_factor_candidates,
    compute_host_density_total,
    transform_empirical_cdf_reference,
    transform_log1p_robust_reference_scale,
)
from components.geospatial_tracking.services.factors.reference_profile import FactorReferenceProfile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig

_UNITS = "animals_per_km2"


def _real_fr(value, *, feature_name, dataset_version="2015", units=_UNITS):
    return {"feature_name": feature_name, "value": value, "units": units, "status": "REAL", "dataset_name": "GLW4", "dataset_version": dataset_version}


def _missing_fr(feature_name):
    return {"feature_name": feature_name, "value": None, "units": _UNITS, "status": "MISSING", "dataset_name": "GLW4", "dataset_version": "2015"}


def _blocked_fr(feature_name):
    return {"feature_name": feature_name, "value": None, "units": _UNITS, "status": "BLOCKED", "dataset_name": "GLW4", "dataset_version": "2015"}


def test_host_01_hostsafe_06_missing_input_not_converted_to_zero():
    cell = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _missing_fr("host_density_cattle_grid_cell"), "buffalo": _real_fr(5.0, feature_name="host_density_buffalo_grid_cell")}}
    raw = compute_host_density_total(cell)
    assert raw.host_density_total is None
    assert raw.host_density_total_status == MISSING


def test_host_02_hostsafe_05_real_zero_distinguishable_from_missing():
    cell_zero = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(0.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(0.0, feature_name="host_density_buffalo_grid_cell")}}
    cell_missing = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _missing_fr("host_density_cattle_grid_cell"), "buffalo": _missing_fr("host_density_buffalo_grid_cell")}}
    raw_zero = compute_host_density_total(cell_zero)
    raw_missing = compute_host_density_total(cell_missing)
    assert raw_zero.host_density_total == 0.0
    assert raw_zero.host_density_total_status == RAW_REAL_COMPONENT
    assert raw_missing.host_density_total is None
    assert raw_missing.host_density_total_status == MISSING


def _reference_profile(values, *, lower_q=0.05, upper_q=0.95):
    tc = FactorTransformConfig(log1p_reference_lower_quantile=lower_q, log1p_reference_upper_quantile=upper_q)
    sorted_values = sorted(values)
    log1p_values = sorted(math.log1p(v) for v in sorted_values)

    def _q(vals, q):
        if not vals:
            return None
        idx = q * (len(vals) - 1)
        lo = int(idx)
        hi = min(lo + 1, len(vals) - 1)
        frac = idx - lo
        return vals[lo] * (1 - frac) + vals[hi] * frac

    return FactorReferenceProfile(
        reference_profile_version="6D.2", development_role="FIT_DEVELOPMENT", development_cutoff="2024-01-01",
        included_origin_ids_digest="x", n_included_origins=1, country_coverage=("Thailand",), n_feature_snapshots_considered=1,
        host_density_total_raw_appearances=len(values), host_density_total_unique_observations=len(sorted_values),
        host_density_total_reference_values=tuple(sorted_values), host_density_total_observation_ids=tuple(f"OBS{i}" for i in range(len(sorted_values))),
        host_density_total_quantiles={"p05": _q(sorted_values, 0.05), "p50": _q(sorted_values, 0.5), "p95": _q(sorted_values, 0.95), "lower": _q(sorted_values, lower_q), "upper": _q(sorted_values, upper_q)},
        host_density_total_log1p_quantiles={"lower": _q(log1p_values, lower_q), "upper": _q(log1p_values, upper_q)},
        reference_observation_digest="digest", dataset_compatibility_stratum=None, n_incompatible_strata_detected=0,
        reference_compatibility_mode="STRICT_COMPATIBLE",
        n_reference_observation_conflicts=0, reference_observation_conflicts=(),
        n_host_species_observations_via_raster_identity=0, n_host_species_observations_via_query_centroid_fallback=0,
        weather_reference_observation_counts={}, dataset_version_composition={}, landcover_comparability_composition={}, weather_model_composition={},
        transform_config_hash=tc.config_hash(), status="COMPLETE_DIAGNOSTIC", generated_at="",
    )


def test_host_03_log1p_candidate_uses_frozen_reference_not_aoi_extrema():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    z, audit, status = transform_log1p_robust_reference_scale(host_density_total=100.0, reference_log1p_lower=reference.host_density_total_log1p_quantiles["lower"], reference_log1p_upper=reference.host_density_total_log1p_quantiles["upper"])
    assert status == REAL_TRANSFORMED_CANDIDATE
    assert audit.was_clipped_high is True
    assert z == 1.0


def test_host_04_hostsafe_hostempirical_cdf_candidate_deterministic():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    p1 = transform_empirical_cdf_reference(host_density_total=12.0, sorted_reference_values=reference.host_density_total_reference_values)
    p2 = transform_empirical_cdf_reference(host_density_total=12.0, sorted_reference_values=reference.host_density_total_reference_values)
    assert p1 == p2
    assert 0.0 <= p1 <= 1.0


def test_ecdf_tie_conventions_documented_and_distinguishable():
    values = (5.0, 10.0, 10.0, 15.0)
    lower = transform_empirical_cdf_reference(host_density_total=10.0, sorted_reference_values=values, tie_convention="LOWER_RANK")
    mid = transform_empirical_cdf_reference(host_density_total=10.0, sorted_reference_values=values, tie_convention="MID_RANK")
    assert lower != mid  # a tie at an existing value must resolve differently under each documented convention


def test_host_05_transformed_value_carries_lineage():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    log1p = candidates["LOG1P_ROBUST_REFERENCE_SCALE"]
    assert log1p.raw_values == (10.0,)
    assert log1p.feature_snapshot_id == "SNAPSHOT:abc"
    assert log1p.reference_profile_hash == reference.reference_profile_hash()
    assert log1p.transform_config_hash == tc.config_hash()
    assert log1p.candidate_status == REAL_TRANSFORMED_CANDIDATE


def test_host_06_clipping_explicitly_recorded():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(9000.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(0.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    clip = candidates["LOG1P_ROBUST_REFERENCE_SCALE"].clipping
    assert clip is not None
    assert clip.was_clipped_high is True
    assert clip.was_clipped_low is False


def test_host_07_never_claims_probability():
    from components.geospatial_tracking.services.factors.contracts import TransformedFactorProvenance

    field_names = {n.lower() for n in TransformedFactorProvenance.__dataclass_fields__}
    assert "probability" not in field_names

    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    cdf_notes = candidates["EMPIRICAL_CDF_REFERENCE"].notes.lower()
    assert "probability" in cdf_notes
    assert "not probability" in cdf_notes


def test_host_08_host_density_labeled_proxy_not_exact_inventory():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    assert "proxy" in candidates["cattle_density"].notes.lower()
    assert "not proof" in candidates["host_density_total"].notes.lower()


def test_blocked_host_input_propagates_to_candidates():
    reference = _reference_profile([5.0, 10.0, 15.0, 20.0, 25.0])
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _blocked_fr("host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    assert candidates["host_density_total"].candidate_status == BLOCKED
    assert candidates["LOG1P_ROBUST_REFERENCE_SCALE"].candidate_status == BLOCKED
    assert candidates["LOG1P_ROBUST_REFERENCE_SCALE"].transformed_value is None


def test_hostsafe_01_compatible_real_units_can_sum():
    cell = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    raw = compute_host_density_total(cell)
    assert raw.host_density_total == 10.0
    assert raw.host_density_total_status == RAW_REAL_COMPONENT


def test_hostsafe_02_unit_mismatch_blocks_sum():
    cell = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {
        "cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell", units="animals_per_km2"),
        "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell", units="animals_per_pixel"),
    }}
    raw = compute_host_density_total(cell)
    assert raw.host_density_total is None
    assert raw.host_density_total_status == UNIT_MISMATCH


def test_hostsafe_03_negative_density_rejected():
    cell = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(-5.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    raw = compute_host_density_total(cell)
    assert raw.host_density_total is None
    assert raw.host_density_total_status == BLOCKED


def test_hostsafe_04_nan_and_infinity_rejected():
    for bad in (float("nan"), float("inf")):
        cell = {"centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(bad, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
        raw = compute_host_density_total(cell)
        assert raw.host_density_total is None
        assert raw.host_density_total_status == BLOCKED


def test_hostsafe_07_08_degenerate_reference_span_returns_explicit_status():
    z, audit, status = transform_log1p_robust_reference_scale(host_density_total=10.0, reference_log1p_lower=3.0, reference_log1p_upper=3.0)
    assert z is None
    assert audit is None
    assert status == DEGENERATE_REFERENCE_DISTRIBUTION

    z2, audit2, status2 = transform_log1p_robust_reference_scale(host_density_total=10.0, reference_log1p_lower=5.0, reference_log1p_upper=3.0)
    assert z2 is None
    assert status2 == DEGENERATE_REFERENCE_DISTRIBUTION


def test_degenerate_reference_propagates_through_build_host_factor_candidates():
    reference = _reference_profile([5.0], lower_q=0.05, upper_q=0.95)  # single value -> degenerate log1p span
    tc = FactorTransformConfig()
    cell = {"grid_cell_id": "C1", "centroid_lat": 15.0, "centroid_lon": 101.0, "host_density": {"cattle": _real_fr(8.0, feature_name="host_density_cattle_grid_cell"), "buffalo": _real_fr(2.0, feature_name="host_density_buffalo_grid_cell")}}
    candidates = build_host_factor_candidates(cell=cell, feature_snapshot_id="SNAPSHOT:abc", reference_profile=reference, transform_config=tc)
    log1p = candidates["LOG1P_ROBUST_REFERENCE_SCALE"]
    assert log1p.transformed_value is None
    assert log1p.candidate_status == DEGENERATE_REFERENCE_DISTRIBUTION

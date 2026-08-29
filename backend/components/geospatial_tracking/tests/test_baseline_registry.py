"""Checkpoint 7A Part 35: baseline candidate registry tests —
BASE-01..08."""

from __future__ import annotations

from components.geospatial_tracking.services.model_development.baseline_registry import (
    BASELINE_CANDIDATES,
    EQUAL_SOURCE_BASELINE,
    BaselineFamily,
)

_BY_FAMILY = {c.family: c for c in BASELINE_CANDIDATES}


def test_base_01_b0_is_explicitly_distance_only():
    b0 = _BY_FAMILY[BaselineFamily.B0_DISTANCE_ONLY.value]
    assert b0.host_factor_candidate is None


def test_base_02_b1_uses_log1p_host_candidate_only():
    b1 = _BY_FAMILY[BaselineFamily.B1_HOST_DISTANCE_LOG1P.value]
    assert b1.host_factor_candidate == "LOG1P_ROBUST_REFERENCE_SCALE"


def test_base_03_b2_uses_ecdf_host_candidate_only():
    b2 = _BY_FAMILY[BaselineFamily.B2_HOST_DISTANCE_ECDF.value]
    assert b2.host_factor_candidate == "EMPIRICAL_CDF_REFERENCE"


def test_base_04_all_are_equal_source_baseline():
    assert all(c.source_weighting == EQUAL_SOURCE_BASELINE for c in BASELINE_CANDIDATES)


def test_base_05_none_claims_source_strength_scientifically_defined():
    # structural: no candidate field/description implies a defined
    # source_strength_factor -- the registry has no such field at all,
    # and the real status lives only in services.factors.source_strength.
    from components.geospatial_tracking.services.factors.source_strength import build_source_strength_status
    from components.geospatial_tracking.services.factors.contracts import NOT_YET_SCIENTIFICALLY_DEFINED
    status = build_source_strength_status(source_id="S1")
    assert status.candidate_status == NOT_YET_SCIENTIFICALLY_DEFINED
    assert not any("source_strength" in f for c in BASELINE_CANDIDATES for f in c.__dataclass_fields__)


def test_base_06_none_uses_environmental_suitability_factor():
    assert all(c.uses_environmental_suitability_factor is False for c in BASELINE_CANDIDATES)


def test_base_07_none_uses_water_context_factor():
    assert all(c.uses_water_context_factor is False for c in BASELINE_CANDIDATES)


def test_base_08_none_emits_infection_probability():
    assert all(c.emits_infection_probability is False for c in BASELINE_CANDIDATES)
    assert all(c.output_label == "RELATIVE_SPATIAL_SCORE" for c in BASELINE_CANDIDATES)


def test_kernel_candidates_include_exponential_and_gaussian_unfrozen_scale():
    from components.geospatial_tracking.services.model_development.baseline_registry import KERNEL_CANDIDATE_FAMILIES, KERNEL_DISTANCE_SCALE_STATUS
    assert set(KERNEL_CANDIDATE_FAMILIES) == {"EXPONENTIAL", "GAUSSIAN"}
    assert KERNEL_DISTANCE_SCALE_STATUS == "UNFROZEN_DEVELOPMENT_PARAMETER"


def test_registry_hashes_are_deterministic():
    from components.geospatial_tracking.services.model_development.baseline_registry import baseline_registry_hash, kernel_registry_hash
    assert baseline_registry_hash() == baseline_registry_hash()
    assert kernel_registry_hash() == kernel_registry_hash()

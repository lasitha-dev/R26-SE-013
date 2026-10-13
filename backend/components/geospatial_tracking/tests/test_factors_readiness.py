"""Checkpoint 6D.6 Part 19: honest global-readiness tests — READY-01..07.

`build_development_reference_audit` must only report
`GLOBAL_REFERENCE_PROFILE_READY` when EVERY intended (runtime-derived)
FIT_DEVELOPMENT origin has an actually, successfully constructed usable
host snapshot, there are no unexpected extras, the reference profile is
COMPLETE_DIAGNOSTIC, and there are zero observation conflicts / zero
incompatible strata. Any shortfall must report
`GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY` with an honest coverage
fraction -- never a silently inflated "ready" label.
"""

from __future__ import annotations

import math

from components.geospatial_tracking.services.factors.audit import build_development_reference_audit
from components.geospatial_tracking.services.factors.contracts import GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY, GLOBAL_REFERENCE_PROFILE_READY
from components.geospatial_tracking.services.factors.reference_profile import FactorReferenceProfile
from components.geospatial_tracking.services.factors.transform_config import FactorTransformConfig
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin


def _origin(i: int) -> ForecastOrigin:
    return ForecastOrigin(
        forecast_origin_id=f"ORIGIN:Thailand:{i:04d}", country="Thailand", t0=f"2021-06-{(i % 28) + 1:02d}",
        temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=[f"X{i}"], trigger_source_count=1,
    )


def _profile(
    *, status="COMPLETE_DIAGNOSTIC", n_reference_observation_conflicts=0, n_incompatible_strata_detected=0
) -> FactorReferenceProfile:
    tc = FactorTransformConfig()
    return FactorReferenceProfile(
        reference_profile_version="6D.2", development_role="FIT_DEVELOPMENT", development_cutoff="2024-01-01",
        included_origin_ids_digest="x", n_included_origins=1, country_coverage=("Thailand",), n_feature_snapshots_considered=1,
        host_density_total_raw_appearances=1, host_density_total_unique_observations=1,
        host_density_total_reference_values=(10.0,), host_density_total_observation_ids=("OBS0",),
        host_density_total_quantiles={"p05": 10.0, "p50": 10.0, "p95": 10.0, "lower": 10.0, "upper": 10.0},
        host_density_total_log1p_quantiles={"lower": math.log1p(10.0), "upper": math.log1p(10.0)},
        reference_observation_digest="digest", dataset_compatibility_stratum=None,
        n_incompatible_strata_detected=n_incompatible_strata_detected, reference_compatibility_mode="STRICT_COMPATIBLE",
        n_reference_observation_conflicts=n_reference_observation_conflicts, reference_observation_conflicts=(),
        n_host_species_observations_via_raster_identity=0, n_host_species_observations_via_query_centroid_fallback=0,
        weather_reference_observation_counts={}, dataset_version_composition={}, landcover_comparability_composition={}, weather_model_composition={},
        transform_config_hash=tc.config_hash(), status=status, generated_at="",
    )


def test_ready_01_all_intended_all_usable_compatible_is_ready():
    origins = [_origin(i) for i in range(5)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}  # every intended origin has a real (non-None) snapshot
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_READY
    assert audit["global_reference_universe_coverage_fraction"] == 1.0


def test_ready_02_one_none_snapshot_is_diagnostic_only():
    origins = [_origin(i) for i in range(5)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    snapshots[intended_ids[0]] = None  # blocked/missing -- represented as None, per the codebase's own convention
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    assert audit["global_reference_universe_coverage_fraction"] == 4 / 5


def test_ready_03_one_blocked_snapshot_is_diagnostic_only():
    # BLOCKED construction failures are represented identically to
    # MISSING ones (None) at this layer -- see reference_profile.py's
    # own module docstring: "None/absent means that origin's snapshot
    # could not be assembled (MISSING/BLOCKED), never silently substituted."
    origins = [_origin(i) for i in range(4)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    snapshots[intended_ids[-1]] = None
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    assert audit["n_feature_snapshots_blocked_or_missing"] == 1


def test_ready_04_missing_intended_origin_is_diagnostic_only():
    origins = [_origin(i) for i in range(3)]
    intended_ids = [o.forecast_origin_id for o in origins] + ["ORIGIN:Thailand:9999"]  # an intended origin never supplied at all
    snapshots = {o.forecast_origin_id: {"grid_cells": []} for o in origins}
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    assert audit["global_reference_universe_coverage_fraction"] == 3 / 4


def test_ready_05_reference_observation_conflict_is_diagnostic_only():
    origins = [_origin(i) for i in range(3)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    conflicted_profile = _profile(status="REFERENCE_OBSERVATION_VALUE_CONFLICT", n_reference_observation_conflicts=1)
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=conflicted_profile,
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    # even full 1.0 origin coverage cannot rescue a conflicted pool
    assert audit["global_reference_universe_coverage_fraction"] == 1.0


def test_ready_06_incompatible_strata_is_diagnostic_only():
    origins = [_origin(i) for i in range(3)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    incompatible_profile = _profile(status="INCOMPATIBLE_REFERENCE_STRATA", n_incompatible_strata_detected=2)
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=incompatible_profile,
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY


def test_ready_07_coverage_fraction_uses_successfully_available_intended_origins():
    # Part 13's exact regression: 100 intended, 100 origin objects
    # supplied, 99 real snapshots, 1 None/BLOCKED -> must NEVER produce
    # READY; expected DIAGNOSTIC_ONLY with coverage_fraction == 0.99.
    origins = [_origin(i) for i in range(100)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    snapshots[intended_ids[42]] = None
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    assert audit["global_reference_universe_coverage_fraction"] == 0.99
    assert audit["n_feature_snapshots_available"] == 99
    assert audit["n_feature_snapshots_blocked_or_missing"] == 1


def test_ready_unexpected_extra_snapshot_id_is_diagnostic_only():
    origins = [_origin(i) for i in range(3)]
    intended_ids = [o.forecast_origin_id for o in origins]
    snapshots = {oid: {"grid_cells": []} for oid in intended_ids}
    snapshots["ORIGIN:Thailand:UNEXPECTED"] = {"grid_cells": []}  # never part of the intended universe
    audit = build_development_reference_audit(
        fit_development_origins=origins, feature_snapshots_by_origin_id=snapshots, reference_profile=_profile(),
        total_fit_development_origin_ids=intended_ids,
    )
    assert audit["global_reference_profile_status"] == GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY
    assert audit["n_unexpected_extra_snapshot_ids"] == 1

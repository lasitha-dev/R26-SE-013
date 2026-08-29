"""Checkpoint 7E Parts 2, 7: the hard model freeze assertion, and the
pre-case-study protocol manifest, for the frozen Sri Lanka geographic-
transfer case study.

There is exactly ONE frozen candidate in Checkpoint 7E -- the same one
Checkpoint 7D used, unchanged. No registry, no selection, no tuning. Sri
Lanka data has ZERO influence on model selection or parameters -- this
module's job is to make that freeze directly auditable and to STOP
before any Sri Lanka predictive score is ever read if the on-disk model
specification does not match exactly.
"""

from __future__ import annotations

import hashlib
import json

from .heldout_protocol_7d import (
    ACTIVE_SOURCE_WINDOW_DAYS_7D as ACTIVE_SOURCE_WINDOW_DAYS_7E,
    AVAILABILITY_PROTOCOL_IDENTITY,
    EVALUATION_DISTANCE_KM_7D as EVALUATION_DISTANCE_KM_7E,
    ENVIRONMENTAL_SUITABILITY_NOT_SELECTED,
    FROZEN_7C_SPEC_HASH,
    GRID_CELL_SIZE_KM_7D as GRID_CELL_SIZE_KM_7E,
    HOST_FACTOR_NOT_SELECTED,
    PARENT_7B_SPEC_HASH,
    SELECTED_CANDIDATE_ID,
    SOURCE_STRENGTH_NOT_SELECTED,
    TARGET_UNIQUENESS_RULE,
    WATER_CONTEXT_NOT_SELECTED,
    WIND_ANISOTROPY_NOT_SELECTED,
    HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D,
    ModelFreezeMismatchError,
    assert_frozen_c0_model,
)
from .candidate_registry_7c import FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM
from .evaluation_protocol_7b import (
    AREA_WEIGHTED_MIDRANK,
    AREA_WEIGHTED_METRIC_VERSION,
    AREA_WEIGHT_FIELD,
    TOP5_THRESHOLD_PERCENTILE,
    TOP10_THRESHOLD_PERCENTILE,
)
from .selection_7b import FOLD_AGGREGATION_RULE, PRIMARY_SELECTION_METRIC

CHECKPOINT_7E = "7E"

EVALUATION_ROLE_7E = "SRI_LANKA_TRANSFER_CASE_STUDY"
EVALUATION_LABEL_7E = "FROZEN_SRI_LANKA_GEOGRAPHIC_TRANSFER_CASE_STUDY_WITH_RETROSPECTIVE_AVAILABILITY_LIMITATIONS_DISCLOSED"

# Part 4: existing project GPS-quality/date-quality semantics reused
# (schemas.GpsQuality, schemas.AvailabilityQuality) -- never invented.
GPS_QUALITY_SEMANTICS = "schemas.GpsQuality (EXACT/APPROXIMATE/COARSE/UNKNOWN)"
DATE_SEMANTICS_7E = (
    "DATE_ONLY calendar t0, geodesic distance, no timestamp precision required for C0 (no weather); "
    "availability_quality reused from schemas.AvailabilityQuality (ACTUAL/CONFIRMATION_PROXY/REPORT_PROXY/"
    "EVENT_DATE_PROXY/OBSERVATION_DATE_PROXY/UNKNOWN) -- never manufactured"
)

NOT_EXTERNAL_VALIDATION_NOTE = (
    "FROZEN_GEOGRAPHIC_TRANSFER_CASE_STUDY -- never EXTERNAL_VALIDATION, INDEPENDENT_VALIDATION, "
    "BLIND_VALIDATION, PROSPECTIVE_VALIDATION, SRI_LANKA_MODEL_TUNING, PRODUCTION_ACCURACY, or "
    "CAUSAL_TRANSMISSION_VALIDATION. Sri Lanka data has ZERO influence on model selection or parameters."
)


def assert_frozen_c0_model_7e(loaded_spec: dict) -> None:
    """Part 2: identical freeze contract to Checkpoint 7D's
    `assert_frozen_c0_model` -- reused directly, never re-implemented,
    so the Sri Lanka case study is provably held to the exact same
    frozen model."""
    assert_frozen_c0_model(loaded_spec)


def sri_lanka_case_study_protocol_dict_7e() -> dict:
    """Every field Part 7 requires, scientific semantics only --
    `generated_at` never participates."""
    return {
        "checkpoint": CHECKPOINT_7E,
        "evaluation_role": EVALUATION_ROLE_7E,
        "evaluation_label": EVALUATION_LABEL_7E,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH,
        "parent_7b_spec_hash": PARENT_7B_SPEC_HASH,
        "historical_7d_evaluation_protocol_hash_reference": HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D,
        "kernel_family": FROZEN_KERNEL_FAMILY,
        "kernel_scale_km": FROZEN_KERNEL_SCALE_KM,
        "grid_cell_size_km": GRID_CELL_SIZE_KM_7E,
        "evaluation_distance_km": EVALUATION_DISTANCE_KM_7E,
        "active_source_window_days": ACTIVE_SOURCE_WINDOW_DAYS_7E,
        "primary_selection_metric": PRIMARY_SELECTION_METRIC,
        "area_weighted_metric_version": AREA_WEIGHTED_METRIC_VERSION,
        "tie_semantics": AREA_WEIGHTED_MIDRANK,
        "area_weight_field": AREA_WEIGHT_FIELD,
        "top5_threshold_percentile": TOP5_THRESHOLD_PERCENTILE,
        "top10_threshold_percentile": TOP10_THRESHOLD_PERCENTILE,
        "fold_aggregation_rule": FOLD_AGGREGATION_RULE,
        "target_uniqueness_rule": TARGET_UNIQUENESS_RULE,
        "availability_protocol_identity": AVAILABILITY_PROTOCOL_IDENTITY,
        "date_semantics": DATE_SEMANTICS_7E,
        "gps_quality_semantics": GPS_QUALITY_SEMANTICS,
        "host_factor_status": HOST_FACTOR_NOT_SELECTED,
        "wind_anisotropy_status": WIND_ANISOTROPY_NOT_SELECTED,
        "environmental_suitability_status": ENVIRONMENTAL_SUITABILITY_NOT_SELECTED,
        "water_context_status": WATER_CONTEXT_NOT_SELECTED,
        "source_strength_status": SOURCE_STRENGTH_NOT_SELECTED,
        "not_external_validation_note": NOT_EXTERNAL_VALIDATION_NOTE,
    }


def sri_lanka_case_study_protocol_hash_7e() -> str:
    canonical = json.dumps(sri_lanka_case_study_protocol_dict_7e(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_pre_case_study_freeze_manifest(*, sri_lanka_origin_count_expected: int, generated_at: str = "") -> dict:
    """Part 7: written before the Sri Lanka case-study predictive scoring
    run -- never before the dataset itself was audited (the origin-
    universe/temporal/GPS audits are non-predictive and are performed
    first, per Part 4-6)."""
    d = sri_lanka_case_study_protocol_dict_7e()
    d["sri_lanka_case_study_protocol_hash_7e"] = sri_lanka_case_study_protocol_hash_7e()
    d["sri_lanka_origin_count_expected"] = sri_lanka_origin_count_expected
    d["generated_at"] = generated_at  # never part of the hash above
    return d

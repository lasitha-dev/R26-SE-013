"""Checkpoint 7D Part 2, 4, 18: the hard model freeze assertion, the
pre-evaluation freeze manifest, and the exposure disclosure.

There is exactly ONE frozen candidate in Checkpoint 7D -- no registry,
no selection, no tuning. This module's job is to make that freeze
directly auditable and to STOP before any held-out predictive score is
ever read if the on-disk model specification does not match exactly.
"""

from __future__ import annotations

import hashlib
import json

from ...config import ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT
from ..forecast_target import PRIMARY_HORIZON_DAYS
from .candidate_registry_7c import FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM, PARENT_7B_FROZEN_SPEC_HASH
from .evaluation_protocol_7b import (
    AREA_WEIGHTED_MIDRANK,
    AREA_WEIGHTED_METRIC_VERSION,
    AREA_WEIGHT_FIELD,
    COVERAGE_ELIGIBILITY_RULE_VERSION,
    SOFTWARE_ZERO_AREA_TOLERANCE_KM2,
    TOP5_THRESHOLD_PERCENTILE,
    TOP10_THRESHOLD_PERCENTILE,
)
from .local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM, PRIMARY_SCOPE_TRUTH_METHOD
from .selection_7b import FOLD_AGGREGATION_RULE, PRIMARY_SELECTION_METRIC

CHECKPOINT_7D = "7D"

EVALUATION_ROLE = "HELD_OUT_FROM_MODEL_FITTING"
EXPOSURE_DISCLOSURE = "PRIOR_DATASET_EXPOSURE_DISCLOSED"

# Checkpoint 7D.1.1 Part 2: explicit historical/corrected separation --
# never silently replace one with the other.
#
# ORIGINAL: the label present in the historical 7D protocol during the
# final 229-origin run. `heldout_evaluation_protocol_dict_7d()` binds
# THIS value (never the corrected one) so `heldout_evaluation_protocol_hash_7d()`
# stays exactly `74be1d652fff4739ddeb612dd21a273004d35117bedc718981c5e7636ce6cb90`
# -- a historical scientific-identity fact, never recomputed/replaced.
EVALUATION_LABEL_7D_ORIGINAL = "PRE_SPECIFIED_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_EXPOSURE_DISCLOSED"
HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D = "74be1d652fff4739ddeb612dd21a273004d35117bedc718981c5e7636ce6cb90"

# CORRECTED (Checkpoint 7D.1): the post-hoc evidence classification after
# disclosure of the pre-final 40-origin predictive subset exposure. This
# label did NOT exist before the original run -- it is current reporting
# language only, never backdated into the historical protocol identity.
EVALUATION_LABEL_7D1_CORRECTED = "FROZEN_HELD_OUT_FROM_FITTING_EVALUATION_WITH_PRIOR_DATASET_AND_PRE_FINAL_PREDICTIVE_SUBSET_EXPOSURE_DISCLOSED"

# Part 2: the exact frozen Checkpoint 7C selection -- copied from the
# real, already-persisted 7C.1.1 outputs, never recomputed here.
SELECTED_CANDIDATE_ID = "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
FROZEN_7C_SPEC_HASH = "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"
PARENT_7B_SPEC_HASH = PARENT_7B_FROZEN_SPEC_HASH

HOST_FACTOR_NOT_SELECTED = "NOT_SELECTED"
WIND_ANISOTROPY_NOT_SELECTED = "NOT_SELECTED"
ENVIRONMENTAL_SUITABILITY_NOT_SELECTED = "NOT_SELECTED"
WATER_CONTEXT_NOT_SELECTED = "NOT_SELECTED"
SOURCE_STRENGTH_NOT_SELECTED = "NOT_SELECTED"

GRID_CELL_SIZE_KM_7D = 5.0
EVALUATION_DISTANCE_KM_7D = PRIMARY_LOCAL_EVALUATION_DISTANCE_KM  # 25.0, same frozen envelope
ACTIVE_SOURCE_WINDOW_DAYS_7D = ACTIVE_SOURCE_WINDOW_DAYS_DEV_DEFAULT

TARGET_UNIQUENESS_RULE = "(forecast_origin_id, target_event_id)"
AVAILABILITY_PROTOCOL_IDENTITY = "RETROSPECTIVE_PROXY_T0_INVARIANT"  # existing source_selector.py temporal_mode
DATE_SEMANTICS = "DATE_ONLY calendar t0, geodesic distance, no timestamp precision required for C0 (no weather)"


class ModelFreezeMismatchError(RuntimeError):
    """Raised the instant the on-disk/loaded model specification does not
    match the frozen Checkpoint 7C selection exactly -- Part 2's hard
    STOP-BEFORE-SCORING gate. Never silently rebuilds a 'similar' model."""


def assert_frozen_c0_model(loaded_spec: dict) -> None:
    """Part 2: verifies every required frozen fact BEFORE any held-out
    predictive score is computed. `loaded_spec`: the real, on-disk
    `local_data/model_development/7c/frozen_checkpoint_7c_spec.json`
    dict."""
    checks = {
        "selected_candidate_id": (loaded_spec.get("selected_candidate_id"), SELECTED_CANDIDATE_ID),
        "frozen_spec_hash": (loaded_spec.get("frozen_spec_hash"), FROZEN_7C_SPEC_HASH),
        "parent_7b_frozen_spec_hash": (loaded_spec.get("parent_7b_frozen_spec_hash"), PARENT_7B_SPEC_HASH),
        "kernel_family": (loaded_spec.get("selected_candidate_spec", {}).get("kernel_family"), FROZEN_KERNEL_FAMILY),
        "kernel_scale_km": (loaded_spec.get("selected_candidate_spec", {}).get("kernel_scale_km"), FROZEN_KERNEL_SCALE_KM),
        "host_factor_status": (loaded_spec.get("host_factor_status"), "NOT_PRIMARY_ELIGIBLE_FROM_7B_COVERAGE_AUDIT"),
        "anisotropy_mode": (loaded_spec.get("anisotropy_mode"), None),
        "anisotropy_kappa": (loaded_spec.get("anisotropy_kappa"), None),
        "environmental_suitability_status": (loaded_spec.get("environmental_suitability_status"), "NOT_YET_SCIENTIFICALLY_DEFINED"),
        "water_context_status": (loaded_spec.get("water_context_status"), "NOT_YET_SCIENTIFICALLY_DEFINED"),
        "source_strength_status": (loaded_spec.get("source_strength_status"), "NOT_SELECTED"),
    }
    mismatches = {k: v for k, v in checks.items() if v[0] != v[1]}
    if mismatches:
        detail = "; ".join(f"{k}: loaded={got!r} expected={want!r}" for k, (got, want) in mismatches.items())
        raise ModelFreezeMismatchError(
            f"Checkpoint 7D hard model freeze failed BEFORE any held-out score was computed -- {detail}"
        )


def heldout_evaluation_protocol_dict_7d() -> dict:
    """Every field Part 4 requires, scientific semantics only --
    `generated_at` never participates."""
    return {
        "checkpoint": CHECKPOINT_7D,
        "evaluation_role": EVALUATION_ROLE,
        "exposure_disclosure": EXPOSURE_DISCLOSURE,
        "evaluation_label": EVALUATION_LABEL_7D_ORIGINAL,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "frozen_7c_spec_hash": FROZEN_7C_SPEC_HASH,
        "parent_7b_spec_hash": PARENT_7B_SPEC_HASH,
        "kernel_family": FROZEN_KERNEL_FAMILY,
        "kernel_scale_km": FROZEN_KERNEL_SCALE_KM,
        "grid_cell_size_km": GRID_CELL_SIZE_KM_7D,
        "evaluation_distance_km": EVALUATION_DISTANCE_KM_7D,
        "active_source_window_days": ACTIVE_SOURCE_WINDOW_DAYS_7D,
        "primary_selection_metric": PRIMARY_SELECTION_METRIC,
        "area_weighted_metric_version": AREA_WEIGHTED_METRIC_VERSION,
        "tie_semantics": AREA_WEIGHTED_MIDRANK,
        "area_weight_field": AREA_WEIGHT_FIELD,
        "top5_threshold_percentile": TOP5_THRESHOLD_PERCENTILE,
        "top10_threshold_percentile": TOP10_THRESHOLD_PERCENTILE,
        "fold_aggregation_rule": FOLD_AGGREGATION_RULE,
        "coverage_eligibility_rule_version": COVERAGE_ELIGIBILITY_RULE_VERSION,
        "software_zero_area_tolerance_km2": SOFTWARE_ZERO_AREA_TOLERANCE_KM2,
        "primary_horizon_days": PRIMARY_HORIZON_DAYS,
        "primary_scope_truth_method": PRIMARY_SCOPE_TRUTH_METHOD,
        "target_uniqueness_rule": TARGET_UNIQUENESS_RULE,
        "availability_protocol_identity": AVAILABILITY_PROTOCOL_IDENTITY,
        "date_semantics": DATE_SEMANTICS,
        "host_factor_status": HOST_FACTOR_NOT_SELECTED,
        "wind_anisotropy_status": WIND_ANISOTROPY_NOT_SELECTED,
        "environmental_suitability_status": ENVIRONMENTAL_SUITABILITY_NOT_SELECTED,
        "water_context_status": WATER_CONTEXT_NOT_SELECTED,
        "source_strength_status": SOURCE_STRENGTH_NOT_SELECTED,
    }


def heldout_evaluation_protocol_hash_7d() -> str:
    canonical = json.dumps(heldout_evaluation_protocol_dict_7d(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_pre_evaluation_freeze_manifest(*, heldout_origin_count_expected: int, generated_at: str = "") -> dict:
    """Part 4: written before the FINAL full 229-origin evaluation
    metrics are computed -- NOT before any/all held-out predictive
    inspection ever (Checkpoint 7D.1 correction: a 40-origin predictive
    sanity subset was scored and inspected before this manifest existed;
    see `pre_final_40_origin_sanity_exposure.json`)."""
    d = heldout_evaluation_protocol_dict_7d()
    d["heldout_evaluation_protocol_hash_7d"] = heldout_evaluation_protocol_hash_7d()
    d["heldout_origin_count_expected"] = heldout_origin_count_expected
    d["generated_at"] = generated_at  # never part of the hash above
    return d


def build_heldout_exposure_disclosure() -> dict:
    """Part 18 (Checkpoint 7D), corrected by Checkpoint 7D.1/7D.1.1: the
    mandatory, honest disclosure of prior dataset exposure -- never
    claims a blind/untouched/single-shot test. A real 40-origin
    predictive sanity subset (`heldout[:40]`) was scored and its metrics
    inspected BEFORE the final 229-origin freeze manifest/run existed
    (see `pre_final_40_origin_sanity_exposure.json`); this function must
    never regress back to claiming otherwise."""
    return {
        "dataset_role": EVALUATION_ROLE,
        "excluded_from_model_fitting": True,
        "model_specification_frozen_before_final_229_origin_predictive_evaluation": True,
        "historical_original_evaluation_label": EVALUATION_LABEL_7D_ORIGINAL,
        "historical_note": (
            "The historical 7D protocol (heldout_evaluation_protocol_hash_7d="
            f"{HISTORICAL_HELDOUT_EVALUATION_PROTOCOL_HASH_7D}) binds EVALUATION_LABEL_7D_ORIGINAL above -- "
            "that hash/label is a historical scientific-identity fact and is never recomputed or replaced. "
            "The label below is CURRENT reporting language only, introduced post-hoc in Checkpoint 7D.1."
        ),
        "prior_dataset_level_inspection_disclosed": (
            "The 2024+ corpus (t0 >= MODEL_FITTING_CUTOFF) had already been inspected/characterized at the "
            "dataset level during project development -- e.g. its existence, row counts, and date range were "
            "referenced when MODEL_FITTING_CUTOFF and the role-classification logic (classify_origin_role) "
            "were designed and tested (Checkpoint 6B)."
        ),
        "pre_final_predictive_subset_exposure_disclosed": (
            "Before the formal Checkpoint 7D test suite and before the final 229-origin freeze manifest/run, "
            "a real predictive sanity evaluation was executed on a 40-origin held-out subset (heldout[:40]) "
            "using the same run_checkpoint_7d_heldout_evaluation function. Its pooled and country-level "
            "predictive metrics were inspected (see pre_final_40_origin_sanity_exposure.json). Direct evidence "
            "(filesystem mtimes plus this session's own tool-call record) shows no numerically load-bearing "
            "scientific code changed between that exposure and the final run -- "
            "NO_POST_EXPOSURE_NUMERICALLY_LOAD_BEARING_CODE_CHANGE_DETECTED_IN_RECORDED_SESSION. This "
            "evidence establishes code/configuration stability; it does not create blindness or erase the "
            "subset exposure itself."
        ),
        "therefore_not_called": ["SINGLE_SHOT", "FIRST_PREDICTIVE_INSPECTION", "BLIND_TEST", "UNTOUCHED_TEST", "UNSEEN_TEST", "EXTERNAL_VALIDATION"],
        "accurate_label": EVALUATION_LABEL_7D1_CORRECTED,
        "accurate_label_scope": "Applies to ALL current reporting/disclosure artifacts. The original 7D protocol/manifest retains its historical label and hash for provenance -- never rewritten.",
        "no_7d_outcome_used_for_model_tuning": True,
    }

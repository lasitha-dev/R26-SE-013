"""Checkpoint 7C Part 26 / 7C.1 Part 11: the frozen post-development
specification.

`parameter_status=FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION` -- never
"externally validated" (Part 26 explicit instruction; Checkpoint 7D
performs the frozen held-out evaluation, not this module). Checkpoint
7C.1 Part 11: every scientifically load-bearing weather/anisotropy/
factor semantic is now an explicit, directly-auditable field on this
dataclass -- not merely folded opaquely into a hash -- so a reader never
has to re-derive WHAT was frozen from the hash alone.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .evaluation_protocol_7c import (
    ANISOTROPY_IMPLEMENTATION_VERSION_7C,
    ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC,
    ENVIRONMENTAL_SUITABILITY_STATUS_7C,
    HOST_FACTOR_STATUS_7C,
    METEOROLOGY_SPATIAL_MODE_7C,
    PRIMARY_WEATHER_TEMPORAL_ROLE_7C,
    SOURCE_STRENGTH_STATUS_7C,
    T0_PRECISION_POLICY_7C,
    WATER_CONTEXT_STATUS_7C,
    WEATHER_LOOKBACK_HOURS_7C,
    WEATHER_MODEL_7C,
)
from .selection_7b import FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION


@dataclass(frozen=True)
class FrozenCheckpoint7CSpecification:
    selected_candidate_id: str
    parent_7b_frozen_spec_hash: str
    selected_candidate_spec: dict
    candidate_registry_hash_7c: str
    evaluation_protocol_hash_7c: str
    development_fold_manifest_hash: str
    selection_metric: str

    weather_temporal_role: str
    weather_model: str
    weather_lookback_hours: int
    t0_precision_policy: str
    meteorology_spatial_mode: str
    anisotropy_implementation_version: str
    anisotropy_mode: str | None  # None for the C0 anchor
    anisotropy_kappa: float | None  # None for the C0 anchor

    host_factor_status: str
    environmental_suitability_status: str
    water_context_status: str
    source_strength_status: str

    development_selection_result: dict
    selection_note: str
    coverage_status: dict
    anisotropy_mode_identifiability_status: str
    parameter_status: str = FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION

    def as_dict(self) -> dict:
        return {
            "selected_candidate_id": self.selected_candidate_id,
            "parent_7b_frozen_spec_hash": self.parent_7b_frozen_spec_hash,
            "selected_candidate_spec": self.selected_candidate_spec,
            "candidate_registry_hash_7c": self.candidate_registry_hash_7c,
            "evaluation_protocol_hash_7c": self.evaluation_protocol_hash_7c,
            "development_fold_manifest_hash": self.development_fold_manifest_hash,
            "selection_metric": self.selection_metric,
            "weather_temporal_role": self.weather_temporal_role,
            "weather_model": self.weather_model,
            "weather_lookback_hours": self.weather_lookback_hours,
            "t0_precision_policy": self.t0_precision_policy,
            "meteorology_spatial_mode": self.meteorology_spatial_mode,
            "anisotropy_implementation_version": self.anisotropy_implementation_version,
            "anisotropy_mode": self.anisotropy_mode,
            "anisotropy_kappa": self.anisotropy_kappa,
            "host_factor_status": self.host_factor_status,
            "environmental_suitability_status": self.environmental_suitability_status,
            "water_context_status": self.water_context_status,
            "source_strength_status": self.source_strength_status,
            "development_selection_result": self.development_selection_result,
            "selection_note": self.selection_note,
            "coverage_status": self.coverage_status,
            "anisotropy_mode_identifiability_status": self.anisotropy_mode_identifiability_status,
            "parameter_status": self.parameter_status,
        }

    def frozen_spec_hash(self) -> str:
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_frozen_checkpoint_7c_specification(
    *, result, parent_7b_frozen_spec_hash: str, candidate_registry_hash_7c: str, evaluation_protocol_hash_7c: str,
) -> FrozenCheckpoint7CSpecification:
    from .selection_7b import PRIMARY_SELECTION_METRIC, development_fold_manifest_hash

    selected_spec = result.selected_candidate_spec
    # Part 9: the selected candidate's own mode/kappa are reported
    # verbatim (tie-break-resolved), never described as "preferred" by
    # the data -- see `anisotropy_mode_identifiability_status` below.
    return FrozenCheckpoint7CSpecification(
        selected_candidate_id=result.selected_candidate_id, parent_7b_frozen_spec_hash=parent_7b_frozen_spec_hash,
        selected_candidate_spec=selected_spec, candidate_registry_hash_7c=candidate_registry_hash_7c,
        evaluation_protocol_hash_7c=evaluation_protocol_hash_7c,
        development_fold_manifest_hash=development_fold_manifest_hash(result.fold_manifest),
        selection_metric=PRIMARY_SELECTION_METRIC,
        weather_temporal_role=PRIMARY_WEATHER_TEMPORAL_ROLE_7C, weather_model=WEATHER_MODEL_7C,
        weather_lookback_hours=WEATHER_LOOKBACK_HOURS_7C, t0_precision_policy=T0_PRECISION_POLICY_7C,
        meteorology_spatial_mode=METEOROLOGY_SPATIAL_MODE_7C,
        anisotropy_implementation_version=ANISOTROPY_IMPLEMENTATION_VERSION_7C,
        anisotropy_mode=selected_spec.get("anisotropy_mode"), anisotropy_kappa=selected_spec.get("anisotropy_kappa"),
        host_factor_status=HOST_FACTOR_STATUS_7C, environmental_suitability_status=ENVIRONMENTAL_SUITABILITY_STATUS_7C,
        water_context_status=WATER_CONTEXT_STATUS_7C, source_strength_status=SOURCE_STRENGTH_STATUS_7C,
        development_selection_result={
            "selected_candidate_id": result.selected_candidate_id, "selection_tie_break_reason": result.selection_tie_break_reason,
            "overall_metric_value": result.candidate_overall_metrics[result.selected_candidate_id],
        },
        selection_note=result.selection_note,
        coverage_status=result.candidate_coverage_summary,
        anisotropy_mode_identifiability_status=ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC,
    )

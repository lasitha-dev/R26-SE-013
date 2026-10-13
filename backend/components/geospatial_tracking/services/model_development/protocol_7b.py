"""Checkpoint 7B Part 30-31: `FrozenBaselineModelSpecification` -- the
single frozen artifact produced by development-fold selection.

This is NOT final external validation (Part 30) and NEVER claims to be:
`parameter_status = FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION`, never
"validated," never "final PISTES model," never "infection probability
model" (Part 33).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .candidate_registry_7b import FULL_CANDIDATE_REGISTRY_VERSION, candidate_registry_hash
from .development_run_7b import Checkpoint7BResult
from .evaluation_protocol_7b import BASELINE_EVALUATION_PROTOCOL_VERSION, baseline_evaluation_protocol_hash
from .selection_7b import FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION, PRIMARY_SELECTION_METRIC, development_fold_manifest_hash, selection_protocol_hash

B0_FAMILY = "B0_DISTANCE_ONLY"
HOST_REFERENCE_NOT_AN_EFFECTIVE_MODEL_INPUT = "HOST_REFERENCE_NOT_AN_EFFECTIVE_MODEL_INPUT"
REUSED_AS_FINAL_DEVELOPMENT_REFERENCE = "REUSED_AS_FINAL_DEVELOPMENT_REFERENCE"
TRANSFORM_CONFIG_MISMATCH_REBUILD_REQUIRED = "TRANSFORM_CONFIG_MISMATCH_REBUILD_REQUIRED"


def existing_reference_metadata_from_persisted_files(*, profile_dict: dict, audit_dict: dict) -> dict:
    """Part 2 (HOSTFINAL7B-03): extracts the REAL, ALREADY-PERSISTED
    Checkpoint 7A.6.2 579-origin host-reference identity from its own
    output files -- `profile_dict` is the loaded
    `scientific_grid_host_reference_profile_7a61.json`
    (`FactorReferenceProfile.as_dict()`), `audit_dict` is the loaded
    `host_reference_rebuild_audit_7a61.json`. This function takes NO
    "selected"/current-run argument at all -- structurally, it cannot
    manufacture the existing hash from whatever the current 7B run
    happens to have selected."""
    return {
        "reference_profile_hash": audit_dict["reference_profile_hash"],
        "status": audit_dict["status"],
        "transform_config_hash": profile_dict["transform_config_hash"],
    }


@dataclass(frozen=True)
class FrozenBaselineModelSpecification:
    baseline_family: str
    kernel_family: str
    kernel_scale_km: float
    host_transform: str | None
    equal_source_semantics: str
    scientific_grid_config_hash: str
    scientific_domain_protocol_hash: str
    scientific_domain_protocol_version: str
    model_development_protocol_hash_7a62: str
    evaluation_protocol_hash: str
    evaluation_protocol_version: str
    candidate_registry_hash: str
    selection_protocol_hash: str
    development_fold_manifest_hash: str
    selection_metric: str
    development_selection_result: dict
    final_host_reference_decision: dict
    parameter_status: str

    def as_dict(self) -> dict:
        return {
            "baseline_family": self.baseline_family, "kernel_family": self.kernel_family,
            "kernel_scale_km": self.kernel_scale_km, "host_transform": self.host_transform,
            "equal_source_semantics": self.equal_source_semantics,
            "scientific_grid_config_hash": self.scientific_grid_config_hash,
            "scientific_domain_protocol_hash": self.scientific_domain_protocol_hash,
            "scientific_domain_protocol_version": self.scientific_domain_protocol_version,
            "model_development_protocol_hash_7a62": self.model_development_protocol_hash_7a62,
            "evaluation_protocol_hash": self.evaluation_protocol_hash, "evaluation_protocol_version": self.evaluation_protocol_version,
            "candidate_registry_hash": self.candidate_registry_hash, "selection_protocol_hash": self.selection_protocol_hash,
            "development_fold_manifest_hash": self.development_fold_manifest_hash, "selection_metric": self.selection_metric,
            "development_selection_result": self.development_selection_result,
            "final_host_reference_decision": self.final_host_reference_decision, "parameter_status": self.parameter_status,
        }

    def frozen_spec_hash(self) -> str:
        canonical = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_final_host_reference_decision(
    *, selected_baseline_family: str, existing_579_origin_reference_hash: str, existing_579_origin_reference_status: str,
    existing_579_origin_transform_config_hash: str, selected_transform_config_hash: str,
) -> dict:
    """Part 31: if B1/B2 was selected, the already-approved complete
    579-origin Checkpoint 7A.6.2 host reference becomes the FINAL
    development reference PROVIDED its transform config matches the
    selected host transform -- never rebuilt using held-out data. If B0
    was selected, the host reference is not an effective model input for
    the frozen spec, but the prior reference is still preserved as
    research evidence, never discarded."""
    if selected_baseline_family == B0_FAMILY:
        return {
            "decision": HOST_REFERENCE_NOT_AN_EFFECTIVE_MODEL_INPUT,
            "preserved_as_research_evidence_hash": existing_579_origin_reference_hash,
        }
    config_matches = existing_579_origin_transform_config_hash == selected_transform_config_hash
    return {
        "decision": REUSED_AS_FINAL_DEVELOPMENT_REFERENCE if config_matches else TRANSFORM_CONFIG_MISMATCH_REBUILD_REQUIRED,
        "existing_579_origin_reference_hash": existing_579_origin_reference_hash,
        "existing_579_origin_reference_status": existing_579_origin_reference_status,
        "existing_579_origin_transform_config_hash": existing_579_origin_transform_config_hash,
        "selected_transform_config_hash": selected_transform_config_hash,
        "transform_config_matches_selected_host_transform": config_matches,
    }


def build_frozen_baseline_model_specification(
    *, result: Checkpoint7BResult, scientific_grid_config_hash: str, scientific_domain_protocol_hash: str,
    scientific_domain_protocol_version: str, model_development_protocol_hash_7a62: str, final_host_reference_decision: dict,
) -> FrozenBaselineModelSpecification:
    spec = result.selected_candidate_spec
    return FrozenBaselineModelSpecification(
        baseline_family=spec["baseline_family"], kernel_family=spec["kernel_family"], kernel_scale_km=spec["kernel_scale_km"],
        host_transform=spec["host_factor_candidate"], equal_source_semantics=spec["source_weighting"],
        scientific_grid_config_hash=scientific_grid_config_hash, scientific_domain_protocol_hash=scientific_domain_protocol_hash,
        scientific_domain_protocol_version=scientific_domain_protocol_version,
        model_development_protocol_hash_7a62=model_development_protocol_hash_7a62,
        evaluation_protocol_hash=baseline_evaluation_protocol_hash(), evaluation_protocol_version=BASELINE_EVALUATION_PROTOCOL_VERSION,
        candidate_registry_hash=candidate_registry_hash(), selection_protocol_hash=selection_protocol_hash(),
        development_fold_manifest_hash=development_fold_manifest_hash(result.fold_manifest), selection_metric=PRIMARY_SELECTION_METRIC,
        development_selection_result={
            "selected_candidate_id": result.selected_candidate_id, "selection_tie_break_reason": result.selection_tie_break_reason,
            "overall_metric_value": result.candidate_overall_metrics[result.selected_candidate_id],
            "full_candidate_registry_version": FULL_CANDIDATE_REGISTRY_VERSION,
        },
        final_host_reference_decision=final_host_reference_decision, parameter_status=FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION,
    )

"""Checkpoint 7A Part 29 / Checkpoint 7A.5 Part 30 / Checkpoint 7A.6 Part 28:
`model_development_protocol_hash` — the single canonical identity
covering every scientific/engineering decision this checkpoint freezes
(or honestly leaves blocked), so a later change to ANY of them is
visible as a changed hash rather than a silent drift. Never includes
`generated_at`.

Checkpoint 7A.5 extended this hash to also cover: the local-context
protocol version/hash, the ST-DBSCAN config hash it was built from (if
any), the (now-superseded) local target-scope rule version, and the
true-union grid mode/projection tolerance already carried inside
`scientific_grid_config`.

Checkpoint 7A.6 extends it further to cover the PRIMARY, ST-DBSCAN-
decoupled evaluation contract: the frozen 25km operational local
evaluation envelope and its status, the pre-registered (never
substituted) 50km sensitivity envelope, the frozen 5km engineering cell
size and its status, the scope-rationale document version, the explicit
disclosure that the development target-distance distribution was
already exposed before the envelope was frozen, the all-source
contribution rule (Part 12), and the ST-DBSCAN-is-contextual-not-gating
policy version (Part 5/29). Changing local-scope semantics changes this
hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..forecast_target import PRIMARY_HORIZON_DAYS
from ..geospatial.scientific_grid import ScientificGridConfig
from ..model_fitting_exposure import MODEL_FITTING_CUTOFF
from .baseline_registry import (
    BASELINE_CANDIDATE_REGISTRY_VERSION,
    KERNEL_CANDIDATE_REGISTRY_VERSION,
    baseline_registry_hash,
    kernel_registry_hash,
)
from ..geospatial.scientific_domain import (
    COMPONENT_EDGE_DISTANCE_KM_MULTIPLE,
    GEODESIC_BOUNDARY_TOLERANCE_KM,
    GEODESIC_BOUNDARY_TOLERANCE_VERSION,
    SCIENTIFIC_CELL_IDENTITY_VERSION,
    SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
)
from .domain_design import PREDECLARED_DOMAIN_CANDIDATES_KM
from .local_context import LOCAL_CONTEXT_PROTOCOL_VERSION
from .local_evaluation_scope import (
    DEVELOPMENT_TARGET_DISTANCE_DISTRIBUTION_ALREADY_EXPOSED,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
    PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
    PRIMARY_SCOPE_TRUTH_METHOD,
    SCIENTIFIC_GRID_CELL_SIZE_KM,
    SCIENTIFIC_GRID_CELL_SIZE_STATUS,
    SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM,
    SENSITIVITY_LOCAL_EVALUATION_DISTANCE_STATUS,
)

PRIMARY_EVALUATION_METRICS: tuple = ("TARGET_PERCENTILE_RANK", "TARGET_CELL_RANK", "TOP_5_PERCENT_CAPTURE", "TOP_10_PERCENT_CAPTURE")
OPTIONAL_EVALUATION_METRICS: tuple = ("DISTANCE_TO_HIGH_RISK_REGION",)
BACKGROUND_SEMANTICS_VERSION = "PRESENCE_BACKGROUND_V1"  # TARGET_EVENT / BACKGROUND, never TRUE_NEGATIVE
PURGE_POLICY_VERSION = "PURGED_7_DAY_HORIZON_POLICY"
TARGET_ASSIGNMENT_RULE = "POLYGON_CONTAINMENT_LEXICOGRAPHIC_MIN_CELL_ID_TIEBREAK"
OUT_OF_DOMAIN_TARGET_RULE = "RETAINED_AND_FLAGGED_TARGET_OUTSIDE_EVALUATION_DOMAIN_NEVER_DROPPED"

# Checkpoint 7A.5 fields — now describing the SUPERSEDED ST-based
# diagnostic target-scope rule (kept for history/continuity, never used
# as the primary contract from 7A.6 onward — see local_evaluation_scope.py).
TARGET_SCOPE_RULE_VERSION = "7A.5.1_SUPERSEDED_ST_TEMPORAL_EPS_TARGET_SCOPE_DIAGNOSTIC"
NONLOCAL_TARGET_POLICY = "NONLOCAL_FUTURE_EVENT_NOT_A_MODEL_COVERAGE_FAILURE_RETAINED_IN_AUDIT_LEDGER"
OUT_OF_DOMAIN_LOCAL_TARGET_POLICY = "LOCAL_SCOPE_TARGET_OUTSIDE_DOMAIN_REMAINS_EXPLICIT_COVERAGE_FAILURE"

# Checkpoint 7A.6 additions (Parts 1-29)
PRIMARY_SCOPE_RULE_VERSION = "7A.6.1"  # local_evaluation_scope.classify_target_primary_scope's rule version
SCOPE_RATIONALE_DOCUMENT_VERSION = "7A.6.1"  # LOCAL_EVALUATION_SCOPE_RATIONALE.md
ALL_SOURCE_CONTRIBUTION_RULE = "DOMAIN_COMPONENT_PARTITION_NEVER_FILTERS_HAZARD_SOURCE_SET"
ST_DBSCAN_GATING_POLICY_VERSION = "ST_DBSCAN_CONTEXTUAL_NEVER_GATING_V1"

# Checkpoint 7A.6.1 additions (Parts 3-4, 7-19, 26-28, 35)
GRID_TRUTH_SEPARATION_POLICY_VERSION = "SCOPE_TRUTH_GEODESIC_GRID_REPRESENTATION_SEPARATE_V1"
ZERO_ORIGIN_DROP_POLICY = "NO_FIT_DEVELOPMENT_ORIGIN_SILENTLY_SKIPPED_OR_DROPPED"
TARGET_GRID_COMPLETENESS_POLICY = "EVERY_WITHIN_SCOPE_TARGET_MUST_RECEIVE_A_SCIENTIFIC_CELL_OR_BLOCK"
HOST_REFERENCE_SAMPLING_PROTOCOL_VERSION = "COMPONENTIZED_PER_COMPONENT_LOCAL_CRS_SAMPLING_V1"
BUFFER_RADIAL_AUDIT_VERSION = "7A.6.1"  # scientific_domain.max_buffer_radial_relative_error's bearing set/method


@dataclass(frozen=True)
class ModelDevelopmentProtocol:
    scientific_grid_config: ScientificGridConfig
    frozen_domain_distance_km: float | None
    domain_rule_status: str
    predeclared_domain_candidates_km: tuple
    primary_horizon_days: int
    target_assignment_rule: str
    out_of_domain_target_rule: str
    primary_evaluation_metrics: tuple
    optional_evaluation_metrics: tuple
    background_semantics_version: str
    model_fitting_cutoff: str
    purge_policy_version: str
    baseline_registry_version: str
    baseline_registry_hash: str
    kernel_registry_version: str
    kernel_registry_hash: str
    # -- Checkpoint 7A.5 (superseded diagnostic; kept for continuity) --
    local_context_protocol_version: str
    local_context_protocol_hash: str | None
    st_dbscan_config_hash_if_used: str | None
    local_context_status: str | None
    target_scope_rule_version: str
    nonlocal_target_policy: str
    out_of_domain_local_target_policy: str
    projection_strategy: str
    projection_tolerance_version: str
    # -- Checkpoint 7A.6 (primary contract) --
    primary_local_evaluation_distance_km: float
    primary_local_evaluation_distance_status: str
    sensitivity_local_evaluation_distance_km: float
    sensitivity_local_evaluation_distance_status: str
    scientific_grid_cell_size_km: float
    scientific_grid_cell_size_status: str
    primary_scope_rule_version: str
    scope_rationale_document_version: str
    development_target_distance_distribution_already_exposed: bool
    all_source_contribution_rule: str
    st_dbscan_gating_policy_version: str
    # -- Checkpoint 7A.6.1 --
    primary_scope_truth_method: str
    geodesic_boundary_tolerance_km: float
    geodesic_boundary_tolerance_version: str
    scientific_domain_protocol_version: str
    component_edge_distance_km_multiple: float
    grid_truth_separation_policy_version: str
    zero_origin_drop_policy: str
    target_grid_completeness_policy: str
    host_reference_sampling_protocol_version: str
    buffer_radial_audit_version: str
    # -- Checkpoint 7A.6.2 --
    scientific_cell_identity_version: str

    def protocol_dict(self) -> dict:
        return {
            "scientific_grid_config": self.scientific_grid_config.config_dict(),
            "frozen_domain_distance_km": self.frozen_domain_distance_km,
            "domain_rule_status": self.domain_rule_status,
            "predeclared_domain_candidates_km": list(self.predeclared_domain_candidates_km),
            "primary_horizon_days": self.primary_horizon_days,
            "target_assignment_rule": self.target_assignment_rule,
            "out_of_domain_target_rule": self.out_of_domain_target_rule,
            "primary_evaluation_metrics": list(self.primary_evaluation_metrics),
            "optional_evaluation_metrics": list(self.optional_evaluation_metrics),
            "background_semantics_version": self.background_semantics_version,
            "model_fitting_cutoff": self.model_fitting_cutoff,
            "purge_policy_version": self.purge_policy_version,
            "baseline_registry_version": self.baseline_registry_version,
            "baseline_registry_hash": self.baseline_registry_hash,
            "kernel_registry_version": self.kernel_registry_version,
            "kernel_registry_hash": self.kernel_registry_hash,
            "local_context_protocol_version": self.local_context_protocol_version,
            "local_context_protocol_hash": self.local_context_protocol_hash,
            "st_dbscan_config_hash_if_used": self.st_dbscan_config_hash_if_used,
            "local_context_status": self.local_context_status,
            "target_scope_rule_version": self.target_scope_rule_version,
            "nonlocal_target_policy": self.nonlocal_target_policy,
            "out_of_domain_local_target_policy": self.out_of_domain_local_target_policy,
            "projection_strategy": self.projection_strategy,
            "projection_tolerance_version": self.projection_tolerance_version,
            "primary_local_evaluation_distance_km": self.primary_local_evaluation_distance_km,
            "primary_local_evaluation_distance_status": self.primary_local_evaluation_distance_status,
            "sensitivity_local_evaluation_distance_km": self.sensitivity_local_evaluation_distance_km,
            "sensitivity_local_evaluation_distance_status": self.sensitivity_local_evaluation_distance_status,
            "scientific_grid_cell_size_km": self.scientific_grid_cell_size_km,
            "scientific_grid_cell_size_status": self.scientific_grid_cell_size_status,
            "primary_scope_rule_version": self.primary_scope_rule_version,
            "scope_rationale_document_version": self.scope_rationale_document_version,
            "development_target_distance_distribution_already_exposed": self.development_target_distance_distribution_already_exposed,
            "all_source_contribution_rule": self.all_source_contribution_rule,
            "st_dbscan_gating_policy_version": self.st_dbscan_gating_policy_version,
            "primary_scope_truth_method": self.primary_scope_truth_method,
            "geodesic_boundary_tolerance_km": self.geodesic_boundary_tolerance_km,
            "geodesic_boundary_tolerance_version": self.geodesic_boundary_tolerance_version,
            "scientific_domain_protocol_version": self.scientific_domain_protocol_version,
            "component_edge_distance_km_multiple": self.component_edge_distance_km_multiple,
            "grid_truth_separation_policy_version": self.grid_truth_separation_policy_version,
            "zero_origin_drop_policy": self.zero_origin_drop_policy,
            "target_grid_completeness_policy": self.target_grid_completeness_policy,
            "host_reference_sampling_protocol_version": self.host_reference_sampling_protocol_version,
            "buffer_radial_audit_version": self.buffer_radial_audit_version,
            "scientific_cell_identity_version": self.scientific_cell_identity_version,
        }

    def model_development_protocol_hash(self) -> str:
        canonical = json.dumps(self.protocol_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_model_development_protocol(
    *, scientific_grid_config: ScientificGridConfig, frozen_domain_distance_km: float | None, domain_rule_status: str,
    local_context_protocol_hash: str | None = None, st_dbscan_config_hash_if_used: str | None = None,
    local_context_status: str | None = None,
) -> ModelDevelopmentProtocol:
    return ModelDevelopmentProtocol(
        scientific_grid_config=scientific_grid_config, frozen_domain_distance_km=frozen_domain_distance_km,
        domain_rule_status=domain_rule_status, predeclared_domain_candidates_km=PREDECLARED_DOMAIN_CANDIDATES_KM,
        primary_horizon_days=PRIMARY_HORIZON_DAYS, target_assignment_rule=TARGET_ASSIGNMENT_RULE,
        out_of_domain_target_rule=OUT_OF_DOMAIN_TARGET_RULE, primary_evaluation_metrics=PRIMARY_EVALUATION_METRICS,
        optional_evaluation_metrics=OPTIONAL_EVALUATION_METRICS, background_semantics_version=BACKGROUND_SEMANTICS_VERSION,
        model_fitting_cutoff=MODEL_FITTING_CUTOFF, purge_policy_version=PURGE_POLICY_VERSION,
        baseline_registry_version=BASELINE_CANDIDATE_REGISTRY_VERSION, baseline_registry_hash=baseline_registry_hash(),
        kernel_registry_version=KERNEL_CANDIDATE_REGISTRY_VERSION, kernel_registry_hash=kernel_registry_hash(),
        local_context_protocol_version=LOCAL_CONTEXT_PROTOCOL_VERSION, local_context_protocol_hash=local_context_protocol_hash,
        st_dbscan_config_hash_if_used=st_dbscan_config_hash_if_used, local_context_status=local_context_status,
        target_scope_rule_version=TARGET_SCOPE_RULE_VERSION, nonlocal_target_policy=NONLOCAL_TARGET_POLICY,
        out_of_domain_local_target_policy=OUT_OF_DOMAIN_LOCAL_TARGET_POLICY,
        projection_strategy=scientific_grid_config.crs_strategy, projection_tolerance_version=scientific_grid_config.projection_tolerance_version,
        primary_local_evaluation_distance_km=PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
        primary_local_evaluation_distance_status=PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS,
        sensitivity_local_evaluation_distance_km=SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM,
        sensitivity_local_evaluation_distance_status=SENSITIVITY_LOCAL_EVALUATION_DISTANCE_STATUS,
        scientific_grid_cell_size_km=SCIENTIFIC_GRID_CELL_SIZE_KM, scientific_grid_cell_size_status=SCIENTIFIC_GRID_CELL_SIZE_STATUS,
        primary_scope_rule_version=PRIMARY_SCOPE_RULE_VERSION, scope_rationale_document_version=SCOPE_RATIONALE_DOCUMENT_VERSION,
        development_target_distance_distribution_already_exposed=DEVELOPMENT_TARGET_DISTANCE_DISTRIBUTION_ALREADY_EXPOSED,
        all_source_contribution_rule=ALL_SOURCE_CONTRIBUTION_RULE, st_dbscan_gating_policy_version=ST_DBSCAN_GATING_POLICY_VERSION,
        primary_scope_truth_method=PRIMARY_SCOPE_TRUTH_METHOD, geodesic_boundary_tolerance_km=GEODESIC_BOUNDARY_TOLERANCE_KM,
        geodesic_boundary_tolerance_version=GEODESIC_BOUNDARY_TOLERANCE_VERSION,
        scientific_domain_protocol_version=SCIENTIFIC_DOMAIN_PROTOCOL_VERSION,
        component_edge_distance_km_multiple=COMPONENT_EDGE_DISTANCE_KM_MULTIPLE,
        grid_truth_separation_policy_version=GRID_TRUTH_SEPARATION_POLICY_VERSION, zero_origin_drop_policy=ZERO_ORIGIN_DROP_POLICY,
        target_grid_completeness_policy=TARGET_GRID_COMPLETENESS_POLICY,
        host_reference_sampling_protocol_version=HOST_REFERENCE_SAMPLING_PROTOCOL_VERSION,
        buffer_radial_audit_version=BUFFER_RADIAL_AUDIT_VERSION,
        scientific_cell_identity_version=SCIENTIFIC_CELL_IDENTITY_VERSION,
    )

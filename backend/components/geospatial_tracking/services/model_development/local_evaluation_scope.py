"""Checkpoint 7A.6 / 7A.6.1: the PRIMARY local evaluation scope contract
— decoupled entirely from ST-DBSCAN, and (7A.6.1) from projected grid
geometry too.

**Critical semantic bug 7A.6 corrected (Parts 1-2)**: 7A.5's target-scope
classifier reused `STDBSCANConfig.eps_time_days` (a SOURCE-SOURCE
clustering temporal neighborhood, e.g. 3 days) as the temporal gate for
future D1-D7 target evaluation. That conflated two unrelated concepts —
a spatially close D4-D7 outcome could be rejected purely because the
source-target event-date gap exceeded the clustering epsilon, which has
nothing to do with the D1-D7 forecast horizon. Forecast target time
eligibility is ALREADY fully defined by `1 <= lead_days <= 7`
(`services.forecast_target.build_forecast_targets`); this module never
re-applies any ST-DBSCAN temporal parameter to a target at all.

**Checkpoint 7A.6.1 correction (Parts 2-6)**: 7A.6's PRIMARY scope
decision itself was computed from a PROJECTED `DomainGeometry.union_geometry`
built from a single AOI-local UTM CRS covering an entire origin's
eligible-source set — the real 7A.6 audit found 9 real origins where
that single-CRS assumption was itself `PROJECTION_CONTEXT_UNSAFE`. From
7A.6.1 onward, PRIMARY SCOPE TRUTH is computed directly from real WGS84
geodesic distance (`services.geospatial.distance.distance_km`) —
`classify_target_primary_scope` has NO projected-geometry parameter at
all. A `services.geospatial.scientific_domain.ScientificEvaluationDomain`
(component-local projected grid geometry) may optionally be supplied for
the SEPARATE grid-cell-assignment step, but it never participates in, and
can never override, the scope decision itself (Part 6, 24) — a projected
grid-representation failure is recorded as its own status
(`GRID_REPRESENTATION_BOUNDARY_MISMATCH`), never silently converted into
`OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE`.

**ST-DBSCAN is contextual, never gating (Part 5, unchanged from 7A.6)**:
nothing in this module accepts an `STDBSCANConfig` (`ST-DECOUPLE-01`).
ST cluster membership, noise/temporal-unusable role, `eps_time_days`,
`MinPts`, and config hash all have ZERO effect on: whether an eligible
source contributes to the domain/hazard-source set, whether a grid cell
exists, D1-D7 target temporal eligibility, or the primary evaluation
denominator (`ST-DECOUPLE-02..05`). `services/model_development/local_context.py`
and `local_target_scope.py` are NOT deleted — they remain valid for
descriptive outbreak-context purposes only.

**Terminology (Parts 4, 19 — unchanged)**: distance/domain membership
alone can never prove an outbreak is biologically independent or
unrelated. This module NEVER emits `NONLOCAL_FUTURE_EVENT` or a
`local_context_id`-like field implying established biological
membership. Its scope labels:

    WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE
    OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE   -- "outside the declared
                                                  modeling claim," never
                                                  "proven unrelated"
    LOCAL_SCOPE_UNRESOLVED                    -- no eligible sources at
                                                  all existed to test against

**Numerical boundary tolerance (7A.6.1 Part 4)**: `GEODESIC_BOUNDARY_TOLERANCE_KM`
(imported from `scientific_domain`, `1e-6`) handles ONLY floating-point
equality at exactly the 25km boundary — never biological uncertainty,
never tuned using outcomes, versioned and included in
`model_development_protocol_hash`.

**Frozen primary envelope (7A.6 Parts 7-8, unchanged)**:
`PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0`, status
`FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE` — an OPERATIONAL LOCAL
ANALYSIS ENVELOPE, never a disease transmission radius, maximum vector
flight distance, infection boundary, kernel scale, spread-front reach,
or speed x time product. See `LOCAL_EVALUATION_SCOPE_RATIONALE.md`.

**Pre-registered, non-primary sensitivity envelope (7A.6 Part 21,
unchanged)**: `SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM = 50.0` exists
ONLY as a future robustness check — never substituted for the primary
envelope, and no predictive score is computed under it here.

**Target scope is not target assignment (Part 6, 16-18)**: a WITHIN-scope
target is additionally, and separately, assigned to a real scientific
grid cell via `scientific_domain.assign_target_to_scientific_evaluation_domain`
(deterministic polygon containment, lexicographically-smallest
`grid_cell_id` tie-break) — never nearest-centroid, and never allowed to
change the scope decision itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geospatial.distance import distance_km
from ..geospatial.scientific_domain import (
    GEODESIC_BOUNDARY_TOLERANCE_KM,
    GEODESIC_BOUNDARY_TOLERANCE_VERSION,
    GRID_CELL_ASSIGNED,
    GRID_REPRESENTATION_BOUNDARY_MISMATCH,
    ScientificEvaluationDomain,
    assign_target_to_scientific_evaluation_domain,
)
from ..geospatial.source_geometry import EligibleSourcePoint

PRIMARY_LOCAL_EVALUATION_DISTANCE_KM = 25.0
PRIMARY_LOCAL_EVALUATION_DISTANCE_STATUS = "FROZEN_OPERATIONAL_LOCAL_EVALUATION_ENVELOPE"

# Part 21 (7A.6): pre-registered future robustness check ONLY — never
# substituted for the primary envelope by any function in this module.
SENSITIVITY_LOCAL_EVALUATION_DISTANCE_KM = 50.0
SENSITIVITY_LOCAL_EVALUATION_DISTANCE_STATUS = "PREREGISTERED_SENSITIVITY_ENVELOPE_NOT_PRIMARY"

# Part 24 (7A.6)
SCIENTIFIC_GRID_CELL_SIZE_KM = 5.0
SCIENTIFIC_GRID_CELL_SIZE_STATUS = "FROZEN_ENGINEERING_RESOLUTION"

WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE = "WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE"
OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE = "OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE"
LOCAL_SCOPE_UNRESOLVED = "LOCAL_SCOPE_UNRESOLVED"

DEVELOPMENT_TARGET_DISTANCE_DISTRIBUTION_ALREADY_EXPOSED = True  # Part 8 (7A.6) — never claimed blind

PRIMARY_SCOPE_TRUTH_METHOD = "WGS84_GEODESIC_DISTANCE"  # Part 6 — never "PROJECTED_UNION_GEOMETRY"


@dataclass(frozen=True)
class PrimaryTargetScopeResult:
    forecast_origin_id: str
    target_id: str
    target_event_id: str
    lead_days: int
    scope_status: str  # WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE | OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE | LOCAL_SCOPE_UNRESOLVED
    target_grid_cell_id: str | None  # assigned only when WITHIN scope and an evaluation_domain was supplied
    grid_representation_status: str | None  # GRID_CELL_ASSIGNED | GRID_REPRESENTATION_BOUNDARY_MISMATCH | None (not attempted)
    nearest_domain_component_id: str | None  # descriptive only (Part 19) — never implies biological membership
    nearest_source_id: str | None  # descriptive only
    min_distance_to_eligible_source_km: float | None  # descriptive only -- also what scope truth itself was computed from

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "target_id": self.target_id, "target_event_id": self.target_event_id,
            "lead_days": self.lead_days, "scope_status": self.scope_status, "target_grid_cell_id": self.target_grid_cell_id,
            "grid_representation_status": self.grid_representation_status,
            "nearest_domain_component_id": self.nearest_domain_component_id, "nearest_source_id": self.nearest_source_id,
            "min_distance_to_eligible_source_km": self.min_distance_to_eligible_source_km,
        }


def classify_target_primary_scope(
    *, target, sources: list[EligibleSourcePoint], evaluation_domain: ScientificEvaluationDomain | None = None,
) -> PrimaryTargetScopeResult:
    """PRIMARY SCOPE TRUTH (Part 3): `min_d_km = min(WGS84 geodesic
    distance(source, target) for every eligible active source)`; WITHIN
    iff `min_d_km <= PRIMARY_LOCAL_EVALUATION_DISTANCE_KM + GEODESIC_BOUNDARY_TOLERANCE_KM`.
    NO `DomainGeometry`/projected-geometry/`STDBSCANConfig` parameter
    exists on this signature at all (`GEO-SCOPE-01`, `ST-DECOUPLE-01`);
    source event-date gaps, ST eps_time, `MinPts`, and cluster role are
    never inspected (`SCOPE-TIME-01..04`). `target`'s own `lead_days` is
    assumed already horizon-filtered by `build_forecast_targets`
    (`1 <= lead_days <= 7`) — this function does not re-derive temporal
    eligibility, it only classifies SPATIAL scope for an already-eligible
    target.

    `evaluation_domain` (optional): used ONLY for the separate grid-cell-
    assignment step (Part 6, 17-18) when the target is WITHIN scope —
    never consulted for the scope decision itself, and its
    `n_unsafe_components()` has no bearing on scope truth
    (`GEO-SCOPE-07`)."""
    if not sources:
        return PrimaryTargetScopeResult(
            forecast_origin_id=target.forecast_origin_id, target_id=target.target_id, target_event_id=target.target_event_id,
            lead_days=target.lead_days, scope_status=LOCAL_SCOPE_UNRESOLVED, target_grid_cell_id=None,
            grid_representation_status=None, nearest_domain_component_id=None, nearest_source_id=None,
            min_distance_to_eligible_source_km=None,
        )

    ordered_sources = sorted(sources, key=lambda s: s.source_id)
    nearest_source_id, min_d = None, None
    for s in ordered_sources:
        d = distance_km(s.latitude, s.longitude, target.latitude, target.longitude)
        if min_d is None or d < min_d:
            min_d, nearest_source_id = d, s.source_id

    within = min_d <= (PRIMARY_LOCAL_EVALUATION_DISTANCE_KM + GEODESIC_BOUNDARY_TOLERANCE_KM)
    status = WITHIN_DECLARED_LOCAL_EVALUATION_SCOPE if within else OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE

    nearest_component_id = None
    if evaluation_domain is not None:
        for component in evaluation_domain.components:
            if nearest_source_id in component.source_ids:
                nearest_component_id = component.component_id
                break

    target_grid_cell_id = None
    grid_representation_status = None
    if within and evaluation_domain is not None:
        target_grid_cell_id, grid_representation_status = assign_target_to_scientific_evaluation_domain(
            target=target, evaluation_domain=evaluation_domain,
        )

    return PrimaryTargetScopeResult(
        forecast_origin_id=target.forecast_origin_id, target_id=target.target_id, target_event_id=target.target_event_id,
        lead_days=target.lead_days, scope_status=status, target_grid_cell_id=target_grid_cell_id,
        grid_representation_status=grid_representation_status, nearest_domain_component_id=nearest_component_id,
        nearest_source_id=nearest_source_id, min_distance_to_eligible_source_km=min_d,
    )

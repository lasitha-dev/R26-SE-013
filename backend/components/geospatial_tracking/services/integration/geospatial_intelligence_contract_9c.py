"""Checkpoint 9C Part 13: `FrozenGeospatialIntelligenceContract9C` --
the DB/framework-independent internal presentation contract combining
the already-frozen risk (7C), direction (8B.3), apparent-rate (9B), and
nominal-reach (9C) components without conflating their scientific
meanings. No FastAPI route exists yet -- this is a plain dataclass DTO.

**The DTO performs no scientific computation.** Every value assembled
here is either a pure frozen constant (rate/nominal-reach/provenance)
or was computed by an already-frozen upstream module and passed in as
an argument (risk score, direction tendency) --
`build_frozen_geospatial_intelligence_contract_9c` never queries a
database and never calls `score_origin_candidates_7c` /
`compute_cell_direction_tendency_8b3` itself; those remain the caller's
responsibility.

**Hard separations enforced by construction** (Parts 3, 6, 7, 11):
`operational_evaluation_envelope_km` (frozen 25km) and
`nominal_reach_by_day` are always two SEPARATE top-level fields, never
merged or reconciled against each other;
`risk.risk_surface_temporal_semantics` is always
`STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT` -- nominal reach is never
used to fabricate a day-varying C0 score; `apparent_rate` never derives
from `direction.bearing_deg`/`directional_clarity`, and direction is
never scaled into km/day.

**Bearing 0 is valid NORTH** (Part 8): every truthiness check in this
module against `bearing_deg`/other optional floats uses `is not None`,
never bare truthiness -- a real 0.0 must never be conflated with
"unavailable".
"""

from __future__ import annotations

from dataclasses import dataclass

from ..direction.c0_cell_local_tendency_8b3 import CellDirectionTendency8B3
from ..model_development.rate_protocol_9b import EXPOSED_ESTIMATOR_VALUE_9B, RATE_LABEL_9B
from .nominal_reach_9c import (
    FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
    FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
    NOMINAL_REACH_SEMANTICS_9C,
    NominalReachDay9C,
    build_nominal_reach_by_day_9c,
)

RISK_SCORE_SEMANTICS_9C = "RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY"
RISK_SURFACE_TEMPORAL_SEMANTICS_9C = "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"

RATE_STATUS_9C = "FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE"
RATE_SCOPE_9C = "D1_D7_25KM_DEVELOPMENT_LOCAL_SCOPE"
RATE_VALIDATION_STATUS_9C = "NOT_HELDOUT_RATE_VALIDATED"
SRI_LANKA_RATE_STATUS_9C = "NOT_EVALUATED"

OPERATIONAL_EVALUATION_ENVELOPE_KM_9C = 25.0

DIRECTION_STATUS_UNAVAILABLE_9C = "DIRECTION_UNAVAILABLE_NO_CELL_INPUT"

NEAREST_SOURCE_SEMANTICS_9C = "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE"

RESEARCH_EVIDENCE_STATUS_9C = {
    "risk": "development selected + held-out-from-fitting assessment disclosed",
    "direction": "descriptive structural geometric field; predictive truth not frozen",
    "rate": "development-derived apparent historical rate",
    "sri_lanka": "small-sample geographic-transfer case-study for risk only, NOT a rate estimate",
}


@dataclass(frozen=True)
class RiskComponent9C:
    risk_score: float | None
    risk_score_semantics: str
    candidate_id: str
    frozen_spec_hash: str
    risk_surface_temporal_semantics: str

    def as_dict(self) -> dict:
        return {
            "risk_score": self.risk_score, "risk_score_semantics": self.risk_score_semantics,
            "candidate_id": self.candidate_id, "frozen_spec_hash": self.frozen_spec_hash,
            "risk_surface_temporal_semantics": self.risk_surface_temporal_semantics,
        }


@dataclass(frozen=True)
class DirectionComponent9C:
    direction_method_id: str | None
    direction_method_version: str | None
    bearing_deg: float | None
    directional_clarity: float | None
    directional_input_coverage: float | None
    direction_status: str
    direction_semantics: str | None

    def as_dict(self) -> dict:
        return {
            "direction_method_id": self.direction_method_id, "direction_method_version": self.direction_method_version,
            "bearing_deg": self.bearing_deg, "directional_clarity": self.directional_clarity,
            "directional_input_coverage": self.directional_input_coverage,
            "direction_status": self.direction_status, "direction_semantics": self.direction_semantics,
        }


@dataclass(frozen=True)
class ApparentRateComponent9C:
    apparent_rate_km_day: float
    apparent_rate_label: str
    rate_interval_lower_km_day: float
    rate_interval_upper_km_day: float
    rate_status: str
    rate_scope: str
    rate_validation_status: str
    sri_lanka_rate_status: str

    def as_dict(self) -> dict:
        return {
            "apparent_rate_km_day": self.apparent_rate_km_day, "apparent_rate_label": self.apparent_rate_label,
            "rate_interval_lower_km_day": self.rate_interval_lower_km_day,
            "rate_interval_upper_km_day": self.rate_interval_upper_km_day,
            "rate_status": self.rate_status, "rate_scope": self.rate_scope,
            "rate_validation_status": self.rate_validation_status, "sri_lanka_rate_status": self.sri_lanka_rate_status,
        }


@dataclass(frozen=True)
class ProvenanceComponent9C:
    frozen_c0_candidate_id: str
    frozen_7c_spec_hash: str
    direction_method_protocol_hash_8b3: str
    direction_evaluation_truth_status: str
    historical_9a_protocol_hash: str
    nine_a1_exposure_classification: str
    s0_bootstrap_protocol_hash_9b: str
    rate_input_csv_sha256: str
    rate_canonical_payload_sha256: str
    research_evidence_status: dict

    def as_dict(self) -> dict:
        return {
            "frozen_c0_candidate_id": self.frozen_c0_candidate_id, "frozen_7c_spec_hash": self.frozen_7c_spec_hash,
            "direction_method_protocol_hash_8b3": self.direction_method_protocol_hash_8b3,
            "direction_evaluation_truth_status": self.direction_evaluation_truth_status,
            "historical_9a_protocol_hash": self.historical_9a_protocol_hash,
            "nine_a1_exposure_classification": self.nine_a1_exposure_classification,
            "s0_bootstrap_protocol_hash_9b": self.s0_bootstrap_protocol_hash_9b,
            "rate_input_csv_sha256": self.rate_input_csv_sha256,
            "rate_canonical_payload_sha256": self.rate_canonical_payload_sha256,
            "research_evidence_status": dict(self.research_evidence_status),
        }


@dataclass(frozen=True)
class FrozenGeospatialIntelligenceContract9C:
    risk: RiskComponent9C
    direction: DirectionComponent9C
    apparent_rate: ApparentRateComponent9C
    nominal_reach_by_day: tuple
    nominal_reach_semantics: str
    operational_evaluation_envelope_km: float
    provenance: ProvenanceComponent9C
    limitations: tuple

    def as_dict(self) -> dict:
        return {
            "risk": self.risk.as_dict(), "direction": self.direction.as_dict(),
            "apparent_rate": self.apparent_rate.as_dict(),
            "nominal_reach_by_day": [d.as_dict() for d in self.nominal_reach_by_day],
            "nominal_reach_semantics": self.nominal_reach_semantics,
            "operational_evaluation_envelope_km": self.operational_evaluation_envelope_km,
            "provenance": self.provenance.as_dict(), "limitations": list(self.limitations),
        }


def default_apparent_rate_component_9c() -> ApparentRateComponent9C:
    """Part 9. The rate component is a single frozen global scalar --
    never per-cell, never recomputed from raw data here."""
    return ApparentRateComponent9C(
        apparent_rate_km_day=EXPOSED_ESTIMATOR_VALUE_9B, apparent_rate_label=RATE_LABEL_9B,
        rate_interval_lower_km_day=FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
        rate_interval_upper_km_day=FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
        rate_status=RATE_STATUS_9C, rate_scope=RATE_SCOPE_9C,
        rate_validation_status=RATE_VALIDATION_STATUS_9C, sri_lanka_rate_status=SRI_LANKA_RATE_STATUS_9C,
    )


def direction_component_from_tendency_9c(tendency: CellDirectionTendency8B3 | None) -> DirectionComponent9C:
    """Part 8. `tendency=None` means direction was never evaluated for
    this cell (e.g. no eligible sources) -- `bearing_deg`/`directional_clarity`
    stay `None`, never fabricated to `0.0`."""
    if tendency is None:
        return DirectionComponent9C(
            direction_method_id=None, direction_method_version=None, bearing_deg=None,
            directional_clarity=None, directional_input_coverage=None,
            direction_status=DIRECTION_STATUS_UNAVAILABLE_9C, direction_semantics=None,
        )
    return DirectionComponent9C(
        direction_method_id=tendency.method_id, direction_method_version=tendency.method_version,
        bearing_deg=tendency.bearing_deg, directional_clarity=tendency.directional_clarity,
        directional_input_coverage=tendency.directional_input_coverage,
        direction_status=tendency.direction_status, direction_semantics=tendency.direction_semantics,
    )


def build_frozen_geospatial_intelligence_contract_9c(
    *,
    risk_score: float | None,
    candidate_id: str,
    frozen_spec_hash: str,
    direction_tendency: CellDirectionTendency8B3 | None,
    direction_method_protocol_hash_8b3: str,
    direction_evaluation_truth_status: str,
    historical_9a_protocol_hash: str,
    nine_a1_exposure_classification: str,
    s0_bootstrap_protocol_hash_9b: str,
    rate_input_csv_sha256: str,
    rate_canonical_payload_sha256: str,
    limitations: tuple,
) -> FrozenGeospatialIntelligenceContract9C:
    """Part 13. Pure assembly: `risk_score` and `direction_tendency` are
    supplied by the caller (already computed by the frozen 7C/8B.3
    services elsewhere) -- this function does not derive them. The rate
    and nominal-reach components are frozen global constants, identical
    across every call."""
    risk = RiskComponent9C(
        risk_score=risk_score, risk_score_semantics=RISK_SCORE_SEMANTICS_9C,
        candidate_id=candidate_id, frozen_spec_hash=frozen_spec_hash,
        risk_surface_temporal_semantics=RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
    )
    direction = direction_component_from_tendency_9c(direction_tendency)
    apparent_rate = default_apparent_rate_component_9c()
    nominal_reach_by_day = build_nominal_reach_by_day_9c()
    provenance = ProvenanceComponent9C(
        frozen_c0_candidate_id=candidate_id, frozen_7c_spec_hash=frozen_spec_hash,
        direction_method_protocol_hash_8b3=direction_method_protocol_hash_8b3,
        direction_evaluation_truth_status=direction_evaluation_truth_status,
        historical_9a_protocol_hash=historical_9a_protocol_hash,
        nine_a1_exposure_classification=nine_a1_exposure_classification,
        s0_bootstrap_protocol_hash_9b=s0_bootstrap_protocol_hash_9b,
        rate_input_csv_sha256=rate_input_csv_sha256, rate_canonical_payload_sha256=rate_canonical_payload_sha256,
        research_evidence_status=RESEARCH_EVIDENCE_STATUS_9C,
    )
    return FrozenGeospatialIntelligenceContract9C(
        risk=risk, direction=direction, apparent_rate=apparent_rate,
        nominal_reach_by_day=nominal_reach_by_day, nominal_reach_semantics=NOMINAL_REACH_SEMANTICS_9C,
        operational_evaluation_envelope_km=OPERATIONAL_EVALUATION_ENVELOPE_KM_9C,
        provenance=provenance, limitations=limitations,
    )

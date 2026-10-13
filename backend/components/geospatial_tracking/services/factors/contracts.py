"""Checkpoint 6D: the real feature->factor transformation contracts.

This package (`services/factors/`) is the DEVELOPMENT-ONLY transformation
layer between raw `FeatureSnapshot`s (Checkpoint 6A/6A.5) and the hazard
engine's dimensionless factor contracts (`services/hazard/`, Checkpoint
6C/6C.5). It never puts fitting logic inside `services/hazard/` — that
package remains a pure mathematical consumer of already-decided factor
values (Part 1).

    RAW FeatureSnapshot
            |
            v
    FIT_DEVELOPMENT-only reference observations
            |
            v
    FactorReferenceProfile
            |
            v
    candidate real transformations -> FactorSnapshot

**Permanent rule**: a scientifically BLOCKED factor is an acceptable
result. Fabricating a factor to make the full hazard equation run is
NOT acceptable. Checkpoint 6D produces `FactorSnapshot`s; it does NOT
produce a real `HazardSnapshot` — see `factor_snapshot.py`'s module
docstring for the architectural firewall that keeps it that way.

**Candidate/status vocabulary** — deliberately DISTINCT from
`services.hazard.contracts.FactorStatus` (`REAL`/`SOFTWARE_FIXTURE_ONLY`/
`MISSING`/`BLOCKED`/`DEMO`), which describes whether a hazard-engine
INPUT is usable. This vocabulary describes the SCIENTIFIC STATE of a
real transformation candidate:

    REAL_TRANSFORMED_CANDIDATE       — a real raw value was successfully
                                        transformed via a named candidate
                                        transform; not yet a frozen
                                        scientific truth.
    RAW_REAL_COMPONENT               — a real raw value/component is
                                        preserved as-is (no transform
                                        applied, or transform is
                                        intentionally identity/component-
                                        level only).
    MISSING                          — the real source was reachable but
                                        had no data for this location/time.
    BLOCKED                          — the real source could not be
                                        retrieved at all.
    NOT_SELECTED                     — a scientifically valid raw input
                                        exists but this checkpoint does
                                        not select/combine it into a
                                        factor (e.g. an unused land-cover
                                        class).
    NOT_YET_SCIENTIFICALLY_DEFINED   — no defensible transformation
                                        exists yet at all (e.g.
                                        `environmental_suitability_factor`,
                                        `water_context_factor`,
                                        `source_strength_factor` in 6D).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from enum import Enum

REAL_TRANSFORMED_CANDIDATE = "REAL_TRANSFORMED_CANDIDATE"
RAW_REAL_COMPONENT = "RAW_REAL_COMPONENT"
MISSING = "MISSING"
BLOCKED = "BLOCKED"
NOT_SELECTED = "NOT_SELECTED"
NOT_YET_SCIENTIFICALLY_DEFINED = "NOT_YET_SCIENTIFICALLY_DEFINED"
# Checkpoint 6D.5 Parts 11, 13: two additional explicit failure statuses
# — neither is ever silently converted to a usable number.
UNIT_MISMATCH = "UNIT_MISMATCH"
DEGENERATE_REFERENCE_DISTRIBUTION = "DEGENERATE_REFERENCE_DISTRIBUTION"

_CANDIDATE_STATUSES = {
    REAL_TRANSFORMED_CANDIDATE, RAW_REAL_COMPONENT, MISSING, BLOCKED, NOT_SELECTED, NOT_YET_SCIENTIFICALLY_DEFINED,
    UNIT_MISMATCH, DEGENERATE_REFERENCE_DISTRIBUTION,
}

UNFROZEN_DEVELOPMENT_CANDIDATE = "UNFROZEN_DEVELOPMENT_CANDIDATE"
ALLOWED_TRANSFORM_PARAMETER_STATUSES = {UNFROZEN_DEVELOPMENT_CANDIDATE}  # never FROZEN_REFERENCE in 6D

# Checkpoint 6D.5 Part 15: reference-profile-level statuses (distinct
# from the per-value candidate_status vocabulary above).
COMPLETE_DIAGNOSTIC = "COMPLETE_DIAGNOSTIC"
INSUFFICIENT_REFERENCE_COVERAGE = "INSUFFICIENT_REFERENCE_COVERAGE"
NO_USABLE_HOST_DENSITY_OBSERVATIONS = "NO_USABLE_HOST_DENSITY_OBSERVATIONS"
INCOMPATIBLE_REFERENCE_STRATA = "INCOMPATIBLE_REFERENCE_STRATA"
# Checkpoint 6D.6 Part 6: the SAME observation identity produced two
# DIFFERENT effective raw values -- a data/identity conflict, never a
# duplicate. Blocks the entire pool, never a partially-cleaned subset.
REFERENCE_OBSERVATION_VALUE_CONFLICT = "REFERENCE_OBSERVATION_VALUE_CONFLICT"

# Checkpoint 6D.5 Part 16: global-readiness labeling — a small real
# smoke NEVER implies the reference profile is ready to be treated as
# THE global development reference.
GLOBAL_REFERENCE_PROFILE_READY = "GLOBAL_REFERENCE_PROFILE_READY"
GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY = "GLOBAL_REFERENCE_PROFILE_DIAGNOSTIC_ONLY"


class HostTransformFamily(str, Enum):
    """Part 11: two explicit candidate host-density transforms — NEITHER
    is scientifically selected in this checkpoint."""

    LOG1P_ROBUST_REFERENCE_SCALE = "LOG1P_ROBUST_REFERENCE_SCALE"
    EMPIRICAL_CDF_REFERENCE = "EMPIRICAL_CDF_REFERENCE"


class EcdfTieConvention(str, Enum):
    """Checkpoint 6D.5 Part 14: the EXACT, documented ECDF tie
    convention — never left implicit. Neither is scientifically
    selected using held-out performance; the choice only fixes
    reproducibility, and it participates in `transform_config_hash` so
    changing it changes scientific identity.

    LOWER_RANK: `bisect_left` — a query value equal to `k` existing
        reference values ranks BELOW all of them (percentile = count of
        reference values strictly less than the query, divided by N).
    MID_RANK: the average of the lower-rank and upper-rank (`bisect_right`)
        positions — the conventional "mid-rank" ECDF tie handling.
    """

    LOWER_RANK = "LOWER_RANK"
    MID_RANK = "MID_RANK"


class ReferenceCompatibilityMode(str, Enum):
    """Checkpoint 6D.5 Part 7: the PRIMARY 6D.5 mode is
    `STRICT_COMPATIBLE` — reference-profile construction inspects
    relevant dataset lineage BEFORE pooling and refuses (never silently
    pools) an incompatible mix."""

    STRICT_COMPATIBLE = "STRICT_COMPATIBLE"


@dataclass(frozen=True)
class ReferenceStratumKey:
    """Checkpoint 6D.5 Part 9 / Checkpoint 6D.6 Part 9: an explicit,
    factor-specific compatibility stratum — country is NEVER
    automatically a normalization stratum; only real dataset-lineage
    facts are. Distinct-stratum detection MUST use ALL fields
    (`canonical_key()`/`digest()`) — never only
    `dataset_comparability_group` + `canonical_units` (6D.6 Part 9-11:
    a `sampling_protocol_version` or `dataset_family` difference alone
    must also make two strata distinct, even if version/units strings
    happen to match)."""

    factor_family: str
    dataset_family: str
    dataset_comparability_group: str
    canonical_units: str
    sampling_protocol_version: str

    def as_dict(self) -> dict:
        return {
            "factor_family": self.factor_family, "dataset_family": self.dataset_family,
            "dataset_comparability_group": self.dataset_comparability_group,
            "canonical_units": self.canonical_units, "sampling_protocol_version": self.sampling_protocol_version,
        }

    def canonical_key(self) -> str:
        """Deterministic, field-order-independent string identity over
        ALL fields — the sole basis for distinct-stratum detection."""
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_key().encode("utf-8")).hexdigest()


class IncompatibleReferenceStrataError(ValueError):
    """Raised when `ReferenceCompatibilityMode.STRICT_COMPATIBLE`
    detects more than one incompatible dataset stratum feeding the same
    reference profile (Part 8 option A)."""


@dataclass(frozen=True)
class ClippingAudit:
    was_clipped_low: bool
    was_clipped_high: bool
    reference_lower: float
    reference_upper: float

    def as_dict(self) -> dict:
        return {
            "was_clipped_low": self.was_clipped_low,
            "was_clipped_high": self.was_clipped_high,
            "reference_lower": self.reference_lower,
            "reference_upper": self.reference_upper,
        }


@dataclass(frozen=True)
class TransformedFactorProvenance:
    """Part 21: the full lineage a candidate transformed value must
    carry. A bare number without this lineage must never enter a
    `FactorSnapshot`."""

    factor_or_component_name: str
    raw_feature_names: tuple
    raw_values: tuple
    raw_units: tuple
    raw_feature_statuses: tuple
    source_dataset_versions: tuple
    feature_snapshot_id: str | None
    transform_id: str | None
    transform_config_hash: str | None
    reference_profile_hash: str | None
    transformed_value: float | None
    candidate_status: str
    clipping: ClippingAudit | None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.candidate_status not in _CANDIDATE_STATUSES:
            raise ValueError(f"unknown candidate_status {self.candidate_status!r}")
        if self.candidate_status not in (REAL_TRANSFORMED_CANDIDATE, RAW_REAL_COMPONENT) and self.transformed_value is not None:
            raise ValueError(
                f"candidate_status={self.candidate_status!r} must never carry a transformed_value — this would "
                "let a MISSING/BLOCKED/NOT_SELECTED/NOT_YET_SCIENTIFICALLY_DEFINED candidate be silently misread "
                "as usable"
            )
        if self.candidate_status in (REAL_TRANSFORMED_CANDIDATE, RAW_REAL_COMPONENT):
            if self.transformed_value is None:
                raise ValueError(f"candidate_status={self.candidate_status!r} requires a non-None transformed_value")
            if math.isnan(self.transformed_value) or math.isinf(self.transformed_value):
                raise ValueError(f"transformed_value must be finite, got {self.transformed_value!r}")

    def as_dict(self) -> dict:
        return {
            "factor_or_component_name": self.factor_or_component_name,
            "raw_feature_names": list(self.raw_feature_names),
            "raw_values": list(self.raw_values),
            "raw_units": list(self.raw_units),
            "raw_feature_statuses": list(self.raw_feature_statuses),
            "source_dataset_versions": list(self.source_dataset_versions),
            "feature_snapshot_id": self.feature_snapshot_id,
            "transform_id": self.transform_id,
            "transform_config_hash": self.transform_config_hash,
            "reference_profile_hash": self.reference_profile_hash,
            "transformed_value": self.transformed_value,
            "candidate_status": self.candidate_status,
            "clipping": self.clipping.as_dict() if self.clipping else None,
            "notes": self.notes,
        }

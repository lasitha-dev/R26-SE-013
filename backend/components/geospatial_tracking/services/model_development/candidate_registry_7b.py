"""Checkpoint 7B Parts 9-11: pre-registered kernel-scale candidates and the
full 24-member baseline x kernel x scale candidate grid.

`KERNEL_SCALE_CANDIDATES_KM = (5.0, 10.0, 15.0, 25.0)` is frozen HERE,
before any baseline predictive score is ever evaluated (Part 10) — never
extended/shrunk after seeing development performance, never re-derived
from held-out or Sri Lanka results. Composed with the already-frozen
`baseline_registry.BASELINE_CANDIDATES` (3 families) and
`baseline_registry.KERNEL_CANDIDATE_FAMILIES` (EXPONENTIAL/GAUSSIAN),
this gives exactly `3 * 2 * 4 = 24` primary candidates (Part 11).

`distance_scale_km` remains `UNFROZEN_DEVELOPMENT_PARAMETER` per
`services.hazard.kernels` — nothing here calls it a transmission
radius/spread radius/vector-travel distance/spread-front reach.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .baseline_registry import (
    BASELINE_CANDIDATE_REGISTRY_VERSION,
    BASELINE_CANDIDATES,
    KERNEL_CANDIDATE_FAMILIES,
    KERNEL_CANDIDATE_REGISTRY_VERSION,
)
from .evaluation_protocol_7b import baseline_evaluation_protocol_hash

KERNEL_SCALE_CANDIDATES_KM: tuple = (5.0, 10.0, 15.0, 25.0)
KERNEL_SCALE_CANDIDATE_REGISTRY_VERSION = "7B.1"
KERNEL_SCALE_CANDIDATE_RATIONALE = (
    "spans short through broader local smoothing scales; remains within the "
    "already-frozen 25km operational evaluation envelope; broadly brackets "
    "the previously exposed development source-spacing scale; selected as a "
    "finite development candidate registry, not from predictive performance"
)

# 7B.1 identity never bound the evaluation protocol (percentile
# definition, tie semantics, thresholds, aggregation, eligibility rule)
# into candidate_id -- kept ONLY as `_legacy_candidate_id_v1` so the
# PROVISIONAL_7B_PRE_FINALIZATION_RUN's ids can be deterministically
# remapped (Part 9's IDENTITY_ONLY_RESULT_REMAP), never as the current
# identity scheme.
LEGACY_FULL_CANDIDATE_REGISTRY_VERSION = "7B.1"
FULL_CANDIDATE_REGISTRY_VERSION = "7B.2"


@dataclass(frozen=True)
class BaselineCandidateSpec:
    """One concrete, fully-parameterized development candidate."""

    candidate_id: str
    baseline_family: str
    host_factor_candidate: str | None
    kernel_family: str
    kernel_scale_km: float
    source_weighting: str
    output_label: str

    def as_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "baseline_family": self.baseline_family,
            "host_factor_candidate": self.host_factor_candidate,
            "kernel_family": self.kernel_family,
            "kernel_scale_km": self.kernel_scale_km,
            "source_weighting": self.source_weighting,
            "output_label": self.output_label,
        }


def _candidate_id_payload(*, baseline_family: str, kernel_family: str, kernel_scale_km: float, host_factor_candidate: str | None, registry_version: str) -> dict:
    payload = {
        "baseline_family": baseline_family,
        "kernel_family": kernel_family,
        "kernel_scale_km": kernel_scale_km,
        "host_factor_candidate": host_factor_candidate,
        "baseline_candidate_registry_version": BASELINE_CANDIDATE_REGISTRY_VERSION,
        "kernel_candidate_registry_version": KERNEL_CANDIDATE_REGISTRY_VERSION,
        "kernel_scale_candidate_registry_version": KERNEL_SCALE_CANDIDATE_REGISTRY_VERSION,
        "full_candidate_registry_version": registry_version,
    }
    if registry_version != LEGACY_FULL_CANDIDATE_REGISTRY_VERSION:
        # Part 8: bind candidate identity to the EVALUATION protocol too
        # -- a percentile-definition/tie/threshold/aggregation/eligibility
        # change must never silently preserve the same candidate_id.
        payload["baseline_evaluation_protocol_hash"] = baseline_evaluation_protocol_hash()
    return payload


def _legacy_candidate_id_v1(*, baseline_family: str, kernel_family: str, kernel_scale_km: float, host_factor_candidate: str | None) -> str:
    """The PRE-finalization-hardening (7B.1) identity scheme -- preserved
    ONLY so `build_identity_only_result_remap` can prove a deterministic
    one-to-one mapping from `PROVISIONAL_7B_PRE_FINALIZATION_RUN`
    candidate ids to the current (7B.2) ones. Never used to build the
    live registry."""
    payload = _candidate_id_payload(
        baseline_family=baseline_family, kernel_family=kernel_family, kernel_scale_km=kernel_scale_km,
        host_factor_candidate=host_factor_candidate, registry_version=LEGACY_FULL_CANDIDATE_REGISTRY_VERSION,
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"CAND:{baseline_family}:{kernel_family}:{kernel_scale_km:g}KM:{host_factor_candidate or 'NONE'}:{digest}"


def _candidate_id(*, baseline_family: str, kernel_family: str, kernel_scale_km: float, host_factor_candidate: str | None) -> str:
    """Deterministic and order-invariant (KERNEL7B-05): a pure function of
    the candidate's own four defining parameters, the frozen registry
    versions, AND `baseline_evaluation_protocol_hash()` (Part 8) — never
    depends on iteration order or dict insertion order."""
    payload = _candidate_id_payload(
        baseline_family=baseline_family, kernel_family=kernel_family, kernel_scale_km=kernel_scale_km,
        host_factor_candidate=host_factor_candidate, registry_version=FULL_CANDIDATE_REGISTRY_VERSION,
    )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"CAND:{baseline_family}:{kernel_family}:{kernel_scale_km:g}KM:{host_factor_candidate or 'NONE'}:{digest}"


def _enumerate_candidate_tuples():
    for baseline in BASELINE_CANDIDATES:
        for kernel_family in KERNEL_CANDIDATE_FAMILIES:
            for scale_km in KERNEL_SCALE_CANDIDATES_KM:
                yield baseline, kernel_family, scale_km


def build_candidate_registry() -> tuple[BaselineCandidateSpec, ...]:
    """The full, frozen 24-candidate development grid (Part 11) — 3
    baseline families x 2 kernel families x 4 kernel scales. Held-out/Sri
    Lanka results can never mutate this (KERNEL7B-04): this function takes
    no arguments and reads only frozen module-level constants."""
    candidates: list[BaselineCandidateSpec] = []
    for baseline, kernel_family, scale_km in _enumerate_candidate_tuples():
        candidates.append(
            BaselineCandidateSpec(
                candidate_id=_candidate_id(
                    baseline_family=baseline.family, kernel_family=kernel_family,
                    kernel_scale_km=scale_km, host_factor_candidate=baseline.host_factor_candidate,
                ),
                baseline_family=baseline.family, host_factor_candidate=baseline.host_factor_candidate,
                kernel_family=kernel_family, kernel_scale_km=scale_km,
                source_weighting=baseline.source_weighting, output_label=baseline.output_label,
            )
        )
    return tuple(sorted(candidates, key=lambda c: c.candidate_id))


def build_identity_only_result_remap() -> dict:
    """Part 9: `IDENTITY_ONLY_RESULT_REMAP` -- a deterministic, one-to-one
    mapping from every legacy (7B.1) `candidate_id` to its current (7B.2)
    `candidate_id`, over the SAME 24 underlying (baseline_family,
    kernel_family, kernel_scale_km, host_factor_candidate) tuples. Proves
    the identity-hardening change never touched grid/source/host-
    transform/kernel-math/score/percentile/selection-metric computation
    -- only how the candidate is NAMED -- so a `PROVISIONAL_7B_PRE_FINALIZATION_RUN`'s
    already-computed numerical results can be relabeled instead of
    re-running the expensive raw GIS extraction."""
    mapping: dict[str, str] = {}
    for baseline, kernel_family, scale_km in _enumerate_candidate_tuples():
        old_id = _legacy_candidate_id_v1(
            baseline_family=baseline.family, kernel_family=kernel_family, kernel_scale_km=scale_km,
            host_factor_candidate=baseline.host_factor_candidate,
        )
        new_id = _candidate_id(
            baseline_family=baseline.family, kernel_family=kernel_family, kernel_scale_km=scale_km,
            host_factor_candidate=baseline.host_factor_candidate,
        )
        mapping[old_id] = new_id
    return mapping


def candidate_registry_dict() -> dict:
    return {
        "version": FULL_CANDIDATE_REGISTRY_VERSION,
        "kernel_scale_candidates_km": list(KERNEL_SCALE_CANDIDATES_KM),
        "kernel_scale_candidate_registry_version": KERNEL_SCALE_CANDIDATE_REGISTRY_VERSION,
        "candidates": [c.as_dict() for c in build_candidate_registry()],
    }


def candidate_registry_hash() -> str:
    canonical = json.dumps(candidate_registry_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

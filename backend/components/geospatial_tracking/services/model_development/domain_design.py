"""Checkpoint 7A Parts 7-11: DEVELOPMENT_DOMAIN_DESIGN — predeclared
domain-distance candidates evaluated against real `FIT_DEVELOPMENT`
D1-D7 target coverage, to freeze (or honestly block) the scientific
evaluation-domain rule BEFORE any model candidate is ever fit or
compared.

**Why inspecting FIT_DEVELOPMENT future-target geometry here is
allowed (Part 7)**: this module is DESIGN-TIME introspection only —
FIT_DEVELOPMENT is development data, no predictive model score exists
anywhere in this checkpoint, and the resulting domain rule is frozen
BEFORE any candidate model is fit or compared using it. This is labeled
`DEVELOPMENT_DOMAIN_DESIGN`, never model validation.
`assert_fit_development_only` is called at this module's own entry
point (a hard firewall, never caller trust) — `HELD_OUT_FROM_MODEL_FITTING`
and `SRI_LANKA_TRANSFER_CASE_STUDY` origins/targets are NEVER inspected
here, for domain design or anything else.

**Domain candidates are COMPUTATIONAL/EVALUATION DOMAIN EXTENTS (Part
8), never a biological claim**: not a spread radius, transmission
boundary, nominal reach, kernel scale, or speed x time product. No
biological meaning is inferred from whichever candidate is selected.

**Coverage test == exact buffer-union membership (Part 9)**: a target
is "covered" by candidate distance D exactly when its geodesic distance
to at least one eligible active source at that origin's t0 is <= D —
this is mathematically identical to testing point-membership in the
union of D-radius buffers around every eligible source (never just the
nearest/trigger source), computed directly via geodesic distance
without needing to construct the buffer polygons themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..forecast_target import build_forecast_targets
from ..geospatial.distance import distance_km
from ..model_fitting_exposure import MODEL_FITTING_CUTOFF, assert_fit_development_only
from ..source_selector import get_eligible_sources

PREDECLARED_DOMAIN_CANDIDATES_KM: tuple = (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)

DOMAIN_LABEL_NOTE = (
    "domain_distance_km is a COMPUTATIONAL/EVALUATION DOMAIN EXTENT only — "
    "never a spread radius, transmission boundary, nominal reach, kernel scale, "
    "or speed x time product. No biological meaning is inferred from it."
)

FROZEN_EVALUATION_DOMAIN_RULE = "FROZEN_EVALUATION_DOMAIN_RULE"
DOMAIN_RULE_BLOCKED = "DOMAIN_RULE_BLOCKED_NO_CANDIDATE_ACHIEVES_FULL_COVERAGE"


@dataclass(frozen=True)
class TargetDomainCoverage:
    forecast_origin_id: str
    target_id: str
    target_event_id: str
    lead_days: int
    min_distance_to_eligible_source_km: float | None  # None only if the origin had zero eligible sources
    covered_by_candidate_km: dict  # {candidate_km: bool}

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id, "target_id": self.target_id,
            "target_event_id": self.target_event_id, "lead_days": self.lead_days,
            "min_distance_to_eligible_source_km": self.min_distance_to_eligible_source_km,
            "covered_by_candidate_km": {str(k): v for k, v in self.covered_by_candidate_km.items()},
        }


@dataclass(frozen=True)
class DomainCandidateAudit:
    candidate_distance_km: float
    n_targets_total: int
    n_targets_covered: int
    coverage_fraction: float | None
    n_targets_uncovered: int
    uncovered_target_ids: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "candidate_distance_km": self.candidate_distance_km, "n_targets_total": self.n_targets_total,
            "n_targets_covered": self.n_targets_covered, "coverage_fraction": self.coverage_fraction,
            "n_targets_uncovered": self.n_targets_uncovered, "uncovered_target_ids": list(self.uncovered_target_ids),
        }


def build_development_domain_candidate_audit(
    repo, *, fit_development_origins: list, disease: str, active_window_days: int,
    candidates_km: tuple = PREDECLARED_DOMAIN_CANDIDATES_KM,
    model_fitting_cutoff: str = MODEL_FITTING_CUTOFF,
) -> tuple[list[DomainCandidateAudit], list[TargetDomainCoverage]]:
    """`FIT_DEVELOPMENT`-only (DOMAIN-02/03: hard firewall, not caller
    trust). Evaluates every `risk_target_eligible` D1-D7 target across
    the supplied origins against each predeclared candidate distance.
    Pseudo-replication safety (Part 20): each row here is one
    (forecast_origin_id, target_event_id) pair, matching
    `ForecastTarget`'s own uniqueness guarantee within an origin — the
    SAME real target event may legitimately appear from several
    different forecast origins (repeated forecasting of one biological
    event), which is intentional, not double-counting.

    `model_fitting_cutoff` (default: the generic `MODEL_FITTING_CUTOFF`)
    is forwarded to `assert_fit_development_only` so a caller with its
    own frozen cutoff (e.g. a disease-specific one) can pass it through
    instead of always being checked against the generic default — no
    dataset-specific cutoff is hardcoded in this module."""
    assert_fit_development_only(
        fit_development_origins,
        caller="build_development_domain_candidate_audit",
        cutoff=model_fitting_cutoff,
    )

    rows: list[TargetDomainCoverage] = []
    for origin in sorted(fit_development_origins, key=lambda o: o.forecast_origin_id):
        result = get_eligible_sources(
            repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
            domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        sources = result.sources
        targets = build_forecast_targets(repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in sources})
        for t in sorted(targets, key=lambda t: t.target_id):
            if not t.risk_target_eligible:
                continue
            if sources:
                min_d = min(distance_km(s.latitude, s.longitude, t.latitude, t.longitude) for s in sources)
            else:
                min_d = None
            covered = {c: (min_d is not None and min_d <= c) for c in candidates_km}
            rows.append(TargetDomainCoverage(
                forecast_origin_id=origin.forecast_origin_id, target_id=t.target_id, target_event_id=t.target_event_id,
                lead_days=t.lead_days, min_distance_to_eligible_source_km=min_d, covered_by_candidate_km=covered,
            ))

    audits: list[DomainCandidateAudit] = []
    for c in candidates_km:
        total = len(rows)
        covered_rows = [r for r in rows if r.covered_by_candidate_km[c]]
        uncovered_rows = [r for r in rows if not r.covered_by_candidate_km[c]]
        audits.append(DomainCandidateAudit(
            candidate_distance_km=c, n_targets_total=total, n_targets_covered=len(covered_rows),
            coverage_fraction=(len(covered_rows) / total) if total else None,
            n_targets_uncovered=len(uncovered_rows),
            uncovered_target_ids=tuple(sorted(r.target_id for r in uncovered_rows)),
        ))
    return audits, rows


def select_frozen_domain_distance(audits: list[DomainCandidateAudit]) -> tuple[float | None, str]:
    """The smallest predeclared candidate achieving 100% target
    coverage — a transparent rule fixed BEFORE any model-score
    computation (Part 10), never chosen using model accuracy/capture.
    Returns `(None, DOMAIN_RULE_BLOCKED)` — never silently expanding
    past the predeclared candidates, and never dropping outliers to
    force a result — if no candidate achieves full coverage."""
    for a in sorted(audits, key=lambda a: a.candidate_distance_km):
        if a.n_targets_total == 0:
            continue
        if a.n_targets_covered == a.n_targets_total:
            return a.candidate_distance_km, FROZEN_EVALUATION_DOMAIN_RULE
    return None, DOMAIN_RULE_BLOCKED

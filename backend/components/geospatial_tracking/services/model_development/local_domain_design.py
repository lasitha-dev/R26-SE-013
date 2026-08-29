"""Checkpoint 7A.5 Part 20: local-domain candidate coverage audit —
reruns the SAME predeclared 25-200km candidates (Part 19 — unchanged,
never expanded post-hoc) against `LOCAL_SCOPE_TARGET`-only rows, each
measured against its OWN `LocalForecastContext`'s member-source
coordinates — never all country-eligible sources (that was 7A's own
finding: a same-country source unrelated to a trigger's local situation
could make a distant target look artificially "close").

`NONLOCAL_FUTURE_EVENT`/`LOCAL_SCOPE_UNRESOLVED` rows never enter this
audit's denominator (Part 21 — a nonlocal event is outside the local
model's scientific claim, not a coverage failure of it). A
`LOCAL_SCOPE_TARGET` that the frozen domain distance still misses stays
an explicit, visible coverage failure (`uncovered_target_ids`, Part 22)
— never silently reclassified as nonlocal.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geospatial.distance import distance_km
from .domain_design import PREDECLARED_DOMAIN_CANDIDATES_KM, DomainCandidateAudit


@dataclass(frozen=True)
class LocalScopedTarget:
    target_id: str
    target_lat: float
    target_lon: float
    local_context_id: str


def build_local_domain_candidate_audit(
    *, local_scoped_targets: list[LocalScopedTarget], member_coords_by_context: dict,
    candidates_km: tuple = PREDECLARED_DOMAIN_CANDIDATES_KM,
) -> list[DomainCandidateAudit]:
    """`member_coords_by_context`: `{local_context_id: [(lat, lon), ...]}`
    — the associated `LocalForecastContext`'s own member coordinates
    only. `candidates_km` defaults to, and is never silently expanded
    beyond, `PREDECLARED_DOMAIN_CANDIDATES_KM` (LOCALDOMAIN-05)."""
    total = len(local_scoped_targets)
    covered_by_candidate: dict = {c: set() for c in candidates_km}
    for t in local_scoped_targets:
        members = member_coords_by_context.get(t.local_context_id, [])
        min_d = min((distance_km(lat, lon, t.target_lat, t.target_lon) for lat, lon in members), default=None)
        for c in candidates_km:
            if min_d is not None and min_d <= c:
                covered_by_candidate[c].add(t.target_id)

    audits: list[DomainCandidateAudit] = []
    for c in candidates_km:
        covered_ids = covered_by_candidate[c]
        uncovered_ids = sorted(t.target_id for t in local_scoped_targets if t.target_id not in covered_ids)
        audits.append(DomainCandidateAudit(
            candidate_distance_km=c, n_targets_total=total, n_targets_covered=len(covered_ids),
            coverage_fraction=(len(covered_ids) / total) if total else None,
            n_targets_uncovered=len(uncovered_ids), uncovered_target_ids=tuple(uncovered_ids),
        ))
    return audits

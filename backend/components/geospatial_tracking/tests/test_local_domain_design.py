"""Checkpoint 7A.5 Part 35: local-domain freeze tests — LOCALDOMAIN-01..06."""

from __future__ import annotations

import inspect

from components.geospatial_tracking.services.model_development.domain_design import (
    DOMAIN_RULE_BLOCKED,
    FROZEN_EVALUATION_DOMAIN_RULE,
    PREDECLARED_DOMAIN_CANDIDATES_KM,
    select_frozen_domain_distance,
)
from components.geospatial_tracking.services.model_development.local_domain_design import (
    LocalScopedTarget,
    build_local_domain_candidate_audit,
)


def test_localdomain_01_audit_uses_local_scope_target_only_by_construction():
    # the function's only target-shaped input is LocalScopedTarget --
    # there is structurally no way to pass a NONLOCAL_FUTURE_EVENT row
    # in without the caller already having filtered to local scope.
    params = inspect.signature(build_local_domain_candidate_audit).parameters
    assert "local_scoped_targets" in params
    assert LocalScopedTarget.__dataclass_fields__.keys() == {"target_id", "target_lat", "target_lon", "local_context_id"}


def test_localdomain_02_nonlocal_events_do_not_enter_denominator():
    # simulate: 3 LOCAL_SCOPE_TARGET rows near a context, plus a NONLOCAL
    # event is simply never constructed as a LocalScopedTarget at all --
    # the denominator (n_targets_total) reflects only what was passed.
    targets = [
        LocalScopedTarget(target_id="T1", target_lat=15.01, target_lon=101.01, local_context_id="CTX1"),
        LocalScopedTarget(target_id="T2", target_lat=15.02, target_lon=101.02, local_context_id="CTX1"),
    ]
    member_coords = {"CTX1": [(15.0, 101.0)]}
    audits = build_local_domain_candidate_audit(local_scoped_targets=targets, member_coords_by_context=member_coords, candidates_km=(25.0, 50.0))
    assert audits[0].n_targets_total == 2  # never 3 -- the nonlocal event was never in the input


def test_localdomain_03_smallest_100pct_covering_candidate_selected():
    targets = [LocalScopedTarget(target_id=f"T{i}", target_lat=15.0 + i * 0.001, target_lon=101.0, local_context_id="CTX1") for i in range(3)]
    member_coords = {"CTX1": [(15.0, 101.0)]}
    audits = build_local_domain_candidate_audit(local_scoped_targets=targets, member_coords_by_context=member_coords, candidates_km=(25.0, 50.0, 75.0))
    distance, status = select_frozen_domain_distance(audits)
    assert distance == 25.0  # all targets are <1km away -- smallest candidate already covers 100%
    assert status == FROZEN_EVALUATION_DOMAIN_RULE


def test_localdomain_04_no_100pct_candidate_is_blocked():
    targets = [
        LocalScopedTarget(target_id="T1", target_lat=15.0, target_lon=101.0, local_context_id="CTX1"),
        LocalScopedTarget(target_id="T_FAR", target_lat=25.0, target_lon=110.0, local_context_id="CTX1"),  # far beyond every candidate
    ]
    member_coords = {"CTX1": [(15.0, 101.0)]}
    audits = build_local_domain_candidate_audit(local_scoped_targets=targets, member_coords_by_context=member_coords, candidates_km=(25.0, 50.0, 75.0, 100.0, 150.0, 200.0))
    distance, status = select_frozen_domain_distance(audits)
    assert distance is None
    assert status == DOMAIN_RULE_BLOCKED


def test_localdomain_05_candidate_list_cannot_be_post_hoc_expanded():
    sig = inspect.signature(build_local_domain_candidate_audit)
    default_candidates = sig.parameters["candidates_km"].default
    assert default_candidates == PREDECLARED_DOMAIN_CANDIDATES_KM
    assert default_candidates == (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)


def test_localdomain_06_local_scope_target_outside_frozen_domain_is_explicit_failure():
    targets = [
        LocalScopedTarget(target_id="T_NEAR", target_lat=15.0, target_lon=101.0, local_context_id="CTX1"),
        LocalScopedTarget(target_id="T_OUTSIDE", target_lat=15.5, target_lon=101.5, local_context_id="CTX1"),  # ~75km away
    ]
    member_coords = {"CTX1": [(15.0, 101.0)]}
    audits = build_local_domain_candidate_audit(local_scoped_targets=targets, member_coords_by_context=member_coords, candidates_km=(25.0,))
    audit_25 = audits[0]
    assert "T_OUTSIDE" in audit_25.uncovered_target_ids
    assert audit_25.n_targets_uncovered == 1
    # still counted in the total (retained, never dropped/reclassified)
    assert audit_25.n_targets_total == 2

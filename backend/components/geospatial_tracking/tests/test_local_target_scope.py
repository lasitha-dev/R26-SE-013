"""Checkpoint 7A.5 Part 32: local target-scope tests — LOCAL-TGT-01..07."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.forecast_target import build_forecast_targets
from components.geospatial_tracking.services.model_development import local_context, local_target_scope
from components.geospatial_tracking.services.stdbscan.config import STDBSCANConfig

DISEASE = "Lumpy skin disease"


@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _st_config(**overrides) -> STDBSCANConfig:
    fields = dict(eps_space_km=10.0, eps_time_days=5.0, min_core_supports=2, active_window_days=14, gps_core_policy="PRIMARY_CORE_SUPPORT", parameter_status="UNFROZEN_DEVELOPMENT_CANDIDATE")
    fields.update(overrides)
    return STDBSCANConfig(**fields)


def _historical(**overrides):
    fields = dict(
        country="Thailand", disease=DISEASE, outbreak_start_date="2026/01/03",
        proxy_availability_date="2026/01/03", proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        gps_quality=GpsQuality.EXACT.value, dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def _origin(*, trigger_ids, t0="2026-01-05") -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id=f"ORIGIN:Thailand:{t0}", country="Thailand", t0=t0, temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=list(trigger_ids), trigger_source_count=len(trigger_ids))


def _setup(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="A2", latitude=15.05, longitude=101.05))
    origin = _origin(trigger_ids=["A1"])
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    member_points_by_context = {c.local_context_id: local_context.member_points(repo, source_ids=c.local_source_ids, t0=origin.t0) for c in contexts}
    return origin, contexts, member_points_by_context


def _target(**overrides):
    fields = dict(forecast_origin_id="O", target_id="O::T1", target_event_id="T1", lead_days=2, latitude=15.02, longitude=101.02, historical_event_date="2026-01-07")
    fields.update(overrides)
    return SimpleNamespace(**fields)


def test_local_tgt_01_all_future_events_remain_in_master_target_ledger(repo):
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="FAR_TARGET", latitude=40.0, longitude=140.0, outbreak_start_date="2026/01/07", proxy_availability_date="2026/01/07"))
    origin = _origin(trigger_ids=["A1"])
    targets = build_forecast_targets(repo, origin, disease=DISEASE, source_ids_at_origin={"A1"})
    # the far, clearly-nonlocal event still appears in the MASTER target ledger -- never dropped before classification
    assert any(t.target_event_id == "FAR_TARGET" for t in targets)


def test_local_tgt_02_local_scope_association_uses_only_frozen_rule(repo):
    origin, contexts, member_points_by_context = _setup(repo)
    near_target = _target(latitude=15.02, longitude=101.02, historical_event_date="2026-01-07")  # within 10km/5days of A1/A2
    result = local_target_scope.classify_target_local_scope(target=near_target, local_contexts=contexts, member_points_by_context=member_points_by_context, st_config=_st_config())
    assert result.scope_status == local_target_scope.LOCAL_SCOPE_TARGET


def test_local_tgt_03_nonlocal_future_event_is_not_silently_dropped(repo):
    origin, contexts, member_points_by_context = _setup(repo)
    far_target = _target(latitude=40.0, longitude=140.0, historical_event_date="2026-01-07")  # far outside eps_space_km
    result = local_target_scope.classify_target_local_scope(target=far_target, local_contexts=contexts, member_points_by_context=member_points_by_context, st_config=_st_config())
    assert result.scope_status == local_target_scope.NONLOCAL_FUTURE_EVENT
    # retained -- a full result row exists, never None/omitted
    assert result.target_event_id == far_target.target_event_id
    assert result.local_context_id is not None


def test_local_tgt_04_local_scope_unresolved_remains_explicit():
    empty_target = _target()
    result = local_target_scope.classify_target_local_scope(target=empty_target, local_contexts=[], member_points_by_context={}, st_config=_st_config())
    assert result.scope_status == local_target_scope.LOCAL_SCOPE_UNRESOLVED


def test_local_tgt_05_no_model_score_parameter_influences_label():
    forbidden = {"score", "risk", "probability", "prediction"}
    for name, fn in inspect.getmembers(local_target_scope, inspect.isfunction):
        if fn.__module__ != local_target_scope.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert not (params & forbidden), f"{name} has forbidden parameter(s) {params & forbidden}"


def test_local_tgt_06_no_kernel_scale_parameter_influences_label():
    forbidden = {"kernel", "distance_scale_km", "kernel_family"}
    for name, fn in inspect.getmembers(local_target_scope, inspect.isfunction):
        if fn.__module__ != local_target_scope.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert not (params & forbidden), f"{name} has forbidden parameter(s) {params & forbidden}"


def test_local_tgt_07_no_domain_distance_parameter_can_alter_the_rule():
    forbidden = {"domain_distance_km", "domain_distance", "candidate_distance_km"}
    for name, fn in inspect.getmembers(local_target_scope, inspect.isfunction):
        if fn.__module__ != local_target_scope.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        assert not (params & forbidden), f"{name} has forbidden parameter(s) {params & forbidden}"


def test_local_scope_result_deterministic(repo):
    origin, contexts, member_points_by_context = _setup(repo)
    near_target = _target(latitude=15.02, longitude=101.02, historical_event_date="2026-01-07")
    r1 = local_target_scope.classify_target_local_scope(target=near_target, local_contexts=contexts, member_points_by_context=member_points_by_context, st_config=_st_config())
    r2 = local_target_scope.classify_target_local_scope(target=near_target, local_contexts=contexts, member_points_by_context=member_points_by_context, st_config=_st_config())
    assert r1.as_dict() == r2.as_dict()

"""Checkpoint 7A.5 Part 31: local source-context tests —
LOCAL-SRC-01..08."""

from __future__ import annotations

import inspect

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.model_development import local_context
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


def _origin(*, trigger_ids, t0="2026-01-05", country="Thailand") -> ForecastOrigin:
    return ForecastOrigin(forecast_origin_id=f"ORIGIN:{country}:{t0}", country=country, t0=t0, temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=list(trigger_ids), trigger_source_count=len(trigger_ids))


def _seed_two_disconnected_groups(repo):
    # Group A: two close sources near (15.0, 101.0) -- ~7.7km apart
    repo.add_historical_record(_historical(source_record_id="A1", latitude=15.0, longitude=101.0))
    repo.add_historical_record(_historical(source_record_id="A2", latitude=15.05, longitude=101.05))
    # Group B: two close sources near (20.0, 105.0) -- ~7.7km apart, >>10km from group A
    repo.add_historical_record(_historical(source_record_id="B1", latitude=20.0, longitude=105.0))
    repo.add_historical_record(_historical(source_record_id="B2", latitude=20.05, longitude=105.05))


def test_local_src_01_disconnected_country_contexts_not_merged(repo):
    _seed_two_disconnected_groups(repo)
    origin = _origin(trigger_ids=["A1", "B1"])
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    assert len(contexts) == 2
    member_sets = [set(c.local_source_ids) for c in contexts]
    assert {"A1", "A2"} in member_sets
    assert {"B1", "B2"} in member_sets
    # never one giant merged context
    assert not any(set(c.local_source_ids) >= {"A1", "A2", "B1", "B2"} for c in contexts)


def test_local_src_02_trigger_remains_in_its_own_context(repo):
    _seed_two_disconnected_groups(repo)
    origin = _origin(trigger_ids=["A1", "B1"])
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    for ctx in contexts:
        assert set(ctx.trigger_source_ids) & set(ctx.local_source_ids) == set(ctx.trigger_source_ids)


def test_local_src_03_noise_trigger_is_singleton_context(repo):
    repo.add_historical_record(_historical(source_record_id="C1", latitude=5.0, longitude=95.0))  # isolated, no neighbors
    origin = _origin(trigger_ids=["C1"])
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    assert len(contexts) == 1
    assert contexts[0].local_source_ids == ("C1",)
    assert contexts[0].trigger_source_ids == ("C1",)


def test_local_src_04_excluded_country_sources_are_auditable(repo):
    _seed_two_disconnected_groups(repo)
    origin = _origin(trigger_ids=["A1"])  # only A1 is a trigger -- group B is country-eligible but excluded
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    assert len(contexts) == 1
    ctx = contexts[0]
    assert set(ctx.local_source_ids) == {"A1", "A2"}
    assert "B1" in ctx.excluded_country_source_ids and "B2" in ctx.excluded_country_source_ids
    assert ctx.excluded_source_reasons["B1"] == local_context.EXCLUDED_OUTSIDE_TRIGGER_LOCAL_CONTEXT
    assert ctx.excluded_source_reasons["B2"] == local_context.EXCLUDED_OUTSIDE_TRIGGER_LOCAL_CONTEXT
    # nothing physically removed from country_eligible_source_ids
    assert {"A1", "A2", "B1", "B2"} <= set(ctx.country_eligible_source_ids)


def test_local_src_05_held_out_origin_rejected_by_development_report(repo):
    _seed_two_disconnected_groups(repo)
    held_out = _origin(trigger_ids=["A1"], t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        local_context.build_local_forecast_context_development_report(repo, fit_development_origins=[held_out], disease=DISEASE, st_config=_st_config())


def test_local_src_06_sri_lanka_origin_rejected_by_development_report(repo):
    _seed_two_disconnected_groups(repo)
    sri_lanka = _origin(trigger_ids=["A1"], country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        local_context.build_local_forecast_context_development_report(repo, fit_development_origins=[sri_lanka], disease=DISEASE, st_config=_st_config())


def test_local_src_07_no_future_target_parameter_in_local_context_construction():
    forbidden = ("target", "future_outcome", "envelope")
    for name, fn in inspect.getmembers(local_context, inspect.isfunction):
        if fn.__module__ != local_context.__name__:
            continue
        params = {p.lower() for p in inspect.signature(fn).parameters}
        for f in forbidden:
            assert not any(f in p for p in params), f"{name} has a forbidden target-like parameter"


def test_local_src_08_deterministic_local_context_id(repo):
    _seed_two_disconnected_groups(repo)
    origin = _origin(trigger_ids=["A1", "B1"])
    contexts_1 = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    contexts_2 = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    ids_1 = sorted(c.local_context_id for c in contexts_1)
    ids_2 = sorted(c.local_context_id for c in contexts_2)
    assert ids_1 == ids_2
    # generated_at never affects identity
    contexts_3 = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config(), generated_at="2099-01-01T00:00:00Z")
    ids_3 = sorted(c.local_context_id for c in contexts_3)
    assert ids_1 == ids_3


def test_context_status_never_claims_frozen(repo):
    _seed_two_disconnected_groups(repo)
    origin = _origin(trigger_ids=["A1"])
    contexts = local_context.build_local_forecast_contexts(repo, origin=origin, disease=DISEASE, st_config=_st_config())
    for ctx in contexts:
        assert ctx.context_status == local_context.CONTEXT_STATUS_UNFROZEN
        assert "FROZEN" not in ctx.context_status.replace("UNFROZEN", "")

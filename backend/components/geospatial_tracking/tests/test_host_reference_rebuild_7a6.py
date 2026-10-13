"""Checkpoint 7A.6 Part 35 / Checkpoint 7A.6.1 Part 29 (hardened):
scientific-grid host-reference rebuild tests — HOSTREF7A6-04/05,
HOSTREF7A61-01..05."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.model_development.host_reference_rebuild import (
    build_scientific_grid_host_reference_development_report,
)

DISEASE = "Lumpy skin disease"


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


class _TouchRepo:
    """Raises if ANY repository method is called -- used to prove the
    FIT_DEVELOPMENT firewall fires BEFORE any repository/raster access
    (HOSTREF7A61-01/02)."""

    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"repository method {name!r} was called before the FIT_DEVELOPMENT firewall check")
        return _fail


class _EmptyRepo:
    def list_historical_records(self, country=None):
        return []

    def list_outbreak_episodes(self, country=None):
        return []


def test_hostref7a61_01_mixed_held_out_raises_before_any_repository_access():
    good = _origin()
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_scientific_grid_host_reference_development_report(
            _TouchRepo(), fit_development_origins=[good, held_out], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
        )


def test_hostref7a61_02_mixed_sri_lanka_raises_before_any_repository_access():
    good = _origin()
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        build_scientific_grid_host_reference_development_report(
            _TouchRepo(), fit_development_origins=[good, sri_lanka], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
        )


def test_hostref7a61_03_all_intended_origins_required_for_completeness():
    # two intended origins, both real (no eligible sources -> both
    # "blocked" with the empty repo) -- completeness must be False,
    # never silently True for whatever subset happened to succeed.
    origin_a = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", t0="2021-06-01")
    origin_b = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-02", t0="2021-06-02")
    profile, snapshots, completeness = build_scientific_grid_host_reference_development_report(
        _EmptyRepo(), fit_development_origins=[origin_a, origin_b], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
    )
    assert completeness["intended_origin_count"] == 2
    assert completeness["successful_snapshot_origin_count"] == 0
    assert completeness["blocked_origin_count"] == 2
    assert completeness["is_complete"] is False


def test_hostref7a61_04_one_unsafe_component_prevents_completeness(monkeypatch):
    import components.geospatial_tracking.services.model_development.host_reference_rebuild as mod

    class _FakeEligibleSource:
        source_id = "S1"
        latitude = 15.0
        longitude = 101.0

    class _FakeResult:
        sources = [_FakeEligibleSource()]

    monkeypatch.setattr(mod, "get_eligible_sources", lambda *a, **k: _FakeResult())

    class _FakeDomain:
        def n_unsafe_components(self):
            return 1  # simulate: this origin had >= 1 UNSAFE component

        def all_cells(self):
            return []  # nothing safe to sample

    monkeypatch.setattr(mod, "build_scientific_evaluation_domain", lambda **k: _FakeDomain())

    origin = _origin()
    profile, snapshots, completeness = build_scientific_grid_host_reference_development_report(
        _EmptyRepo(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
    )
    assert completeness["n_origins_with_unsafe_components"] == 1
    assert completeness["is_complete"] is False
    assert origin.forecast_origin_id in completeness["unsafe_origin_ids"]


def test_hostref7a61_05_require_effective_sample_identity_actually_passed(monkeypatch):
    import components.geospatial_tracking.services.model_development.host_reference_rebuild as mod

    captured = {}
    real_build_profile = mod.build_factor_reference_profile

    def _spy(*args, **kwargs):
        captured.update(kwargs)
        return real_build_profile(*args, **kwargs)

    monkeypatch.setattr(mod, "build_factor_reference_profile", _spy)

    origin = _origin()
    build_scientific_grid_host_reference_development_report(
        _EmptyRepo(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
    )
    assert captured.get("require_effective_sample_identity") is True


def test_hostref7a6_04_deterministic_reference_hash():
    origin = _origin()
    profile_1, _, _ = build_scientific_grid_host_reference_development_report(
        _EmptyRepo(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
    )
    profile_2, _, _ = build_scientific_grid_host_reference_development_report(
        _EmptyRepo(), fit_development_origins=[origin], disease=DISEASE, active_window_days=14, grid_config=_grid_config(),
    )
    assert profile_1.reference_profile_hash() == profile_2.reference_profile_hash()

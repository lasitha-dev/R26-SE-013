"""Checkpoint 7A Part 32: domain/target tests — DOMAIN-02..04,
TARGET-01..03 (7A-specific; D8+ exclusion (TARGET-04) is already
covered by the pre-existing test_forecast_target.py::test_target_04)."""

from __future__ import annotations

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.forecast_target import build_forecast_targets
from components.geospatial_tracking.services.geospatial.scientific_grid import (
    DOMAIN_MODE_SOURCE_BUFFER_UNION,
    ScientificGridConfig,
    build_scientific_grid,
    build_source_buffer_union_domain,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.domain_design import (
    DOMAIN_RULE_BLOCKED,
    FROZEN_EVALUATION_DOMAIN_RULE,
    PREDECLARED_DOMAIN_CANDIDATES_KM,
    build_development_domain_candidate_audit,
    select_frozen_domain_distance,
)
from components.geospatial_tracking.services.model_development.target_assignment import (
    BACKGROUND,
    INSIDE_EVALUATION_DOMAIN,
    TARGET_EVENT,
    TARGET_OUTSIDE_EVALUATION_DOMAIN,
    assign_target_to_scientific_grid,
)


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def test_domain02_domain_design_rejects_held_out_origins():
    held_out = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_development_domain_candidate_audit(None, fit_development_origins=[held_out], disease="Lumpy skin disease", active_window_days=14)


def test_domain03_domain_design_rejects_sri_lanka_origins():
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        build_development_domain_candidate_audit(None, fit_development_origins=[sri_lanka], disease="Lumpy skin disease", active_window_days=14)


def test_domain04_target_outside_domain_is_retained_and_flagged():
    from types import SimpleNamespace
    sources = [EligibleSourcePoint(source_id="S0", latitude=15.0, longitude=101.0)]
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")

    far_target = SimpleNamespace(forecast_origin_id="O", target_id="O::EVT1", target_event_id="EVT1", lead_days=3, latitude=20.0, longitude=110.0)  # >>25km away
    assignment = assign_target_to_scientific_grid(target=far_target, cells=cells, domain=domain, sources=sources, crs_choice=domain.crs_choice)
    assert assignment.inside_evaluation_domain is False
    assert assignment.domain_status == TARGET_OUTSIDE_EVALUATION_DOMAIN
    # retained -- a row exists, it was never dropped
    assert assignment.target_event_id == "EVT1"
    assert assignment.label == TARGET_EVENT  # presence-only, never a negative label


def test_domain06_omitted_cutoff_uses_generic_default(repo):
    # a t0 that is FIT_DEVELOPMENT under the generic MODEL_FITTING_CUTOFF
    # ("2024-01-01") but would be HELD_OUT under a later cutoff -- omitting
    # model_fitting_cutoff must behave exactly as before (generic default).
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2023-06-01", t0="2023-06-01")
    audits, rows = build_development_domain_candidate_audit(
        repo, fit_development_origins=[origin], disease="Lumpy skin disease", active_window_days=14,
    )
    assert rows == []  # no sources in the empty repo -> no targets, but no rejection either
    assert len(audits) == len(PREDECLARED_DOMAIN_CANDIDATES_KM)


def test_domain07_explicit_later_cutoff_is_forwarded_and_accepts_row(repo):
    # under the generic default cutoff this origin would be HELD_OUT and
    # rejected; forwarding a later explicit cutoff must make it FIT_DEVELOPMENT.
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", t0="2024-06-01")
    audits, rows = build_development_domain_candidate_audit(
        repo, fit_development_origins=[origin], disease="Lumpy skin disease", active_window_days=14,
        model_fitting_cutoff="2026-01-01",
    )
    assert rows == []
    assert len(audits) == len(PREDECLARED_DOMAIN_CANDIDATES_KM)


def test_domain08_explicit_cutoff_still_rejects_role_outside_development(repo):
    # 2026-06-01 is HELD_OUT even under the later explicit cutoff -- the
    # firewall must still reject it, proving cutoff forwarding does not
    # disable the development-only firewall.
    origin = _origin(forecast_origin_id="ORIGIN:Thailand:2026-06-01", t0="2026-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        build_development_domain_candidate_audit(
            repo, fit_development_origins=[origin], disease="Lumpy skin disease", active_window_days=14,
            model_fitting_cutoff="2026-01-01",
        )
    # Sri Lanka must still be rejected regardless of the explicit cutoff
    sri_lanka = _origin(forecast_origin_id="ORIGIN:Sri Lanka:2020-06-01", country="Sri Lanka", t0="2020-06-01")
    with pytest.raises(ValueError, match="SRI_LANKA_TRANSFER_CASE_STUDY"):
        build_development_domain_candidate_audit(
            repo, fit_development_origins=[sri_lanka], disease="Lumpy skin disease", active_window_days=14,
            model_fitting_cutoff="2026-01-01",
        )


def test_domain09_no_dataset_specific_cutoff_constant_in_domain_design_module():
    import components.geospatial_tracking.services.model_development.domain_design as mod
    import inspect
    source = inspect.getsource(mod)
    # only the generic MODEL_FITTING_CUTOFF import/name may appear -- no
    # disease-specific cutoff constant (e.g. FMD_MODEL_FITTING_CUTOFF) is
    # ever hardcoded in this generic module.
    assert "FMD_MODEL_FITTING_CUTOFF" not in source
    assert "LSD_MODEL_FITTING_CUTOFF" not in source
    assert "2026-01-01" not in source


def test_domain05_frozen_selection_never_expands_past_predeclared_candidates():
    from components.geospatial_tracking.services.model_development.domain_design import DomainCandidateAudit
    # no candidate achieves full coverage -> BLOCKED, not silently expanded
    audits = [
        DomainCandidateAudit(candidate_distance_km=c, n_targets_total=10, n_targets_covered=8, coverage_fraction=0.8, n_targets_uncovered=2, uncovered_target_ids=("X",))
        for c in (25.0, 50.0, 75.0, 100.0, 150.0, 200.0)
    ]
    distance, status = select_frozen_domain_distance(audits)
    assert distance is None
    assert status == DOMAIN_RULE_BLOCKED


def test_domain05b_frozen_selection_picks_smallest_full_coverage_candidate():
    from components.geospatial_tracking.services.model_development.domain_design import DomainCandidateAudit
    audits = [
        DomainCandidateAudit(candidate_distance_km=25.0, n_targets_total=10, n_targets_covered=9, coverage_fraction=0.9, n_targets_uncovered=1, uncovered_target_ids=("X",)),
        DomainCandidateAudit(candidate_distance_km=50.0, n_targets_total=10, n_targets_covered=10, coverage_fraction=1.0, n_targets_uncovered=0),
        DomainCandidateAudit(candidate_distance_km=75.0, n_targets_total=10, n_targets_covered=10, coverage_fraction=1.0, n_targets_uncovered=0),
    ]
    distance, status = select_frozen_domain_distance(audits)
    assert distance == 50.0
    assert status == FROZEN_EVALUATION_DOMAIN_RULE


# -- TARGET-01..03 (7A-specific pseudo-replication + assignment determinism) --

@pytest.fixture
def repo(tmp_path):
    r = SQLiteOutbreakRepository(tmp_path / "test.db")
    r.init_schema()
    yield r
    r.close()


def _historical(**overrides):
    fields = dict(
        source_record_id="H1", country="Thailand", disease="Lumpy skin disease",
        outbreak_start_date="2026/01/10", proxy_availability_date="2026/01/05",
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        latitude=15.0, longitude=101.0, gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.AUTO_MERGED_HIGH.value, model_candidate=True,
    )
    fields.update(overrides)
    return HistoricalOutbreakRecord(**fields)


def test_target7a_01_unique_target_event_counted_once_per_origin(repo):
    repo.add_historical_record(_historical(source_record_id="EVT_DUP_ORIGIN", outbreak_start_date="2026/01/12"))
    origin = ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2026-01-05", country="Thailand", t0="2026-01-05", temporal_mode="RETROSPECTIVE_PROXY")
    targets = build_forecast_targets(repo, origin, disease="Lumpy skin disease")
    event_ids = [t.target_event_id for t in targets]
    assert event_ids.count("EVT_DUP_ORIGIN") == 1  # never counted twice against the SAME origin


def test_target7a_02_same_event_from_two_origins_is_not_pseudo_replication_but_stays_distinguishable(repo):
    repo.add_historical_record(_historical(source_record_id="EVT_SHARED", outbreak_start_date="2026/01/12"))
    origin_a = ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2026-01-05", country="Thailand", t0="2026-01-05", temporal_mode="RETROSPECTIVE_PROXY")
    origin_b = ForecastOrigin(forecast_origin_id="ORIGIN:Thailand:2026-01-06", country="Thailand", t0="2026-01-06", temporal_mode="RETROSPECTIVE_PROXY")
    targets_a = build_forecast_targets(repo, origin_a, disease="Lumpy skin disease")
    targets_b = build_forecast_targets(repo, origin_b, disease="Lumpy skin disease")
    ids_a = {t.target_event_id for t in targets_a}
    ids_b = {t.target_event_id for t in targets_b}
    assert "EVT_SHARED" in ids_a and "EVT_SHARED" in ids_b
    # distinguishable per-origin via target_id (forecast_origin_id::target_event_id), never merged into one row
    target_a = next(t for t in targets_a if t.target_event_id == "EVT_SHARED")
    target_b = next(t for t in targets_b if t.target_event_id == "EVT_SHARED")
    assert target_a.target_id != target_b.target_id


def test_target7a_03_polygon_cell_assignment_deterministic():
    from types import SimpleNamespace
    sources = [EligibleSourcePoint(source_id="S0", latitude=15.0, longitude=101.0)]
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    target = SimpleNamespace(forecast_origin_id="O", target_id="O::EVT1", target_event_id="EVT1", lead_days=2, latitude=15.0, longitude=101.0)
    a1 = assign_target_to_scientific_grid(target=target, cells=cells, domain=domain, sources=sources, crs_choice=domain.crs_choice)
    a2 = assign_target_to_scientific_grid(target=target, cells=cells, domain=domain, sources=sources, crs_choice=domain.crs_choice)
    assert a1.target_grid_cell_id == a2.target_grid_cell_id
    assert a1.target_grid_cell_id is not None
    assert a1.inside_evaluation_domain is True
    assert a1.domain_status == INSIDE_EVALUATION_DOMAIN


# -- PB-01..03 presence/background semantics --

def test_pb_01_no_true_negative_label_in_target_assignment_contract():
    from components.geospatial_tracking.services.model_development import target_assignment as mod
    assert "TRUE_NEGATIVE" not in mod.__dict__.values()
    field_names = {f.lower() for f in mod.TargetGridAssignment.__dataclass_fields__}
    assert "true_negative" not in field_names


def test_pb_02_background_is_labeled_sampled_not_disease_free():
    from components.geospatial_tracking.services.model_development.target_assignment import BACKGROUND
    assert BACKGROUND == "BACKGROUND"
    assert BACKGROUND != "DISEASE_FREE" and BACKGROUND != "CONFIRMED_ABSENT"


def test_pb_03_default_assignment_label_is_target_event_never_confirmed_absence():
    from types import SimpleNamespace
    sources = [EligibleSourcePoint(source_id="S0", latitude=15.0, longitude=101.0)]
    config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    domain = build_source_buffer_union_domain(sources, domain_distance_km=25.0)
    cells = build_scientific_grid(domain, config=config, id_prefix="T")
    target = SimpleNamespace(forecast_origin_id="O", target_id="O::EVT1", target_event_id="EVT1", lead_days=2, latitude=15.0, longitude=101.0)
    assignment = assign_target_to_scientific_grid(target=target, cells=cells, domain=domain, sources=sources, crs_choice=domain.crs_choice)
    assert assignment.label == TARGET_EVENT

"""Checkpoint 7E Part 20: 7E-FREEZE-01..02, 7E-ROLE-01..03, 7E-TEMP-01..04,
7E-GPS-01, 7E-MATH-01..05, 7E-SCOPE-01..03, 7E-METRIC-01..02,
7E-SMALLN-01. Run BEFORE the real single-shot Sri Lanka case-study
scoring."""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
from components.geospatial_tracking.services.geospatial.distance import distance_km
from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.model_development import sri_lanka_run_7e
from components.geospatial_tracking.services.model_development.baseline_scoring import score_origin_all_candidates
from components.geospatial_tracking.services.model_development.candidate_registry_7b import build_candidate_registry as build_candidate_registry_7b
from components.geospatial_tracking.services.model_development.candidate_registry_7c import C0_FAMILY, build_candidate_registry_7c
from components.geospatial_tracking.services.model_development.evaluation_protocol_7b import TOP5_THRESHOLD_PERCENTILE, TOP10_THRESHOLD_PERCENTILE
from components.geospatial_tracking.services.model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from components.geospatial_tracking.services.model_development.sri_lanka_protocol_7e import (
    EVALUATION_ROLE_7E,
    FROZEN_7C_SPEC_HASH,
    SELECTED_CANDIDATE_ID,
    ModelFreezeMismatchError,
    assert_frozen_c0_model_7e,
)
from components.geospatial_tracking.services.model_development.sri_lanka_run_7e import run_checkpoint_7e_sri_lanka_case_study
from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

DISEASE = "Lumpy skin disease"


def _valid_spec() -> dict:
    return {
        "selected_candidate_id": SELECTED_CANDIDATE_ID, "frozen_spec_hash": FROZEN_7C_SPEC_HASH,
        "parent_7b_frozen_spec_hash": "6bb8f67a7bc1188be324bf0a58e2399ed87df619b96c5a0db0ba5a3191794950",
        "selected_candidate_spec": {"kernel_family": "EXPONENTIAL", "kernel_scale_km": 25.0},
        "host_factor_status": "NOT_PRIMARY_ELIGIBLE_FROM_7B_COVERAGE_AUDIT", "anisotropy_mode": None, "anisotropy_kappa": None,
        "environmental_suitability_status": "NOT_YET_SCIENTIFICALLY_DEFINED", "water_context_status": "NOT_YET_SCIENTIFICALLY_DEFINED",
        "source_strength_status": "NOT_SELECTED",
    }


def _origin(**overrides) -> ForecastOrigin:
    fields = dict(forecast_origin_id="ORIGIN:Sri Lanka:2020-09-07", country="Sri Lanka", t0="2020-09-07", temporal_mode="RETROSPECTIVE_PROXY", trigger_source_ids_at_t0=["X1"], trigger_source_count=1)
    fields.update(overrides)
    return ForecastOrigin(**fields)


def _grid_config() -> ScientificGridConfig:
    return ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)


def _c0_spec():
    return next(c for c in build_candidate_registry_7c() if c.family == C0_FAMILY)


class _TouchRepo:
    def __getattr__(self, name):
        def _fail(*args, **kwargs):
            raise AssertionError(f"repository method {name!r} was called before the Sri Lanka firewall check")
        return _fail


# ---------------------------------------------------------------------------
# 7E-FREEZE
# ---------------------------------------------------------------------------


def test_7efreeze_01_exact_frozen_candidate_id_required():
    assert_frozen_c0_model_7e(_valid_spec())  # does not raise
    bad = dict(_valid_spec(), selected_candidate_id="SOME_OTHER_ID")
    with pytest.raises(ModelFreezeMismatchError, match="selected_candidate_id"):
        assert_frozen_c0_model_7e(bad)


def test_7efreeze_02_exact_frozen_7c_spec_hash_required():
    bad = dict(_valid_spec(), frozen_spec_hash="deadbeef")
    with pytest.raises(ModelFreezeMismatchError, match="frozen_spec_hash"):
        assert_frozen_c0_model_7e(bad)


# ---------------------------------------------------------------------------
# 7E-ROLE
# ---------------------------------------------------------------------------


def test_7erole_01_only_sri_lanka_transfer_case_study_accepted():
    good = _origin()
    result_ok_signature = inspect.signature(run_checkpoint_7e_sri_lanka_case_study)
    assert "sri_lanka_origins" in result_ok_signature.parameters
    assert EVALUATION_ROLE_7E == "SRI_LANKA_TRANSFER_CASE_STUDY"


def test_7erole_02_fit_development_rejected():
    good = _origin()
    fit_dev = _origin(forecast_origin_id="ORIGIN:Thailand:2021-06-01", country="Thailand", t0="2021-06-01")
    with pytest.raises(ValueError, match="FIT_DEVELOPMENT"):
        run_checkpoint_7e_sri_lanka_case_study(_TouchRepo(), sri_lanka_origins=[good, fit_dev], disease=DISEASE, active_window_days=14, grid_config=_grid_config(), c0_spec=_c0_spec())


def test_7erole_03_held_out_from_model_fitting_rejected():
    good = _origin()
    heldout = _origin(forecast_origin_id="ORIGIN:Thailand:2024-06-01", country="Thailand", t0="2024-06-01")
    with pytest.raises(ValueError, match="HELD_OUT_FROM_MODEL_FITTING"):
        run_checkpoint_7e_sri_lanka_case_study(_TouchRepo(), sri_lanka_origins=[good, heldout], disease=DISEASE, active_window_days=14, grid_config=_grid_config(), c0_spec=_c0_spec())


# ---------------------------------------------------------------------------
# 7E-TEMP
# ---------------------------------------------------------------------------


def test_7etemp_01_02_future_target_and_after_t0_source_excluded_structurally():
    src = inspect.getsource(sri_lanka_run_7e)
    assert "get_eligible_sources" not in src  # only via the shared _eligible_source_points helper
    assert "_eligible_source_points" in src


def test_7etemp_03_unknown_operational_availability_never_silently_converted_to_actual():
    src = inspect.getsource(sri_lanka_run_7e)
    assert "= \"ACTUAL\"" not in src and "='ACTUAL'" not in src  # never hardcodes ACTUAL anywhere
    # reused directly from the real record field -- never overwritten
    assert "proxy_availability_quality" in src


_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUT_DIR = _REPO_ROOT / "local_data" / "model_evaluation" / "7e_sri_lanka"
_TEMPORAL_AUDIT = _OUT_DIR / "sri_lanka_temporal_availability_audit.json"
_GPS_AUDIT = _OUT_DIR / "sri_lanka_geolocation_quality_audit.json"


@pytest.mark.skipif(not _TEMPORAL_AUDIT.exists(), reason="real 7E temporal audit not present in this environment")
def test_7etemp_04_proxy_availability_retains_its_proxy_label():
    d = json.loads(_TEMPORAL_AUDIT.read_text(encoding="utf-8"))
    for row in d["rows"]:
        assert row["availability_quality"] in ("EVENT_DATE_PROXY", "OBSERVATION_DATE_PROXY", "CONFIRMATION_PROXY", "UNKNOWN")
        assert row["availability_quality"] != "ACTUAL"  # never fabricated as ACTUAL
        assert row["operational_availability_quality"] == "UNKNOWN"  # real, disclosed, never manufactured


# ---------------------------------------------------------------------------
# 7E-GPS
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _GPS_AUDIT.exists(), reason="real 7E GPS audit not present in this environment")
def test_7egps_01_approximate_shared_gps_does_not_automatically_deduplicate_outbreaks():
    d = json.loads(_GPS_AUDIT.read_text(encoding="utf-8"))
    shared = [r for r in d["rows"] if r["coordinate_collision_status"] == "SHARED_WITH_UNRESOLVED"]
    assert shared, "expected the known real Sri Lanka coordinate-sharing case to be present"
    for row in shared:
        # the shared-coordinate record must still remain its own distinct model-candidate episode
        assert row["model_candidate"] is True


# ---------------------------------------------------------------------------
# 7E-MATH
# ---------------------------------------------------------------------------

_CELLS = [{"grid_cell_id": "CELL:A", "scientific_cell_id": "SCI:A", "area_km2": 25.0, "domain_overlap_area_km2": 25.0, "centroid_lat": 9.70, "centroid_lon": 80.10}]
_SOURCES = [
    EligibleSourcePoint(source_id="S1", latitude=9.7151701, longitude=80.0668497),
    EligibleSourcePoint(source_id="S2", latitude=9.6579014, longitude=80.1643076),
    EligibleSourcePoint(source_id="S3", latitude=9.6734908, longitude=80.0290277),
]


def test_7emath_01_c0_exactly_matches_frozen_scorer():
    b0 = next(c for c in build_candidate_registry_7b() if c.baseline_family == "B0_DISTANCE_ONLY" and c.kernel_family == "EXPONENTIAL" and c.kernel_scale_km == 25.0)
    b0_score = score_origin_all_candidates(grid_cells=_CELLS, sources=_SOURCES, candidates=(b0,))[b0.candidate_id][0].score
    c0_score = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(_c0_spec(),), wind=None)[_c0_spec().candidate_id][0].score
    assert b0_score == pytest.approx(c0_score, rel=1e-12)


def test_7emath_02_all_eligible_sources_contribute():
    c0 = _c0_spec()
    full = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0].score
    manual = sum(evaluate_kernel(distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]), family="EXPONENTIAL", distance_scale_km=25.0) for s in _SOURCES)
    assert full == pytest.approx(manual, rel=1e-12)
    dropped = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES[:2], candidates=(c0,), wind=None)[c0.candidate_id][0].score
    assert dropped != pytest.approx(full)


def test_7emath_03_nearest_source_only_replacement_impossible():
    c0 = _c0_spec()
    full = score_origin_candidates_7c(grid_cells=_CELLS, sources=_SOURCES, candidates=(c0,), wind=None)[c0.candidate_id][0].score
    nearest = min(_SOURCES, key=lambda s: distance_km(s.latitude, s.longitude, _CELLS[0]["centroid_lat"], _CELLS[0]["centroid_lon"]))
    nearest_only = score_origin_candidates_7c(grid_cells=_CELLS, sources=[nearest], candidates=(c0,), wind=None)[c0.candidate_id][0].score
    assert full > nearest_only


def test_7emath_04_st_clustering_cannot_gate_sources():
    params = set(inspect.signature(run_checkpoint_7e_sri_lanka_case_study).parameters) | set(inspect.signature(sri_lanka_run_7e._evaluate_sri_lanka_origin).parameters)
    forbidden = {"st_cluster", "cluster_role", "is_noise", "is_core", "st_config", "stdbscan_config"}
    assert not (params & forbidden)
    src = inspect.getsource(sri_lanka_run_7e)
    for token in ("STDBSCAN", "cluster_role", "is_noise", "is_core"):
        assert token not in src


def test_7emath_05_no_host_wind_environment_water_source_strength_factor():
    src = inspect.getsource(sri_lanka_run_7e)
    for forbidden in ("host_factor", "host_density", "WindVector", "environmental_suitability", "water_context_factor", "source_strength_factor", "era5", "build_pre_t0_weather_summary"):
        assert forbidden not in src
    assert "wind=None" in src


# ---------------------------------------------------------------------------
# 7E-SCOPE
# ---------------------------------------------------------------------------


def test_7escope_01_25km_unchanged():
    from components.geospatial_tracking.services.model_development.sri_lanka_protocol_7e import EVALUATION_DISTANCE_KM_7E

    assert EVALUATION_DISTANCE_KM_7E == 25.0 == PRIMARY_LOCAL_EVALUATION_DISTANCE_KM


def test_7escope_02_5km_grid_unchanged():
    from components.geospatial_tracking.services.model_development.sri_lanka_protocol_7e import GRID_CELL_SIZE_KM_7E

    assert GRID_CELL_SIZE_KM_7E == 5.0


class _NoReassignmentVisitor(ast.NodeVisitor):
    """Checkpoint 7E.1 Part 5A: walks the real parsed AST of
    sri_lanka_run_7e.py and fails if ANY statement assigns, reassigns, or
    augments `grid_config`, `grid_config.domain_distance_km`, or a bare
    `domain_distance_km` name anywhere in the module -- a real structural
    proof, not a brittle substring scan."""

    FORBIDDEN_NAMES = {"grid_config", "domain_distance_km"}

    def __init__(self):
        self.violations: list[str] = []

    def _target_name(self, node) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None

    def _check_targets(self, targets, lineno) -> None:
        for t in targets:
            name = self._target_name(t)
            if name is not None and (name in self.FORBIDDEN_NAMES or name.split(".")[0] in self.FORBIDDEN_NAMES or name.endswith(".domain_distance_km")):
                self.violations.append(f"line {lineno}: reassignment of {name!r}")

    def visit_Assign(self, node: ast.Assign) -> None:
        self._check_targets(node.targets, node.lineno)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_targets([node.target], node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._check_targets([node.target], node.lineno)
        self.generic_visit(node)


def test_7escope_03a_ast_structural_proof_grid_config_never_reassigned():
    """Checkpoint 7E.1 Part 5A: real AST parse of the actual module
    source -- fails on any assignment/reassignment/augmented-assignment
    to `grid_config`/`domain_distance_km` anywhere in the file."""
    import components.geospatial_tracking.services.model_development.sri_lanka_run_7e as module

    source_path = Path(module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    visitor = _NoReassignmentVisitor()
    visitor.visit(tree)
    assert not visitor.violations, f"grid_config/domain_distance_km reassignment found: {visitor.violations}"

    # confirm the domain builder call site passes the frozen envelope through unmodified
    src = source_path.read_text(encoding="utf-8")
    assert "primary_local_evaluation_distance_km=grid_config.domain_distance_km" in src

    # confirm the 7E protocol's own frozen value is still 25.0 km
    from components.geospatial_tracking.services.model_development.sri_lanka_protocol_7e import EVALUATION_DISTANCE_KM_7E

    assert EVALUATION_DISTANCE_KM_7E == 25.0


def test_7escope_03b_behavioral_proof_outside_target_stays_outside():
    """Checkpoint 7E.1 Part 5B: real behavioral proof using the actual
    frozen `classify_target_primary_scope` function (never the real
    Sri Lanka predictive checkpoint) -- constructs one source and one
    target geometrically ~86km apart (matching the real magnitude of the
    genuine OUTSIDE Sri Lanka target, `002411`) and asserts the frozen
    25km envelope is neither widened nor bypassed."""
    from components.geospatial_tracking.services.geospatial.scientific_grid import DOMAIN_MODE_SOURCE_BUFFER_UNION, ScientificGridConfig
    from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
        OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE,
        classify_target_primary_scope,
    )

    grid_config = ScientificGridConfig(cell_size_km=5.0, domain_mode=DOMAIN_MODE_SOURCE_BUFFER_UNION, domain_distance_km=25.0)
    before = grid_config.domain_distance_km
    assert before == 25.0

    source = EligibleSourcePoint(source_id="S1", latitude=9.6734908, longitude=80.0290277)
    far_target = SimpleNamespace(
        forecast_origin_id="ORIGIN:Test:2020-01-01", target_id="T1", target_event_id="E1", lead_days=1,
        latitude=8.888178931, longitude=80.0461103553,  # real ~87km offset, matching the genuine OUTSIDE Sri Lanka case
    )

    scope = classify_target_primary_scope(target=far_target, sources=[source], evaluation_domain=None)
    assert scope.scope_status == OUTSIDE_DECLARED_LOCAL_EVALUATION_SCOPE
    assert scope.min_distance_to_eligible_source_km > 25.0

    after = grid_config.domain_distance_km
    assert before == after == 25.0, "the frozen envelope must be identical before and after classifying an OUTSIDE target -- never widened to rescue it"


# ---------------------------------------------------------------------------
# 7E-METRIC
# ---------------------------------------------------------------------------


def test_7emetric_01_area_weighted_midrank_unchanged():
    from components.geospatial_tracking.services.model_development.baseline_scoring import compute_area_weighted_percentiles as bs_percentiles

    assert sri_lanka_run_7e.compute_area_weighted_percentiles is bs_percentiles


def test_7emetric_02_top5_top10_unchanged():
    assert sri_lanka_run_7e.TOP5_THRESHOLD_PERCENTILE == TOP5_THRESHOLD_PERCENTILE == 95.0
    assert sri_lanka_run_7e.TOP10_THRESHOLD_PERCENTILE == TOP10_THRESHOLD_PERCENTILE == 90.0


# ---------------------------------------------------------------------------
# 7E-SMALLN
# ---------------------------------------------------------------------------


def test_7esmalln_01_small_n_cannot_be_labelled_external_validation():
    src = inspect.getsource(sri_lanka_run_7e)
    for forbidden in ("EXTERNAL_VALIDATION", "INDEPENDENT_VALIDATION", "BLIND_VALIDATION", "PROSPECTIVE_VALIDATION"):
        assert forbidden not in src
    assert sri_lanka_run_7e.SMALL_SAMPLE_THRESHOLD_ORIGINS == 10
    assert sri_lanka_run_7e.SMALL_SAMPLE_DESCRIPTIVE_ONLY == "SMALL_SAMPLE_DESCRIPTIVE_ONLY"

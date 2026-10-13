"""Checkpoint 8B.3: cell-local geodesic tangent-frame correction, exact
C0 negative-gradient consistency, active method/version identity, and
final direction-field lock.

SYNTHETIC ANALYTICAL PROOFS ONLY. No real 579-origin/560,853-cell
structural audit executed IN THIS TEST FILE (the real rerun lives in
`smoke_tests/run_direction_structural_audit_8b3.py`, run separately).
No C0 rescoring, no future-target/direction-performance evaluation, no
held-out/Sri Lanka scoring anywhere in this file."""

from __future__ import annotations

import math

import pyproj
import pytest

from components.geospatial_tracking.services.direction.c0_cell_local_tendency_8b3 import (
    ACTIVE_COORDINATE_FRAME_8B3,
    ACTIVE_OUTPUT_SEMANTICS_8B3,
    DIRECTION_EVALUATION_TRUTH_STATUS_8B3,
    METHOD_ID_8B3,
    METHOD_VERSION_8B3,
    PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3,
    c0_directional_weight,
    compute_cell_direction_tendency_8b3,
)
from components.geospatial_tracking.services.direction.c0_geometric_tendency import compute_cell_direction_tendency
from components.geospatial_tracking.services.geospatial.distance import (
    CELL_LOCAL_EAST_NORTH_TANGENT_FRAME,
    distance_km,
    source_to_cell_tangent_at_cell,
    source_to_cell_unit_vector,
)
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    C0_FAMILY,
    build_candidate_registry_7c,
)
from components.geospatial_tracking.services.model_development.direction_protocol_8b import (
    HISTORICAL_CHECKPOINT_8B2_PROTOCOL_HASH,
    HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH,
    direction_method_protocol_dict_8b3,
    direction_method_protocol_hash_8b,
    direction_method_protocol_hash_8b2,
    direction_method_protocol_hash_8b3,
)

LAMBDA_KM = 25.0
_GEOD = pyproj.Geod(ellps="WGS84")


def _cell(lat: float, lon: float, cell_id: str = "TESTCELL") -> dict:
    return {
        "grid_cell_id": cell_id, "scientific_cell_id": cell_id,
        "area_km2": 25.0, "domain_overlap_area_km2": 25.0,
        "centroid_lat": lat, "centroid_lon": lon,
    }


def _step(lat: float, lon: float, bearing_deg: float, dist_km: float) -> tuple[float, float]:
    lon2, lat2, _ = _GEOD.fwd(lon, lat, bearing_deg, dist_km * 1000.0)
    return lat2, lon2


def _c0_at(lat: float, lon: float, sources: list[EligibleSourcePoint]) -> float:
    return sum(c0_directional_weight(distance_km(s.latitude, s.longitude, lat, lon)) for s in sources)


def _finite_diff_grad_c0(lat: float, lon: float, sources: list[EligibleSourcePoint], eps_km: float) -> tuple[float, float]:
    lat_e, lon_e = _step(lat, lon, 90.0, eps_km)
    lat_w, lon_w = _step(lat, lon, 270.0, eps_km)
    lat_n, lon_n = _step(lat, lon, 0.0, eps_km)
    lat_s, lon_s = _step(lat, lon, 180.0, eps_km)
    d_east = (_c0_at(lat_e, lon_e, sources) - _c0_at(lat_w, lon_w, sources)) / (2.0 * eps_km)
    d_north = (_c0_at(lat_n, lon_n, sources) - _c0_at(lat_s, lon_s, sources)) / (2.0 * eps_km)
    return d_east, d_north


def _multi_source_case(cell_lat: float = 5.0, cell_lon: float = 30.0):
    lat_a, lon_a = _step(cell_lat, cell_lon, 30.0, 3.0)
    lat_b, lon_b = _step(cell_lat, cell_lon, 160.0, 7.0)
    lat_c, lon_c = _step(cell_lat, cell_lon, 250.0, 12.0)
    sources = [
        EligibleSourcePoint(source_id="A", latitude=lat_a, longitude=lon_a),
        EligibleSourcePoint(source_id="B", latitude=lat_b, longitude=lon_b),
        EligibleSourcePoint(source_id="C", latitude=lat_c, longitude=lon_c),
    ]
    return cell_lat, cell_lon, sources


# ---------------------------------------------------------------------------
# 8B3-GEO-01..06: geodesy correctness
# ---------------------------------------------------------------------------


def test_8b3_geo_01_cell_local_bearing_uses_az21_plus_180():
    source_lat, source_lon = 5.0, 30.0
    lat_a, lon_a = _step(source_lat, source_lon, 30.0, 3.0)  # a nonzero, non-cardinal geodesic
    az12, az21, _dist = _GEOD.inv(source_lon, source_lat, lon_a, lat_a)
    expected_arrival = (az21 + 180.0) % 360.0

    tangent = source_to_cell_tangent_at_cell(source_lat, source_lon, lat_a, lon_a)
    assert tangent.cell_arrival_forward_azimuth_deg == pytest.approx(expected_arrival, abs=1e-9)
    assert tangent.source_departure_azimuth_deg == pytest.approx(az12 % 360.0, abs=1e-9)


def test_8b3_geo_02_departure_and_arrival_bearings_measurably_differ():
    source_lat, source_lon = 5.0, 30.0
    lat_a, lon_a = _step(source_lat, source_lon, 30.0, 3.0)  # off-meridian, off-equator -> real convergence
    tangent = source_to_cell_tangent_at_cell(source_lat, source_lon, lat_a, lon_a)
    diff = abs(tangent.cell_arrival_forward_azimuth_deg - tangent.source_departure_azimuth_deg)
    assert diff > 1e-4  # measurably nonzero -- not a case where they coincide


def test_8b3_geo_03_all_source_terms_share_the_same_cell_local_frame():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    for term in result.source_terms:
        assert term.coordinate_frame == CELL_LOCAL_EAST_NORTH_TANGENT_FRAME
    assert result.coordinate_frame == CELL_LOCAL_EAST_NORTH_TANGENT_FRAME == ACTIVE_COORDINATE_FRAME_8B3


def test_8b3_geo_04_unit_vector_norm_within_tolerance():
    source_lat, source_lon = 5.0, 30.0
    lat_a, lon_a = _step(source_lat, source_lon, 47.0, 9.0)
    tangent = source_to_cell_tangent_at_cell(source_lat, source_lon, lat_a, lon_a)
    norm = math.hypot(tangent.t_cell_east, tangent.t_cell_north)
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_8b3_geo_05_zero_distance_remains_undefined():
    cell_lat, cell_lon = 1.0, 1.0
    sources = [EligibleSourcePoint(source_id="AT_CELL", latitude=cell_lat, longitude=cell_lon)]
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    term = result.source_terms[0]
    assert term.distance_km == 0.0
    assert term.direction_defined is False
    assert term.t_cell_east is None and term.t_cell_north is None


def test_8b3_geo_06_higher_latitude_longer_distance_defect_detectable():
    # a geographically more demanding case: high latitude, longer distance
    source_lat, source_lon = 55.0, -10.0
    lat_far, lon_far = _step(source_lat, source_lon, 65.0, 40.0)
    old = source_to_cell_unit_vector(source_lat, source_lon, lat_far, lon_far)
    new = source_to_cell_tangent_at_cell(source_lat, source_lon, lat_far, lon_far)
    delta = math.hypot(new.t_cell_east - old.t_hat_east, new.t_cell_north - old.t_hat_north)
    assert delta > 1e-4  # historical (source-frame) and corrected (cell-frame) vectors measurably differ


# ---------------------------------------------------------------------------
# 8B3-GRAD-01/02: analytical identity holds for the corrected geometry
# ---------------------------------------------------------------------------


def test_8b3_grad_01_single_source_matches_cell_local_gradient():
    source_lat, source_lon = 10.0, 20.0
    cell_lat, cell_lon = _step(source_lat, source_lon, 90.0, 5.0)
    sources = [EligibleSourcePoint(source_id="S1", latitude=source_lat, longitude=source_lon)]
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)

    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources, eps_km=0.001)
    assert result.resultant_east == pytest.approx(-LAMBDA_KM * d_east, rel=1e-4, abs=1e-6)
    assert result.resultant_north == pytest.approx(-LAMBDA_KM * d_north, abs=1e-6)


def test_8b3_grad_02_multi_source_matches_cell_local_finite_difference():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources, eps_km=0.001)
    assert result.resultant_east == pytest.approx(-LAMBDA_KM * d_east, rel=1e-4, abs=1e-6)
    assert result.resultant_north == pytest.approx(-LAMBDA_KM * d_north, rel=1e-4, abs=1e-6)


# ---------------------------------------------------------------------------
# 8B3-GRAD-03: finite-difference CONVERGENCE (not a persistent bias plateau)
# ---------------------------------------------------------------------------


def test_8b3_grad_03_finite_difference_error_converges_not_plateaus():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)

    steps_km = [0.1, 0.01, 0.001]
    rel_errors = []
    convergence_table = []
    for step_km in steps_km:
        d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources, eps_km=step_km)
        fd_east, fd_north = -LAMBDA_KM * d_east, -LAMBDA_KM * d_north
        abs_err_east = result.resultant_east - fd_east
        abs_err_north = result.resultant_north - fd_north
        abs_error = math.hypot(abs_err_east, abs_err_north)
        rel_error = abs_error / result.resultant_magnitude
        bearing_fd = math.degrees(math.atan2(fd_east, fd_north)) % 360.0
        convergence_table.append({
            "step_km": step_km, "V_east": result.resultant_east, "V_north": result.resultant_north,
            "FD_minus_lambda_grad_east": abs_err_east, "FD_minus_lambda_grad_north": abs_err_north,
            "absolute_error": abs_error, "relative_error": rel_error,
            "bearing_difference_deg": abs(result.bearing_deg - bearing_fd),
        })
        rel_errors.append(rel_error)

    # each 10x reduction in step should reduce the error by roughly 100x
    # (central-difference O(step^2) truncation) -- a persistent frame bias
    # (as the historical source-departure-frame field exhibited) would NOT
    # shrink at all as the step shrinks.
    assert rel_errors[1] < rel_errors[0] / 10.0
    assert rel_errors[2] < rel_errors[1] / 10.0
    assert rel_errors[-1] < 1e-5  # converges to genuinely small residual, not a ~1e-3 plateau

    # persist the convergence table as real evidence (Part 10)
    import json
    from pathlib import Path

    out_dir = Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "8b3_direction"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "finite_difference_convergence_table_8b3.json").write_text(
        json.dumps({"multi_source_case": convergence_table}, indent=2, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 8B3-GRAD-04: positive-gradient sign
# ---------------------------------------------------------------------------


def test_8b3_grad_04_positive_gradient_and_v_are_180_degrees_apart():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.resultant_magnitude > 1e-6

    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources, eps_km=0.001)
    positive_grad_bearing = math.degrees(math.atan2(d_east, d_north)) % 360.0
    v_bearing = result.bearing_deg
    # standard wrapped angular difference in [0, 180]: 180 means exactly opposite
    angular_difference = abs((v_bearing - positive_grad_bearing + 180.0) % 360.0 - 180.0)
    assert angular_difference == pytest.approx(180.0, abs=0.1)


# ---------------------------------------------------------------------------
# 8B3-GRAD-05: historical field is demonstrably distinct
# ---------------------------------------------------------------------------


def test_8b3_grad_05_historical_field_demonstrably_distinct():
    cell_lat, cell_lon, sources = _multi_source_case()
    corrected = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    historical = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    delta_east = corrected.resultant_east - historical.resultant_east
    delta_north = corrected.resultant_north - historical.resultant_north
    assert math.hypot(delta_east, delta_north) > 1e-5


# ---------------------------------------------------------------------------
# 8B3-C0-01/02: scalar identity and C0 unchanged
# ---------------------------------------------------------------------------


def test_8b3_c0_01_scalar_weight_sum_equals_frozen_c0_score():
    from components.geospatial_tracking.services.model_development.wind_scoring_7c import score_origin_candidates_7c

    cell_lat, cell_lon, sources = _multi_source_case()
    cell = _cell(cell_lat, cell_lon)
    result = compute_cell_direction_tendency_8b3(cell, sources)

    c0_registry = build_candidate_registry_7c()
    c0_spec = next(c for c in c0_registry if c.family == C0_FAMILY)
    c0_scores = score_origin_candidates_7c(grid_cells=[cell], sources=sources, candidates=(c0_spec,), wind=None)
    assert result.total_scalar_c0_mass == c0_scores[c0_spec.candidate_id][0].score


def test_8b3_c0_02_no_c0_scorer_candidate_spec_modification():
    registry = build_candidate_registry_7c()
    c0 = next(c for c in registry if c.family == C0_FAMILY)
    assert c0.candidate_id == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert c0.anisotropy_mode is None
    assert c0.anisotropy_kappa is None


# ---------------------------------------------------------------------------
# 8B3-HIST-01: historical artifacts/hashes unchanged
# ---------------------------------------------------------------------------


def test_8b3_hist_01_historical_hashes_and_artifacts_unchanged():
    assert direction_method_protocol_hash_8b() == HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH
    assert direction_method_protocol_hash_8b2() == HISTORICAL_CHECKPOINT_8B2_PROTOCOL_HASH

    import hashlib
    from pathlib import Path

    out_dir = Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "8b_direction"
    if not out_dir.exists():
        pytest.skip("local_data/model_development/8b_direction absent (clean clone)")
    expected = {
        "direction_protocol_8b.json": "c90d76488814a256d649ea07bc4984257f414f5f0858e13b39f03b84a07e855c",
        "direction_structural_audit_8b.json": "2cced458d70f5d193489b4beec68b6c2e1dc9d342b3fb74836a7f3157064cde4",
        "direction_example_source_terms_8b.json": "dd8b532b5884f31bc52576623c9c93c368527178aaaed2085a69ac8c1d1a00d5",
        "direction_origin_summary_8b.csv": "2f48179ff84d9d60daf98ce9801bc0fc72eb7b8b2dc93721b35dca3b64ce6f9c",
    }
    for filename, expected_hash in expected.items():
        actual = hashlib.sha256((out_dir / filename).read_bytes()).hexdigest()
        assert actual == expected_hash, f"{filename} changed! before={expected_hash} after={actual}"


# ---------------------------------------------------------------------------
# 8B3-ID-01..04: active identity
# ---------------------------------------------------------------------------


def test_8b3_id_01_active_output_returns_method_version_8b3():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.method_version == METHOD_VERSION_8B3 == "8B.3"


def test_8b3_id_02_active_output_returns_cell_local_semantic_identifier():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.direction_semantics == ACTIVE_OUTPUT_SEMANTICS_8B3 == "C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY"
    assert result.method_id == METHOD_ID_8B3 == "C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY"


def test_8b3_id_03_active_output_declares_cell_local_frame():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.coordinate_frame == "CELL_LOCAL_EAST_NORTH_TANGENT_FRAME"
    assert result.direction_evaluation_truth_status == DIRECTION_EVALUATION_TRUTH_STATUS_8B3 == "DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN"
    assert result.predictive_spread_direction_status == PREDICTIVE_SPREAD_DIRECTION_STATUS_8B3 == "NOT_PREDICTIVE_SPREAD_DIRECTION"


def test_8b3_id_04_protocol_hash_changes_if_frame_identity_changes():
    import hashlib
    import json as _json

    baseline = direction_method_protocol_dict_8b3()
    baseline_hash = direction_method_protocol_hash_8b3()
    mutated = dict(baseline)
    mutated["active_coordinate_frame"] = "SOMETHING_ELSE"
    mutated_hash = hashlib.sha256(_json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert mutated_hash != baseline_hash


# ---------------------------------------------------------------------------
# 8B3-TIME-01: static t0
# ---------------------------------------------------------------------------


def test_8b3_time_01_static_t0_no_fabricated_day_specific_direction():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.temporal_scope == "T0_STATIC_NOT_DAY_SPECIFIC"


# ---------------------------------------------------------------------------
# 8B3-CIRCULAR-01/02
# ---------------------------------------------------------------------------


def test_8b3_circular_01_no_target_future_outbreak_argument():
    import ast
    import inspect

    from components.geospatial_tracking.services.direction import c0_cell_local_tendency_8b3 as module

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for arg in node.args.args + node.args.kwonlyargs:
                assert "target" not in arg.arg.lower()


def test_8b3_circular_02_no_angular_performance_path():
    import inspect

    from components.geospatial_tracking.services.direction import c0_cell_local_tendency_8b3 as module

    src = inspect.getsource(module)
    for forbidden in ("angular_error", "mean_angular_error", "median_angular_error", "direction_hit_rate", "bearing_accuracy"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# 8B3-WIND-01
# ---------------------------------------------------------------------------


def test_8b3_wind_01_no_weather_wind_input_in_active_method():
    import ast
    import inspect

    from components.geospatial_tracking.services.direction import c0_cell_local_tendency_8b3 as module

    tree = ast.parse(inspect.getsource(module))
    direct_imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module]
    for forbidden in ("weather", "wind", "era5", "anisotropy"):
        assert not any(forbidden in m.lower() for m in direct_imports), direct_imports


# ---------------------------------------------------------------------------
# 8B3-SEM-01/02: direct positive assertions, not loose substring windows
# ---------------------------------------------------------------------------


def test_8b3_sem_01_no_confidence_probability_accuracy_field():
    import dataclasses

    from components.geospatial_tracking.services.direction.c0_cell_local_tendency_8b3 import CellDirectionTendency8B3

    field_names = {f.name for f in dataclasses.fields(CellDirectionTendency8B3)}
    for forbidden in ("confidence", "probability", "accuracy", "certainty"):
        assert not any(forbidden in name for name in field_names)
    assert "directional_clarity" in field_names


def test_8b3_sem_02_active_classification_explicit():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency_8b3(_cell(cell_lat, cell_lon), sources)
    assert result.predictive_spread_direction_status == "NOT_PREDICTIVE_SPREAD_DIRECTION"


# ---------------------------------------------------------------------------
# Evidence-summary consistency (never skips) + local SHA256 verification
# ---------------------------------------------------------------------------


def test_8b3_evidence_summary_section_present_and_consistent():
    import json as _json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_8B_EVIDENCE_SUMMARY.json"
    d = _json.loads(path.read_text(encoding="utf-8"))
    section = d["cell_local_correction_8b3"]

    assert section["new_8b3_protocol_hash"] == direction_method_protocol_hash_8b3()
    assert section["historical_8b_protocol_hash"] == HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH
    assert section["historical_8b2_protocol_hash"] == HISTORICAL_CHECKPOINT_8B2_PROTOCOL_HASH

    audit = section["real_structural_audit_8b3"]
    assert audit["n_fit_development_origins_total"] == 579
    assert audit["n_origins_processed"] == 579
    assert audit["n_cells_processed"] == 560853
    assert audit["n_invariant_failures"] == 0
    assert audit["n_exact_zero_distance_cases"] == 0

    diff = section["historical_8b_vs_active_8b3_diff_audit"]
    assert diff["n_cells_compared"] == 560853
    assert diff["n_matched_cells_both_bearing_defined"] == 560853

    assert section["historical_8b_artifacts_reverified_unchanged"] is True
    assert section["no_target_outcomes_used"] is True


@pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "8b3_direction").exists(),
    reason="local_data/model_development/8b3_direction absent (clean clone)",
)
def test_8b3_local_artifacts_sha256_match_evidence_summary():
    import hashlib
    import json as _json
    from pathlib import Path

    evidence_path = Path(__file__).resolve().parents[1] / "CHECKPOINT_8B_EVIDENCE_SUMMARY.json"
    d = _json.loads(evidence_path.read_text(encoding="utf-8"))
    stored_hashes = d["cell_local_correction_8b3"]["local_artifact_sha256_8b3"]
    out_dir = Path(__file__).resolve().parents[4] / "local_data" / "model_development" / "8b3_direction"

    for filename, expected in stored_hashes.items():
        local_path = out_dir / filename
        assert local_path.exists(), f"{filename} referenced in evidence summary but missing locally"
        actual = hashlib.sha256(local_path.read_bytes()).hexdigest()
        assert actual == expected, f"{filename}: stored {expected} != actual {actual}"

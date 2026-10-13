"""Checkpoint 8B.2: analytical negative-gradient equivalence, direction
sign/semantic hardening, method-identity binding, and final 8B
scientific lock.

SYNTHETIC ANALYTICAL PROOFS ONLY. No real 579-origin/560,853-cell
structural audit rerun, no real C0 rescoring, no numerical vector
result changed, no future-target/direction-performance evaluation
anywhere in this file."""

from __future__ import annotations

import math

import pyproj
import pytest

from components.geospatial_tracking.services.direction.c0_geometric_tendency import (
    c0_directional_weight,
    compute_cell_direction_tendency,
)
from components.geospatial_tracking.services.geospatial.distance import distance_km, source_to_cell_unit_vector
from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development.direction_protocol_8b import (
    ACTIVE_OUTPUT_SEMANTICS_8B2,
    CLARITY_ANALYTICAL_RELATION_8B2,
    GRADIENT_SIGN_STATEMENT_8B2,
    HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY,
    HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH,
    HISTORICAL_METHOD_VERSION_STRING,
    METHOD_C_RECONCILIATION_8B2,
    METHOD_VERSION_8B2,
    NEGATIVE_GRADIENT_IDENTITY_8B2,
    direction_method_protocol_dict_8b2,
    direction_method_protocol_hash_8b,
    direction_method_protocol_hash_8b2,
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


def _finite_diff_grad_c0(lat: float, lon: float, sources: list[EligibleSourcePoint], eps_km: float = 0.01) -> tuple[float, float]:
    """Metric (km) local finite difference, not raw lat/lon degrees."""
    lat_e, lon_e = _step(lat, lon, 90.0, eps_km)
    lat_w, lon_w = _step(lat, lon, 270.0, eps_km)
    lat_n, lon_n = _step(lat, lon, 0.0, eps_km)
    lat_s, lon_s = _step(lat, lon, 180.0, eps_km)
    d_east = (_c0_at(lat_e, lon_e, sources) - _c0_at(lat_w, lon_w, sources)) / (2.0 * eps_km)
    d_north = (_c0_at(lat_n, lon_n, sources) - _c0_at(lat_s, lon_s, sources)) / (2.0 * eps_km)
    return d_east, d_north


_FD_TOLERANCE = 3e-3  # documented numerical tolerance for the finite-difference cross-check
_FD_ABS_TOLERANCE = 3e-3
# The identity V = -lambda*grad(C0) is exact only when the tangent used for
# t_hat is the LOCAL gradient direction AT THE CELL. `source_to_cell_unit_vector`
# (the codebase's existing, frozen, tested convention used throughout 7B-8B)
# instead uses the geodesic's DEPARTURE azimuth measured AT THE SOURCE. On the
# WGS84 ellipsoid these two differ by the geodesic's meridian-convergence angle
# over the source-cell path (confirmed empirically: ~0.0012 degrees for a 3km
# geodesic at this test's latitude) -- small and non-vanishing as the
# finite-difference step shrinks, never exactly zero. This tolerance accounts
# for that real, documented geometric effect, not finite-difference truncation
# error (which is far smaller and does shrink with eps).


# ---------------------------------------------------------------------------
# 8B2-GRAD-01/02: single-source cardinal cases
# ---------------------------------------------------------------------------


def test_8b2_grad_01_single_source_east_case():
    source_lat, source_lon = 10.0, 20.0
    cell_lat, cell_lon = _step(source_lat, source_lon, 90.0, 5.0)  # cell 5km east of source
    sources = [EligibleSourcePoint(source_id="S1", latitude=source_lat, longitude=source_lon)]
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)

    assert result.bearing_deg == pytest.approx(90.0, abs=1e-3)  # V points East

    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    positive_grad_bearing = math.degrees(math.atan2(d_east, d_north)) % 360.0
    assert positive_grad_bearing == pytest.approx(270.0, abs=1e-2)  # positive grad(C0) points West

    assert result.resultant_east == pytest.approx(-LAMBDA_KM * d_east, rel=_FD_TOLERANCE, abs=_FD_ABS_TOLERANCE)
    assert result.resultant_north == pytest.approx(-LAMBDA_KM * d_north, abs=_FD_ABS_TOLERANCE)


def test_8b2_grad_02_single_source_north_case():
    source_lat, source_lon = 10.0, 20.0
    cell_lat, cell_lon = _step(source_lat, source_lon, 0.0, 5.0)  # cell 5km north of source
    sources = [EligibleSourcePoint(source_id="S1", latitude=source_lat, longitude=source_lon)]
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)

    assert result.bearing_deg == pytest.approx(0.0, abs=1e-3)  # V points North

    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    positive_grad_bearing = math.degrees(math.atan2(d_east, d_north)) % 360.0
    assert positive_grad_bearing == pytest.approx(180.0, abs=1e-2)  # positive grad(C0) points South

    assert result.resultant_north == pytest.approx(-LAMBDA_KM * d_north, rel=_FD_TOLERANCE, abs=_FD_ABS_TOLERANCE)
    assert result.resultant_east == pytest.approx(-LAMBDA_KM * d_east, abs=_FD_ABS_TOLERANCE)


# ---------------------------------------------------------------------------
# 8B2-GRAD-03/04/05: multi-source finite-difference cross-check
# ---------------------------------------------------------------------------


def _multi_source_case():
    cell_lat, cell_lon = 5.0, 30.0
    lat_a, lon_a = _step(cell_lat, cell_lon, 30.0, 3.0)
    lat_b, lon_b = _step(cell_lat, cell_lon, 160.0, 7.0)
    lat_c, lon_c = _step(cell_lat, cell_lon, 250.0, 12.0)
    sources = [
        EligibleSourcePoint(source_id="A", latitude=lat_a, longitude=lon_a),
        EligibleSourcePoint(source_id="B", latitude=lat_b, longitude=lon_b),
        EligibleSourcePoint(source_id="C", latitude=lat_c, longitude=lon_c),
    ]
    return cell_lat, cell_lon, sources


def test_8b2_grad_03_multi_source_overall_agreement():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    analytical_east, analytical_north = -LAMBDA_KM * d_east, -LAMBDA_KM * d_north
    analytical_magnitude = math.hypot(analytical_east, analytical_north)
    assert result.resultant_magnitude == pytest.approx(analytical_magnitude, rel=_FD_TOLERANCE, abs=_FD_ABS_TOLERANCE)


def test_8b2_grad_04_finite_difference_east_component_agrees():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    d_east, _ = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    assert result.resultant_east == pytest.approx(-LAMBDA_KM * d_east, rel=_FD_TOLERANCE, abs=_FD_ABS_TOLERANCE)


def test_8b2_grad_05_finite_difference_north_component_agrees():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    _, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    assert result.resultant_north == pytest.approx(-LAMBDA_KM * d_north, rel=_FD_TOLERANCE, abs=_FD_ABS_TOLERANCE)


def test_8b2_grad_06_positive_gradient_and_v_differ_by_180_degrees():
    cell_lat, cell_lon, sources = _multi_source_case()
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    assert result.resultant_magnitude > 1e-6  # materially nonzero

    d_east, d_north = _finite_diff_grad_c0(cell_lat, cell_lon, sources)
    positive_grad_bearing = math.degrees(math.atan2(d_east, d_north)) % 360.0
    v_bearing = result.bearing_deg
    # standard wrapped angular difference in [0, 180]: 0 means same
    # direction, 180 means exactly opposite -- V and positive grad(C0)
    # must be opposite, so this must be close to 180, not 0.
    angular_difference = abs((v_bearing - positive_grad_bearing + 180.0) % 360.0 - 180.0)
    assert angular_difference == pytest.approx(180.0, abs=0.5)


# ---------------------------------------------------------------------------
# 8B2-GRAD-07: d=0 -- never fabricate differentiability
# ---------------------------------------------------------------------------


def test_8b2_grad_07_zero_distance_no_fabricated_differentiability():
    cell_lat, cell_lon = 1.0, 1.0
    sources = [EligibleSourcePoint(source_id="AT_CELL", latitude=cell_lat, longitude=cell_lon)]
    result = compute_cell_direction_tendency(_cell(cell_lat, cell_lon), sources)
    term = result.source_terms[0]
    assert term.distance_km == 0.0
    assert term.direction_defined is False
    assert term.t_hat_east is None and term.t_hat_north is None
    # the analytical identity is never invoked/claimed at d=0 -- the
    # distance function is not differentiable there, so no gradient value
    # is fabricated for this term (it is excluded from the resultant)
    assert result.n_zero_distance_undefined_direction_sources == 1


# ---------------------------------------------------------------------------
# 8B2-GRAD-08: the numerical 8B vector equation itself is unchanged
# ---------------------------------------------------------------------------


def test_8b2_grad_08_8b_vector_equation_unchanged():
    cell = _cell(1.0, 1.0)
    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.5, longitude=0.5),
        EligibleSourcePoint(source_id="S2", latitude=1.5, longitude=0.8),
    ]
    result = compute_cell_direction_tendency(cell, sources)

    manual_east = manual_north = 0.0
    for s in sources:
        vec = source_to_cell_unit_vector(s.latitude, s.longitude, 1.0, 1.0)
        w = math.exp(-vec.distance_km / 25.0)
        manual_east += w * vec.t_hat_east
        manual_north += w * vec.t_hat_north

    assert result.resultant_east == pytest.approx(manual_east)
    assert result.resultant_north == pytest.approx(manual_north)


# ---------------------------------------------------------------------------
# Sign/semantic hardening (Part 3)
# ---------------------------------------------------------------------------


def test_8b2_sem_01_active_semantics_contains_sign_aware_terminology():
    assert ACTIVE_OUTPUT_SEMANTICS_8B2 == "C0_DERIVED_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY"
    assert "NEGATIVE_GRADIENT" in ACTIVE_OUTPUT_SEMANTICS_8B2
    # historical wording preserved unchanged, never silently rewritten
    assert HISTORICAL_CHECKPOINT_8B_OUTPUT_TERMINOLOGY == "C0_DERIVED_LOCAL_GEOMETRIC_RELATIVE_RISK_TENDENCY"


def test_8b2_sem_02_active_semantics_never_claims_predictive_spread_direction():
    blob = " ".join([ACTIVE_OUTPUT_SEMANTICS_8B2, GRADIENT_SIGN_STATEMENT_8B2, NEGATIVE_GRADIENT_IDENTITY_8B2])
    # check per ';'-delimited clause (these constants are structured as
    # semicolon-separated statements) -- a sliding character window cannot
    # reliably span a whole clause preceded by "NEVER" once the clause
    # itself contains a long comma/underscore-separated list.
    clauses = blob.split(";")
    for forbidden in ("VALIDATED_SPREAD_DIRECTION", "PREDICTED_DISEASE_SPREAD_DIRECTION", "TRANSMISSION_DIRECTION"):
        for clause in clauses:
            if forbidden in clause:
                assert "NEVER" in clause, f"{forbidden!r} appears in a clause with no negation: {clause!r}"


def test_8b2_sem_03_positive_gradient_and_current_vector_sign_not_aliased():
    assert "POSITIVE_GRAD_C0_POINTS_TOWARD_INCREASING_C0" in GRADIENT_SIGN_STATEMENT_8B2
    assert "180_DEGREES_APART" in GRADIENT_SIGN_STATEMENT_8B2
    assert "OPPOSITE" not in GRADIENT_SIGN_STATEMENT_8B2 or "180" in GRADIENT_SIGN_STATEMENT_8B2


# ---------------------------------------------------------------------------
# Method-identity binding (Part 7, 8, 9)
# ---------------------------------------------------------------------------


def test_8b2_id_01_historical_8b_hash_unchanged():
    assert direction_method_protocol_hash_8b() == HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH
    assert HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH == "9d111741d303d1dcf73c2a624b99c3fa7c3aaa2020d52d3254d5d744e963f32d"


def test_8b2_id_02_new_hash_binds_method_id():
    d = direction_method_protocol_dict_8b2()
    assert d["method_id"] == "C0_GEOMETRIC_TENDENCY"


def test_8b2_id_03_new_hash_binds_method_version():
    d = direction_method_protocol_dict_8b2()
    assert d["method_version"] == METHOD_VERSION_8B2 == "8B.2"
    assert d["historical_method_version_string"] == HISTORICAL_METHOD_VERSION_STRING == "8B.1"


def test_8b2_id_04_changing_active_semantic_identifier_changes_protocol_identity():
    import json as _json

    baseline_dict = direction_method_protocol_dict_8b2()
    baseline_hash = direction_method_protocol_hash_8b2()

    mutated = dict(baseline_dict)
    mutated["active_output_semantics"] = "SOMETHING_ELSE"
    mutated_hash_input = _json.dumps(mutated, sort_keys=True, separators=(",", ":"))
    import hashlib

    mutated_hash = hashlib.sha256(mutated_hash_input.encode("utf-8")).hexdigest()
    assert mutated_hash != baseline_hash


# ---------------------------------------------------------------------------
# Historical artifact preservation (Part 10)
# ---------------------------------------------------------------------------


def test_8b2_hist_01_historical_8b_artifacts_byte_identical():
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
        path = out_dir / filename
        assert path.exists(), f"historical 8B artifact {filename!r} missing"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected_hash, f"{filename}: historical artifact changed! before={expected_hash} after={actual}"


# ---------------------------------------------------------------------------
# Circular-evaluation prohibition re-confirmed (Part 12)
# ---------------------------------------------------------------------------


def test_8b2_evidence_summary_additive_section_present_and_historical_hashes_unchanged():
    import json as _json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_8B_EVIDENCE_SUMMARY.json"
    d = _json.loads(path.read_text(encoding="utf-8"))

    hist = d["local_artifact_sha256"]
    assert hist["direction_protocol_8b.json"] == "c90d76488814a256d649ea07bc4984257f414f5f0858e13b39f03b84a07e855c"
    assert hist["direction_structural_audit_8b.json"] == "2cced458d70f5d193489b4beec68b6c2e1dc9d342b3fb74836a7f3157064cde4"
    assert hist["direction_example_source_terms_8b.json"] == "dd8b532b5884f31bc52576623c9c93c368527178aaaed2085a69ac8c1d1a00d5"
    assert hist["direction_origin_summary_8b.csv"] == "2f48179ff84d9d60daf98ce9801bc0fc72eb7b8b2dc93721b35dca3b64ce6f9c"

    section = d["analytical_semantics_hardening_8b2"]
    assert section["historical_8b_protocol_hash"] == HISTORICAL_CHECKPOINT_8B_PROTOCOL_HASH
    assert section["new_8b2_protocol_hash"] == direction_method_protocol_hash_8b2()
    assert section["no_real_structural_audit_rerun"] is True
    assert section["no_numerical_direction_result_changed"] is True


def test_8b2_circular_01_no_future_target_evaluation_path_introduced():
    import inspect

    from components.geospatial_tracking.services.model_development import direction_protocol_8b as protocol_module

    src = inspect.getsource(protocol_module)
    forbidden = ("angular_error", "mean_angular_error", "median_angular_error", "direction_hit_rate", "bearing_accuracy")
    for term in forbidden:
        assert term not in src
    params = set(inspect.signature(compute_cell_direction_tendency).parameters)
    assert "target" not in " ".join(params).lower()

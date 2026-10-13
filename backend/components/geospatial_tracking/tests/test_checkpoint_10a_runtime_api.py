"""Checkpoint 10A: production-safe frozen geospatial runtime analysis
service and read-only FastAPI boundary.

No frozen scientific model is modified anywhere in this file. No
held-out/Sri Lanka evaluation, no 9B bootstrap rerun, no new research
metric. Real-DB-dependent tests skip gracefully on a clean clone (no
`data/local/pistes_dev.db`) -- structural/unit tests never skip."""

from __future__ import annotations

import ast
import inspect
import json
import math
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api import schemas as schemas_module
from components.geospatial_tracking.api.router import router
from components.geospatial_tracking.api.schemas import DirectionSchema, ProtocolResponse
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.application import frozen_geospatial_analysis_10a as app_service
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A,
    RuntimeAnalysisError10A,
    run_frozen_geospatial_runtime_analysis_10a,
)
from components.geospatial_tracking.services.build_historical_replay import DISEASE
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger
from components.geospatial_tracking.services.geospatial.distance import distance_km
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import geospatial_api_protocol_hash_10a
from components.geospatial_tracking.services.integration.geospatial_intelligence_contract_9c import NEAREST_SOURCE_SEMANTICS_9C
from components.geospatial_tracking.services.integration.geospatial_intelligence_protocol_9c import integration_protocol_hash_9c
from components.geospatial_tracking.services.model_development.candidate_registry_7c import FROZEN_KERNEL_FAMILY, FROZEN_KERNEL_SCALE_KM
from components.geospatial_tracking.services.model_development.rate_scope_conditioning_protocol_9c1 import rate_scope_conditioning_protocol_hash_9c1

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")


def _open_repo() -> SQLiteOutbreakRepository:
    return SQLiteOutbreakRepository(_DB_PATH)


def _direct_imports(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def _real_call_names(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


@pytest.fixture(scope="module")
def real_origin_id():
    if not _DB_AVAILABLE:
        pytest.skip("dev SQLite DB absent")
    repo = _open_repo()
    try:
        origins = build_forecast_origin_ledger(repo, disease=DISEASE)
        for o in origins:
            try:
                run_frozen_geospatial_runtime_analysis_10a(repo, o.forecast_origin_id)
                return o.forecast_origin_id
            except RuntimeAnalysisError10A:
                continue
    finally:
        repo.close()
    pytest.skip("no analyzable origin found in dev DB")


@pytest.fixture(scope="module")
def multi_source_origin_id():
    if not _DB_AVAILABLE:
        pytest.skip("dev SQLite DB absent")
    repo = _open_repo()
    try:
        origins = build_forecast_origin_ledger(repo, disease=DISEASE)
        for o in origins:
            try:
                result = run_frozen_geospatial_runtime_analysis_10a(repo, o.forecast_origin_id)
                if len(result.eligible_sources) >= 2:
                    return o.forecast_origin_id
            except RuntimeAnalysisError10A:
                continue
    finally:
        repo.close()
    pytest.skip("no multi-source analyzable origin found in dev DB")


@pytest.fixture(scope="module")
def real_analysis(real_origin_id):
    repo = _open_repo()
    try:
        return run_frozen_geospatial_runtime_analysis_10a(repo, real_origin_id)
    finally:
        repo.close()


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# 10A-PARENT-01/02
# ---------------------------------------------------------------------------


def test_10a_parent_01_9c_integration_hash_exact():
    assert integration_protocol_hash_9c() == "cec826a26c860c752d1fa32d94edcdfba2e0186950cdccfc96067fef2ce51a90"


def test_10a_parent_02_9c1_conditioning_hash_exact():
    assert rate_scope_conditioning_protocol_hash_9c1() == "26168ca784b5f8cb5393db872baa1e7e7f1d74f782b16df17c97354b9bf52b8f"


# ---------------------------------------------------------------------------
# 10A-SCI-01..05
# ---------------------------------------------------------------------------


def test_10a_sci_01_risk_uses_frozen_c0_scorer_not_duplicated_formula():
    imports = _direct_imports(app_service)
    assert any("wind_scoring_7c" in m for m in imports)
    src = inspect.getsource(app_service)
    assert "math.exp(" not in src and "evaluate_kernel(" not in src


@_skip_no_db
def test_10a_sci_02_all_eligible_sources_contribute(real_analysis):
    repo = _open_repo()
    try:
        assert len(real_analysis.eligible_sources) >= 1
        cell = real_analysis.cells[0]
        expected = sum(
            evaluate_kernel(
                distance_km(s.latitude, s.longitude, cell.centroid_latitude, cell.centroid_longitude),
                family=FROZEN_KERNEL_FAMILY, distance_scale_km=FROZEN_KERNEL_SCALE_KM,
            )
            for s in real_analysis.eligible_sources
        )
        assert cell.risk.raw_c0_score == pytest.approx(expected, rel=1e-9)
    finally:
        repo.close()


@_skip_no_db
def test_10a_sci_03_nearest_source_cannot_replace_all_source_scoring(multi_source_origin_id):
    repo = _open_repo()
    try:
        result = run_frozen_geospatial_runtime_analysis_10a(repo, multi_source_origin_id)
        cell = result.cells[0]
        per_source_terms = [
            evaluate_kernel(
                distance_km(s.latitude, s.longitude, cell.centroid_latitude, cell.centroid_longitude),
                family=FROZEN_KERNEL_FAMILY, distance_scale_km=FROZEN_KERNEL_SCALE_KM,
            )
            for s in result.eligible_sources
        ]
        assert cell.risk.raw_c0_score == pytest.approx(sum(per_source_terms), rel=1e-9)
        assert cell.risk.raw_c0_score != pytest.approx(max(per_source_terms), rel=1e-9) or len(per_source_terms) == 1
        assert cell.risk.raw_c0_score > max(per_source_terms) - 1e-12
    finally:
        repo.close()


def test_10a_sci_04_rate_reach_cannot_alter_c0():
    tree = ast.parse(inspect.getsource(app_service))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_frozen_geospatial_runtime_analysis_10a")
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "score_origin_candidates_7c":
            kw_names = {kw.arg for kw in node.keywords}
            assert kw_names == {"grid_cells", "sources", "candidates", "wind"}
            for kw in node.keywords:
                arg_src = ast.dump(kw.value)
                assert "rate" not in arg_src.lower() and "reach" not in arg_src.lower()


def test_10a_sci_05_no_weather_host_environment_water_source_strength_in_c0():
    imports = _direct_imports(app_service)
    for forbidden in ("host_transform", "environmental_suitability", "water_context", "weather", "source_strength"):
        assert not any(forbidden in m for m in imports), imports


# ---------------------------------------------------------------------------
# 10A-DIR-01..04
# ---------------------------------------------------------------------------


def test_10a_dir_01_direction_via_canonical_8b3_implementation():
    imports = _direct_imports(app_service)
    assert any("c0_cell_local_tendency_8b3" in m for m in imports)


@_skip_no_db
def test_10a_dir_01b_cross_check_against_canonical_function(real_analysis):
    from components.geospatial_tracking.services.direction.c0_cell_local_tendency_8b3 import compute_cell_direction_tendency_8b3

    cell = real_analysis.cells[0]
    cell_dict = {"scientific_cell_id": cell.scientific_cell_id, "centroid_lat": cell.centroid_latitude, "centroid_lon": cell.centroid_longitude}
    sources = [type("P", (), {"source_id": s.source_id, "latitude": s.latitude, "longitude": s.longitude})() for s in real_analysis.eligible_sources]
    from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
    points = [EligibleSourcePoint(source_id=s.source_id, latitude=s.latitude, longitude=s.longitude) for s in real_analysis.eligible_sources]
    recomputed = compute_cell_direction_tendency_8b3(cell_dict, points)
    if cell.direction.bearing_deg is None:
        assert recomputed.bearing_deg is None
    else:
        assert recomputed.bearing_deg == pytest.approx(cell.direction.bearing_deg, abs=1e-9)


def test_10a_dir_02_bearing_zero_survives_serialization():
    schema = DirectionSchema(
        method_id="C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY", method_version="8B.3", bearing_deg=0.0,
        directional_clarity=0.5, directional_input_coverage=1.0, direction_status="DIRECTIONAL_RESULTANT_DEFINED",
        direction_semantics="C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY",
    )
    payload = json.loads(schema.model_dump_json())
    assert payload["bearing_deg"] is not None
    assert payload["bearing_deg"] == 0.0


def test_10a_dir_03_undefined_bearing_serializes_to_null_never_zero():
    schema = DirectionSchema(
        method_id=None, method_version=None, bearing_deg=None, directional_clarity=None,
        directional_input_coverage=None, direction_status="DIRECTION_UNAVAILABLE_NO_CELL_RESULT", direction_semantics=None,
    )
    payload = json.loads(schema.model_dump_json())
    assert payload["bearing_deg"] is None


def test_10a_dir_04_no_confidence_alias_for_clarity():
    field_names = list(DirectionSchema.model_fields.keys())
    assert "directional_clarity" in field_names
    assert not any("confidence" in name for name in field_names)


# ---------------------------------------------------------------------------
# 10A-RATE-01..04
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10a_rate_01_rate_exact(real_analysis):
    assert real_analysis.apparent_rate_context["apparent_rate_km_day"] == 3.946421443154751


@_skip_no_db
def test_10a_rate_02_rate_interval_exact(real_analysis):
    assert real_analysis.apparent_rate_context["rate_interval_lower_km_day"] == 3.5491046170907765
    assert real_analysis.apparent_rate_context["rate_interval_upper_km_day"] == 4.343077329563724


@_skip_no_db
def test_10a_rate_03_rate_status_development_historical(real_analysis):
    assert real_analysis.apparent_rate_context["rate_status"] == "FROZEN_DEVELOPMENT_HISTORICAL_APPARENT_RATE"


@_skip_no_db
def test_10a_rate_04_9c1_conditioning_limitation_exposed(real_analysis):
    ctx = real_analysis.apparent_rate_context
    assert "25-km" in ctx["conditioning_limitation"] or "25 km" in ctx["conditioning_limitation"]
    assert "conditional" in ctx["conditioning_limitation"].lower()
    assert "25-km" in ctx["conditioning_statement"] or "25 km" in ctx["conditioning_statement"]


# ---------------------------------------------------------------------------
# 10A-REACH-01..03
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10a_reach_01_nominal_reaches_exact(real_analysis):
    expected = {
        1: 3.946421443154751, 2: 7.892842886309502, 3: 11.839264329464253, 4: 15.785685772619004,
        5: 19.732107215773755, 6: 23.678528658928506, 7: 27.624950102083258,
    }
    for entry in real_analysis.nominal_reach_by_day:
        assert entry.nominal_reach_km == pytest.approx(expected[entry.day], rel=1e-15)


@_skip_no_db
def test_10a_reach_02_d7_exceeds_25km_preserved(real_analysis):
    d7 = next(e for e in real_analysis.nominal_reach_by_day if e.day == 7)
    assert d7.nominal_reach_km > 25.0


@_skip_no_db
def test_10a_reach_03_operational_envelope_25km(client, real_origin_id):
    r = client.get(f"/api/geospatial/analysis/{real_origin_id}/summary")
    assert r.status_code == 200
    assert r.json()["operational_evaluation_envelope_km"] == 25.0


# ---------------------------------------------------------------------------
# 10A-CRS-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10a_crs_01_geojson_wgs84_lon_lat(client, real_origin_id, real_analysis):
    r = client.get(f"/api/geospatial/analysis/{real_origin_id}/cells")
    assert r.status_code == 200
    body = r.json()
    assert body["geojson_crs"] == "EPSG:4326"
    features_by_id = {f["properties"]["scientific_cell_id"]: f for f in body["features"]}
    for cell in real_analysis.cells:
        feature = features_by_id[cell.scientific_cell_id]
        lon, lat = feature["geometry"]["coordinates"]
        assert lon == pytest.approx(cell.centroid_longitude, abs=1e-9)
        assert lat == pytest.approx(cell.centroid_latitude, abs=1e-9)


def test_10a_crs_02_known_fixture_catches_lat_lon_reversal():
    from components.geospatial_tracking.api.schemas import GeoJSONPointGeometry

    bangkok_lon, bangkok_lat = 100.523186, 13.756331  # real, well-known coordinate -- |lon| > 90
    geom = GeoJSONPointGeometry(coordinates=(bangkok_lon, bangkok_lat))
    assert geom.coordinates[0] == bangkok_lon
    assert geom.coordinates[1] == bangkok_lat
    # a reversal would place an out-of-range value (>90) in the latitude slot
    assert abs(bangkok_lon) > 90.0
    assert abs(bangkok_lat) <= 90.0
    assert not (abs(geom.coordinates[1]) > 90.0)


# ---------------------------------------------------------------------------
# 10A-JSON-01
# ---------------------------------------------------------------------------


def _assert_no_nan_inf(value) -> None:
    if isinstance(value, float):
        assert math.isfinite(value), f"non-finite float found: {value!r}"
    elif isinstance(value, dict):
        for v in value.values():
            _assert_no_nan_inf(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _assert_no_nan_inf(v)


@_skip_no_db
def test_10a_json_01_no_nan_infinity(real_analysis):
    payload = real_analysis.as_dict()
    json.dumps(payload, allow_nan=False)  # raises ValueError on NaN/Infinity
    _assert_no_nan_inf(payload)


# ---------------------------------------------------------------------------
# 10A-ORDER-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10a_order_01_cells_deterministic_by_scientific_cell_id(real_analysis):
    ids = [c.scientific_cell_id for c in real_analysis.cells]
    assert ids == sorted(ids)


@_skip_no_db
def test_10a_order_02_sources_deterministic_by_source_id(real_analysis):
    ids = [s.source_id for s in real_analysis.eligible_sources]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# 10A-ERROR-01/02
# ---------------------------------------------------------------------------


@_skip_no_db
def test_10a_error_01_unknown_origin_404(client):
    r = client.get("/api/geospatial/analysis/ORIGIN:DOES_NOT_EXIST_XYZ:2099-01-01/summary")
    assert r.status_code == 404
    assert r.json()["detail"]["status"] == "ORIGIN_NOT_FOUND"


@_skip_no_db
def test_10a_error_02_no_eligible_source_never_fabricated(monkeypatch, real_origin_id):
    class _EmptyResult:
        sources: list = []

    monkeypatch.setattr(app_service, "get_eligible_sources", lambda *a, **kw: _EmptyResult())
    repo = _open_repo()
    try:
        with pytest.raises(RuntimeAnalysisError10A) as exc_info:
            run_frozen_geospatial_runtime_analysis_10a(repo, real_origin_id)
        assert exc_info.value.status == ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A
    finally:
        repo.close()

    app = FastAPI()
    app.include_router(router)
    tc = TestClient(app)
    # Checkpoint 10B: /summary now resolves a shared, process-wide
    # snapshot cache -- clear it first so this monkeypatched failure is
    # actually recomputed rather than serving an already-cached real
    # result from an earlier test.
    router_module.SNAPSHOT_STORE_10B.clear()
    r = tc.get(f"/api/geospatial/analysis/{real_origin_id}/summary")
    assert r.status_code == 409
    assert r.json()["detail"]["status"] == ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_10A


# ---------------------------------------------------------------------------
# 10A-ROUTER-01/02
# ---------------------------------------------------------------------------


def test_10a_router_01_no_copied_scientific_formula():
    # the router legitimately imports frozen SEMANTIC CONSTANTS (e.g.
    # ACTIVE_OUTPUT_SEMANTICS_8B3 for the /protocol endpoint) from
    # scientific modules -- what must be structurally absent is any
    # real CALL to a scoring/direction/bootstrap FUNCTION, and any
    # import of the bootstrap module at all (never needed for labels).
    src = inspect.getsource(router_module)
    assert "25.0" not in src
    assert "math.exp(" not in src and "evaluate_kernel(" not in src and "statistics.median(" not in src
    imports = _direct_imports(router_module)
    assert not any("rate_s0_bootstrap_9b" in m or "hazard.kernels" in m for m in imports), imports
    calls = _real_call_names(router_module)
    for forbidden in ("score_origin_candidates_7c", "compute_cell_direction_tendency_8b3", "run_bootstrap", "evaluate_kernel"):
        assert forbidden not in calls, (forbidden, calls)


def test_10a_router_02_no_direct_sqlite_query():
    calls = _real_call_names(router_module)
    for forbidden in ("execute", "cursor", "fetchall", "fetchone"):
        assert forbidden not in calls
    src = inspect.getsource(router_module)
    assert "import sqlite3" not in src


# ---------------------------------------------------------------------------
# 10A-FIREWALL-01..03
# ---------------------------------------------------------------------------


def test_10a_firewall_01_no_gitignored_research_artifact_at_runtime():
    for module in (router_module, app_service):
        src = inspect.getsource(module)
        assert "local_data" not in src
        calls = _real_call_names(module)
        assert "read_text" not in calls and "load" not in calls


def test_10a_firewall_02_no_9b_bootstrap_invocation():
    for module in (router_module, app_service):
        imports = _direct_imports(module)
        assert not any("rate_s0_bootstrap_9b" in m for m in imports), (module.__name__, imports)


def test_10a_firewall_03_no_held_out_sri_lanka_rate_inspection():
    # Real IMPORTS are the authoritative structural check -- neither
    # module imports a held-out/Sri Lanka RUN module. A raw full-source
    # substring scan is NOT used here because `app_service`'s own
    # Checkpoint 10A.1 provenance-audit docstring legitimately NAMES
    # `sri_lanka_protocol_7e` (Part 2's historical-inheritance audit
    # trail, a negated/descriptive mention, never a real import).
    for module in (router_module, app_service):
        imports = _direct_imports(module)
        assert not any("heldout_run_7d" in m for m in imports), (module.__name__, imports)
        assert not any("sri_lanka_run_7e" in m or "sri_lanka_protocol_7e" in m for m in imports), (module.__name__, imports)
    # router.py itself has no such legitimate mention -- keep the
    # stronger full-source check there.
    router_src = inspect.getsource(router_module)
    assert "heldout_run_7d" not in router_src
    assert "sri_lanka_run_7e" not in router_src and "sri_lanka_protocol_7e" not in router_src


# ---------------------------------------------------------------------------
# 10A-SEM-01..03
# ---------------------------------------------------------------------------


def test_10a_sem_01_no_infection_probability_field():
    for model in (schemas_module.RiskSchema, schemas_module.AnalysisSummaryResponse, schemas_module.ProtocolResponse):
        for name in model.model_fields:
            assert "probability" not in name.lower()
            assert "accuracy" not in name.lower()
            assert "chance_of_infection" not in name.lower()


def test_10a_sem_02_no_predictive_spread_direction_field():
    for name in schemas_module.DirectionSchema.model_fields:
        assert "predicted" not in name.lower() and "validated_spread" not in name.lower()


def test_10a_sem_03_nearest_source_geometric_only():
    assert "nearest_source_semantics" in schemas_module.SourceFeatureProperties.model_fields
    assert NEAREST_SOURCE_SEMANTICS_9C == "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE"


# ---------------------------------------------------------------------------
# 10A-PROTOCOL-01
# ---------------------------------------------------------------------------


def test_10a_protocol_01_hash_deterministic():
    assert geospatial_api_protocol_hash_10a() == geospatial_api_protocol_hash_10a()


# ---------------------------------------------------------------------------
# TestClient integration tests for every route
# ---------------------------------------------------------------------------


def test_10a_route_protocol(client):
    r = client.get("/api/geospatial/protocol")
    assert r.status_code == 200
    ProtocolResponse.model_validate(r.json())


@_skip_no_db
def test_10a_route_origins(client):
    r = client.get("/api/geospatial/origins")
    assert r.status_code == 200
    assert r.json()["n_origins"] >= 1


@_skip_no_db
def test_10a_route_origins_country_filter(client, real_analysis):
    country = real_analysis.analysis_metadata.country
    r = client.get("/api/geospatial/origins", params={"country": country})
    assert r.status_code == 200
    assert all(o["country"] == country for o in r.json()["origins"])


@_skip_no_db
def test_10a_route_analysis_summary(client, real_origin_id):
    r = client.get(f"/api/geospatial/analysis/{real_origin_id}/summary")
    assert r.status_code == 200
    assert r.json()["analysis_metadata"]["status"] == "ANALYZED"


@_skip_no_db
def test_10a_route_analysis_cells(client, real_origin_id):
    r = client.get(f"/api/geospatial/analysis/{real_origin_id}/cells")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 1


@_skip_no_db
def test_10a_route_analysis_sources(client, real_origin_id):
    r = client.get(f"/api/geospatial/analysis/{real_origin_id}/sources")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 1


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_10a_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_10A_API_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_10A_API_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["parent_integration_protocol_hash_9c"] == integration_protocol_hash_9c()
    assert d["parent_rate_scope_conditioning_protocol_hash_9c1"] == rate_scope_conditioning_protocol_hash_9c1()
    assert d["api_protocol_hash_10a"] == geospatial_api_protocol_hash_10a()
    assert d["apparent_rate_km_day"] == 3.946421443154751
    assert d["rate_interval_km_day"] == {"lower": 3.5491046170907765, "upper": 4.343077329563724}
    assert d["operational_evaluation_envelope_km"] == 25.0
    assert d["day_7_exceeds_operational_envelope"] is True
    assert d["nominal_reach_by_day_km"]["day_7"] > d["operational_evaluation_envelope_km"]
    assert d["held_out_rate_status"] == "NOT_EVALUATED"
    assert d["sri_lanka_rate_status"] == "NOT_EVALUATED"
    assert d["websocket_status"] == "NOT_IMPLEMENTED_IN_10A"
    assert d["final_classification"] == "FROZEN_GEOSPATIAL_SCIENTIFIC_RUNTIME_AND_READ_ONLY_API_READY_FOR_REALTIME_LAYER"

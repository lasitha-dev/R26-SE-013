"""Multi-vet dynamic behaviour of the spatial timeline, clusters and environment
reference point. FICTIONAL in-memory fixtures only (no database, no network).

Cases: A Matara vet, B Colombo vet, C vet in a district with no nearby
sources, D vet with zero assigned farms, F records without GPS, G no
cross-vet farm/case/clinical leakage (incl. a shared snapshot cache), I
cluster inputs follow the selected disease/date, J disease without a model.
"""

from __future__ import annotations

import json
from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point

from components.geospatial_tracking.api.spatial_timeline_router_factory import create_spatial_timeline_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.services.spatial_timeline.clusters import operational_case_points
from components.geospatial_tracking.services.spatial_timeline.districts import find_district
from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document

AS_OF = "2026-10-13"


class _NoHistory:
    def eligible_sources(self, **_):
        return []


def _world():
    vets = {
        "matara": make_vet_document(email="matara@example.com", district="Matara"),
        "colombo": make_vet_document(email="colombo@example.com", district="Colombo"),
        "kandy": make_vet_document(email="kandy@example.com", district="Kandy"),
    }
    farms = {
        "m1": make_farm_document(latitude=6.05, longitude=80.52, location_district="Matara", assigned_vet_emails=["matara@example.com"]),
        "m2": make_farm_document(latitude=6.10, longitude=80.48, location_district="Matara"),
        "c1": make_farm_document(latitude=6.90, longitude=79.95, location_district="Colombo"),
        "nogps": make_farm_document(latitude=None, longitude=None, location_district="Matara"),
    }
    case = lambda f, **kw: make_diagnostic_case_document(farm_id=str(farms[f]["_id"]), disease_name=kw.pop("disease_name", "Lumpy Skin Disease"),
                                                       verified=True, verified_at=kw.pop("verified_at", "2026-10-10 09:00:00"),
                                                       clinical_notes=f"FICTIONAL NOTE {f}", **kw)
    cases = [case("m1"), case("m2"), case("c1"), case("nogps"), case("c1", disease_name="Foot and Mouth Disease")]
    return vets, farms, cases


def _client(vets, farms, cases, who, store):
    port = MongoOperationalDataPort(FakeCollection(list(vets.values())), FakeCollection(list(farms.values())), FakeCollection(cases))
    vet = AuthenticatedVetContext(email=vets[who]["email"], role="vet")
    app = FastAPI()
    app.include_router(create_spatial_timeline_router(get_authenticated_vet_context=lambda: vet, get_operational_data_port=lambda: port,
                                                      get_historical_source_reader=lambda: _NoHistory(), snapshot_store=store))
    return TestClient(app)


def _timeline(client, **params):
    return client.get("/api/geospatial/spatial-timeline", params={"disease": "lsd", "as_of": AS_OF, **params})


def test_each_vet_gets_their_own_district_and_only_their_own_farm_identities():
    vets, farms, cases = _world()
    store = SnapshotStore10B(ttl_seconds=600.0)
    matara = _timeline(_client(vets, farms, cases, "matara", store)).json()
    colombo = _timeline(_client(vets, farms, cases, "colombo", store)).json()
    assert matara["scope"]["district"] == "Matara" and colombo["scope"]["district"] == "Colombo"   # A, B
    assert {s["farm_id"] for s in matara["sources"]} == {str(farms["m1"]["_id"]), str(farms["m2"]["_id"])}
    assert [s["farm_id"] for s in colombo["sources"]] == [str(farms["c1"]["_id"])]
    assert matara["snapshot_id"] != colombo["snapshot_id"]


def test_no_cross_vet_leakage_even_through_a_shared_snapshot_cache():
    vets, farms, cases = _world()
    store = SnapshotStore10B(ttl_seconds=600.0)
    _timeline(_client(vets, farms, cases, "matara", store), scope="national")  # warms the cache with Matara's authorised view
    colombo = _timeline(_client(vets, farms, cases, "colombo", store), scope="national")
    raw = json.dumps(colombo.json())
    for secret in [str(farms["m1"]["_id"]), str(farms["m2"]["_id"]), "FICTIONAL NOTE m1", "FICTIONAL NOTE m2"]:
        assert secret not in raw                                                                        # G
    matara_case_ids = [str(c["_id"]) for c in cases if c["farm_id"] in (str(farms["m1"]["_id"]), str(farms["m2"]["_id"]))]
    assert not any(cid in raw for cid in matara_case_ids)
    assert colombo.headers["X-Spatial-Timeline-Cache"].startswith("MISS")  # different authorised view -> different key


def test_vet_in_a_district_without_nearby_sources_gets_an_explicit_empty_state():
    vets, farms, cases = _world()
    body = _timeline(_client(vets, farms, cases, "kandy", SnapshotStore10B(ttl_seconds=600.0))).json()
    assert body["scope"]["district"] == "Kandy"                                                         # C, D (no farms)
    assert body["status"] == "NO_ELIGIBLE_SOURCES" and body["sources"] == [] and body["cells"] == []
    assert body["risk_zones"]["features"] == [] and all(f["source_corridors"] == [] for f in body["frames"])
    assert body["source_exclusions"].get("operational:BEYOND_MODEL_REACH_OF_DISTRICT", 0) >= 2


def test_records_without_gps_are_counted_never_placed():
    vets, farms, cases = _world()
    body = _timeline(_client(vets, farms, cases, "matara", SnapshotStore10B(ttl_seconds=600.0))).json()
    assert body["source_exclusions"]["operational:MISSING_OR_INVALID_COORDINATES"] == 1                # F
    assert all(s["latitude"] is not None for s in body["sources"])


def test_disease_without_a_model_never_receives_another_diseases_result():
    vets, farms, cases = _world()
    body = _timeline(_client(vets, farms, cases, "colombo", SnapshotStore10B(ttl_seconds=600.0)), disease="fmd").json()
    assert body["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"                           # J
    assert body["cells"] == [] and body["risk_zones"]["features"] == []
    assert all(f["reach"]["nominal_reach_km"] is None for f in body["frames"])


def test_cluster_inputs_follow_the_selected_disease_and_date():
    _vets, farms, cases = _world()
    farm_docs = {str(f["_id"]): f for f in farms.values()}
    lsd, _ = operational_case_points(cases, farm_docs, disease_code="LSD", as_of=date(2026, 10, 13), window_days=14)
    fmd, _ = operational_case_points(cases, farm_docs, disease_code="FMD", as_of=date(2026, 10, 13), window_days=14)
    early, _ = operational_case_points(cases, farm_docs, disease_code="LSD", as_of=date(2026, 10, 1), window_days=14)
    assert len(lsd) == 3 and len(fmd) == 1 and early == []                                           # I


def test_environment_reference_point_lies_inside_the_vets_own_district():
    for name in ("Matara", "Colombo", "Galle", "Kandy", "Kurunegala", "Kegalle", "Kalutara"):
        district = find_district(name)
        point = district.geometry.representative_point()
        assert district.geometry.contains(Point(point.x, point.y)), name


def test_geometry_contract_ids_district_polygon_and_capped_corridors():
    from shapely.geometry import shape

    vets, farms, cases = _world()
    body = _timeline(_client(vets, farms, cases, "matara", SnapshotStore10B(ttl_seconds=600.0))).json()
    assert body["provenance"]["engine_version"] == "SPATIAL_TIMELINE_ENGINE_3.2"
    district = shape(body["scope"]["district_geometry"])
    assert district.is_valid and district.equals(find_district("Matara").geometry)
    assert [f["id"] for f in body["risk_zones"]["features"]] == [f"zone:{f['properties']['tier']}" for f in body["risk_zones"]["features"]]
    for frame in body["frames"]:
        for z in frame["reach_limited_risk_zones"]["features"]:
            assert z["id"] == f"reach:d{frame['day']}:{z['properties']['tier']}"
        for c in frame["source_corridors"]:
            assert c["length_km"] <= 25.0 and c["nominal_reach_km"] == frame["reach"]["nominal_reach_km"]
            assert c["corridor_id"] == f"corridor:d{frame['day']}:{c['source_id']}"
    assert any(c["length_km"] == 25.0 for c in body["frames"][14]["source_corridors"])  # D14 reach 55 km, arrow capped

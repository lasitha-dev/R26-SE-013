"""End-to-end (API level) dynamic-update scenarios for the spatial timeline
that feeds the Outbreak Map, My Area and Analysis & Trends. Every farm and
case is FICTIONAL and lives in in-memory fake collections; a "new case in
the database" is a record appended to the same fake collection between two
requests on the same app and snapshot cache (exactly how the running
service sees a new MongoDB record).

A  Matara vet -> Matara district view.
B  Galle vet on the same server/cache -> Galle view; no Matara vet details.
C  A new verified, GPS-valid case -> new snapshot: sources, risk raster,
   paths (only when the model gives a direction), district influence and the
   new-outbreak scenario all recomputed; Days 0/3/7/14.
D  Overlapping sources -> combined score >= each source alone (validated
   additive field 1 - exp(-sum)).
E  An outside source reaches the vet's district only from its modelled day.
F  Pending, duplicate, missing-GPS and other-disease records never become sources.
"""
from __future__ import annotations

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point

from components.geospatial_tracking.api.spatial_timeline_router_factory import create_spatial_timeline_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.services.spatial_timeline.districts import find_district
from components.geospatial_tracking.services.spatial_timeline.risk_raster import GRID_SOUTH, GRID_STEP_DEG, GRID_WEST, LEVELS, decode_day_raster
from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document

AS_OF = "2026-10-13"
DAYS = (0, 3, 7, 14)
MATARA_A = (6.05, 80.52)  # FICTIONAL inland Matara farm
MATARA_NEAR = (6.06, 80.55)  # FICTIONAL farm ~3.5 km away (overlap)
GALLE_A = (6.20, 80.30)  # FICTIONAL inland Galle farm


class _NoHistory:
    def eligible_sources(self, **_kwargs):
        return []


def _farm(position, district, assigned=()):
    return make_farm_document(latitude=position[0], longitude=position[1], location_district=district, assigned_vet_emails=list(assigned))


def _case(farm, **extra):
    return make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name=extra.pop("disease_name", "Lumpy Skin Disease"),
                                         verified=extra.pop("verified", True), verified_at=extra.pop("verified_at", "2026-10-10 09:00:00"), **extra)


class _World:
    """One fake database + one server-side snapshot cache, shared by vets."""

    def __init__(self, farms, cases):
        self.farms, self.cases = list(farms), list(cases)
        self.vets = []
        self.store = SnapshotStore10B(ttl_seconds=600.0)

    def client(self, email, district):
        vet_doc = make_vet_document(email=email, district=district)
        self.vets.append(vet_doc)
        port = MongoOperationalDataPort(FakeCollection(self.vets), FakeCollection(self.farms), FakeCollection(self.cases))
        app = FastAPI()
        app.include_router(create_spatial_timeline_router(
            get_authenticated_vet_context=lambda: AuthenticatedVetContext(email=email, role="vet"),
            get_operational_data_port=lambda: port, get_historical_source_reader=lambda: _NoHistory(), snapshot_store=self.store))
        return TestClient(app)


def _timeline(client, **params):
    response = client.get("/api/geospatial/spatial-timeline", params={"disease": "lsd", "as_of": AS_OF, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _score_at(raster, lon, lat):
    if raster is None:
        return 0.0
    dec = decode_day_raster(raster)
    i0, j0, w, h = dec["window"]
    i, j = int((lon - GRID_WEST) // GRID_STEP_DEG) - i0, int((lat - GRID_SOUTH) // GRID_STEP_DEG) - j0
    if not (0 <= i < w and 0 <= j < h):
        return 0.0
    score = np.zeros((h, w))
    score[dec["drawn"]] = dec["pixels"]["score"] / LEVELS
    return float(score[j, i])


def test_scenarios_a_b_each_vet_gets_their_own_district_and_no_other_vets_details():
    matara_farm = _farm(MATARA_A, "Matara", assigned=["matara.vet@example.com"])
    galle_farm = _farm(GALLE_A, "Galle", assigned=["galle.vet@example.com"])
    world = _World([matara_farm, galle_farm], [_case(matara_farm), _case(galle_farm)])
    matara = _timeline(world.client("matara.vet@example.com", "Matara"))
    galle = _timeline(world.client("galle.vet@example.com", "Galle"))
    assert matara["scope"]["kind"] == "district" and matara["scope"]["district"] == "Matara"
    assert galle["scope"]["district"] == "Galle"
    assert matara["district_influence"]["district"] == "Matara" and galle["district_influence"]["district"] == "Galle"
    assert len(matara["frames"]) == len(galle["frames"]) == 15
    # Each vet sees their own farm's details only; the other farm is privacy-reduced,
    # even though both responses came from the same server cache.
    own = lambda body, farm: [s for s in body["sources"] if s.get("farm_id") == str(farm["_id"])]
    assert own(matara, matara_farm) and not own(matara, galle_farm)
    assert own(galle, galle_farm) and not own(galle, matara_farm)
    assert matara["snapshot_id"] != galle["snapshot_id"]


def test_scenario_c_a_new_verified_case_recomputes_every_output():
    farm_a = _farm(MATARA_A, "Matara")
    world = _World([farm_a], [_case(farm_a)])
    client = world.client("matara.vet@example.com", "Matara")
    before = _timeline(client)
    # A new case is reported at another farm, then verified (appended to the same "database").
    new_farm = _farm(MATARA_NEAR, "Matara")
    world.farms.append(new_farm)
    world.cases.append(_case(new_farm, verified_at="2026-10-12 10:00:00"))
    after = _timeline(client)
    assert after["snapshot_id"] != before["snapshot_id"]  # never the cached old result
    assert len(after["sources"]) == len(before["sources"]) + 1
    new_id = next(s["source_id"] for s in after["sources"] if s["source_id"] not in {b["source_id"] for b in before["sources"]})
    for day in DAYS:
        kernels = {k["source_id"] for k in after["frames"][day]["risk_field"]["kernels"]}
        assert new_id in kernels  # part of the day's risk field
        assert after["frames"][day]["risk_field"]["raster"] != before["frames"][day]["risk_field"]["raster"]
    # A trajectory only when the model gives the new case a direction; otherwise it is listed with its reason.
    has_path = any(p["source_id"] == new_id for p in after["source_paths"])
    without = {e["source_id"] for e in after["sources_without_path"]}
    assert has_path or new_id in without
    # District influence and the new-outbreak scenario cover the new case too.
    assert new_id in {e["source_id"] for e in after["district_influence"]["sources"]}
    for p in after["possible_new_cases"]:
        assert p["triggered_by"][0] in {s["source_id"] for s in after["sources"]}


def test_scenario_d_overlapping_sources_add_up_on_the_validated_field():
    farm_a = _farm(MATARA_A, "Matara")
    world = _World([farm_a], [_case(farm_a)])
    client = world.client("matara.vet@example.com", "Matara")
    single = _timeline(client)
    near = _farm(MATARA_NEAR, "Matara")
    world.farms.append(near)
    world.cases.append(_case(near))
    both = _timeline(client)
    mid = ((MATARA_A[1] + MATARA_NEAR[1]) / 2, (MATARA_A[0] + MATARA_NEAR[0]) / 2)
    for day in DAYS:
        alone = _score_at(single["frames"][day]["risk_field"]["raster"], *mid)
        combined = _score_at(both["frames"][day]["risk_field"]["raster"], *mid)
        assert combined >= alone - 1e-6  # a second overlapping source never lowers the score
    assert _score_at(both["frames"][0]["risk_field"]["raster"], *mid) > _score_at(single["frames"][0]["risk_field"]["raster"], *mid)


def test_scenario_e_an_outside_source_reaches_the_district_only_from_its_modelled_day():
    matara = find_district("Matara")
    galle_farm = _farm(GALLE_A, "Galle")
    matara_farm = _farm(MATARA_A, "Matara")
    world = _World([galle_farm, matara_farm], [_case(galle_farm), _case(matara_farm)])
    body = _timeline(world.client("matara.vet@example.com", "Matara"))
    entry = next(e for e in body["district_influence"]["sources"] if not e["inside_district"])
    first = entry["first_influence_day"]
    if first is None:  # never reaches the district: no modelled influence on any day
        assert all(d["area_km2"] == 0 for d in entry["by_day"])
        return
    assert all(d["area_km2"] == 0 for d in entry["by_day"][:first]) and entry["by_day"][first]["area_km2"] > 0
    # A new outbreak from that source appears only when its front stands in the district.
    for p in body["possible_new_cases"]:
        if p["triggered_by"] == [entry["source_id"]]:
            for day in range(1, p["seed_day"]):
                front = next(q["front"] for q in body["frames"][day]["source_paths"] if q["source_id"] == entry["source_id"])
                assert not matara.geometry.contains(Point(*front))


def test_scenario_f_pending_duplicate_missing_gps_and_other_disease_never_become_sources():
    farm_a = _farm(MATARA_A, "Matara")
    world = _World([farm_a], [_case(farm_a)])
    client = world.client("matara.vet@example.com", "Matara")
    before = _timeline(client)
    no_gps = make_farm_document(latitude=None, longitude=None, location_district="Matara")
    other = _farm(MATARA_NEAR, "Matara")
    duplicate = world.cases[0]
    world.farms += [no_gps, other]
    world.cases += [
        _case(other, verified=False, verified_at=None),          # pending
        duplicate,                                                # the same record twice
        _case(no_gps),                                            # verified, no farm GPS
        _case(other, disease_name="Foot and Mouth Disease"),      # another disease
    ]
    after = _timeline(client)
    assert [s["source_id"] for s in after["sources"]] == [s["source_id"] for s in before["sources"]]
    excluded = after["source_exclusions"]
    assert excluded.get("operational:NOT_VET_VERIFIED", 0) >= 1
    assert excluded.get("operational:DUPLICATE_CASE_RECORD", 0) >= 1
    assert excluded.get("operational:MISSING_OR_INVALID_COORDINATES", 0) >= 1
    assert excluded.get("operational:WRONG_DISEASE", 0) >= 1

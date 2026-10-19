"""Phase 2: GET /api/geospatial/spatial-timeline and its engine.

Every farm, case, coordinate and identity below is a FICTIONAL TEST FIXTURE
held in memory (in-memory fake collections behind the real
`MongoOperationalDataPort`); nothing here reads or writes any real database.
"""

from __future__ import annotations

import math
from datetime import date

import pyproj
import pytest
import shapely
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Point, shape

from components.geospatial_tracking.api.spatial_timeline_router_factory import create_spatial_timeline_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.repositories.provider import ScientificDatasetUnavailableError
from components.geospatial_tracking.services.integration.nominal_reach_9c import FROZEN_S0_RATE_KM_DAY_9C
from components.geospatial_tracking.services.source_selector import EligibleSource
from components.geospatial_tracking.services.spatial_timeline.districts import find_district, load_districts, sri_lanka_land
from components.geospatial_tracking.services.spatial_timeline.engine import (
    HORIZON_AS_OF,
    HORIZON_EVALUATED,
    HORIZON_EXPLORATORY,
    TimelineScope,
    build_spatial_timeline,
)
from components.geospatial_tracking.services.spatial_timeline.sources import TimelineSource
from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document

AS_OF = "2026-10-13"
TODAY = date(2026, 10, 13)
LSD = "Lumpy skin disease"
_GEOD = pyproj.Geod(ellps="WGS84")
VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
FARM_ROLE = AuthenticatedVetContext(email="farm@example.com", role="farm")

# Fictional farms (inland positions so reach discs are not cut by the coast).
MATARA_A = (6.05, 80.52)
MATARA_B = (6.10, 80.48)
KANDY_A = (7.29, 80.63)


class FakeHistoricalReader:
    def __init__(self, sources=None, unavailable=False):
        self._sources = sources or []
        self._unavailable = unavailable
        self.calls = []

    def eligible_sources(self, *, disease, as_of, window_days, country):
        self.calls.append((disease, as_of, window_days, country))
        if self._unavailable:
            raise ScientificDatasetUnavailableError("fixture: no dataset")
        return list(self._sources)


def _farm(position, district, **extra):
    return make_farm_document(latitude=position[0], longitude=position[1], location_district=district,
                              assigned_vet_emails=extra.pop("assigned", []), **extra)


def _case(farm, **extra):
    return make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name=extra.pop("disease_name", "Lumpy Skin Disease"),
                                         verified=extra.pop("verified", True), verified_at=extra.pop("verified_at", "2026-10-10 09:00:00"), **extra)


def _client(vet_doc, farms, cases, *, vet=VET, historical=None, store=None):
    port = MongoOperationalDataPort(FakeCollection([vet_doc]), FakeCollection(farms), FakeCollection(cases))
    app = FastAPI()
    app.include_router(create_spatial_timeline_router(
        get_authenticated_vet_context=lambda: vet,
        get_operational_data_port=lambda: port,
        get_historical_source_reader=lambda: historical or FakeHistoricalReader(),
        snapshot_store=store if store is not None else SnapshotStore10B(ttl_seconds=600.0),
    ))
    return TestClient(app)


def _get(client, **params):
    query = {"disease": "lsd", "as_of": AS_OF, **params}
    return client.get("/api/geospatial/spatial-timeline", params=query)


def _matara_setup(extra_farms=(), extra_cases=()):
    farm_a = _farm(MATARA_A, "6.05, 80.52 (Matara District)")
    farm_b = _farm(MATARA_B, "Matara")
    farms = [farm_a, farm_b, *extra_farms]
    cases = [_case(farm_a), _case(farm_b), *extra_cases]
    return make_vet_document(district="Matara"), farms, cases


def _source(i, lat, lon, domain="OPERATIONAL"):
    return TimelineSource(source_id=f"TEST-FICTIONAL-{i}", record_domain=domain, disease=LSD, latitude=lat, longitude=lon,
                          observation_date=AS_OF, provenance="TEST_FIXTURE_FICTIONAL", member_record_ids=(f"case-{i}",))


# 1. no eligible sources ------------------------------------------------------
def test_no_eligible_sources_returns_explicit_status_and_all_dated_frames():
    body = _get(_client(make_vet_document(district="Matara"), [], [])).json()
    assert body["status"] == "NO_ELIGIBLE_SOURCES"
    assert body["sources"] == [] and body["risk_zones"]["features"] == []
    assert [f["day"] for f in body["frames"]] == list(range(15))
    assert all(f["reach_limited_risk_zones"]["features"] == [] for f in body["frames"])


# 2/3. one and multiple verified sources --------------------------------------
def test_one_verified_source_has_zones_but_indeterminate_direction():
    farm = _farm(MATARA_A, "Matara")
    body = _get(_client(make_vet_document(district="Matara"), [farm], [_case(farm)])).json()
    assert body["status"] == "OK"
    assert len(body["sources"]) == 1 and body["sources"][0]["record_domain"] == "OPERATIONAL"
    assert body["risk_zones"]["features"]
    direction = body["source_directions"][0]
    assert direction["bearing_deg"] is None and direction["direction_status"] == "INDETERMINATE_NO_DIRECTIONAL_MASS"
    assert all(f["source_corridors"] == [] for f in body["frames"])  # never a fabricated corridor


def test_multiple_verified_sources_are_all_traceable():
    vet, farms, cases = _matara_setup()
    body = _get(_client(vet, farms, cases)).json()
    assert body["status"] == "OK"
    assert {s["farm_id"] for s in body["sources"]} == {str(f["_id"]) for f in farms}
    assert all(s["provenance"] == "ADRS_VET_VERIFIED_DIAGNOSTIC_CASE_AT_VALIDATED_FARM_GPS" for s in body["sources"])
    assert all(d["direction_status"] == "GEOMETRIC_TENDENCY_AVAILABLE" for d in body["source_directions"])


# 4. different coordinates -----------------------------------------------------
def test_zones_follow_the_real_source_coordinates():
    scope = TimelineScope("national")
    near = build_spatial_timeline(sources=[_source(1, *MATARA_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=1, scope=scope)
    far = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=1, scope=scope)
    assert near["snapshot_id"] != far["snapshot_id"]
    for body, (lat, lon) in ((near, MATARA_A), (far, KANDY_A)):
        highest = next(f for f in body["risk_zones"]["features"] if f["properties"]["tier"] == "highest")
        assert shape(highest["geometry"]).contains(Point(lon, lat))  # source-centred


# 5. diseases ----------------------------------------------------------------------
def test_other_disease_cases_are_excluded_and_fmd_model_is_not_reused():
    farm = _farm(MATARA_A, "Matara")
    client = _client(make_vet_document(district="Matara"), [farm], [_case(farm, disease_name="Foot and Mouth Disease")])
    lsd = _get(client).json()
    assert lsd["status"] == "NO_ELIGIBLE_SOURCES"
    assert lsd["source_exclusions"] == {"operational:WRONG_DISEASE": 1}
    fmd = _get(client, disease="fmd").json()
    assert fmd["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
    assert fmd["source_statuses"]["historical"] == "NOT_REQUESTED_DISEASE_MODEL_NOT_READY"
    assert _get(client, disease="rabies").status_code == 422


# 6/18. districts and district authorisation -------------------------------------
def test_district_scope_defaults_to_the_vets_registered_district():
    vet, farms, cases = _matara_setup()
    body = _get(_client(vet, farms, cases)).json()
    assert body["scope"] == {**body["scope"], "kind": "district", "district": "Matara"}
    assert [d["district"] for d in body["district_summaries"]] == ["Matara"]
    matara = find_district("Matara").geometry
    for zone in body["risk_zones"]["features"]:
        assert shape(zone["geometry"]).difference(matara.buffer(1e-5)).area == pytest.approx(0.0, abs=1e-9)


def test_unauthorised_district_is_forbidden_and_missing_district_is_explicit():
    vet, farms, cases = _matara_setup()
    client = _client(vet, farms, cases)
    response = _get(client, district="Kandy")
    assert response.status_code == 403 and response.json()["detail"]["status"] == "DISTRICT_NOT_AUTHORISED"
    assert _get(client, district="Atlantis").json()["detail"]["status"] == "DISTRICT_NOT_FOUND"
    no_district = make_vet_document()
    del no_district["district"]
    response = _get(_client(no_district, farms, cases))
    assert response.status_code == 409 and response.json()["detail"]["status"] == "NO_AUTHORISED_DISTRICT"


def test_assigned_farm_district_and_national_accounts_are_authorised():
    kandy_farm = _farm(KANDY_A, "Kandy", assigned=["vet@example.com"])
    vet, farms, cases = _matara_setup(extra_farms=[kandy_farm], extra_cases=[_case(kandy_farm)])
    assert _get(_client(vet, farms, cases), district="Kandy").json()["scope"]["district"] == "Kandy"
    national_vet = make_vet_document(district="ALL_DISTRICTS")
    client = _client(national_vet, farms, cases)
    assert _get(client, district="Galle").status_code == 200
    assert _get(client).json()["detail"]["status"] == "DISTRICT_REQUIRED"
    assert _get(client, scope="national").json()["scope"]["kind"] == "national"


# 7. all 25 districts ----------------------------------------------------------------
def test_every_one_of_the_25_districts_produces_valid_clipped_output():
    districts = load_districts()
    assert len(districts) == 25
    for district in districts:
        anchor = district.geometry.representative_point()
        body = build_spatial_timeline(sources=[_source(1, anchor.y, anchor.x)], disease_display=LSD, disease_code="LSD",
                                      as_of=TODAY, horizon_days=2, scope=TimelineScope("district", district))
        assert body["status"] == "OK", district.name
        assert body["district_summaries"][0]["district"] == district.name
        assert body["district_summaries"][0]["max_tier"] == "highest"
        for zone in body["risk_zones"]["features"]:
            geometry = shape(zone["geometry"])
            assert geometry.is_valid and not geometry.is_empty, district.name
            assert geometry.difference(district.geometry.buffer(1e-5)).area == pytest.approx(0.0, abs=1e-9), district.name


# 8/9. missing coordinates, dates ---------------------------------------------------
def test_missing_coordinates_and_unverified_cases_never_become_sources():
    no_gps = make_farm_document(latitude=None, longitude=None, location_district="Matara")
    farm = _farm(MATARA_A, "Matara")
    cases = [_case(no_gps), _case(farm, verified=False)]
    body = _get(_client(make_vet_document(district="Matara"), [no_gps, farm], cases)).json()
    assert body["status"] == "NO_ELIGIBLE_SOURCES"
    assert body["sources"] == []


def test_farm_coordinates_off_the_island_never_become_sources():
    # Range-valid but impossible for a Sri Lanka farm: 0,0 default, swapped
    # lat/lon, a point in India. Each is excluded and counted, never scored.
    off_island = [_farm(position, "Matara") for position in [(0.0, 0.0), (80.52, 6.05), (13.08, 80.27)]]
    farm = _farm(MATARA_A, "Matara")
    cases = [_case(f) for f in [*off_island, farm]]
    body = _get(_client(make_vet_document(district="Matara"), [*off_island, farm], cases)).json()
    assert body["status"] == "OK"
    assert [s["farm_id"] for s in body["sources"]] == [str(farm["_id"])]
    assert body["source_exclusions"]["operational:FARM_COORDINATES_OUTSIDE_SRI_LANKA"] == 3


def test_coastal_and_island_farms_stay_eligible():
    # Galle Fort shoreline, Delft island (Jaffna), Kalpitiya peninsula.
    coastal = [_farm(position, district) for position, district in
               [((6.0266, 80.2168), "Galle"), ((9.5167, 79.6833), "Jaffna"), ((8.2333, 79.7667), "Puttalam")]]
    body = _get(_client(make_vet_document(district="ALL_DISTRICTS"), coastal, [_case(f) for f in coastal]),
                scope="national").json()
    assert len(body["sources"]) == 3
    assert "operational:FARM_COORDINATES_OUTSIDE_SRI_LANKA" not in body["source_exclusions"]


def test_dates_are_validated_and_the_window_is_applied():
    farm = _farm(MATARA_A, "Matara")
    cases = [_case(farm, verified_at="2026-10-20 09:00:00"), _case(farm, verified_at="2026-08-01 09:00:00"), _case(farm, verified_at=None)]
    client = _client(make_vet_document(district="Matara"), [farm], cases)
    body = _get(client).json()
    assert body["status"] == "NO_ELIGIBLE_SOURCES"
    # the national source pool sees every host case, so the case with no
    # verified_at is counted explicitly rather than vanishing upstream
    assert body["source_exclusions"] == {
        "operational:MISSING_OR_UNPARSEABLE_VERIFICATION_DATE": 1,
        "operational:OUTSIDE_ACTIVE_SOURCE_WINDOW": 1,
        "operational:VERIFIED_AFTER_AS_OF_DATE": 1,
    }
    assert _get(client, as_of="2026-02-30").json()["detail"]["status"] == "INVALID_AS_OF_DATE"
    assert _get(client, as_of="2099-01-01").json()["detail"]["status"] == "AS_OF_DATE_IN_FUTURE"
    assert _get(client, horizon_days=15).status_code == 422


def test_duplicate_cases_on_one_farm_count_once():
    farm = _farm(MATARA_A, "Matara")
    body = _get(_client(make_vet_document(district="Matara"), [farm], [_case(farm), _case(farm), _case(farm)])).json()
    assert len(body["sources"]) == 1 and body["sources"][0]["member_count"] == 3
    assert body["source_exclusions"] == {"operational:MERGED_DUPLICATE_SAME_FARM_SAME_DISEASE": 2}


# 10. day indexing ----------------------------------------------------------------------
def test_day_0_to_14_frames_are_dated_and_labelled():
    vet, farms, cases = _matara_setup()
    frames = _get(_client(vet, farms, cases)).json()["frames"]
    assert [f["day"] for f in frames] == list(range(15))
    assert frames[0]["date"] == "2026-10-13" and frames[14]["date"] == "2026-10-27"
    assert [f["horizon_status"] for f in frames] == [HORIZON_AS_OF] + [HORIZON_EVALUATED] * 7 + [HORIZON_EXPLORATORY] * 7
    assert frames[0]["reach"]["nominal_reach_km"] is None and frames[0]["reach_limited_risk_zones"]["features"] == []
    assert len({tuple(f["active_source_ids"]) for f in frames}) == 1  # no source appears or disappears


# 11/19/20. identity, cache, new verified case ------------------------------------------
def test_snapshot_identity_cache_and_new_case_invalidation():
    vet, farms, cases = _matara_setup()
    store = SnapshotStore10B(ttl_seconds=600.0)
    first = _get(_client(vet, farms, cases, store=store))
    second = _get(_client(vet, farms, cases, store=store))
    assert first.headers["X-Spatial-Timeline-Cache"].startswith("MISS") and second.headers["X-Spatial-Timeline-Cache"] == "HIT_REUSED"
    assert first.json()["snapshot_id"] == second.json()["snapshot_id"]
    new_farm = _farm((6.00, 80.58), "Matara")
    third = _get(_client(vet, [*farms, new_farm], [*cases, _case(new_farm)], store=store))
    assert third.headers["X-Spatial-Timeline-Cache"].startswith("MISS")
    assert third.json()["snapshot_id"] != first.json()["snapshot_id"]
    assert len(third.json()["sources"]) == len(first.json()["sources"]) + 1


def test_cache_never_serves_another_vets_sources():
    vet, farms, cases = _matara_setup()
    store = SnapshotStore10B(ttl_seconds=600.0)
    _get(_client(vet, farms, cases, store=store))
    other_vet = make_vet_document(district="Galle")
    response = _get(_client(other_vet, farms, cases, store=store), district="Matara")
    assert response.status_code == 403  # rejected before any cache lookup


# 12. GeoJSON validity ------------------------------------------------------------------
def test_zone_geometry_is_valid_wgs84_inside_sri_lanka():
    vet, farms, cases = _matara_setup()
    body = _get(_client(vet, farms, cases), scope="national").json()
    land = sri_lanka_land()
    layers = [body["risk_zones"]] + [f["reach_limited_risk_zones"] for f in body["frames"]]
    for layer in layers:
        for feature in layer["features"]:
            geometry = shape(feature["geometry"])
            assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
            assert geometry.is_valid and not geometry.is_empty
            minx, miny, maxx, maxy = geometry.bounds
            assert 79.4 < minx and maxx < 82.0 and 5.8 < miny and maxy < 10.0
            assert geometry.difference(land.buffer(1e-5)).area == pytest.approx(0.0, abs=1e-9)
    tiers = [f["properties"]["tier"] for f in body["risk_zones"]["features"]]
    assert tiers == [t for t in ("lower", "moderate", "high", "highest") if t in tiers]


# 13. relative-risk calculation ----------------------------------------------------------
def test_cell_scores_equal_the_frozen_c0_formula_and_tiers_follow_quartiles():
    sources = [_source(1, *MATARA_A), _source(2, *MATARA_B)]
    body = build_spatial_timeline(sources=sources, disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=0, scope=TimelineScope("national"))
    thresholds = body["tier_thresholds"]
    land_scores = sorted(c["raw_c0_score"] for c in body["cells"] if c["on_land"])
    assert thresholds["median"] == pytest.approx(land_scores[(len(land_scores) - 1) // 2] if len(land_scores) % 2 else
                                                 (land_scores[len(land_scores) // 2 - 1] + land_scores[len(land_scores) // 2]) / 2)
    for cell in body["cells"][::7]:
        lon, lat = cell["centroid"]["longitude"], cell["centroid"]["latitude"]
        expected = sum(math.exp(-(_GEOD.inv(s.longitude, s.latitude, lon, lat)[2] / 1000.0) / 25.0) for s in sources)
        assert cell["raw_c0_score"] == pytest.approx(expected, rel=1e-9)
        score = cell["raw_c0_score"]
        if not cell["on_land"]:  # offshore cells keep their C0 score but are never tiered
            assert cell["tier"] is None and cell["tier_status"] == "OFF_LAND_NOT_TIERED"
            continue
        expected_tier = ("highest" if score >= thresholds["q3"] else "high" if score >= thresholds["median"]
                         else "moderate" if score >= thresholds["q1"] else "lower")
        assert cell["tier"] == expected_tier


# 14. nominal reach ------------------------------------------------------------------------
def test_nominal_reach_matches_the_frozen_9c_rate_and_envelope_area():
    body = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14, scope=TimelineScope("national"))
    for frame in body["frames"][1:]:
        day = frame["day"]
        assert frame["reach"]["nominal_reach_km"] == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C * day)
    envelope = shape(body["frames"][2]["reach_envelope"])  # inland disc, ~7.9 km radius, not cut by the coast
    area_m2, _ = _GEOD.geometry_area_perimeter(envelope)
    radius_m = FROZEN_S0_RATE_KM_DAY_9C * 2 * 1000.0
    assert abs(area_m2) == pytest.approx(math.pi * radius_m ** 2, rel=0.01)
    areas = [sum(z["properties"]["area_km2"] for z in f["reach_limited_risk_zones"]["features"]) for f in body["frames"][1:7]]
    assert areas == sorted(areas)  # the reached part of the SAME zones only grows


# 15. direction field -------------------------------------------------------------------------
def test_direction_at_a_source_points_away_from_its_neighbour():
    a, b = _source(1, *MATARA_A), _source(2, *MATARA_B)
    body = build_spatial_timeline(sources=[a, b], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=1, scope=TimelineScope("national"))
    direction_a = next(d for d in body["source_directions"] if d["source_id"] == a.source_id)
    toward_b_at_a = _GEOD.inv(b.longitude, b.latitude, a.longitude, a.latitude)[1]  # back azimuth: at A, pointing to B
    away_from_b = (toward_b_at_a + 180.0) % 360.0
    assert direction_a["bearing_deg"] == pytest.approx(away_from_b, abs=0.5)
    corridor = body["frames"][1]["source_corridors"][0]
    assert corridor["length_km"] == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C)


# 16. environment -------------------------------------------------------------------------------
def test_environmental_data_is_descriptive_and_never_used_in_the_score():
    vet, farms, cases = _matara_setup()
    environment = _get(_client(vet, farms, cases)).json()["environment"]
    assert environment["status"] == "NOT_INTEGRATED" and environment["used_in_score"] is False


# 17. authentication --------------------------------------------------------------------------------
def test_authentication_is_required_and_vet_only():
    vet, farms, cases = _matara_setup()
    assert _get(_client(vet, farms, cases, vet=None)).status_code == 401
    assert _get(_client(vet, farms, cases, vet=FARM_ROLE)).status_code == 403


# historical sources ---------------------------------------------------------------------------------
def test_historical_sources_are_read_with_the_frozen_window_and_kept_distinct():
    historical = FakeHistoricalReader([EligibleSource(
        source_id="WAHIS_TEST_FIXTURE_1", record_domain="HISTORICAL", disease=LSD, country="Sri Lanka", latitude=6.02,
        longitude=80.50, effective_availability_date="2026-10-01", availability_quality="EXACT", gps_quality="EXACT", status=None)])
    vet, farms, cases = _matara_setup()
    body = _get(_client(vet, farms, cases, historical=historical)).json()
    assert historical.calls == [(LSD, AS_OF, 14, "Sri Lanka")]
    domains = {s["source_id"]: s["record_domain"] for s in body["sources"]}
    assert domains["HIST:WAHIS_TEST_FIXTURE_1"] == "HISTORICAL"
    assert sum(1 for d in domains.values() if d == "OPERATIONAL") == 2
    unavailable = _get(_client(vet, farms, cases, historical=FakeHistoricalReader(unavailable=True))).json()
    assert unavailable["source_statuses"]["historical"] == "SCIENTIFIC_DATASET_UNAVAILABLE"
    assert unavailable["status"] == "OK"


def test_corridors_are_clipped_to_land_and_never_cross_the_sea():
    coastal = _source(1, 5.95, 80.55)  # fictional point near the south coast
    inland = _source(2, 6.05, 80.52)
    body = build_spatial_timeline(sources=[coastal, inland], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14, scope=TimelineScope("national"))
    land = sri_lanka_land().buffer(1e-5)
    for frame in body["frames"]:
        for corridor in frame["source_corridors"]:
            assert shape(corridor["geometry"]).difference(land).length == pytest.approx(0.0, abs=1e-9)


def test_district_view_display_geometry_is_land_clipped_not_cut_at_the_border():
    """Scenario E: a source near the Matara/Galle border. The district product
    (zones, summaries, `geometry`) stays clipped to Matara; `display_geometry`
    and `reach_envelope_display` follow land only, so the map is not cut at an
    administrative line -- and nothing is drawn over the sea."""
    matara = find_district("Matara")
    galle = find_district("Galle").geometry
    tol = 1e-4  # ~11 m: outputs are precision-snapped to 1e-5 degrees
    land = sri_lanka_land().buffer(tol)
    body = build_spatial_timeline(sources=[_source(1, *MATARA_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                  horizon_days=7, scope=TimelineScope("district", matara))
    displayed = [shape(c["display_geometry"]) for c in body["cells"] if c["display_geometry"]]
    scoped = [shape(c["geometry"]) for c in body["cells"] if c["geometry"]]
    assert displayed and scoped
    # District product unchanged: scope geometry never leaves Matara.
    assert all(matara.geometry.buffer(tol).contains(g) for g in scoped)
    # Display geometry crosses into Galle where the model scored land ...
    assert any(g.intersects(galle) and g.intersection(galle).area > 0 for g in displayed)
    # ... but never over the sea.
    assert all(land.contains(g) for g in displayed)
    day7 = body["frames"][7]
    assert shape(day7["reach_envelope"]).difference(matara.geometry.buffer(tol)).is_empty
    display_env = shape(day7["reach_envelope_display"])
    assert display_env.intersection(galle).area > 0 and land.contains(display_env)
    # Same tiers and scores as before: only the drawn footprint differs.
    tiered = [c for c in body["cells"] if c["tier"]]
    assert all(c["display_geometry"] is not None for c in tiered if c["geometry"] is not None)


def test_national_view_display_geometry_equals_the_land_clipped_geometry():
    body = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                  horizon_days=2, scope=TimelineScope("national"))
    assert all(c["display_geometry"] == c["geometry"] for c in body["cells"])
    assert body["frames"][2]["reach_envelope_display"] == body["frames"][2]["reach_envelope"]
    assert body["frames"][0]["reach_envelope_display"] is None


def test_display_bands_are_fixed_on_the_bounded_score_and_overlap_raises_the_band():
    """B = 1 - exp(-C0): same ranking as the frozen C0, bounded to [0, 1).
    One isolated source peaks in `elevated` (orange); two overlapping sources
    reach `high` (red). Bands never depend on the day or on the other cells."""
    from components.geospatial_tracking.services.spatial_timeline.engine import DISPLAY_BANDS, bounded_score, display_band
    one = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                 horizon_days=3, scope=TimelineScope("national"))
    two = build_spatial_timeline(sources=[_source(1, *KANDY_A), _source(2, KANDY_A[0] + 0.01, KANDY_A[1])], disease_display=LSD,
                                 disease_code="LSD", as_of=TODAY, horizon_days=3, scope=TimelineScope("national"))
    one_cells = [c for c in one["cells"] if c["bounded_score"] is not None]
    two_cells = [c for c in two["cells"] if c["bounded_score"] is not None]
    assert max(c["bounded_score"] for c in one_cells) < 0.70 <= max(c["bounded_score"] for c in two_cells)
    assert "high" not in {c["band"] for c in one_cells} and "high" in {c["band"] for c in two_cells}
    for c in one_cells + two_cells:
        assert 0.0 <= c["bounded_score"] < 1.0
        assert c["bounded_score"] == pytest.approx(1 - math.exp(-c["raw_c0_score"]))
        assert c["band"] == display_band(c["bounded_score"])
    # Same ranking as the frozen C0.
    order = sorted(one_cells, key=lambda c: c["raw_c0_score"])
    assert [c["cell_id"] for c in order] == [c["cell_id"] for c in sorted(one_cells, key=lambda c: c["bounded_score"])]
    assert [band for band, _ in DISPLAY_BANDS] == ["high", "elevated", "moderate", "low"]
    assert bounded_score(None) is None and display_band(0.7) == "high" and display_band(0.6999) == "elevated"


def _angle(a, b):
    return abs(((a - b) + 180.0) % 360.0 - 180.0)


def _wind(by_day):
    """Fake, offline NET daily wind: {day offset: (toward_deg, steadiness)}."""
    from datetime import timedelta
    table = {(TODAY + timedelta(days=d)).isoformat(): {"toward_deg": t, "steadiness": s, "mean_speed_ms": 4.0, "kind": "TEST"} for d, (t, s) in by_day.items()}
    return lambda lat, lon: table


def _steady(toward, steadiness=0.9, days=15):
    return _wind({d: (toward, steadiness) for d in range(days)})


def _max_step_turn(coords):
    geod = pyproj.Geod(ellps="WGS84")
    heads = [geod.inv(*coords[i], *coords[i + 1])[0] % 360 for i in range(len(coords) - 1)]
    return max((_angle(heads[i], heads[i + 1]) for i in range(len(heads) - 1)), default=0.0)


def test_every_case_gets_a_daily_heading_from_land_cattle_net_wind_and_nearby_cases():
    """Test B/C/D/E: an isolated inland case follows a steady net wind; each
    case of a pair is pushed away from its neighbour; every path advances S0 a
    day on land, within the 25 km evaluated domain, with a distance check."""
    geod = pyproj.Geod(ellps="WGS84")
    lone = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=7,
                                  scope=TimelineScope("national"), wind_lookup=_steady(45.0, 0.95))
    path = lone["source_paths"][0]
    assert path["wind_status"] == "OK"
    day3 = lone["frames"][3]["source_paths"][0]
    assert _angle(geod.inv(KANDY_A[1], KANDY_A[0], *day3["front"])[0] % 360, 45.0) < 45  # downwind-led
    basis = day3["heading_basis"]
    assert basis["wind_toward_deg"] == 45.0 and basis["cattle_source"].startswith("FAO GLW4") and 0 < basis["confidence"] <= 1
    a, b = _source(1, *MATARA_A), _source(2, *MATARA_B)
    pair = build_spatial_timeline(sources=[a, b], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14, scope=TimelineScope("national"))
    near_land = sri_lanka_land().buffer(0.0101)
    for src, other in ((a, b), (b, a)):
        away = geod.inv(other.longitude, other.latitude, src.longitude, src.latitude)[0] % 360
        sp = next(p for p in pair["source_paths"] if p["source_id"] == src.source_id)
        assert _angle(geod.inv(src.longitude, src.latitude, *sp["geometry"]["coordinates"][8])[0] % 360, away) < 90  # pushed apart
        assert near_land.contains(shape(sp["geometry"])) and sp["length_km"] <= 25.0 + 1e-6
    lengths = {}
    for frame in pair["frames"]:
        for sp in frame["source_paths"]:
            if frame["day"] == 0:
                assert sp["geometry"] is None and sp["length_km"] == 0.0 and sp["plume"] is None and sp["distance_check"] is None
                continue
            check = sp["distance_check"]
            assert check["within_nominal_reach"] and check["displacement_km"] <= check["drawn_km"] + 1e-6
            assert sp["length_km"] <= min(FROZEN_S0_RATE_KM_DAY_9C * frame["day"], 25.0) + 1e-3
            assert sp["length_km"] >= lengths.get(sp["source_id"], 0.0)
            lengths[sp["source_id"]] = sp["length_km"]


def test_direction_changes_with_the_daily_wind_but_never_zigzags():
    """Test D/F: a wind that turns from east to north turns the path -- gradually
    within each day, so the step-to-step turn stays small."""
    turning = _wind({**{d: (90.0, 0.95) for d in range(3)}, **{d: (0.0, 0.95) for d in range(3, 15)}})
    body = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=6,
                                  scope=TimelineScope("national"), wind_lookup=turning)
    bearings = [f["source_paths"][0]["front_bearing_deg"] for f in body["frames"][1:]]
    assert _angle(bearings[1], bearings[5]) > 30  # it does turn with the wind
    assert _max_step_turn(body["source_paths"][0]["geometry"]["coordinates"]) < 15  # but smoothly
    # 3-hour sea/land-breeze swings are not followed: only the NET daily wind is used.
    steady = build_spatial_timeline(sources=[_source(1, *MATARA_A), _source(2, *MATARA_B)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                    horizon_days=14, scope=TimelineScope("national"), wind_lookup=_steady(150.0, 0.5))
    geod = pyproj.Geod(ellps="WGS84")
    for path in steady["source_paths"]:
        coords = path["geometry"]["coordinates"]
        heads = [geod.inv(*coords[i], *coords[i + 1])[0] % 360 for i in range(len(coords) - 1)]
        sharp = sum(_angle(heads[i], heads[i + 1]) >= 15 for i in range(len(heads) - 1))
        bases = [sp["heading_basis"] or {} for f in steady["frames"][1:] for sp in f["source_paths"] if sp["source_id"] == path["source_id"]]
        held = sum(bool(b.get("held_at_coast")) for b in bases)
        assert sharp <= held  # a bend only where the front waited at the coast, never a zigzag
        straight = geod.inv(*coords[0], *coords[-1])[2] / 1000.0
        assert path["length_km"] / straight < 1.25


def test_a_front_waits_at_the_coast_and_never_slides_along_it_or_goes_to_sea():
    """Test G: a step that would leave land ends the day's movement; no point at
    sea; the path is never deflected sideways along the shore."""
    from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
    from components.geospatial_tracking.services.spatial_timeline.engine import trace_source_path
    from datetime import timedelta
    lat, lon = 7.0, 80.5
    sea_east = lambda p: p.x < lon + 0.02  # "sea" ~2 km east
    wind = {(TODAY + timedelta(days=d)).isoformat(): {"toward_deg": 90.0, "steadiness": 1.0} for d in range(3)}
    trace = trace_source_path(lat, lon, [EligibleSourcePoint(source_id="O", latitude=lat, longitude=lon)], 3, sea_east, as_of=TODAY, wind_by_date=wind)
    assert all(x < lon + 0.02 for x, _ in trace["coords"])
    day1 = trace["basis_by_day"][1]
    assert all(abs(y - lat) < 0.01 for x, y in trace["coords"][: trace["day_index"][1] + 1])  # day 1 heads straight at the coast...
    assert day1["held_at_coast"] or day1["moved_km"] < FROZEN_S0_RATE_KM_DAY_9C  # ...and waits there, it does not slide along it
    from shapely.prepared import prep
    land = prep(sri_lanka_land().buffer(0.01))
    real = trace_source_path(6.06, 80.25, [EligibleSourcePoint(source_id="G", latitude=6.06, longitude=80.25)], 7, land.contains, as_of=TODAY,
                             wind_by_date={(TODAY + timedelta(days=d)).isoformat(): {"toward_deg": 180.0, "steadiness": 1.0} for d in range(7)})
    assert all(land.contains(Point(x, y)) for x, y in real["coords"])  # Galle coast, wind straight out to sea


def test_no_path_is_invented_without_any_preferred_direction(monkeypatch):
    """Test I: no land ahead, or every factor flat -> no direction, no path."""
    from components.geospatial_tracking.services.spatial_timeline import spread_direction as sd
    assert sd.daily_heading(7.0, 80.5, land_contains=lambda p: False)["bearing_deg"] is None
    monkeypatch.setattr(sd, "cattle_density_grid", lambda: None)  # no host layer -> host factor flat
    flat = sd.daily_heading(7.0, 80.5, land_contains=lambda p: True)
    assert flat["bearing_deg"] is None and flat["reason"] == "NO_PREFERRED_DIRECTION"
    from components.geospatial_tracking.services.spatial_timeline.engine import trace_source_path
    from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
    trace = trace_source_path(7.0, 80.5, [EligibleSourcePoint(source_id="O", latitude=7.0, longitude=80.5)], 5, lambda p: True)
    assert len(trace["coords"]) == 1 and trace["stop_reason"] == "NO_DIRECTIONAL_EVIDENCE"


def test_wind_and_cattle_are_labelled_extensions_rain_and_humidity_unused():
    body = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=2,
                                  scope=TimelineScope("national"))
    rule = body["provenance"]["spread_path_rule"]
    assert "EXTENSION" in rule["inputs"]["wind"] and "EXTENSION" in rule["inputs"]["cattle"]
    assert set(rule["not_inputs"]) == {"rain", "humidity"} and rule["length_cap_km"] == 25.0
    entry = (body["source_paths"] or body["sources_without_path"])[0]
    assert entry["wind_status"] == "UNAVAILABLE"  # no wind lookup: reported, never substituted


def test_reach_display_is_the_path_ribbon_on_land():
    a, b = _source(1, *MATARA_A), _source(2, *MATARA_B)
    body = build_spatial_timeline(sources=[a, b], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=3, scope=TimelineScope("national"))
    assert body["frames"][0]["reach_display"] is None
    frame = body["frames"][3]
    shaped = shape(frame["reach_display"])
    assert shaped.is_valid and sri_lanka_land().buffer(1e-4).contains(shaped)
    assert shaped.area < shape(frame["reach_envelope_display"]).area


# Practical day-d risk field (Risk Zones surface) ------------------------------
def _field(body, day):
    from components.geospatial_tracking.services.spatial_timeline.engine import risk_field_value
    kernels = body["frames"][day]["risk_field"]["kernels"]
    return lambda lon, lat: risk_field_value(lon, lat, kernels)


def _c0(body, lon, lat):
    return sum(math.exp(-_GEOD.inv(s["longitude"], s["latitude"], lon, lat)[2] / 25000.0) for s in body["sources"])


def _offset(lat, lon, bearing, km):
    lon2, lat2, _ = _GEOD.fwd(lon, lat, bearing, km * 1000.0)
    return lon2, lat2


def test_risk_field_starts_at_the_case_and_never_exceeds_the_frozen_c0():
    """Day 0: only the case's own surroundings (half a 5 km cell + fringe).
    Every day, at every point, the field is <= the frozen C0."""
    body = build_spatial_timeline(sources=[_source(1, *KANDY_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                  horizon_days=14, scope=TimelineScope("national"))
    day0 = _field(body, 0)
    lat, lon = KANDY_A
    assert day0(lon, lat) == pytest.approx(1.0)
    assert day0(*_offset(lat, lon, 90, 10)) < 0.01  # 10 km away is not yet reached on Day 0
    for day in (0, 1, 3, 7, 14):
        field = _field(body, day)
        for bearing in range(0, 360, 45):
            for km in (0, 2, 5, 10, 20, 30):
                plon, plat = _offset(lat, lon, bearing, km)
                assert field(plon, plat) <= _c0(body, plon, plat) + 1e-9
    assert _field(body, 14)(*_offset(lat, lon, 90, 45)) < 0.01  # never a district-wide spread


def test_risk_field_grows_day_by_day_in_the_spread_direction_not_behind_it():
    from components.geospatial_tracking.services.spatial_timeline.engine import risk_field_value
    a, b = _source(1, *MATARA_A), _source(2, *MATARA_B)
    body = build_spatial_timeline(sources=[a, b], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                  horizon_days=7, scope=TimelineScope("national"))
    lat, lon = MATARA_A
    path = next(sp for sp in body["frames"][3]["source_paths"] if sp["source_id"] == a.source_id)
    heading = _GEOD.inv(lon, lat, *path["front"])[0] % 360
    ahead, behind = _offset(lat, lon, heading, 8), _offset(lat, lon, heading + 180, 8)
    own = lambda day: [k for k in body["frames"][day]["risk_field"]["kernels"] if k["source_id"] == a.source_id]
    values = [risk_field_value(*ahead, own(d)) for d in range(8)]
    assert values[0] < 0.01 < values[3]
    assert all(v2 >= v1 - 1e-9 for v1, v2 in zip(values, values[1:]))  # gradual, never jumps back
    assert risk_field_value(*ahead, own(5)) > 3 * risk_field_value(*behind, own(5))  # direction-aware, not a circle


def test_overlapping_cases_raise_the_risk_field_to_high():
    from components.geospatial_tracking.services.spatial_timeline.engine import bounded_score
    lat, lon = KANDY_A
    one = build_spatial_timeline(sources=[_source(1, lat, lon)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                 horizon_days=2, scope=TimelineScope("national"))
    two = build_spatial_timeline(sources=[_source(1, lat, lon), _source(2, lat + 0.02, lon)], disease_display=LSD, disease_code="LSD",
                                 as_of=TODAY, horizon_days=2, scope=TimelineScope("national"))
    mid_lon, mid_lat = lon, lat + 0.01
    assert bounded_score(_field(one, 0)(lon, lat)) < 0.70  # an isolated case peaks orange
    assert bounded_score(_field(two, 0)(mid_lon, mid_lat)) >= 0.70  # overlap between two farms ~2 km apart: red
    assert _field(two, 1)(mid_lon, mid_lat) > _field(one, 1)(mid_lon, mid_lat)


def test_risk_field_keeps_the_as_of_source_set_on_every_day():
    """As in the evaluated STATIC-T0 model, every eligible case drives every
    day (none is retired mid-horizon); its age on each frame date is reported."""
    old = TimelineSource(source_id="TEST-FICTIONAL-OLD", record_domain="OPERATIONAL", disease=LSD, latitude=KANDY_A[0],
                         longitude=KANDY_A[1], observation_date="2026-10-01", provenance="TEST_FIXTURE_FICTIONAL", member_record_ids=("case-old",))
    body = build_spatial_timeline(sources=[old, _source(2, *MATARA_A)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                  horizon_days=5, scope=TimelineScope("national"))
    for day, frame in enumerate(body["frames"]):
        kernels = {k["source_id"]: k for k in frame["risk_field"]["kernels"]}
        assert set(kernels) == {"TEST-FICTIONAL-OLD", "TEST-FICTIONAL-2"}
        assert kernels["TEST-FICTIONAL-OLD"]["age_days"] == 12 + day
    assert _field(body, 5)(KANDY_A[1], KANDY_A[0]) == pytest.approx(1.0)


def test_risk_field_raster_is_the_field_the_map_draws():
    """The map colours only the backend raster: each drawn cell carries the
    day's score, the contributing-case count and the top two cases."""
    from components.geospatial_tracking.services.spatial_timeline.engine import bounded_score
    from components.geospatial_tracking.services.spatial_timeline.risk_raster import GRID_SOUTH, GRID_STEP_DEG, GRID_WEST, LEVELS, decode_day_raster
    sources = [_source(1, *MATARA_A), _source(2, *MATARA_B)]
    body = build_spatial_timeline(sources=sources, disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=4,
                                  scope=TimelineScope("national"))
    assert body["provenance"]["risk_field_rule"]["raster"]["step_deg"] == GRID_STEP_DEG
    drawn_by_day = []
    for day in (0, 4):
        raster = body["frames"][day]["risk_field"]["raster"]
        decoded = decode_day_raster(raster)
        i0, j0, w, h = decoded["window"]
        drawn = decoded["drawn"]
        assert drawn.sum() == len(decoded["pixels"]) == raster["drawn_cells"] > 0
        drawn_by_day.append(int(drawn.sum()))
        field = _field(body, day)
        rows, cols = drawn.nonzero()
        for n in range(0, len(rows), max(1, len(rows) // 25)):
            lon = GRID_WEST + (i0 + cols[n] + 0.5) * GRID_STEP_DEG
            lat = GRID_SOUTH + (j0 + rows[n] + 0.5) * GRID_STEP_DEG
            px = decoded["pixels"][n]
            assert px["score"] / LEVELS == pytest.approx(bounded_score(field(lon, lat)), abs=0.01)
            assert 1 <= px["count"] <= 2 and px["case1"] in (1, 2)
            assert px["share1"] + px["share2"] <= LEVELS + 1
            if px["count"] == 2:
                assert {px["case1"], px["case2"]} == {1, 2}
    assert drawn_by_day[1] > drawn_by_day[0]  # Day 4 has spread beyond the farms' own area


# My Area cross-district influence (district scope) -----------------------------
def test_district_influence_first_day_comes_from_the_source_specific_risk_geometry():
    """A source outside the vet's district has no influence there until its own
    day-d risk kernel visibly colours district land; then it is reported, by
    day, from the backend output. Nothing is created on that day."""
    import math as _m
    from components.geospatial_tracking.services.spatial_timeline.engine import FROZEN_S0_RATE_KM_DAY_9C as S0
    from components.geospatial_tracking.services.spatial_timeline.risk_raster import MIN_SCORE
    galle = find_district("Galle")
    inside, outside = _source(1, 6.20, 80.30), _source(2, *MATARA_A)
    assert galle.geometry.contains(Point(inside.longitude, inside.latitude)) and not galle.geometry.contains(Point(outside.longitude, outside.latitude))
    body = build_spatial_timeline(sources=[inside, outside], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                  scope=TimelineScope("district", galle))
    influence = body["district_influence"]
    assert influence["district"] == "Galle" and influence["district_land_cells"] > 100
    entries = {e["source_id"]: e for e in influence["sources"]}
    own = entries[inside.source_id]
    assert own["inside_district"] and own["first_nominal_reach_day"] == 0 and own["first_influence_day"] == 0
    ext = entries[outside.source_id]
    assert not ext["inside_district"] and ext["distance_to_district_km"] > 0
    assert ext["first_nominal_reach_day"] == _m.ceil(ext["distance_to_district_km"] / S0)
    first = ext["first_influence_day"]
    assert first is not None and first >= 1
    areas = [d["area_km2"] for d in ext["by_day"]]
    assert all(a == 0 for a in areas[:first]) and areas[first] > 0
    assert all(b >= a - 1e-6 for a, b in zip(areas, areas[1:]))  # the source's reach only grows
    # The reported influence is the source's own kernel on district land cells.
    ext_kernel = lambda day: [k for k in body["frames"][day]["risk_field"]["kernels"] if k["source_id"] == outside.source_id]
    assert ext["by_day"][first]["max_score"] >= MIN_SCORE
    import numpy as _np
    from components.geospatial_tracking.services.spatial_timeline.risk_raster import district_cells, kernel_values
    from shapely.ops import unary_union as _union
    drawable = _union([shape(c["display_geometry"]) for c in body["cells"] if c["display_geometry"]])  # the land the map colours
    lons, lats, km2 = district_cells(galle.geometry, drawable)
    for day in (first - 1, first, 14):
        score = 1 - _np.exp(-kernel_values(ext_kernel(day)[0], lons, lats))
        assert ext["by_day"][day]["area_km2"] == pytest.approx(float(km2[score >= MIN_SCORE].sum()), abs=0.01)
    # Same eligible sources on every day; modelled new outbreaks are separate
    # kernels (flagged possible_new_case), never new eligible sources.
    assert all(len([k for k in f["risk_field"]["kernels"] if not k.get("possible_new_case")]) == 2 for f in body["frames"])
    assert all(k["source_id"].startswith("POSSIBLE:") for f in body["frames"] for k in f["risk_field"]["kernels"] if k.get("possible_new_case"))
    assert {e["source_id"] for e in influence["sources"]} == {inside.source_id, outside.source_id}


def test_district_influence_is_dynamic_and_absent_in_the_national_view():
    """Any district / source pair: a far source never influences a district it
    cannot reach in 14 days; the national view has no district influence."""
    kandy = find_district("Kandy")
    far = _source(1, *MATARA_A)  # ~120 km from Kandy
    body = build_spatial_timeline(sources=[far], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                  scope=TimelineScope("district", kandy))
    entry = body["district_influence"]["sources"][0]
    assert entry["first_influence_day"] is None and entry["first_nominal_reach_day"] is None
    assert all(d["area_km2"] == 0 for d in entry["by_day"])
    national = build_spatial_timeline(sources=[far], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=2,
                                      scope=TimelineScope("national"))
    assert national["district_influence"] is None


# My Area Future Impact timeline (district scope), Days 0 / 3 / 7 / 13 / 14 ----
def _decoded_scores(raster):
    """{(i, j): score} of one encoded day raster."""
    from components.geospatial_tracking.services.spatial_timeline.risk_raster import LEVELS, decode_day_raster
    if not raster:
        return {}
    dec = decode_day_raster(raster)
    i0, j0, _, _ = dec["window"]
    rows, cols = dec["drawn"].nonzero()
    return {(i0 + c, j0 + r): int(px["score"]) / LEVELS for r, c, px in zip(rows, cols, dec["pixels"])}


def test_district_timeline_days_0_3_7_13_14():
    from datetime import timedelta
    galle = find_district("Galle")
    sources = [_source(1, 6.20, 80.30), _source(2, 6.24, 80.33), _source(3, *MATARA_A)]
    body = build_spatial_timeline(sources=sources, disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                  scope=TimelineScope("district", galle))
    frames = body["frames"]
    assert [f["date"] for f in frames] == [(TODAY + timedelta(days=d)).isoformat() for d in range(15)]  # as-of + d (Asia/Colombo as-of)
    day0 = frames[0]
    assert all(sp["geometry"] is None and sp["plume"] is None for sp in day0["source_paths"])  # no future line/arrow on Day 0
    assert day0["risk_field"]["raster"]["drawn_cells"] > 0  # the baseline zone around each farm
    for d in (3, 7, 13, 14):
        frame = frames[d]
        assert frame["risk_field"]["raster"]["drawn_cells"] > 0
        for sp in frame["source_paths"]:
            assert sp["length_km"] <= min(FROZEN_S0_RATE_KM_DAY_9C * d, 25.0) + 1e-3  # no long jump
            assert sp["distance_check"]["within_nominal_reach"]
    assert [frames[d]["horizon_status"] for d in (0, 3, 7, 13, 14)] == [HORIZON_AS_OF, HORIZON_EVALUATED, HORIZON_EVALUATED, HORIZON_EXPLORATORY, HORIZON_EXPLORATORY]
    # Overlap combines (two farms ~5 km apart add up), but a duplicate farm never counts twice.
    dup = build_spatial_timeline(sources=sources + [_source(4, 6.20, 80.30)], disease_display=LSD, disease_code="LSD", as_of=TODAY,
                                 horizon_days=0, scope=TimelineScope("district", galle))
    assert max(_decoded_scores(dup["frames"][0]["risk_field"]["raster"]).values()) >= max(_decoded_scores(day0["risk_field"]["raster"]).values())


def test_district_and_national_views_draw_the_same_risk_inside_the_district():
    """Cross-page consistency: the same sources give the same day-d risk cells
    inside the district in My Area (district scope) and the Outbreak Map on
    every day before the first modelled new outbreak in the district (from
    then My Area adds it and hands the front over; the Outbreak Map never does)."""
    from shapely.geometry import Point as _Point
    from components.geospatial_tracking.services.spatial_timeline.risk_raster import GRID_SOUTH, GRID_STEP_DEG, GRID_WEST
    galle = find_district("Galle")
    sources = [_source(1, 6.20, 80.30), _source(3, *MATARA_A)]
    kwargs = dict(sources=sources, disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=7)
    district = build_spatial_timeline(**kwargs, scope=TimelineScope("district", galle))
    national = build_spatial_timeline(**kwargs, scope=TimelineScope("national"))
    assert national["possible_new_cases"] == []
    first_new = min((p["seed_day"] for p in district["possible_new_cases"]), default=8)
    for d in sorted({0, *range(0, min(first_new, 8))}):
        a, b = _decoded_scores(district["frames"][d]["risk_field"]["raster"]), _decoded_scores(national["frames"][d]["risk_field"]["raster"])
        inside = [k for k in a if galle.geometry.contains(_Point(GRID_WEST + (k[0] + 0.5) * GRID_STEP_DEG, GRID_SOUTH + (k[1] + 0.5) * GRID_STEP_DEG))]
        assert len(inside) > 20
        assert all(abs(a[k] - b.get(k, 0.0)) <= 0.005 for k in inside)


def test_a_source_up_to_the_model_reach_outside_the_district_is_kept():
    from components.geospatial_tracking.services.spatial_timeline.engine import max_influence_distance_km
    from components.geospatial_tracking.services.spatial_timeline.service import district_relevant_sources
    from components.geospatial_tracking.services.spatial_timeline.districts import distance_to_district_km
    galle = find_district("Galle")
    lat, lon = 6.05, 80.52
    candidates = [_source(i, lat + 0.02 * i, lon + 0.08 * i) for i in range(1, 6)]
    kept, dropped = district_relevant_sources(candidates, TimelineScope("district", galle), 14)
    for source in candidates:
        km = distance_to_district_km(galle, source.latitude, source.longitude)
        assert (source in kept) == (km <= max_influence_distance_km(14))
    assert any(25 < distance_to_district_km(galle, s.latitude, s.longitude) <= max_influence_distance_km(14) for s in kept)


# New outbreaks in the vet's district (My Area Future Impact, district view) --
def _outside_upwind(district, bearing_out, km_beyond):
    """A FICTIONAL point `km_beyond` km outside the district, reached by
    walking from its centroid along `bearing_out`."""
    from shapely.geometry import Point as _P
    c = district.geometry.representative_point()
    step = 0.5
    km = 0.0
    lon, lat = c.x, c.y
    while district.geometry.contains(_P(lon, lat)):
        km += step
        lon, lat = _offset(c.y, c.x, bearing_out, km)
    return _offset(lat, lon, bearing_out, km_beyond)[::-1]


def _entries(body, source_id):
    return [next(p for p in f["source_paths"] if p["source_id"] == source_id) for f in body["frames"]]


def test_an_outbreak_inside_the_district_becomes_a_new_outbreak_where_it_first_moves():
    from shapely.geometry import Point as _P
    kandy = find_district("Kandy")
    case = _source(1, *KANDY_A)
    body = build_spatial_timeline(sources=[case], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                  scope=TimelineScope("district", kandy), wind_lookup=_steady(90.0))
    [p] = body["possible_new_cases"]
    parent = _entries(body, case.source_id)
    assert p["seed_day"] == 1 and p["arrival"] == "FIRST_MOVE_INSIDE_DISTRICT" and p["triggered_by"] == [case.source_id]
    assert [p["longitude"], p["latitude"]] == parent[1]["front"]  # where the front stands on Day 1
    assert kandy.geometry.contains(_P(p["longitude"], p["latitude"]))
    assert p["farm_id"] is None and 0 < p["seed_score"] <= 1.0
    # The existing outbreak's path stops at the hand-over point; the new one moves on from the next day.
    for day in range(1, 15):
        assert parent[day]["front"] == parent[1]["front"] and parent[day]["handed_over_to"] == p["id"]
    new = [next((q for q in f["source_paths"] if q["source_id"] == p["id"]), None) for f in body["frames"]]
    assert new[0] is None and new[1]["geometry"] is None and new[2]["geometry"] is not None
    # Kernels: the new outbreak from its day, weighted by its seed score; the old spine frozen after it.
    for frame in body["frames"]:
        kernels = {k["source_id"]: k for k in frame["risk_field"]["kernels"]}
        assert (p["id"] in kernels) == (frame["day"] >= 1) == (p["id"] in frame["possible_new_case_ids"])
        if frame["day"] >= 2:
            assert kernels[case.source_id]["handed_over_at_day"] == 1
            assert kernels[case.source_id]["spine"][-1][:2] == [round(v, 6) for v in parent[1]["front"]]
            assert kernels[p["id"]]["weight"] == p["seed_score"]


def test_an_outbreak_outside_starts_a_new_outbreak_on_the_day_it_arrives():
    from shapely.geometry import Point as _P
    kandy = find_district("Kandy")
    outside = _source(2, *_outside_upwind(kandy, 270.0, 6.0))  # 6 km west of the district, wind blowing east
    assert not kandy.geometry.contains(_P(outside.longitude, outside.latitude))
    body = build_spatial_timeline(sources=[outside], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                  scope=TimelineScope("district", kandy), wind_lookup=_steady(90.0))
    [p] = body["possible_new_cases"]
    parent = _entries(body, outside.source_id)
    arrival = next(d for d in range(1, 15) if kandy.geometry.contains(_P(*parent[d]["front"])))
    assert p["seed_day"] == arrival > 1 and p["arrival"] == "ARRIVAL_FROM_OUTSIDE_THE_DISTRICT"
    for day in range(1, arrival):
        assert "handed_over_to" not in parent[day]  # still travelling: never shown as arrived
    new = [next((q for q in f["source_paths"] if q["source_id"] == p["id"]), None) for f in body["frames"]]
    assert all(entry is None for entry in new[:arrival])
    assert new[arrival]["geometry"] is None  # appears on its day ...
    assert arrival == 14 or new[arrival + 1]["geometry"] is not None  # ... and moves from the next


def test_no_movement_no_new_outbreak_and_none_in_the_national_view():
    kandy = find_district("Kandy")
    case = _source(1, *KANDY_A)
    still = build_spatial_timeline(sources=[case], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                   scope=TimelineScope("district", kandy), wind_lookup=None)
    if not still["source_paths"]:  # an isolated case with no direction does not move
        assert still["possible_new_cases"] == []
    national = build_spatial_timeline(sources=[case], disease_display=LSD, disease_code="LSD", as_of=TODAY, horizon_days=14,
                                      scope=TimelineScope("national"), wind_lookup=_steady(90.0))
    assert national["possible_new_cases"] == []
    assert all("handed_over_at_day" not in k for f in national["frames"] for k in f["risk_field"]["kernels"])
    assert all("handed_over_to" not in q for f in national["frames"] for q in f["source_paths"])

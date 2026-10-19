"""P0 regressions: UTC -> Asia/Colombo dates, source-anchored direction,
national vs district source selection, outside-district relevance, clinical
authorisation/privacy and source de-duplication for the spatial timeline.

Every farm, case, coordinate and identity below is a FICTIONAL TEST FIXTURE
held in memory behind the real `MongoOperationalDataPort`; nothing here reads
or writes any real database.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date

import pyproj
import pytest
from shapely.geometry import Point

from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort, host_timestamp_text
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import ACTIVE_SOURCE_WINDOW_DAYS_10A
from components.geospatial_tracking.services.integration.nominal_reach_9c import FROZEN_S0_RATE_KM_DAY_9C
from components.geospatial_tracking.services.model_development.candidate_registry_7c import FROZEN_KERNEL_SCALE_KM
from components.geospatial_tracking.services.model_development.heldout_protocol_7d import SELECTED_CANDIDATE_ID
from components.geospatial_tracking.services.model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from components.geospatial_tracking.services.operational.national_cases import record_key
from components.geospatial_tracking.services.spatial_timeline.districts import distance_to_district_km, find_district
from components.geospatial_tracking.services.spatial_timeline.engine import TimelineScope, build_spatial_timeline
from components.geospatial_tracking.services.spatial_timeline.sources import (
    DETAIL_AUTHORISED_FARM,
    DETAIL_PRIVACY_REDUCED,
    OperationalCaseRecord,
    OperationalFarmLocation,
    TimelineSource,
    collect_eligible_operational_sources,
)
from components.geospatial_tracking.services.sri_lanka_time import sri_lanka_date
from components.geospatial_tracking.api.spatial_timeline_router_factory import create_spatial_timeline_router
from components.geospatial_tracking.domain.operational_models import AuthenticatedVetContext
from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document

LSD = "Lumpy skin disease"
VET = AuthenticatedVetContext(email="vet@example.com", role="vet")
_GEOD = pyproj.Geod(ellps="WGS84")

# Fictional farm positions.
MATARA_1 = (5.948, 80.548)
MATARA_2 = (5.950, 80.562)  # ~1.56 km east of MATARA_1
MATARA_INLAND = (6.05, 80.52)
KANDY = (7.29, 80.63)  # > 100 km from Matara


class _NoHistory:
    def eligible_sources(self, **_):
        return []


class _AuthorisedOnlyPort:
    """A port WITHOUT a national case reader (older host adapters)."""

    def __init__(self, inner: MongoOperationalDataPort) -> None:
        self._inner = inner

    def __getattr__(self, name):
        if name == "get_national_case_documents":
            raise AttributeError(name)
        return getattr(self._inner, name)


def _farm(position, district, **extra):
    return make_farm_document(latitude=position[0], longitude=position[1], location_district=district,
                              assigned_vet_emails=extra.pop("assigned", []), **extra)


def _case(farm, verified_at, **extra):
    return make_diagnostic_case_document(farm_id=str(farm["_id"]), disease_name=extra.pop("disease_name", "Lumpy Skin Disease"),
                                         verified=extra.pop("verified", True), verified_at=verified_at, **extra)


def _client(vet_doc, farms, cases, *, port_wrapper=None):
    port = MongoOperationalDataPort(FakeCollection([vet_doc]), FakeCollection(farms), FakeCollection(cases))
    if port_wrapper is not None:
        port = port_wrapper(port)
    app = FastAPI()
    app.include_router(create_spatial_timeline_router(
        get_authenticated_vet_context=lambda: VET,
        get_operational_data_port=lambda: port,
        get_historical_source_reader=lambda: _NoHistory(),
        snapshot_store=SnapshotStore10B(ttl_seconds=600.0),
    ))
    return TestClient(app)


def _get(client, as_of, **params):
    return client.get("/api/geospatial/spatial-timeline", params={"disease": "lsd", "as_of": as_of, **params})


def _source(i, lat, lon):
    return TimelineSource(source_id=f"TEST-FICTIONAL-{i}", record_domain="OPERATIONAL", disease=LSD, latitude=lat, longitude=lon,
                          observation_date="2026-10-13", provenance="TEST_FIXTURE_FICTIONAL", member_record_ids=(f"case-{i}",))


def _corridor_count(body):
    return sum(len(frame["source_corridors"]) for frame in body["frames"])


# -- frozen parameters are untouched ---------------------------------------------------------
def test_frozen_scientific_parameters_are_unchanged():
    assert SELECTED_CANDIDATE_ID == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"
    assert FROZEN_KERNEL_SCALE_KM == 25.0
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM == 25.0
    assert ACTIVE_SOURCE_WINDOW_DAYS_10A == 14
    assert FROZEN_S0_RATE_KM_DAY_9C == pytest.approx(3.946421443154751)


# -- 1. UTC -> Sri Lanka calendar boundary ----------------------------------------------------
@pytest.mark.parametrize("raw, expected", [
    ("2026-08-30 18:29:59", date(2026, 8, 30)),        # 23:59:59 in Colombo
    ("2026-08-30 18:30:00", date(2026, 8, 31)),        # 00:00:00 next day in Colombo
    ("2026-08-30 20:05:46", date(2026, 8, 31)),        # legacy naive UTC text
    ("2026-08-30T20:05:46+00:00", date(2026, 8, 31)),  # explicit UTC
    ("2026-08-31T01:35:46+05:30", date(2026, 8, 31)),  # explicit Colombo offset, same instant
    ("2026-08-31T18:28:38.880000+00:00", date(2026, 8, 31)),  # 23:58 Colombo
    ("2026-08-31T18:32:38.580000+00:00", date(2026, 9, 1)),   # 00:02 Colombo
    ("2026-08-30", date(2026, 8, 30)),                 # a calendar date is never shifted
    (None, None), ("", None), ("not a date", None),
])
def test_sri_lanka_date_of_a_verification_instant(raw, expected):
    assert sri_lanka_date(raw) == expected


def test_host_boundary_conversion_is_never_applied_twice():
    for raw in ["2026-08-30 20:05:46", "2026-08-30T20:05:46+00:00", "2026-08-31T01:35:46+05:30"]:
        once = host_timestamp_text(raw)
        assert host_timestamp_text(once) == once
        assert sri_lanka_date(once) == sri_lanka_date(raw) == date(2026, 8, 31)


def test_late_evening_utc_verification_belongs_to_the_next_sri_lanka_day():
    farm = _farm(MATARA_INLAND, "Matara")
    client = _client(make_vet_document(district="Matara"), [farm], [_case(farm, "2026-10-12 20:00:00")])  # 01:30 on 13 Oct in Colombo
    before = _get(client, "2026-10-12").json()
    assert before["status"] == "NO_ELIGIBLE_SOURCES"
    assert before["source_exclusions"] == {"operational:VERIFIED_AFTER_AS_OF_DATE": 1}
    after = _get(client, "2026-10-13").json()
    assert after["status"] == "OK" and after["sources"][0]["observation_date"] == "2026-10-13"


def test_window_start_uses_the_sri_lanka_calendar_date():
    farm_a, farm_b = _farm(MATARA_INLAND, "Matara"), _farm((6.10, 80.48), "Matara")
    cases = [_case(farm_a, "2026-09-28 18:29:59"),  # 28 Sep 23:59:59 Colombo -> before the 29 Sep window start
             _case(farm_b, "2026-09-28 18:30:00")]  # 29 Sep 00:00:00 Colombo -> inside
    body = _get(_client(make_vet_document(district="Matara"), [farm_a, farm_b], cases), "2026-10-13").json()
    assert body["time_window"]["source_window_start"] == "2026-09-29"
    assert [s["observation_date"] for s in body["sources"]] == ["2026-09-29"]
    assert body["source_exclusions"] == {"operational:OUTSIDE_ACTIVE_SOURCE_WINDOW": 1}


# -- 2. one-source vs multi-source direction -------------------------------------------------
def test_matara_style_replay_has_no_direction_until_a_second_local_source_exists():
    """Farm 1 verified 13:00 Colombo on 30 Aug; farm 2 verified 01:35 Colombo on
    31 Aug (20:05 UTC on 30 Aug). On 30 Aug only farm 1 exists -> no arrow."""
    farm_1, farm_2 = _farm(MATARA_1, "Matara"), _farm(MATARA_2, "Matara")
    cases = [_case(farm_1, "2026-08-30 07:30:00"), _case(farm_2, "2026-08-30 20:05:46")]
    client = _client(make_vet_document(district="Matara"), [farm_1, farm_2], cases)
    aug_30 = _get(client, "2026-08-30").json()
    assert len(aug_30["sources"]) == 1
    assert aug_30["source_directions"][0]["direction_status"] == "INDETERMINATE_NO_DIRECTIONAL_MASS"
    assert aug_30["source_directions"][0]["direction_input_source_count"] == 0
    assert _corridor_count(aug_30) == 0
    aug_31 = _get(client, "2026-08-31").json()
    assert len(aug_31["sources"]) == 2
    assert all(d["direction_status"] == "GEOMETRIC_TENDENCY_AVAILABLE" and d["direction_input_source_count"] == 1
               for d in aug_31["source_directions"])


def test_a_source_beyond_the_local_domain_never_creates_a_direction():
    matara, kandy = _source(1, *MATARA_INLAND), _source(2, *KANDY)
    body = build_spatial_timeline(sources=[matara, kandy], disease_display=LSD, disease_code="LSD", as_of=date(2026, 10, 13),
                                  horizon_days=14, scope=TimelineScope("national"))
    assert all(d["bearing_deg"] is None and d["direction_status"] == "INDETERMINATE_NO_DIRECTIONAL_MASS" for d in body["source_directions"])
    assert _corridor_count(body) == 0
    # The frozen C0 surface itself is unchanged: every cell still sums both sources.
    for cell in body["cells"][::9]:
        lon, lat = cell["centroid"]["longitude"], cell["centroid"]["latitude"]
        expected = sum(math.exp(-(_GEOD.inv(s.longitude, s.latitude, lon, lat)[2] / 1000.0) / 25.0) for s in (matara, kandy))
        assert cell["raw_c0_score"] == pytest.approx(expected, rel=1e-9)


def test_nearby_sources_keep_the_frozen_8b3_bearing():
    a, b = _source(1, *MATARA_INLAND), _source(2, 6.10, 80.48)  # ~7 km apart
    body = build_spatial_timeline(sources=[a, b], disease_display=LSD, disease_code="LSD", as_of=date(2026, 10, 13),
                                  horizon_days=1, scope=TimelineScope("national"))
    direction_a = next(d for d in body["source_directions"] if d["source_id"] == a.source_id)
    away_from_b = (_GEOD.inv(b.longitude, b.latitude, a.longitude, a.latitude)[1] + 180.0) % 360.0
    assert direction_a["bearing_deg"] == pytest.approx(away_from_b, abs=0.5)
    assert direction_a["direction_neighbourhood_km"] == PRIMARY_LOCAL_EVALUATION_DISTANCE_KM


# -- 3/4. national vs district selection, outside-district relevance -------------------------
def _galle_point_near_matara():
    """A deterministic point inside Galle district, 5-20 km from the Matara boundary."""
    galle, matara = find_district("Galle"), find_district("Matara")
    minx, miny, maxx, maxy = galle.geometry.bounds
    steps = 60
    for i in range(steps):
        for j in range(steps):
            lon = minx + (maxx - minx) * (i + 0.5) / steps
            lat = miny + (maxy - miny) * (j + 0.5) / steps
            if galle.geometry.contains(Point(lon, lat)) and 5.0 < distance_to_district_km(matara, lat, lon) < 20.0:
                return lat, lon
    raise AssertionError("no fixture point found")


def test_distance_to_district_matches_geodesic_distance():
    matara = find_district("Matara")
    assert distance_to_district_km(matara, *MATARA_INLAND) == 0.0
    lat, lon = _galle_point_near_matara()
    boundary = matara.geometry.boundary
    nearest = boundary.interpolate(boundary.project(Point(lon, lat)))
    geodesic_km = _GEOD.inv(lon, lat, nearest.x, nearest.y)[2] / 1000.0
    assert distance_to_district_km(matara, lat, lon) == pytest.approx(geodesic_km, rel=0.02)


def test_national_scope_is_not_limited_to_the_vets_district():
    own = _farm(MATARA_INLAND, "Matara")
    external = _farm(KANDY, "7.29, 80.63 (Kandy District)")
    cases = [_case(own, "2026-10-10 09:00:00"), _case(external, "2026-10-10 09:00:00")]
    client = _client(make_vet_document(district="Matara"), [own, external], cases)
    national = _get(client, "2026-10-13", scope="national").json()
    assert len(national["sources"]) == 2
    assert national["source_selection"]["operational_pool"] == "ALL_VET_VERIFIED_ADRS_CASES_NATIONWIDE"
    assert national["source_selection"]["scope_rule"] == "ALL_ELIGIBLE_SOURCES"
    district = _get(client, "2026-10-13").json()
    assert [s["farm_id"] for s in district["sources"]] == [str(own["_id"])]
    assert district["source_exclusions"] == {"operational:BEYOND_MODEL_REACH_OF_DISTRICT": 1}
    # The cut-off is the model's own largest 14-day risk reach (path + position uncertainty), not a fixed 25 km.
    from components.geospatial_tracking.services.spatial_timeline.engine import max_influence_distance_km
    assert district["source_selection"]["district_relevance_distance_km"] == pytest.approx(max_influence_distance_km(14), abs=1e-3)
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM < district["source_selection"]["district_relevance_distance_km"] < 50


def test_district_analysis_includes_a_relevant_outside_district_source():
    own = _farm(MATARA_INLAND, "Matara")
    near_border = _farm(_galle_point_near_matara(), "Galle")
    cases = [_case(own, "2026-10-10 09:00:00"), _case(near_border, "2026-10-11 09:00:00")]
    body = _get(_client(make_vet_document(district="Matara"), [own, near_border], cases), "2026-10-13").json()
    assert body["scope"]["district"] == "Matara"
    assert len(body["sources"]) == 2
    external = next(s for s in body["sources"] if s["detail_access"] == DETAIL_PRIVACY_REDUCED)
    assert external["farm_id"] is None
    assert body["district_summaries"][0]["n_sources_in_district"] == 1  # the outside source is counted as outside


# -- 5. clinical authorisation and privacy ---------------------------------------------------
def test_outside_sources_expose_no_farm_or_case_identity():
    own = _farm(MATARA_INLAND, "Matara")
    external = _farm(KANDY, "Kandy")
    external_case = _case(external, "2026-10-10 09:00:00", clinical_notes="FICTIONAL NOTE", farm_name="FICTIONAL FARM")
    body = _get(_client(make_vet_document(district="Matara"), [own, external], [_case(own, "2026-10-10 09:00:00"), external_case]),
                "2026-10-13", scope="national").json()
    by_access = {s["detail_access"]: s for s in body["sources"]}
    authorised, outside = by_access[DETAIL_AUTHORISED_FARM], by_access[DETAIL_PRIVACY_REDUCED]
    assert authorised["farm_id"] == str(own["_id"])
    assert outside["farm_id"] is None
    assert outside["member_record_ids"] == [record_key(str(external_case["_id"]))]
    raw = json.dumps(body)
    for secret in (str(external["_id"]), str(external_case["_id"]), "FICTIONAL NOTE", "FICTIONAL FARM"):
        assert secret not in raw
    assert all(str(own["_id"]) not in s["source_id"] for s in body["sources"])  # source ids are one-way keys


def test_unverified_cases_are_never_promoted_and_evidence_stays_vet_verified():
    external = _farm(KANDY, "Kandy")
    cases = [_case(external, None, verified=False)]
    body = _get(_client(make_vet_document(district="Matara"), [external], cases), "2026-10-13", scope="national").json()
    assert body["status"] == "NO_ELIGIBLE_SOURCES"
    assert body["source_exclusions"] == {"operational:NOT_VET_VERIFIED": 1}
    assert body["source_selection"]["operational_evidence"] == "VET_VERIFIED_DIAGNOSTIC_CASE_NOT_OFFICIAL_OUTBREAK_CONFIRMATION"
    assert "OPERATIONAL_SOURCES_ARE_VET_VERIFIED_DIAGNOSES_NOT_OFFICIAL_OUTBREAK_CONFIRMATIONS" in body["limitations"]


def test_district_authorisation_is_unchanged_by_the_national_source_pool():
    own = _farm(MATARA_INLAND, "Matara")
    client = _client(make_vet_document(district="Matara"), [own], [_case(own, "2026-10-10 09:00:00")])
    response = _get(client, "2026-10-13", district="Kandy")
    assert response.status_code == 403 and response.json()["detail"]["status"] == "DISTRICT_NOT_AUTHORISED"


def test_fmd_never_reuses_the_lsd_reach_or_model():
    own = _farm(MATARA_INLAND, "Matara")
    body = _get(_client(make_vet_document(district="Matara"), [own], [_case(own, "2026-10-10 09:00:00", disease_name="Foot and Mouth Disease")]),
                "2026-10-13", disease="fmd").json()
    assert body["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"
    assert body["cells"] == [] and body["risk_zones"]["features"] == [] and body["source_directions"] == []
    assert all(f["reach"]["nominal_reach_km"] is None and f["reach"]["rate_km_day"] is None for f in body["frames"])
    assert body["model"] == {"risk": None, "direction": None, "reach": None}


def test_ocean_cells_never_enter_land_tier_statistics():
    coastal = _source(1, 5.95, 80.55)  # fictional point near the south coast: many offshore cells
    body = build_spatial_timeline(sources=[coastal], disease_display=LSD, disease_code="LSD", as_of=date(2026, 10, 13),
                                  horizon_days=1, scope=TimelineScope("national"))
    offshore = [c for c in body["cells"] if not c["on_land"]]
    assert offshore and all(c["tier"] is None and c["tier_status"] == "OFF_LAND_NOT_TIERED" and c["geometry"] is None for c in offshore)
    land = sorted(c["raw_c0_score"] for c in body["cells"] if c["on_land"])
    assert body["tier_thresholds"]["q1"] >= land[0] and body["tier_thresholds"]["q3"] <= land[-1]
    assert all(c["geometry"] is not None for c in body["cells"] if c["tier"] is not None)


def test_disease_specific_eligibility_is_preserved():
    own = _farm(MATARA_INLAND, "Matara")
    external = _farm(KANDY, "Kandy")
    cases = [_case(own, "2026-10-10 09:00:00", disease_name="Foot and Mouth Disease"),
             _case(external, "2026-10-10 09:00:00", disease_name="Mastitis")]
    body = _get(_client(make_vet_document(district="Matara"), [own, external], cases), "2026-10-13", scope="national").json()
    assert body["status"] == "NO_ELIGIBLE_SOURCES"
    assert body["source_exclusions"] == {"operational:WRONG_DISEASE": 2}


def test_port_without_a_national_reader_falls_back_explicitly():
    own = _farm(MATARA_INLAND, "Matara")
    external = _farm(KANDY, "Kandy")
    cases = [_case(own, "2026-10-10 09:00:00"), _case(external, "2026-10-10 09:00:00")]
    body = _get(_client(make_vet_document(district="Matara"), [own, external], cases, port_wrapper=_AuthorisedOnlyPort),
                "2026-10-13", scope="national").json()
    assert body["source_statuses"]["operational"] == "AUTHORISED_FARMS_ONLY_NATIONAL_CASE_READER_UNAVAILABLE"
    assert body["source_selection"]["operational_pool"] == "AUTHORISED_FARMS_ONLY_NATIONAL_CASE_READER_UNAVAILABLE"
    assert [s["farm_id"] for s in body["sources"]] == [str(own["_id"])]


# -- 6. source de-duplication ------------------------------------------------------------------
def test_repeat_reports_on_one_outside_farm_collapse_to_one_source():
    external = _farm(KANDY, "Kandy")
    cases = [_case(external, f"2026-10-1{d} 09:00:00") for d in (0, 1, 2)]
    body = _get(_client(make_vet_document(district="Matara"), [external], cases), "2026-10-13", scope="national").json()
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["member_count"] == 3 and source["observation_date"] == "2026-10-12"
    assert body["source_exclusions"] == {"operational:MERGED_DUPLICATE_SAME_FARM_SAME_DISEASE": 2}


def test_a_case_listed_twice_is_counted_once():
    farm = OperationalFarmLocation(farm_id="F-FICTIONAL", latitude=MATARA_INLAND[0], longitude=MATARA_INLAND[1], location_valid=True)
    case = OperationalCaseRecord(case_id="C-FICTIONAL", farm_id="F-FICTIONAL", disease="LSD", verified=True,
                                 verification_time="2026-10-10T09:00:00+00:00")
    sources, exclusions = collect_eligible_operational_sources(
        [case, case], {"F-FICTIONAL": farm}, disease_code="LSD", disease_display=LSD, as_of=date(2026, 10, 13),
        window_days=14, authorised_farms=frozenset({"F-FICTIONAL"}))
    assert len(sources) == 1 and sources[0].member_record_ids == ("C-FICTIONAL",)
    assert exclusions == Counter({"DUPLICATE_CASE_RECORD": 1})


def test_case_numbers_only_for_the_vets_own_farms():
    """Task 4 cards: the vet sees the real case number of their own farms'
    sources (latest first); another vet's source never carries one."""
    own = OperationalFarmLocation(farm_id="F-OWN", latitude=MATARA_INLAND[0], longitude=MATARA_INLAND[1], location_valid=True)
    other = OperationalFarmLocation(farm_id="F-OTHER", latitude=KANDY[0], longitude=KANDY[1], location_valid=True)
    cases = [
        OperationalCaseRecord(case_id="C1", farm_id="F-OWN", disease="LSD", verified=True, verification_time="2026-10-09T09:00:00+00:00", case_number="REC-FICTIONAL-1"),
        OperationalCaseRecord(case_id="C2", farm_id="F-OWN", disease="LSD", verified=True, verification_time="2026-10-11T09:00:00+00:00", case_number="REC-FICTIONAL-2"),
        OperationalCaseRecord(case_id="C3", farm_id="F-OTHER", disease="LSD", verified=True, verification_time="2026-10-11T09:00:00+00:00", case_number="REC-FICTIONAL-3"),
    ]
    sources, _ = collect_eligible_operational_sources(
        cases, {"F-OWN": own, "F-OTHER": other}, disease_code="LSD", disease_display=LSD, as_of=date(2026, 10, 13),
        window_days=14, authorised_farms=frozenset({"F-OWN"}))
    by_farm = {s.farm_id: s for s in sources}
    assert by_farm["F-OWN"].case_refs == ("REC-FICTIONAL-2", "REC-FICTIONAL-1")
    external = next(s for s in sources if s.farm_id is None)
    assert external.case_refs == () and external.as_dict()["case_refs"] == []
    assert "REC-FICTIONAL-3" not in json.dumps([s.as_dict() for s in sources])

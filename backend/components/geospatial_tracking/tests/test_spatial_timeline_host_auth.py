"""Phase 5: the spatial-timeline API behind the HOST's real JWT dependency.

`test_spatial_timeline.py` injects an already-resolved vet context. These
tests instead wire the router to `main.get_authenticated_vet_context` (the
shared ADRS Bearer/JWT contract) and send real signed tokens, so missing,
forged, expired, non-vet and district-manipulation requests are exercised
end to end.

Isolation: `isolated_main_module` supplies an unreachable placeholder
database and a random throwaway secret generated inside the test process
(never the team's secret); every farm/case/vet is an in-memory FICTIONAL
fixture. No shared database is contacted and no shared configuration is
read or changed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.spatial_timeline_router_factory import create_spatial_timeline_router
from components.geospatial_tracking.repositories.host_operational_adapter import MongoOperationalDataPort
from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

from ._main_import import isolated_main_module
from ._operational_fakes import FakeCollection, make_diagnostic_case_document, make_farm_document, make_vet_document

AS_OF = "2026-10-13"
URL = "/api/geospatial/spatial-timeline"


class _NoHistoricalSources:
    def eligible_sources(self, *, disease, as_of, window_days, country):
        return []


def _fictional_world():
    """Two FICTIONAL vets: Galle (no Matara farm assigned) and Matara."""
    galle_vet = make_vet_document(email="galle.vet@example.com", district="Galle")
    matara_vet = make_vet_document(email="matara.vet@example.com", district="Matara")
    matara_farm = make_farm_document(latitude=6.05, longitude=80.52, location_district="Matara")
    galle_farm = make_farm_document(latitude=6.10, longitude=80.25, location_district="Galle")
    cases = [
        make_diagnostic_case_document(farm_id=str(matara_farm["_id"]), disease_name="Lumpy Skin Disease", verified=True,
                                      verified_at="2026-10-10 09:00:00"),
        make_diagnostic_case_document(farm_id=str(galle_farm["_id"]), disease_name="Lumpy Skin Disease", verified=True,
                                      verified_at="2026-10-11 09:00:00"),
    ]
    return [galle_vet, matara_vet], [matara_farm, galle_farm], cases


VETS, FARMS, CASES = _fictional_world()
MATARA_FARM_ID = str(FARMS[0]["_id"])
GALLE_FARM_ID = str(FARMS[1]["_id"])


def _host_vet_context_dependency(main_module):
    """The host's own JWT -> vet-context dependency. Module-level on some host
    versions, nested inside `create_app()` on others (group main), so it is
    taken from a mounted Geospatial route of the REAL host app when needed."""
    direct = getattr(main_module, "get_authenticated_vet_context", None)
    if direct is not None:
        return direct

    def walk(routes):
        for route in routes:
            original = getattr(route, "original_router", None)
            if original is not None:
                yield from walk(original.routes)
            dependant = getattr(route, "dependant", None)
            if dependant is not None:
                for dependency in dependant.dependencies:
                    if getattr(dependency.call, "__name__", "") == "get_authenticated_vet_context":
                        yield dependency.call

    found = next(walk(main_module.app.routes), None)
    assert found is not None, "host app mounts no Geospatial route using get_authenticated_vet_context"
    return found


@pytest.fixture()
def host(monkeypatch):
    with isolated_main_module(monkeypatch) as main_module:
        port = MongoOperationalDataPort(FakeCollection(VETS), FakeCollection(FARMS), FakeCollection(CASES))
        app = FastAPI()
        app.include_router(create_spatial_timeline_router(
            get_authenticated_vet_context=_host_vet_context_dependency(main_module),
            get_operational_data_port=lambda: port,
            get_historical_source_reader=lambda: _NoHistoricalSources(),
            snapshot_store=SnapshotStore10B(ttl_seconds=600.0),
        ))
        yield TestClient(app), main_module


def _token(main_module, *, sub, role=None, secret=None, expires_in=timedelta(hours=1)):
    claims = {"sub": sub, "exp": datetime.now(timezone.utc) + expires_in}
    if role is not None:
        claims["role"] = role
    return jwt.encode(claims, secret or main_module.JWT_SECRET, algorithm=main_module.JWT_ALGORITHM)


def _get(client, token=None, **params):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(URL, params={"disease": "lsd", "as_of": AS_OF, **params}, headers=headers)


def test_missing_and_malformed_authorization_is_401(host):
    client, _ = host
    assert _get(client).status_code == 401
    assert client.get(URL, params={"disease": "lsd"}, headers={"Authorization": "Basic abc"}).status_code == 401
    assert _get(client, token="not-a-jwt").status_code == 401


def test_forged_and_expired_tokens_are_401(host):
    client, main_module = host
    forged = _token(main_module, sub="galle.vet@example.com", role="vet", secret="a-different-throwaway-secret-for-forgery-test")
    assert _get(client, token=forged).status_code == 401
    expired = _token(main_module, sub="galle.vet@example.com", role="vet", expires_in=timedelta(minutes=-5))
    assert _get(client, token=expired).status_code == 401
    no_subject = jwt.encode({"role": "vet"}, main_module.JWT_SECRET, algorithm=main_module.JWT_ALGORITHM)
    assert _get(client, token=no_subject).status_code == 401


def test_farm_tokens_and_other_roles_are_403(host):
    client, main_module = host
    farm_token = _token(main_module, sub="farmer@example.com")  # host farm tokens carry no role claim
    assert _get(client, token=farm_token).status_code == 403
    assert _get(client, token=_token(main_module, sub="x@example.com", role="admin")).status_code == 403


def test_valid_vet_token_gets_only_their_registered_district(host):
    client, main_module = host
    response = _get(client, token=_token(main_module, sub="galle.vet@example.com", role="vet"))
    assert response.status_code == 200
    body = response.json()
    assert body["scope"]["district"] == "Galle"
    assert [summary["district"] for summary in body["district_summaries"]] == ["Galle"]
    # The Matara case is outside the Galle scope: never exposed as a source.
    serialised = response.text
    assert MATARA_FARM_ID not in serialised
    assert GALLE_FARM_ID in serialised


def test_district_manipulation_is_rejected(host):
    client, main_module = host
    galle_token = _token(main_module, sub="galle.vet@example.com", role="vet")
    response = _get(client, token=galle_token, district="Matara")
    assert response.status_code == 403
    assert response.json()["detail"]["status"] == "DISTRICT_NOT_AUTHORISED"
    assert MATARA_FARM_ID not in response.text
    # A token for an e-mail that is not a registered vet resolves no district.
    stranger = _get(client, token=_token(main_module, sub="unknown.vet@example.com", role="vet"))
    assert stranger.status_code in (403, 409)
    assert MATARA_FARM_ID not in stranger.text and GALLE_FARM_ID not in stranger.text


def test_matara_vet_sees_matara_and_not_galle(host):
    client, main_module = host
    response = _get(client, token=_token(main_module, sub="matara.vet@example.com", role="vet"))
    assert response.status_code == 200
    assert response.json()["scope"]["district"] == "Matara"
    assert GALLE_FARM_ID not in response.text

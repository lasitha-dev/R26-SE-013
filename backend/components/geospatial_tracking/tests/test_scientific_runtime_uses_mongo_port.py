"""GEO-MONGODB-NATIVE-INTEGRATION-24B: proves the LIVE scientific HTTP API
(`api/router.py`'s `router`, mounted in `backend/main.py` as
`geospatial_scientific_router`) resolves its repository through whatever
`repositories.provider.create_outbreak_repository()` returns -- and once
the composition root installs the Mongo override (exactly as
`backend/main.py` now does), `/origins` serves data from the Mongo-backed
repository, opening ZERO SQLite connections, with no router/transport code
needing to change.

Uses `FakeSyncCollection` -- no real Mongo driver, no network, and this
test asserts `sqlite3.connect` is never called at all during the request,
which is the sharpest possible proof "ordinary Geospatial API requests
open no SQLite connection" once the override is active."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.router import router
from components.geospatial_tracking.repositories import provider
from components.geospatial_tracking.repositories.mongo_repository import MongoOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality

from ._mongo_repository_fakes import FakeSyncCollection


@pytest.fixture
def mongo_backed_client(monkeypatch):
    """Seeds a fake-Mongo-collection-backed repository with ONE synthetic
    historical record for a country that never appears in the real
    development SQLite corpus (`TESTONLY_MONGO_COUNTRY`), installs it as
    the process-wide provider override, and asserts `sqlite3.connect` is
    never invoked for the duration of the test."""
    collections = {
        "animal_reports": FakeSyncCollection(),
        "outbreak_episodes": FakeSyncCollection(),
        "historical_outbreak_records": FakeSyncCollection(),
        "prediction_runs": FakeSyncCollection(),
    }
    seed_repo = MongoOutbreakRepository(
        collections["animal_reports"], collections["outbreak_episodes"],
        collections["historical_outbreak_records"], collections["prediction_runs"],
    )
    from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord

    seed_repo.add_historical_record(
        HistoricalOutbreakRecord(
            source_record_id="TESTONLY_MONGO_SOURCE_1",
            country="TESTONLY_MONGO_COUNTRY",
            disease="Lumpy skin disease",
            proxy_availability_date="2026-01-01",
            proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
            latitude=1.23,
            longitude=4.56,
            model_candidate=True,
        )
    )

    def _factory() -> MongoOutbreakRepository:
        return MongoOutbreakRepository(
            collections["animal_reports"], collections["outbreak_episodes"],
            collections["historical_outbreak_records"], collections["prediction_runs"],
        )

    def _forbidden_sqlite_connect(*args, **kwargs):
        raise AssertionError(
            "sqlite3.connect was called while the Mongo provider override was "
            "active -- the runtime scientific API must never open SQLite once "
            "the composition root has redirected create_outbreak_repository()."
        )

    monkeypatch.setattr(sqlite3, "connect", _forbidden_sqlite_connect)
    provider.set_repository_factory_override(_factory)
    try:
        app = FastAPI()
        app.include_router(router)
        yield TestClient(app)
    finally:
        provider.set_repository_factory_override(None)


def test_origins_route_serves_data_from_the_mongo_backed_repository(mongo_backed_client):
    r = mongo_backed_client.get("/api/geospatial/origins")
    assert r.status_code == 200
    body = r.json()
    assert body["n_origins"] == 1
    assert body["origins"][0]["country"] == "TESTONLY_MONGO_COUNTRY"
    assert body["origins"][0]["forecast_origin_id"] == "ORIGIN:TESTONLY_MONGO_COUNTRY:2026-01-01"


def test_origins_route_country_filter_against_mongo_backed_repository(mongo_backed_client):
    r = mongo_backed_client.get("/api/geospatial/origins", params={"country": "TESTONLY_MONGO_COUNTRY"})
    assert r.status_code == 200
    assert r.json()["n_origins"] == 1

    r_miss = mongo_backed_client.get("/api/geospatial/origins", params={"country": "SomeOtherCountry"})
    assert r_miss.status_code == 200
    assert r_miss.json()["n_origins"] == 0


def test_trigger_sources_route_serves_data_from_the_mongo_backed_repository(mongo_backed_client):
    r = mongo_backed_client.get(
        "/api/geospatial/origins/ORIGIN:TESTONLY_MONGO_COUNTRY:2026-01-01/trigger-sources"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["n_points"] == 1
    assert body["features"][0]["properties"]["source_id"] == "TESTONLY_MONGO_SOURCE_1"
    assert body["features"][0]["geometry"]["coordinates"] == [4.56, 1.23]

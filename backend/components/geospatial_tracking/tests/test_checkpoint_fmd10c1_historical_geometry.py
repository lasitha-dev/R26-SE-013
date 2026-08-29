"""Checkpoint FMD-10C1: real, OBSERVED historical T0 trigger-source
geometry for Page 1's map markers.

No frozen scientific model is modified anywhere in this file. No
candidate selection, retuning, or new evaluation metric.
`DISEASE_MODEL_READINESS_10A` is verified UNCHANGED (still has no FMD
entry) -- FMD's LSD-shaped `/summary`/`/cells`/`/sources` routes must
stay model-not-ready. Real-DB-dependent tests skip gracefully on a
clean clone (no `data/local/pistes_dev.db`) -- structural/unit tests
never skip.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.router import router
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.application.frozen_fmd_risk_analysis_9 import FMD_DISEASE_NAME_9
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    DISEASE_MODEL_READINESS_10A,
)
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")

_SRI_LANKA = "Sri Lanka"


def _open_repo() -> SQLiteOutbreakRepository:
    return SQLiteOutbreakRepository(_DB_PATH)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestFmd10C1ModelReadinessUnchanged:
    """FMD-10C1 must not touch the LSD-shaped readiness gate at all --
    checked first, before any real-DB test, so a genuine regression here
    fails even on a clean clone."""

    def test_disease_model_readiness_10a_has_no_fmd_entry(self):
        assert FMD_DISEASE_NAME_9 not in DISEASE_MODEL_READINESS_10A


class TestFmd10C1LsdShapedRoutesStillModelNotReady:
    @_skip_no_db
    def test_fmd_summary_still_409(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka FMD origins in dev DB")
        response = _client().get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/summary", params={"disease": "fmd"})
        assert response.status_code == 409
        assert response.json()["detail"]["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

    @_skip_no_db
    def test_fmd_cells_still_409(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka FMD origins in dev DB")
        response = _client().get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/cells", params={"disease": "fmd"})
        assert response.status_code == 409
        assert response.json()["detail"]["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"

    @_skip_no_db
    def test_fmd_sources_still_409(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka FMD origins in dev DB")
        response = _client().get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/sources", params={"disease": "fmd"})
        assert response.status_code == 409
        assert response.json()["detail"]["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"


class TestFmd10C1FmdRiskUnchanged:
    @_skip_no_db
    def test_fmd_risk_still_scores_the_same_frozen_candidate(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka FMD origins in dev DB")
        response = _client().get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/fmd-risk")
        assert response.status_code == 200
        body = response.json()
        assert body["frozen_candidate_id"].startswith("FMD07B:SPATIAL:B0_DISTANCE_ONLY:GAUSSIAN:")
        assert body["threshold"] == 0.05
        assert body["risk_score_semantics"] == "RELATIVE_ORIGIN_LEVEL_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY"


class TestFmd10C1RealHistoricalGeometry:
    """Points 1-5, 11 of the checkpoint's backend-test list."""

    @_skip_no_db
    def test_sri_lanka_fmd_origins_expose_real_coordinate_bearing_points(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        assert origins, "expected real Sri Lanka FMD origins in the dev DB"

        client = _client()
        response = client.get(f"/api/geospatial/origins/{origins[0].forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
        assert response.status_code == 200
        body = response.json()
        assert body["n_points"] >= 1
        assert len(body["features"]) == body["n_points"]

    @_skip_no_db
    def test_every_point_has_finite_valid_lat_lon(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        assert origins

        client = _client()
        for origin in origins:
            response = client.get(f"/api/geospatial/origins/{origin.forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
            assert response.status_code == 200
            for feature in response.json()["features"]:
                lon, lat = feature["geometry"]["coordinates"]
                assert math.isfinite(lon) and math.isfinite(lat)
                assert -180.0 <= lon <= 180.0
                assert -90.0 <= lat <= 90.0

    @_skip_no_db
    def test_every_point_is_traceable_to_a_real_source_and_the_requested_origin(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        assert origins
        origin = origins[0]

        response = _client().get(f"/api/geospatial/origins/{origin.forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
        body = response.json()
        real_trigger_ids = set(origin.trigger_source_ids_at_t0)
        for feature in body["features"]:
            props = feature["properties"]
            assert props["source_id"] in real_trigger_ids
            assert props["forecast_origin_id"] == origin.forecast_origin_id

    @_skip_no_db
    def test_multiple_trigger_sources_are_preserved_as_multiple_real_points(self):
        """FMD Sri Lanka origins are all single-source today, so this
        proves the multi-point path against the wider real FMD corpus
        (the identical code path, disease-neutral) -- never a synthetic
        fixture standing in for a real multi-source origin."""
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
        finally:
            repo.close()
        multi = [o for o in origins if o.trigger_source_count > 1]
        if not multi:
            pytest.skip("no real multi-trigger-source FMD origin in dev DB")
        origin = multi[0]

        response = _client().get(f"/api/geospatial/origins/{origin.forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
        assert response.status_code == 200
        body = response.json()
        assert body["n_points"] == origin.trigger_source_count
        returned_ids = {f["properties"]["source_id"] for f in body["features"]}
        assert returned_ids == set(origin.trigger_source_ids_at_t0)

    @_skip_no_db
    def test_no_synthetic_default_or_centroid_coordinate_is_introduced(self):
        """Every returned coordinate is byte-identical to the real stored
        `HistoricalOutbreakRecord` coordinate for that exact source_id --
        never a country/district centroid or an averaged point."""
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
            origin = origins[0]
            response = _client().get(f"/api/geospatial/origins/{origin.forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
            body = response.json()
            for feature in body["features"]:
                source_id = feature["properties"]["source_id"]
                lon, lat = feature["geometry"]["coordinates"]
                record = repo.get_historical_record(source_id)
                assert record is not None
                assert lon == record.longitude
                assert lat == record.latitude
        finally:
            repo.close()

    @_skip_no_db
    def test_unknown_origin_is_404_never_a_fabricated_empty_result(self):
        response = _client().get("/api/geospatial/origins/ORIGIN:Nowhere:1999-01-01/trigger-sources", params={"disease": "fmd"})
        assert response.status_code == 404
        assert response.json()["detail"]["status"] == "ORIGIN_NOT_FOUND"

    @_skip_no_db
    def test_response_geometry_semantics_never_claims_risk_forecast_or_reach(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        response = _client().get(f"/api/geospatial/origins/{origins[0].forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
        semantics = response.json()["geometry_semantics"]
        # The whole tail after "ONLY_" is a single negated clause -- every
        # forbidden concept below appears only as part of that negation,
        # never asserted as this point's actual meaning.
        assert semantics == (
            "OBSERVED_HISTORICAL_TRIGGER_SOURCE_ONLY_NOT_A_RISK_CELL_FORECAST_POINT_"
            "DISEASE_BOUNDARY_NOMINAL_REACH_OR_TRAJECTORY_POINT"
        )
        assert semantics.startswith("OBSERVED_HISTORICAL_TRIGGER_SOURCE_ONLY_NOT_A_")


class TestFmd10C1LsdNonRegression:
    """LSD's own existing contracts (origins, trigger-sources reused
    disease-neutrally, and the LSD-shaped snapshot routes) are
    unaffected by this checkpoint."""

    @_skip_no_db
    def test_lsd_origins_and_summary_still_work_unchanged(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease="Lumpy skin disease", country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka LSD origins in dev DB")
        client = _client()
        response = client.get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/summary", params={"disease": "lsd"})
        assert response.status_code == 200

    @_skip_no_db
    def test_lsd_can_also_use_the_new_disease_neutral_trigger_sources_route(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease="Lumpy skin disease", country_scope=_SRI_LANKA)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no Sri Lanka LSD origins in dev DB")
        response = _client().get(f"/api/geospatial/origins/{origins[0].forecast_origin_id}/trigger-sources", params={"disease": "lsd"})
        assert response.status_code == 200
        assert response.json()["disease"] == "Lumpy skin disease"


class TestFmd10C1SriLankaScope:
    """Point 11: proves the global FMD corpus cannot leak into the Sri
    Lanka product view, and that a resolved single origin's response
    country can never mismatch the requested scope."""

    @_skip_no_db
    def test_sri_lanka_scoped_origin_listing_is_strictly_smaller_than_global(self):
        repo = _open_repo()
        try:
            global_origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
            sri_lanka_origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        assert len(sri_lanka_origins) < len(global_origins)
        assert all(o.country == _SRI_LANKA for o in sri_lanka_origins)

    @_skip_no_db
    def test_trigger_sources_response_country_matches_the_resolved_origin_never_a_foreign_country(self):
        repo = _open_repo()
        try:
            sri_lanka_origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9, country_scope=_SRI_LANKA)
        finally:
            repo.close()
        assert sri_lanka_origins
        client = _client()
        for origin in sri_lanka_origins:
            response = client.get(f"/api/geospatial/origins/{origin.forecast_origin_id}/trigger-sources", params={"disease": "fmd"})
            assert response.json()["country"] == _SRI_LANKA

    def test_router_route_endpoint_does_not_accept_a_country_query_param_that_could_widen_scope(self):
        """Structural: the new route resolves purely by `forecast_origin_id`
        (which already encodes country) -- it has no `country` query
        parameter at all, so there is no way to request a widened scope
        through this endpoint."""
        import inspect

        from components.geospatial_tracking.api.router import get_origin_trigger_sources

        params = inspect.signature(get_origin_trigger_sources).parameters
        assert "country" not in params

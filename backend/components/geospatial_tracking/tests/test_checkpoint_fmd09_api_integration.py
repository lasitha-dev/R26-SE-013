"""Checkpoint FMD-09: backend/API integration for the single FMD-08-
locked frozen RISK model.

No frozen scientific model is modified anywhere in this file. No
candidate selection, retuning, or new evaluation metric. Real-DB-
dependent tests skip gracefully on a clean clone (no
`data/local/pistes_dev.db`) -- structural/unit tests never skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from components.geospatial_tracking.api.router import router
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.services.application.frozen_fmd_risk_analysis_9 import (
    ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9,
    FMD_DISEASE_NAME_9,
    FMD_SPATIAL_EVALUATION_RADIUS_KM,
    FmdRiskAnalysisError9,
    ORIGIN_NOT_FOUND_9,
    run_frozen_fmd_risk_runtime_analysis_9,
)
from components.geospatial_tracking.services.fmd_calibration import FMD_SPATIAL_EVALUATION_RADIUS_KM as CALIBRATION_RADIUS_KM
from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger
from components.geospatial_tracking.services.model_development.fmd_frozen_model_9 import (
    FROZEN_MODEL_SPEC_SHA256_FMD09,
    FROZEN_THRESHOLD_FMD09,
    SELECTED_CANDIDATE_ID_FMD09,
)
from components.geospatial_tracking.services.model_development.local_evaluation_scope import (
    PRIMARY_LOCAL_EVALUATION_DISTANCE_KM,
)

from fastapi import FastAPI

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")


def _open_repo() -> SQLiteOutbreakRepository:
    return SQLiteOutbreakRepository(_DB_PATH)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestFmd09DiseaseIsolation:
    """FMD-09's own frozen local-evaluation radius must never be
    conflated with LSD's separately-calibrated one -- even though both
    currently happen to be numerically distinct (200km vs 25km), the
    real regression this protects against is a FUTURE accidental import
    swap, not today's specific values."""

    def test_fmd_radius_is_its_own_frozen_constant_not_lsd_25km(self):
        assert FMD_SPATIAL_EVALUATION_RADIUS_KM == CALIBRATION_RADIUS_KM
        assert FMD_SPATIAL_EVALUATION_RADIUS_KM != PRIMARY_LOCAL_EVALUATION_DISTANCE_KM

    def test_fmd_disease_name_resolves_to_canonical_fmd_string(self):
        assert FMD_DISEASE_NAME_9 == "Foot and mouth disease"


class TestFmd09FrozenConstants:
    """The frozen candidate/threshold/spec-hash are literal constants
    promoted from the real, already-persisted FMD-07B/FMD-08 artifacts
    (`fmd_frozen_model_9.py`) -- this test only checks internal
    consistency (never re-reads `local_data`); see
    `smoke_tests/run_fmd09_freeze_verification.py` for the on-disk
    cross-check."""

    def test_frozen_candidate_id_matches_frozen_spec_naming(self):
        # FMD-10B: refrozen to the FMD-10A multi-fold-aggregation-corrected
        # candidate (GAUSSIAN:100KM). The original EXPONENTIAL:25KM candidate
        # was selected under a since-fixed defect (fold-retention bug in
        # fmd_model_development_7b_finalizer.py) and is superseded -- its
        # evidence remains preserved, unmodified, under the original
        # fmd07b_* paths, but it no longer drives active FMD-09 runtime.
        assert SELECTED_CANDIDATE_ID_FMD09.startswith("FMD07B:SPATIAL:B0_DISTANCE_ONLY:GAUSSIAN:")

    def test_frozen_threshold_is_the_locked_fmd08_value(self):
        assert FROZEN_THRESHOLD_FMD09 == 0.05

    def test_frozen_spec_sha256_is_a_real_hex_digest(self):
        assert len(FROZEN_MODEL_SPEC_SHA256_FMD09) == 64
        int(FROZEN_MODEL_SPEC_SHA256_FMD09, 16)  # raises ValueError if not hex


class TestFmd09ErrorPaths:
    @_skip_no_db
    def test_unknown_origin_raises_origin_not_found(self):
        repo = _open_repo()
        try:
            with pytest.raises(FmdRiskAnalysisError9) as exc_info:
                run_frozen_fmd_risk_runtime_analysis_9(repo, "ORIGIN:Nowhere:1999-01-01")
            assert exc_info.value.status == ORIGIN_NOT_FOUND_9
        finally:
            repo.close()

    def test_router_maps_origin_not_found_to_404(self):
        client = _client()
        response = client.get("/api/geospatial/analysis/ORIGIN:Nowhere:1999-01-01/fmd-risk")
        assert response.status_code == 404
        assert response.json()["detail"]["status"] == ORIGIN_NOT_FOUND_9


class TestFmd09RealOriginScoring:
    @_skip_no_db
    def test_a_real_fmd_origin_scores_without_fabrication(self):
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
            analyzed = None
            for o in origins[:50]:
                try:
                    analyzed = run_frozen_fmd_risk_runtime_analysis_9(repo, o.forecast_origin_id)
                    break
                except FmdRiskAnalysisError9 as exc:
                    if exc.status != ANALYSIS_UNAVAILABLE_NO_ELIGIBLE_SOURCE_9:
                        raise
                    continue
            if analyzed is None:
                pytest.skip("no analyzable FMD origin found among the first 50 in dev DB")
            assert analyzed.frozen_candidate_id == SELECTED_CANDIDATE_ID_FMD09
            assert analyzed.threshold == FROZEN_THRESHOLD_FMD09
            assert analyzed.local_evaluation_radius_km == FMD_SPATIAL_EVALUATION_RADIUS_KM
            assert analyzed.disease == FMD_DISEASE_NAME_9
            if analyzed.risk_score is not None:
                assert analyzed.above_threshold == (analyzed.risk_score >= FROZEN_THRESHOLD_FMD09)
        finally:
            repo.close()

    @_skip_no_db
    def test_lsd_shaped_endpoints_stay_unaware_of_fmd_origins(self):
        """Invariant 3 (never let LSD's frozen values leak onto an FMD
        code path) also runs the other way: the generic `/summary`
        endpoint's default (LSD) disease scope must never resolve an
        FMD-only forecast_origin_id."""
        repo = _open_repo()
        try:
            origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE_NAME_9)
        finally:
            repo.close()
        if not origins:
            pytest.skip("no FMD origins in dev DB")
        client = _client()
        response = client.get(f"/api/geospatial/analysis/{origins[0].forecast_origin_id}/summary")
        assert response.status_code in (404, 409)

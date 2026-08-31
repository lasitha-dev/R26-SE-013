"""FMD-02: disease-parameterization plumbing and LSD/FMD isolation.

Software-architecture checkpoint only -- no FMD data, no FMD model
training, no LSD scientific parameter change. Every test here either (a)
proves the new `services.disease` canonical-selection registry behaves
correctly, (b) proves disease is now a real, explicit runtime dimension
threaded through the application/transport/API layers, (c) proves the
snapshot cache can never conflate two different diseases, or (d) proves
an unsupported/not-yet-modeled disease fails safely -- LSD's frozen
Checkpoint 7B-9C kernel/rate values are never substituted for it.

No historical Checkpoint 10A/10A.1/10B/10B.1/10B.1a protocol hash is
expected to change -- verified directly below (FMD02-HASH-01/02).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from components.geospatial_tracking.api import router as router_module
from components.geospatial_tracking.api.router import router as fastapi_router
from components.geospatial_tracking.api.websocket_schemas import (
    INBOUND_MESSAGE_MODELS_10B,
    SnapshotRefreshMessage,
    SnapshotRequestMessage,
)
from components.geospatial_tracking.config import DEFAULT_SQLITE_DB_PATH
from components.geospatial_tracking.services.application.frozen_geospatial_analysis_10a import (
    ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A,
    DISEASE_MODEL_READINESS_10A,
    DISEASE_MODEL_STATUS_READY_10A,
    ORIGIN_NOT_FOUND_10A,
    UNSUPPORTED_DISEASE_10A,
    RuntimeAnalysisError10A,
    resolve_forecast_origin_10a,
    run_frozen_geospatial_runtime_analysis_10a,
)
from components.geospatial_tracking.services.build_historical_replay import DISEASE
from components.geospatial_tracking.services.disease import (
    DEFAULT_DISEASE,
    SUPPORTED_DISEASES,
    UnsupportedDiseaseError,
    resolve_disease_selection,
)
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import (
    geospatial_api_protocol_hash_10a,
)
from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a1 import (
    geospatial_api_protocol_hash_10a1,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b import (
    geospatial_transport_protocol_hash_10b,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b1 import (
    geospatial_transport_protocol_hash_10b1,
)
from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b1a import (
    geospatial_transport_protocol_hash_10b1a,
)

_ORIGIN = "ORIGIN:Afghanistan:2022-05-29"
_HISTORICAL_10A_HASH = "8485968af638e34bbfcc7c4c7d8bae30cc297235edb2c9fa8b2f5fa2fca27716"
_HISTORICAL_10A1_HASH = "e44761319870e9196768599ad88fde237d709c2b17b03f17662ab144bd5634b8"
_HISTORICAL_10B_HASH = "071dbd1baebfa18d30626a39b218287bb25269a0ec1e61b809a955b31191f657"
_HISTORICAL_10B1_HASH = "476a7593aafd4011eec840a7ca60cb339302c037f4e00dd7ba11a239ff153a25"
_HISTORICAL_10B1A_HASH = "0549339d2d79659048e2d265403507b756b464d454419c28c295d005d8450f0e"

_DB_PATH = Path(__file__).resolve().parents[1] / DEFAULT_SQLITE_DB_PATH
_DB_AVAILABLE = _DB_PATH.exists()
_skip_no_db = pytest.mark.skipif(not _DB_AVAILABLE, reason="dev SQLite DB absent (clean clone)")


# ---------------------------------------------------------------------------
# FMD02-HASH-01/02: every historical protocol identity is byte-unchanged.
# ---------------------------------------------------------------------------


def test_fmd02_hash_01_historical_api_protocol_hashes_unchanged():
    assert geospatial_api_protocol_hash_10a() == _HISTORICAL_10A_HASH
    assert geospatial_api_protocol_hash_10a1() == _HISTORICAL_10A1_HASH


def test_fmd02_hash_02_historical_transport_protocol_hashes_unchanged():
    assert geospatial_transport_protocol_hash_10b() == _HISTORICAL_10B_HASH
    assert geospatial_transport_protocol_hash_10b1() == _HISTORICAL_10B1_HASH
    assert geospatial_transport_protocol_hash_10b1a() == _HISTORICAL_10B1A_HASH


def test_fmd02_hash_03_new_active_inbound_contract_hash_binds_the_unchanged_historical_one():
    from components.geospatial_tracking.services.integration.geospatial_transport_protocol_10b2 import (
        INBOUND_CONTRACT_10B2,
        geospatial_transport_protocol_dict_10b2,
        geospatial_transport_protocol_hash_10b2,
    )

    dict_10b2 = geospatial_transport_protocol_dict_10b2()
    assert dict_10b2["historical_10b1_transport_protocol_hash"] == _HISTORICAL_10B1_HASH
    assert "disease" in INBOUND_CONTRACT_10B2["snapshot_request"]
    assert "disease" in INBOUND_CONTRACT_10B2["snapshot_refresh"]
    # deterministic -- same inputs, same hash, every call
    assert geospatial_transport_protocol_hash_10b2() == geospatial_transport_protocol_hash_10b2()
    assert geospatial_transport_protocol_hash_10b2() != _HISTORICAL_10B1_HASH


# ---------------------------------------------------------------------------
# FMD02-NORM-01..06: disease normalization / canonical registry
# ---------------------------------------------------------------------------


def test_fmd02_norm_01_lsd_accepted_by_full_name():
    assert resolve_disease_selection("Lumpy skin disease") == "Lumpy skin disease"


def test_fmd02_norm_02_fmd_accepted_by_full_name():
    assert resolve_disease_selection("Foot and mouth disease") == "Foot and mouth disease"


def test_fmd02_norm_03_abbreviations_normalized_using_existing_project_convention():
    # Reuses services.disease.normalize_disease's pre-existing
    # _ABBREVIATION_EXPANSIONS table (lsd/fmd) -- not a new abbreviation
    # rule invented for FMD-02.
    assert resolve_disease_selection("lsd") == "Lumpy skin disease"
    assert resolve_disease_selection("LSD") == "Lumpy skin disease"
    assert resolve_disease_selection("fmd") == "Foot and mouth disease"
    assert resolve_disease_selection("FMD") == "Foot and mouth disease"


def test_fmd02_norm_04_equivalent_raw_spellings_collapse_to_the_same_canonical_value():
    # WAHIS-style spelling for LSD, mirrors REPOSITORY_DESIGN.md's own example.
    assert resolve_disease_selection("Lumpy skin disease virus (Inf. with)") == "Lumpy skin disease"


def test_fmd02_norm_05_unsupported_disease_rejected():
    with pytest.raises(UnsupportedDiseaseError):
        resolve_disease_selection("Rabies")
    with pytest.raises(UnsupportedDiseaseError):
        resolve_disease_selection("")
    with pytest.raises(UnsupportedDiseaseError):
        resolve_disease_selection("   ")


def test_fmd02_norm_06_lsd_and_fmd_never_collide():
    assert resolve_disease_selection("lsd") != resolve_disease_selection("fmd")
    assert set(SUPPORTED_DISEASES.values()) == {"Lumpy skin disease", "Foot and mouth disease"}


# ---------------------------------------------------------------------------
# FMD02-DEFAULT-01/02: omitted disease == pre-FMD-02 LSD behavior exactly
# ---------------------------------------------------------------------------


def test_fmd02_default_01_none_resolves_to_default_disease():
    assert resolve_disease_selection(None) == DEFAULT_DISEASE == "Lumpy skin disease"


def test_fmd02_default_02_build_historical_replay_disease_constant_unchanged():
    # DISEASE is now an alias for services.disease.DEFAULT_DISEASE --
    # same importable name, same value, for every pre-existing caller.
    assert DISEASE == "Lumpy skin disease" == DEFAULT_DISEASE


# ---------------------------------------------------------------------------
# FMD02-CACHE-01..05: snapshot cache identity includes disease
# ---------------------------------------------------------------------------


def test_fmd02_cache_01_omitted_disease_key_equals_explicit_lsd_key():
    key_omitted = router_module._snapshot_cache_key_10b(_ORIGIN)
    key_explicit = router_module._snapshot_cache_key_10b(_ORIGIN, "Lumpy skin disease")
    key_abbrev = router_module._snapshot_cache_key_10b(_ORIGIN, "lsd")
    assert key_omitted == key_explicit == key_abbrev


def test_fmd02_cache_02_different_disease_never_shares_a_key_for_the_same_origin():
    key_lsd = router_module._snapshot_cache_key_10b(_ORIGIN, "lsd")
    key_fmd = router_module._snapshot_cache_key_10b(_ORIGIN, "fmd")
    assert key_lsd != key_fmd
    assert key_lsd[0] == "Lumpy skin disease"
    assert key_fmd[0] == "Foot and mouth disease"


def test_fmd02_cache_03_disease_is_part_of_the_key_tuple():
    key = router_module._snapshot_cache_key_10b(_ORIGIN, "fmd")
    assert "Foot and mouth disease" in key
    assert _ORIGIN in key
    assert geospatial_api_protocol_hash_10a1() in key


def test_fmd02_cache_04_invalid_disease_raises_before_producing_a_key():
    with pytest.raises(UnsupportedDiseaseError):
        router_module._snapshot_cache_key_10b(_ORIGIN, "Rabies")


def test_fmd02_cache_05_store_get_or_compute_isolates_lsd_and_fmd_entries():
    from components.geospatial_tracking.services.transport.snapshot_store_10b import SnapshotStore10B

    store = SnapshotStore10B()
    key_lsd = ("Lumpy skin disease", _ORIGIN, "p")
    key_fmd = ("Foot and mouth disease", _ORIGIN, "p")
    value_lsd, _ = store.get_or_compute(key_lsd, lambda: "LSD_SNAPSHOT")
    value_fmd, _ = store.get_or_compute(key_fmd, lambda: "FMD_SNAPSHOT")
    assert value_lsd == "LSD_SNAPSHOT"
    assert value_fmd == "FMD_SNAPSHOT"
    # An FMD lookup can never retrieve the LSD entry, and vice versa --
    # both are cache HITS against their OWN key, never cross-served.
    reread_lsd, status_lsd = store.get_or_compute(key_lsd, lambda: "SHOULD_NOT_RECOMPUTE")
    reread_fmd, status_fmd = store.get_or_compute(key_fmd, lambda: "SHOULD_NOT_RECOMPUTE")
    assert reread_lsd == "LSD_SNAPSHOT"
    assert reread_fmd == "FMD_SNAPSHOT"
    assert status_lsd == status_fmd == "HIT_REUSED"


# ---------------------------------------------------------------------------
# FMD02-READY-01..04: disease-model readiness is separate from disease
# identifier support, and is enforced BEFORE any repository access
# (Invariant 3: LSD's frozen scientific parameters cannot be selected
# for FMD).
# ---------------------------------------------------------------------------


def test_fmd02_ready_01_lsd_is_model_ready():
    assert DISEASE_MODEL_READINESS_10A.get(DEFAULT_DISEASE) == DISEASE_MODEL_STATUS_READY_10A


def test_fmd02_ready_02_fmd_is_a_supported_identifier_but_not_model_ready():
    assert "Foot and mouth disease" in set(SUPPORTED_DISEASES.values())  # identifier: supported
    assert DISEASE_MODEL_READINESS_10A.get("Foot and mouth disease") != DISEASE_MODEL_STATUS_READY_10A  # model: not ready


class _RepositoryTouchedError(AssertionError):
    """Raised by `_UntouchableRepo` if the application layer ever
    attempts to use it -- proves the FMD readiness gate runs BEFORE any
    repository access, so the eventual repository query can never be
    misdirected at LSD data for an FMD request (the FMD-01 Invariant
    "requested disease = FMD but database query disease = LSD must
    never happen")."""


class _UntouchableRepo:
    def __getattr__(self, name):
        raise _RepositoryTouchedError(f"repository.{name} was accessed for a not-model-ready disease")


def test_fmd02_ready_03_fmd_request_fails_before_touching_the_repository():
    repo = _UntouchableRepo()
    with pytest.raises(RuntimeAnalysisError10A) as excinfo:
        run_frozen_geospatial_runtime_analysis_10a(repo, "anything", disease="fmd")
    assert excinfo.value.status == ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY_10A


def test_fmd02_ready_04_unsupported_disease_also_fails_before_touching_the_repository():
    repo = _UntouchableRepo()
    with pytest.raises(RuntimeAnalysisError10A) as excinfo:
        run_frozen_geospatial_runtime_analysis_10a(repo, "anything", disease="Rabies")
    assert excinfo.value.status == UNSUPPORTED_DISEASE_10A


# ---------------------------------------------------------------------------
# FMD02-TRACE-01..03: requested disease reaches repository/origin
# resolution correctly for a MODEL-READY disease (LSD) -- and metadata
# reports exactly the disease that was requested (Invariant 5).
# ---------------------------------------------------------------------------


@_skip_no_db
def test_fmd02_trace_01_omitted_disease_reaches_real_lsd_analysis_unchanged():
    from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository

    repo = SQLiteOutbreakRepository(_DB_PATH)
    try:
        result_default = run_frozen_geospatial_runtime_analysis_10a(repo, _ORIGIN)
        result_explicit_lsd = run_frozen_geospatial_runtime_analysis_10a(repo, _ORIGIN, disease="lsd")
    finally:
        repo.close()
    assert result_default.analysis_metadata.disease == "Lumpy skin disease"
    assert result_default.analysis_metadata.as_dict() == result_explicit_lsd.analysis_metadata.as_dict()
    assert result_default.cells == result_explicit_lsd.cells
    assert result_default.eligible_sources == result_explicit_lsd.eligible_sources


@_skip_no_db
def test_fmd02_trace_02_resolve_forecast_origin_uses_the_requested_disease():
    from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository

    repo = SQLiteOutbreakRepository(_DB_PATH)
    try:
        origin_lsd = resolve_forecast_origin_10a(repo, "Lumpy skin disease", _ORIGIN)
    finally:
        repo.close()
    assert origin_lsd is not None
    assert origin_lsd.forecast_origin_id == _ORIGIN


def test_fmd02_trace_03_unsupported_disease_origin_lookup_raises_before_ledger_query():
    repo = _UntouchableRepo()
    with pytest.raises(UnsupportedDiseaseError):
        resolve_disease_selection("Rabies")
    # resolve_forecast_origin_10a itself has no disease-resolution logic
    # (that already happened one layer up); confirms the untouched-repo
    # class is exercised correctly for the readiness-gate tests above.
    with pytest.raises(_RepositoryTouchedError):
        resolve_forecast_origin_10a(repo, "Lumpy skin disease", _ORIGIN)


# ---------------------------------------------------------------------------
# FMD02-WS-01..04: disease survives the WebSocket inbound-message contract
# ---------------------------------------------------------------------------


def test_fmd02_ws_01_snapshot_request_accepts_optional_disease():
    msg = SnapshotRequestMessage(type="snapshot_request", forecast_origin_id=_ORIGIN, disease="fmd")
    assert msg.disease == "fmd"


def test_fmd02_ws_02_snapshot_request_disease_omission_still_validates():
    msg = SnapshotRequestMessage(type="snapshot_request", forecast_origin_id=_ORIGIN)
    assert msg.disease is None


def test_fmd02_ws_03_snapshot_refresh_accepts_optional_disease():
    msg = SnapshotRefreshMessage(type="snapshot_refresh", forecast_origin_id=_ORIGIN, disease="Lumpy skin disease")
    assert msg.disease == "Lumpy skin disease"


def test_fmd02_ws_04_inbound_message_models_registry_unchanged_shape():
    assert set(INBOUND_MESSAGE_MODELS_10B.keys()) == {"snapshot_request", "snapshot_refresh", "ping"}


# ---------------------------------------------------------------------------
# FMD02-HTTP-01..05: FastAPI route-level behavior (TestClient, real DB)
# ---------------------------------------------------------------------------


@_skip_no_db
def test_fmd02_http_01_origins_omitted_disease_matches_pre_fmd02_response():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp_omitted = client.get("/api/geospatial/origins", params={"country": "Afghanistan"})
    resp_explicit = client.get("/api/geospatial/origins", params={"country": "Afghanistan", "disease": "lsd"})
    assert resp_omitted.status_code == resp_explicit.status_code == 200
    assert resp_omitted.json() == resp_explicit.json()


@_skip_no_db
def test_fmd02_http_02_origins_fmd_never_returns_lsd_data():
    """FMD-10 hardening update (Checkpoint FMD-10, not a scientific
    change): this test's ORIGINAL assertion (`n_origins == 0`) was a
    proxy for the real invariant -- at FMD-02 time no FMD historical
    data had been loaded yet, so "empty" and "never LSD data" were
    indistinguishable. FMD-03 onward loaded 3,182 real FMD forecast
    origins, making the zero-count proxy obsolete while the underlying
    invariant (`disease=fmd` must never surface LSD's ledger, mislabeled
    or otherwise) remains exactly as load-bearing as before. This
    version tests that invariant directly rather than via the
    now-stale proxy -- it is NOT weakened, and it is NOT a scientific
    change (no model/threshold/candidate touched)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp_fmd = client.get("/api/geospatial/origins", params={"disease": "fmd"})
    resp_lsd = client.get("/api/geospatial/origins", params={"disease": "lsd"})
    assert resp_fmd.status_code == resp_lsd.status_code == 200
    fmd_body, lsd_body = resp_fmd.json(), resp_lsd.json()

    fmd_ids = {o["forecast_origin_id"] for o in fmd_body["origins"]}
    lsd_ids = {o["forecast_origin_id"] for o in lsd_body["origins"]}
    assert len(fmd_ids) == fmd_body["n_origins"]
    # `forecast_origin_id` is `ORIGIN:{country}:{date}` -- disease-free --
    # so a coincidental per-id overlap across two real, independent
    # disease corpora is legitimate (both diseases can genuinely have an
    # outbreak in the same country on the same date) and is NOT itself
    # evidence of the bug this test guards against. The bug this test
    # existed to catch is `disease=fmd` wholesale reproducing the ENTIRE
    # LSD ledger (i.e. the `disease` param being silently ignored) --
    # ruled out directly below.
    assert fmd_ids != lsd_ids

    # Cross-check against the real, independently-computed service-layer
    # FMD ledger -- the HTTP layer must reproduce it exactly, never a
    # fabricated or partial subset.
    from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
    from components.geospatial_tracking.services.forecast_origin import build_forecast_origin_ledger

    repo = SQLiteOutbreakRepository(_DB_PATH)
    try:
        real_fmd_ledger_ids = {
            o.forecast_origin_id for o in build_forecast_origin_ledger(repo, disease=SUPPORTED_DISEASES["fmd"])
        }
    finally:
        repo.close()
    assert fmd_ids == real_fmd_ledger_ids
    assert len(real_fmd_ledger_ids) > 0  # documents why n_origins==0 is no longer the right assertion


def test_fmd02_http_03_origins_unsupported_disease_returns_422():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp = client.get("/api/geospatial/origins", params={"disease": "Rabies"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["status"] == "UNSUPPORTED_DISEASE"


@_skip_no_db
def test_fmd02_http_04_analysis_summary_fmd_returns_409_not_lsd_result():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp = client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary", params={"disease": "fmd"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["status"] == "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY"


@_skip_no_db
def test_fmd02_http_05_analysis_summary_omitted_disease_unchanged():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp_omitted = client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary")
    resp_explicit = client.get(f"/api/geospatial/analysis/{_ORIGIN}/summary", params={"disease": "Lumpy skin disease"})
    assert resp_omitted.status_code == resp_explicit.status_code == 200
    assert resp_omitted.json()["analysis_metadata"]["disease"] == "Lumpy skin disease"
    assert resp_omitted.json()["snapshot_id"] == resp_explicit.json()["snapshot_id"]


def test_fmd02_http_06_protocol_response_lists_new_error_statuses_additively():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from components.geospatial_tracking.services.integration.geospatial_api_protocol_10a import (
        ERROR_STATUS_TAXONOMY_10A,
    )

    app = FastAPI()
    app.include_router(fastapi_router)
    client = TestClient(app)

    resp = client.get("/api/geospatial/protocol")
    assert resp.status_code == 200
    body = resp.json()
    for historical_status in ERROR_STATUS_TAXONOMY_10A:
        assert historical_status in body["error_statuses"]
    assert "UNSUPPORTED_DISEASE" in body["error_statuses"]
    assert "ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY" in body["error_statuses"]
    # The hash fields themselves are the historical, unchanged values --
    # the additive statuses above are response-only.
    assert body["historical_api_protocol_hash_10a"] == _HISTORICAL_10A_HASH
    assert body["active_api_protocol_hash_10a1"] == _HISTORICAL_10A1_HASH

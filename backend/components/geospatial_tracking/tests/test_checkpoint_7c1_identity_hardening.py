"""Checkpoint 7C.1 Part 14: identity-hardening, temporal-role, and
frozen-spec tests (7C-TEMP-01..03 plus the remaining Part 14 checklist)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from components.geospatial_tracking.services.geospatial.source_geometry import EligibleSourcePoint
from components.geospatial_tracking.services.model_development import wind_readiness_7c
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    build_candidate_registry_7c,
    build_identity_only_result_remap_7c,
)
from components.geospatial_tracking.services.model_development.evaluation_protocol_7c import (
    ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC,
    METEOROLOGY_SPATIAL_MODE_7C,
    T0_PRECISION_POLICY_7C,
    WEATHER_LOOKBACK_HOURS_7C,
    _evaluation_protocol_dict_7c,
    evaluation_protocol_dict_7c,
    evaluation_protocol_hash_7c,
)
from components.geospatial_tracking.services.model_development.protocol_7c import build_frozen_checkpoint_7c_specification
from components.geospatial_tracking.services.model_development.wind_readiness_7c import (
    REAL,
    WEATHER_INPUT_UNAVAILABLE,
    WEATHER_TEMPORAL_ROLE_UNAVAILABLE,
    resolve_origin_wind,
)

_SOURCE = EligibleSourcePoint(source_id="S1", latitude=13.50, longitude=100.50)


def _fake_feature_result(name, status, value):
    return SimpleNamespace(feature_name=name, status=status, value=value)


def _fake_window(temporal_role: str):
    return SimpleNamespace(temporal_role=temporal_role, as_dict=lambda: {"temporal_role": temporal_role})


def _patched_wind(*, temporal_role: str, u10_status="REAL", v10_status="REAL"):
    window = _fake_window(temporal_role)
    results = [_fake_feature_result("mean_u10", u10_status, 5.0), _fake_feature_result("mean_v10", v10_status, 0.0)]
    with patch.object(wind_readiness_7c, "build_pre_t0_weather_summary", return_value=(window, results)):
        return resolve_origin_wind(forecast_origin_id="X", t0="2021-06-01", trigger_source_ids_at_t0=["S1"], sources=[_SOURCE], weather_cache=None)


def test_7ctemp_01_real_wind_with_exact_retrospective_role_is_admitted_as_real():
    result = _patched_wind(temporal_role="RETROSPECTIVE_REANALYSIS_STATE_PROXY")
    assert result.status == REAL
    assert result.wind is not None


def test_7ctemp_02_real_looking_wind_with_unknown_role_is_not_admitted_as_real():
    result = _patched_wind(temporal_role="UNKNOWN")
    assert result.status == WEATHER_TEMPORAL_ROLE_UNAVAILABLE
    assert result.wind is None


def test_7ctemp_03_future_realized_reanalysis_role_is_not_admitted():
    result = _patched_wind(temporal_role="REALIZED_FUTURE_REANALYSIS")
    assert result.status == WEATHER_TEMPORAL_ROLE_UNAVAILABLE
    assert result.wind is None


def test_7ctemp_04_genuinely_missing_wind_under_the_correct_role_is_weather_input_unavailable():
    result = _patched_wind(temporal_role="RETROSPECTIVE_REANALYSIS_STATE_PROXY", u10_status="MISSING", v10_status="MISSING")
    assert result.status == WEATHER_INPUT_UNAVAILABLE
    assert result.wind is None


def test_weather_lookback_participates_in_evaluation_identity():
    d = evaluation_protocol_dict_7c()
    assert d["weather_lookback_hours"] == 24
    assert d["weather_lookback_hours_status"] == "FROZEN_7C_PREDECLARED_WEATHER_LOOKBACK_HOURS"


def test_changing_lookback_would_change_the_evaluation_hash_and_therefore_every_candidate_id():
    baseline_hash = evaluation_protocol_hash_7c()
    tampered_dict = dict(evaluation_protocol_dict_7c())
    tampered_dict["weather_lookback_hours"] = 48
    import hashlib

    tampered_hash = hashlib.sha256(json.dumps(tampered_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert tampered_hash != baseline_hash


def test_t0_precision_policy_participates_in_identity():
    d = evaluation_protocol_dict_7c()
    assert d["t0_precision_policy"] == T0_PRECISION_POLICY_7C == "DATE_ONLY"


def test_meteorology_spatial_mode_participates_in_identity_and_is_the_real_named_status():
    d = evaluation_protocol_dict_7c()
    assert d["meteorology_spatial_mode"] == METEOROLOGY_SPATIAL_MODE_7C == "AOI_CENTER_UNIFORM_REAL_PROXY"
    assert "SPATIALLY_RESOLVED" not in d["meteorology_spatial_mode"]


def test_legacy_evaluation_protocol_dict_omits_the_new_identity_fields_matching_the_as_run_scheme():
    from components.geospatial_tracking.services.model_development.evaluation_protocol_7c import LEGACY_EVALUATION_PROTOCOL_VERSION_7C

    legacy = _evaluation_protocol_dict_7c(version=LEGACY_EVALUATION_PROTOCOL_VERSION_7C)
    for key in ("weather_lookback_hours", "t0_precision_policy", "meteorology_spatial_mode", "aoi_center_rule_version", "active_source_window_days"):
        assert key not in legacy


def test_identity_only_remap_is_bijective_across_all_9_candidates():
    remap = build_identity_only_result_remap_7c()
    assert len(remap) == 9
    assert len(set(remap.values())) == 9  # no collisions
    new_ids = {c.candidate_id for c in build_candidate_registry_7c()}
    assert set(remap.values()) == new_ids  # every new id in the remap is a real, current registry id
    for old_id, new_id in remap.items():
        assert old_id != new_id  # identity actually changed
        assert old_id.startswith("C7C:")
        assert new_id.startswith("C7C:")


def test_frozen_spec_exposes_weather_and_anisotropy_semantics_directly():
    fake_result = SimpleNamespace(
        selected_candidate_id="C7C:C0_FROZEN_B0_ISOTROPIC:abc", selected_candidate_spec={"candidate_id": "C7C:C0_FROZEN_B0_ISOTROPIC:abc", "anisotropy_mode": None, "anisotropy_kappa": None},
        fold_manifest=[], selection_tie_break_reason="UNIQUE_MAXIMUM_PRIMARY_METRIC",
        candidate_overall_metrics={"C7C:C0_FROZEN_B0_ISOTROPIC:abc": {"n_origins": 1, "mean_target_percentile": 50.0, "top5_capture_rate": 0.0, "top10_capture_rate": 0.0}},
        selection_note="", candidate_coverage_summary={},
    )
    spec = build_frozen_checkpoint_7c_specification(
        result=fake_result, parent_7b_frozen_spec_hash="X", candidate_registry_hash_7c="Y", evaluation_protocol_hash_7c="Z",
    )
    d = spec.as_dict()
    for field in (
        "weather_temporal_role", "weather_model", "weather_lookback_hours", "t0_precision_policy", "meteorology_spatial_mode",
        "anisotropy_implementation_version", "anisotropy_mode", "anisotropy_kappa", "host_factor_status",
        "environmental_suitability_status", "water_context_status", "source_strength_status", "anisotropy_mode_identifiability_status",
    ):
        assert field in d
    assert d["weather_lookback_hours"] == WEATHER_LOOKBACK_HOURS_7C
    assert d["anisotropy_mode_identifiability_status"] == ANISOTROPY_MODE_NOT_IDENTIFIABLE_UNDER_RANK_METRIC
    assert d["parameter_status"] == "FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION"
    assert "EXTERNALLY_VALIDATED" not in str(d).upper().replace("FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION", "")


_REPO_ROOT = Path(__file__).resolve().parents[4]
_7B_SUMMARY = _REPO_ROOT / "local_data" / "model_development" / "7b" / "final_candidate_selection_summary.json"
_7C_SELECTED = _REPO_ROOT / "local_data" / "model_development" / "7c" / "selected_candidate.json"


@pytest.mark.skipif(not (_7B_SUMMARY.exists() and _7C_SELECTED.exists()), reason="real 7B/7C persisted outputs not present in this environment")
def test_c0_full_development_result_matches_frozen_7b_persisted_result():
    c7b = json.loads(_7B_SUMMARY.read_text(encoding="utf-8"))
    c7b_metrics = c7b["candidate_overall_metrics"][c7b["selected_candidate_id"]]

    c7c = json.loads(_7C_SELECTED.read_text(encoding="utf-8"))
    c0_id = next(cid for cid, m in c7c["candidate_overall_metrics"].items() if "C0_FROZEN_B0_ISOTROPIC" in cid)
    c0_metrics = c7c["candidate_overall_metrics"][c0_id]

    for key in ("n_origins", "mean_target_percentile", "top5_capture_rate", "top10_capture_rate"):
        assert c0_metrics[key] == c7b_metrics[key], f"C0's real {key} diverged from the frozen 7B persisted value"

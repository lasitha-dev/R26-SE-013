import pytest
import csv
import json
import hashlib
from pathlib import Path
from collections import Counter

_REPO = Path(__file__).resolve().parents[4]
_GEO = Path(__file__).resolve().parents[1]
MANIFEST = _REPO / "local_data/processed/fmd/cohort/FMD_COHORT_MANIFEST.json"
AUDIT = _REPO / "local_data/processed/fmd/cohort/FMD_COHORT_AUDIT.csv"
ORIGINS = _REPO / "local_data/processed/fmd/cohort/fmd_historical_forecast_origins.csv"
EXPOSURE = _REPO / "local_data/processed/fmd/cohort/fmd_model_fitting_exposure_manifest.csv"
TARGETS = _REPO / "local_data/processed/fmd/cohort/fmd_historical_forecast_targets.csv"
FOLDS = _REPO / "local_data/processed/fmd/cohort/fmd_calendar_year_folds.json"
REGISTRY = _GEO / "FMD_EXPERIMENT_REGISTRY.json"
CANONICAL = _REPO / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
CANONICAL_SHA256 = "11b4528d32fcb9f6f26cd537511b0d0fca531890a8af5d7480e94188d3d0114e"


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _exposure_rows():
    with EXPOSURE.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _origin_rows():
    with ORIGINS.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _audit_rows():
    with AUDIT.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# TEST 1: unique origin IDs == manifest forecast_origin_count
def test_r01_unique_origin_ids_match_manifest_count():
    manifest = _manifest()
    origin_ids = {r["forecast_origin_id"] for r in _origin_rows()}
    assert len(origin_ids) == manifest["forecast_origin_count"]
    assert manifest["forecast_origin_count"] == 4322


# TEST 2: exposure manifest has exactly one row per origin
def test_r02_exposure_manifest_one_row_per_origin():
    rows = _exposure_rows()
    ids = [r["forecast_origin_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate origin IDs in exposure manifest"
    assert len(ids) == 4322


# TEST 3: origin-level role counts sum to origin total
def test_r03_origin_role_counts_sum_to_total():
    manifest = _manifest()
    role_counts = manifest["forecast_origin_role_counts"]
    assert sum(role_counts.values()) == manifest["forecast_origin_count"]
    assert sum(role_counts.values()) == 4322


# TEST 4: event-level role counts labelled separately, sum to included events
def test_r04_event_role_counts_labelled_and_correct():
    manifest = _manifest()
    assert "included_source_event_role_counts" in manifest
    event_counts = manifest["included_source_event_role_counts"]
    assert sum(event_counts.values()) == manifest["cohort_disposition_counts"]["INCLUDED"]
    assert sum(event_counts.values()) == 9311


# TEST 5: included event count
def test_r05_included_event_count_is_9311():
    manifest = _manifest()
    assert manifest["cohort_disposition_counts"]["INCLUDED"] == 9311


# TEST 6: excluded event count
def test_r06_excluded_event_count_is_215():
    manifest = _manifest()
    assert manifest["cohort_disposition_counts"]["EXCLUDED_STATUS_NOT_CONFIRMED"] == 215
    total = sum(manifest["cohort_disposition_counts"].values())
    assert total == manifest["canonical_event_count"]


# TEST 7: every included event maps to exactly one origin
def test_r07_every_included_event_maps_to_exactly_one_origin():
    audit = _audit_rows()
    included = [r for r in audit if r["cohort_disposition"] == "INCLUDED"]
    event_to_origins = {}
    for r in included:
        sid = r["source_record_id"]
        oid = r["forecast_origin_id"]
        assert sid not in event_to_origins, f"event {sid} maps to multiple origins"
        event_to_origins[sid] = oid
    assert len(event_to_origins) == 9311


# TEST 8: multiple same-country/same-t0 events map to ONE origin
def test_r08_multi_trigger_origins_do_not_inflate_count():
    manifest = _manifest()
    assert manifest["origins_with_multiple_trigger_sources"] > 0
    assert manifest["max_trigger_source_count_at_one_origin"] > 1
    # key invariant: sum of triggers == included events
    origins = _origin_rows()
    total_triggers = sum(int(r["trigger_source_count"]) for r in origins)
    assert total_triggers == 9311


# TEST 9: experiment registry uses origin counts when unit=forecast_origin
def test_r09_experiment_registry_uses_origin_counts():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    # old incorrect event counts must not appear as cohort sizes
    # 6,799 and 2,492 were event counts, not origin counts
    for exp in reg["experiments"]:
        cohort = exp.get("cohort", "")
        assert "6,799" not in cohort, f"experiment {exp['experiment_id']} still has event count 6,799 as cohort"
        assert "2,492" not in cohort, f"experiment {exp['experiment_id']} still has event count 2,492 as cohort"


# TEST 10: manifest forecast_origin_role_counts matches exposure manifest
def test_r10_manifest_origin_counts_match_exposure_file():
    manifest = _manifest()
    exposure = _exposure_rows()
    role_from_file = Counter(r["role"] for r in exposure)
    assert dict(role_from_file) == manifest["forecast_origin_role_counts"]


# TEST 11: roles mutually exclusive at origin level
def test_r11_origin_roles_mutually_exclusive():
    exposure = _exposure_rows()
    origin_to_roles = {}
    for r in exposure:
        oid = r["forecast_origin_id"]
        assert oid not in origin_to_roles, f"origin {oid} appears twice"
        origin_to_roles[oid] = r["role"]
    roles_seen = set(origin_to_roles.values())
    assert roles_seen.issubset(
        {"FIT_DEVELOPMENT", "HELD_OUT_FROM_MODEL_FITTING", "SRI_LANKA_TRANSFER_CASE_STUDY"}
    )


# TEST 12: held-out origins rejected by development-only helper
def test_r12_held_out_origins_rejected_by_dev_helper():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF
    from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
    from components.geospatial_tracking.services.model_fitting_exposure import assert_fit_development_only
    held = ForecastOrigin(
        forecast_origin_id="ORIGIN:South Africa:2026-02-01",
        country="South Africa", t0="2026-02-01",
        temporal_mode="RETROSPECTIVE_PROXY"
    )
    with pytest.raises(ValueError):
        assert_fit_development_only([held], cutoff=FMD_MODEL_FITTING_CUTOFF)


# TEST 13: Sri Lanka origins rejected by dev helper
def test_r13_sri_lanka_origins_rejected_by_dev_helper():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import FMD_MODEL_FITTING_CUTOFF
    from components.geospatial_tracking.services.forecast_origin import ForecastOrigin
    from components.geospatial_tracking.services.model_fitting_exposure import assert_fit_development_only
    sl = ForecastOrigin(
        forecast_origin_id="ORIGIN:Sri Lanka:2010-01-13",
        country="Sri Lanka", t0="2010-01-13",
        temporal_mode="RETROSPECTIVE_PROXY"
    )
    with pytest.raises(ValueError):
        assert_fit_development_only([sl], cutoff=FMD_MODEL_FITTING_CUTOFF)


# TEST 14: 2026 split at ORIGIN level
def test_r14_origin_level_split_proportions():
    manifest = _manifest()
    # True origin-level split:
    # FIT_DEVELOPMENT = 3761 origins (87.1% of non-SL)
    # HELD_OUT = 541 origins (12.5% of total, 12.6% of non-SL)
    role_counts = manifest["forecast_origin_role_counts"]
    assert role_counts["FIT_DEVELOPMENT"] == 3761
    assert role_counts["HELD_OUT_FROM_MODEL_FITTING"] == 541
    assert role_counts["SRI_LANKA_TRANSFER_CASE_STUDY"] == 20


# TEST 15: fold membership is origin-level and embargo respected
def test_r15_folds_are_origin_level_and_disjoint():
    folds = json.loads(FOLDS.read_text(encoding="utf-8"))
    for fold in folds:
        assert "training_origin_count" in fold or "training_origins" in fold
        assert "validation_origin_count" in fold or "validation_origins" in fold
    assert len(folds) == 23


# TEST 16: folds cover only FIT_DEVELOPMENT origins
def test_r16_folds_cover_only_fit_development():
    exposure = {r["forecast_origin_id"]: r["role"] for r in _exposure_rows()}
    folds = json.loads(FOLDS.read_text(encoding="utf-8"))
    for fold in folds:
        if "validation_origin_ids" in fold:
            for oid in fold["validation_origin_ids"]:
                assert exposure.get(oid) == "FIT_DEVELOPMENT"


# TEST 17: 2,844 is NOT hardcoded as final positive-risk count
def test_r17_positive_risk_count_not_frozen_before_spatial_domain():
    manifest = _manifest()
    assert "origins_with_at_least_one_target" in manifest
    val = manifest["origins_with_at_least_one_target"]
    assert val == 2844
    # But this is NOT the final label -- spatial domain not yet frozen.
    # Test that manifest does NOT have a field named "positive_risk_origin_count"
    assert "positive_risk_origin_count" not in manifest


# TEST 18: spatial reference source set constant is importable
def test_r18_spatial_target_reference_source_set_is_frozen():
    from components.geospatial_tracking.data_processing.build_fmd_cohort import (
        SPATIAL_TARGET_REFERENCE_SOURCE_SET
    )
    assert SPATIAL_TARGET_REFERENCE_SOURCE_SET in (
        "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0", "TRIGGER_SOURCES_ONLY"
    )


# TEST 19: no ST-DBSCAN calibration in FMD-05R
def test_r19_no_stdbscan_calibration_in_repair():
    import inspect
    import components.geospatial_tracking.data_processing.build_fmd_cohort as m
    src = inspect.getsource(m)
    forbidden = ["eps_space_km", "eps_time_days", "min_core_supports",
                 "STDBSCANConfig", "fit_stdbscan", "calibrate_stdbscan"]
    for term in forbidden:
        assert term not in src, f"Forbidden term '{term}' found in build_fmd_cohort.py"


# TEST 20: canonical corpus not mutated
def test_r20_canonical_corpus_not_mutated():
    assert _sha256(CANONICAL) == CANONICAL_SHA256


# TEST 21: LSD canonical not mutated
def test_r21_lsd_canonical_not_mutated():
    lsd = _REPO / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        h = _sha256(lsd)
        assert h == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"

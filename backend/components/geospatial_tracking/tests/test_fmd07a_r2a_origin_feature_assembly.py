"""FMD-07A-R2A: transparent pre-extraction forecast-origin feature-assembly
protocol amendment and freeze."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest

from components.geospatial_tracking.domain.models import HistoricalOutbreakRecord
from components.geospatial_tracking.repositories.sqlite_repository import SQLiteOutbreakRepository
from components.geospatial_tracking.schemas import AvailabilityQuality, DedupStatus, GpsQuality
from components.geospatial_tracking.services.fmd_calibration import FMD_DISEASE
from components.geospatial_tracking.services.fmd_model_development import derive_eligible_predictor_features
from components.geospatial_tracking.services.fmd_model_development_r2a import (
    AMENDMENT_STATUS,
    CENTROID_USED,
    FMD07_FEATURE_VALUE_STATUS,
    FROZEN_ACTIVE_WINDOW_DAYS,
    NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0,
    NUMERIC_AGGREGATION_RULE,
    ORIGIN_AGGREGATE_ALL_VALID,
    ORIGIN_AGGREGATE_NO_VALID_VALUE,
    ORIGIN_AGGREGATE_PARTIAL_VALID,
    ORIGINAL_R2_STATUS,
    SOURCE_SET_DEFINITION,
    TRIGGER_ONLY_USED,
    aggregate_origin_feature_status,
    aggregate_source_feature_values_for_origin,
    build_origin_feature_assembly_protocol,
    build_origin_feature_row_from_source_features,
    deduplicate_sources_by_canonical_id,
    get_eligible_active_sources_for_origin,
    run_fmd07a_r2a,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_R2_AUDIT_JSON = _MODEL_DEV_DIR / "fmd07a_r2_origin_feature_assembly_audit.json"
_R2A_PROTOCOL_JSON = _MODEL_DEV_DIR / "fmd07_origin_feature_assembly_protocol.json"
_FEATURE_TABLE_CSV = _REPO_ROOT / "local_data/processed/fmd/features/fmd_feature_table.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source(source_id: str, value, status: str, feature: str = "x") -> dict:
    return {"source_id": source_id, f"{feature}_value": value, f"{feature}_status": status}


@pytest.fixture
def repo(tmp_path):
    repository = SQLiteOutbreakRepository(tmp_path / "r2a.db")
    repository.init_schema()
    yield repository
    repository.close()


def _historical(source_id: str, availability_date: str, *, country: str = "Example", latitude: float = 7.0, longitude: float = 80.0) -> HistoricalOutbreakRecord:
    return HistoricalOutbreakRecord(
        source_record_id=source_id,
        country=country,
        disease=FMD_DISEASE,
        outbreak_start_date=availability_date,
        proxy_availability_date=availability_date,
        proxy_availability_quality=AvailabilityQuality.EVENT_DATE_PROXY.value,
        proxy_availability_source_field="outbreak_start_date",
        latitude=latitude,
        longitude=longitude,
        gps_quality=GpsQuality.EXACT.value,
        dedup_status=DedupStatus.SINGLETON.value,
        model_candidate=True,
    )


# ---------------------------------------------------------------------------
# 1-3: core mean / partial / no-valid-value semantics
# ---------------------------------------------------------------------------


def test_r2a_1_three_valid_sources_mean_is_2():
    records = [_source("A", 1.0, "SOURCE_VALUE_AVAILABLE"), _source("B", 2.0, "SOURCE_VALUE_AVAILABLE"), _source("C", 3.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 2.0
    assert result["status"] == ORIGIN_AGGREGATE_ALL_VALID


def test_r2a_2_one_valid_one_missing():
    records = [_source("A", 5.0, "SOURCE_VALUE_AVAILABLE"), _source("B", "", "SOURCE_VALUE_MISSING")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 5.0
    assert result["status"] == ORIGIN_AGGREGATE_PARTIAL_VALID


def test_r2a_3_all_missing():
    records = [_source("A", "", "SOURCE_VALUE_MISSING"), _source("B", "", "FEATURE_NOT_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] is None
    assert result["status"] == ORIGIN_AGGREGATE_NO_VALID_VALUE


# ---------------------------------------------------------------------------
# 4-7: identity / trigger-weight neutrality
# ---------------------------------------------------------------------------


def test_r2a_4_duplicate_canonical_source_id_counted_once():
    records = [_source("A", 10.0, "SOURCE_VALUE_AVAILABLE"), _source("A", 20.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["total_source_count"] == 1
    assert result["value"] == 10.0  # first occurrence wins, deterministically
    deduped = deduplicate_sources_by_canonical_id(records)
    assert len(deduped) == 1


def test_r2a_5_trigger_source_receives_no_extra_weight():
    records = [_source("TRIG", 10.0, "SOURCE_VALUE_AVAILABLE"), _source("OTHER", 20.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 15.0  # simple equal-weight mean, trigger status irrelevant
    signature = inspect.signature(aggregate_source_feature_values_for_origin)
    assert "trigger" not in " ".join(signature.parameters).lower()


def test_r2a_6_multiple_triggers_remain_equal_weight():
    records = [_source("T1", 1.0, "SOURCE_VALUE_AVAILABLE"), _source("T2", 2.0, "SOURCE_VALUE_AVAILABLE"), _source("NON_TRIG", 3.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 2.0
    assert result["total_source_count"] == 3


def test_r2a_7_non_trigger_eligible_sources_are_included():
    records = [_source("NON_TRIG_ONLY", 42.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 42.0
    assert result["total_source_count"] == 1


# ---------------------------------------------------------------------------
# 8-11: source-selection boundary (integration with the existing, frozen
# get_eligible_sources implementation -- via SQLite, no network)
# ---------------------------------------------------------------------------


def test_r2a_8_future_source_rejected(repo):
    repo.add_historical_record(_historical("FUTURE", "2025-06-11"))
    sources = get_eligible_active_sources_for_origin(repo, disease=FMD_DISEASE, t0="2025-06-10", country="Example")
    assert "FUTURE" not in {s.source_id for s in sources}


def test_r2a_9_source_older_than_window_excluded(repo):
    repo.add_historical_record(_historical("TOO_OLD", "2025-05-26"))  # t0 - 15 days
    sources = get_eligible_active_sources_for_origin(repo, disease=FMD_DISEASE, t0="2025-06-10", country="Example")
    assert "TOO_OLD" not in {s.source_id for s in sources}


def test_r2a_10_lower_boundary_t0_minus_14_accepted(repo):
    repo.add_historical_record(_historical("LOWER_BOUND", "2025-05-27"))  # exactly t0 - 14 days
    sources = get_eligible_active_sources_for_origin(repo, disease=FMD_DISEASE, t0="2025-06-10", country="Example")
    assert "LOWER_BOUND" in {s.source_id for s in sources}


def test_r2a_11_upper_boundary_t0_accepted(repo):
    repo.add_historical_record(_historical("AT_T0", "2025-06-10"))
    sources = get_eligible_active_sources_for_origin(repo, disease=FMD_DISEASE, t0="2025-06-10", country="Example")
    assert "AT_T0" in {s.source_id for s in sources}
    assert FROZEN_ACTIVE_WINDOW_DAYS == 14


# ---------------------------------------------------------------------------
# 12-14: label/target firewall
# ---------------------------------------------------------------------------


def test_r2a_12_labels_do_not_alter_predictor_values():
    records = [{"source_id": "A", "x_value": 5.0, "x_status": "SOURCE_VALUE_AVAILABLE", "risk_target_label": "1"}]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["value"] == 5.0  # the extra key is silently ignored


def test_r2a_13_label_shuffling_produces_identical_predictors():
    features = ["x"]
    records_a = [_source("A", 1.0, "SOURCE_VALUE_AVAILABLE"), _source("B", 2.0, "SOURCE_VALUE_AVAILABLE")]
    for r in records_a:
        r["risk_target_label"] = "1"
    records_b = [dict(r) for r in reversed(records_a)]
    for r in records_b:
        r["risk_target_label"] = "0"  # different label, same predictor sources
    row_a = build_origin_feature_row_from_source_features("O1", records_a, features)["row"]
    row_b = build_origin_feature_row_from_source_features("O1", records_b, features)["row"]
    assert row_a["x_value"] == row_b["x_value"]


def test_r2a_14_target_rows_never_read():
    from components.geospatial_tracking.services import fmd_model_development_r2a as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("local_domain_positive", "has_eligible_d1_d7_target", "outside_domain_target_present", "build_forecast_targets"):
        assert forbidden not in source
    signature = inspect.signature(aggregate_source_feature_values_for_origin)
    assert not {"target", "label", "risk_target_label"} & set(signature.parameters)


# ---------------------------------------------------------------------------
# 15-16: determinism
# ---------------------------------------------------------------------------


def test_r2a_15_source_order_permutation_gives_identical_output():
    records = [_source("A", 1.0, "SOURCE_VALUE_AVAILABLE"), _source("B", 2.0, "SOURCE_VALUE_AVAILABLE"), _source("C", 3.0, "SOURCE_VALUE_AVAILABLE")]
    forward = aggregate_source_feature_values_for_origin(records, "x")
    reversed_result = aggregate_source_feature_values_for_origin(list(reversed(records)), "x")
    import random

    shuffled = list(records)
    random.Random(42).shuffle(shuffled)
    shuffled_result = aggregate_source_feature_values_for_origin(shuffled, "x")
    assert forward == reversed_result == shuffled_result


def test_r2a_16_aggregation_is_deterministic():
    records = [_source("A", 1.5, "SOURCE_VALUE_AVAILABLE"), _source("B", 2.5, "SOURCE_VALUE_AVAILABLE")]
    result1 = aggregate_source_feature_values_for_origin(records, "x")
    result2 = aggregate_source_feature_values_for_origin(records, "x")
    assert result1 == result2


# ---------------------------------------------------------------------------
# 17-18: no centroid, no weather winner
# ---------------------------------------------------------------------------


def test_r2a_17_no_centroid_is_computed():
    from components.geospatial_tracking.services import fmd_model_development_r2a as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("centroid_lat", "centroid_lon", "aoi_center", "AOI_CENTER"):
        assert forbidden not in source
    assert "latitude" not in source and "longitude" not in source  # no spatial-point math of any kind
    assert CENTROID_USED is False
    assert TRIGGER_ONLY_USED is False


def test_r2a_18_weather_window_winner_remains_unselected():
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["weather_winner_used"] is False
    assert protocol["weather_winner_selected"] is False
    assert "window not selected" in protocol["weather_source_level_semantics"].lower() or "no weather-window winner is selected" in protocol["weather_source_level_semantics"].lower()


# ---------------------------------------------------------------------------
# 19-20: land-cover / hydrology use the same generic mean rule
# ---------------------------------------------------------------------------


def test_r2a_19_landcover_fraction_means_within_floating_tolerance():
    records = [
        _source("A", 0.2, "SOURCE_VALUE_AVAILABLE", feature="landcover_cropland_fraction"),
        _source("B", 0.4, "SOURCE_VALUE_AVAILABLE", feature="landcover_cropland_fraction"),
        _source("C", 0.6, "SOURCE_VALUE_AVAILABLE", feature="landcover_cropland_fraction"),
    ]
    result = aggregate_source_feature_values_for_origin(records, "landcover_cropland_fraction")
    assert abs(result["value"] - 0.4) < 1e-9


def test_r2a_20_hydrology_uses_mean_not_min():
    records = [
        _source("A", 1.0, "SOURCE_VALUE_AVAILABLE", feature="distance_to_nearest_river_km"),
        _source("B", 9.0, "SOURCE_VALUE_AVAILABLE", feature="distance_to_nearest_river_km"),
    ]
    result = aggregate_source_feature_values_for_origin(records, "distance_to_nearest_river_km")
    assert result["value"] == 5.0  # mean, not min(1.0)


# ---------------------------------------------------------------------------
# 21-22: zero-source retention / audit reconciliation
# ---------------------------------------------------------------------------


def test_r2a_21_zero_source_case_preserves_origin_row():
    row_result = build_origin_feature_row_from_source_features("ORIGIN:Empty", [], ["x"])
    assert row_result["row"]["forecast_origin_id"] == "ORIGIN:Empty"
    assert row_result["row"]["x_value"] == ""
    assert row_result["row"]["x_status"] == NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0


def test_r2a_22_audit_counts_reconcile():
    records = [_source("A", 1.0, "SOURCE_VALUE_AVAILABLE"), _source("B", "", "SOURCE_VALUE_MISSING"), _source("C", 3.0, "SOURCE_VALUE_AVAILABLE")]
    result = aggregate_source_feature_values_for_origin(records, "x")
    assert result["total_source_count"] == 3
    assert result["valid_source_count"] == 2
    assert result["invalid_source_count"] == 1
    assert result["valid_source_count"] + result["invalid_source_count"] == result["total_source_count"]
    assert result["valid_source_fraction"] == round(2 / 3, 6)
    assert sum(result["underlying_status_counts"].values()) == 3


def test_r2a_22b_aggregate_status_pure_function_of_counts():
    assert aggregate_origin_feature_status(0, 0) == NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0
    assert aggregate_origin_feature_status(3, 0) == ORIGIN_AGGREGATE_NO_VALID_VALUE
    assert aggregate_origin_feature_status(3, 3) == ORIGIN_AGGREGATE_ALL_VALID
    assert aggregate_origin_feature_status(3, 1) == ORIGIN_AGGREGATE_PARTIAL_VALID
    signature = inspect.signature(aggregate_origin_feature_status)
    assert not {"score", "metric", "label", "target"} & set(signature.parameters)


# ---------------------------------------------------------------------------
# 23-24: held-out / Sri Lanka role firewall (structural)
# ---------------------------------------------------------------------------


def test_r2a_23_24_no_held_out_or_sri_lanka_role_concept_used():
    from components.geospatial_tracking.services import fmd_model_development_r2a as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert "held_out_from_model_fitting_origins" not in source
    assert "sri_lanka_transfer_case_study_origins" not in source
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["held_out_outcomes_used"] is False
    assert protocol["sri_lanka_outcomes_used"] is False


# ---------------------------------------------------------------------------
# 25-26: no model trained, no predictive metric
# ---------------------------------------------------------------------------


def test_r2a_25_26_no_model_trained_no_predictive_metric():
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["model_trained"] is False
    assert protocol["predictive_metrics_computed"] is False
    assert protocol["threshold_selected"] is False
    from components.geospatial_tracking.services import fmd_model_development_r2a as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "sklearn" not in source
    assert "pr_auc" not in source.lower() and "prauc" not in source.lower()


# ---------------------------------------------------------------------------
# Amendment classification / R2 preservation / extraction status
# ---------------------------------------------------------------------------


def test_r2a_amendment_classification_and_r2_preservation():
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["amendment_status"] == "PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT"
    assert AMENDMENT_STATUS == "PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT"
    assert protocol["original_r2_status"] == ORIGINAL_R2_STATUS == "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"
    assert protocol["introduced_after_r2_preflight"] is True
    assert protocol["introduced_before_full_feature_extraction"] is True
    assert protocol["introduced_before_any_predictive_model"] is True
    assert "not preregistered" in protocol["not_preregistered_statement"].lower()

    r2_audit = json.loads(_R2_AUDIT_JSON.read_text(encoding="utf-8"))
    assert r2_audit["overall_rule_status"] == "UNDEFINED"
    assert r2_audit["block_name"] == "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"


def test_r2a_source_set_and_numeric_rule_frozen_exactly():
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["source_set"] == SOURCE_SET_DEFINITION == "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
    assert protocol["numeric_aggregation_rule"] == NUMERIC_AGGREGATION_RULE == "UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES"
    assert protocol["active_window_days"] == 14


def test_r2a_extraction_status_still_not_run():
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["feature_value_status"] == "FULL_CORPUS_EXTRACTION_NOT_RUN"
    assert FMD07_FEATURE_VALUE_STATUS == "FULL_CORPUS_EXTRACTION_NOT_RUN"
    import csv

    rows = list(csv.DictReader((_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv").open(encoding="utf-8", newline="")))
    assert len(rows) == 3761
    for row in rows[:20]:
        for key, value in row.items():
            if key.endswith("_value") and not key.startswith("audit_only") and key != "risk_target_label":
                assert value == ""


def test_r2a_fmd07a_matrix_unchanged():
    assert _sha256(_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv") == "023ed97a10b7c27be090f6009ee8600da08cf1c76519e3926d68fbc013fd6dad"


def test_r2a_eligible_feature_count_matches_fmd07a():
    eligible, unavailable = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)
    protocol = json.loads(_R2A_PROTOCOL_JSON.read_text(encoding="utf-8"))
    assert protocol["eligible_predictor_feature_count"] == 47 == len(eligible)
    assert protocol["eligible_predictor_features"] == eligible


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_r2a_reproducible_across_two_independent_temp_builds(tmp_path):
    import shutil

    eligible, _ = derive_eligible_predictor_features(_FEATURE_TABLE_CSV)

    def _build(out_dir: Path) -> str:
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_R2_AUDIT_JSON, out_dir / _R2_AUDIT_JSON.name)
        run_fmd07a_r2a(out_dir, eligible)
        return _sha256(out_dir / "fmd07_origin_feature_assembly_protocol.json")

    hash1 = _build(tmp_path / "run1")
    hash2 = _build(tmp_path / "run2")
    assert hash1 == hash2


def test_r2a_rejects_if_r2_audit_was_rewritten(tmp_path):
    tampered = {"overall_rule_status": "RESOLVED", "block_name": "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"}
    (tmp_path / "fmd07a_r2_origin_feature_assembly_audit.json").write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="R2's original finding must be preserved"):
        build_origin_feature_assembly_protocol(tampered, ["x"])

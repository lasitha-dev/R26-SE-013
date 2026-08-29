"""FMD-07A-R2: forecast-origin feature-assembly preflight.

Confirms the repository does NOT contain a pre-existing rule mapping
event/source-level features to one forecast-origin predictor row, and
that this checkpoint correctly stops BEFORE any remote extraction rather
than inventing one."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from components.geospatial_tracking.services.fmd_model_development_r2 import (
    BLOCK_NAME,
    RULE_STATUS_UNDEFINED,
    build_origin_feature_assembly_audit,
    run_fmd07a_r2_preflight,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_MODEL_DEV_DIR = _REPO_ROOT / "local_data/processed/fmd/model_development"
_CALIBRATION_DIR = _REPO_ROOT / "local_data/processed/fmd/calibration"
_COHORT_DIR = _REPO_ROOT / "local_data/processed/fmd/cohort"

_AUDIT_JSON = _MODEL_DEV_DIR / "fmd07a_r2_origin_feature_assembly_audit.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_fmd07a_r2_audit_reports_rule_undefined():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["overall_rule_status"] == "UNDEFINED"
    assert audit["blocking"] is True
    assert audit["block_name"] == "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"
    assert RULE_STATUS_UNDEFINED == "UNDEFINED"
    assert BLOCK_NAME == "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"


def test_fmd07a_r2_undefined_fields_are_the_genuinely_unresolved_ones():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    undefined_fields = {
        "forecast_origin_feature_reference_rule",
        "source_event_selection_rule",
        "multi_source_aggregation_rule_per_feature_family",
        "static_feature_spatial_reference_rule",
        "missing_source_aggregation_rule",
        "status_aggregation_rule",
    }
    for field in undefined_fields:
        assert audit[field]["status"] == "UNDEFINED", field
    # what IS already established remains correctly distinguished, never
    # collapsed into a blanket "everything is unknown" claim
    assert audit["source_set_semantics"]["status"] == "PARTIALLY_ESTABLISHED"
    assert audit["weather_temporal_reference_rule"]["status"] == "PARTIALLY_ESTABLISHED"
    assert audit["availability_at_t0_rule"]["status"] == "ESTABLISHED"


def test_fmd07a_r2_audit_deterministic():
    audit1 = build_origin_feature_assembly_audit()
    audit2 = build_origin_feature_assembly_audit()
    assert audit1 == audit2


def test_fmd07a_r2_reproducible_across_two_independent_temp_builds(tmp_path):
    result1 = run_fmd07a_r2_preflight(tmp_path / "run1")
    result2 = run_fmd07a_r2_preflight(tmp_path / "run2")
    hash1 = _sha256(Path(result1["audit_path"]))
    hash2 = _sha256(Path(result2["audit_path"]))
    assert hash1 == hash2


def test_fmd07a_r2_no_network_no_extraction_performed():
    from components.geospatial_tracking.services import fmd_model_development_r2 as m

    source = Path(m.__file__).read_text(encoding="utf-8")
    for forbidden in ("import requests", "era5", "extract_elevation", "extract_density", "extract_landcover_fractions", "distance_to_nearest_river_km", "FileWeatherCache"):
        assert forbidden not in source, f"unexpected network/adapter reference: {forbidden}"


def test_fmd07a_r2_held_out_and_sri_lanka_unused():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["held_out_outcomes_used"] is False
    assert audit["sri_lanka_outcomes_used"] is False
    assert audit["predictive_metrics_used_to_define"] is False


def test_fmd07a_r2_modelling_row_unit_preserved_as_forecast_origin():
    audit = json.loads(_AUDIT_JSON.read_text(encoding="utf-8"))
    assert audit["modelling_row_unit_preserved"] == "FORECAST_ORIGIN (never converted to source-event rows anywhere in this audit)"


# ---------------------------------------------------------------------------
# Section 22: frozen artifact hash protection (nothing extraction-related
# was written, so every earlier checkpoint's artifact must be byte-identical
# to its previously-recorded value)
# ---------------------------------------------------------------------------


def test_fmd07a_r2_fmd06_and_earlier_artifacts_unchanged():
    assert _sha256(_REPO_ROOT / "local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv") == "11b4528d32fcb9f6f26cd537511b0d0fca531890a8af5d7480e94188d3d0114e"
    lsd = _REPO_ROOT / "local_data/processed/canonical_outbreaks_conservative.csv"
    if lsd.exists():
        assert _sha256(lsd) == "fa8e77d81b48af6bc2839deb4be9d4046d502ab948ce8e4e67a02a84c281d7f7"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_freeze.json") == "f72ff161066223a63de185188ae97de46793a4aea91ad14c3a8ab3aadace66a0"
    assert _sha256(_CALIBRATION_DIR / "fmd06_risk_origin_labels.csv") == "e6eb43aae1fa65aa3e243c1770f44ecc047593a5012a8155a8b00aadc081e438"
    assert _sha256(_CALIBRATION_DIR / "fmd06_calibration_manifest.json") == "a5b6b6ead805357a887f2b80c0ea9f7d9d96a96723840a7d4e6b8373c965b113"


def test_fmd07a_r2_fmd07a_artifacts_unchanged():
    assert _sha256(_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv") == "023ed97a10b7c27be090f6009ee8600da08cf1c76519e3926d68fbc013fd6dad"
    assert _sha256(_MODEL_DEV_DIR / "fmd07_feature_matrix_audit.json") == "45cebf44a3ca41a317801b6810a80a28f10fe28d963c4098a46ac815c45736fc"
    assert _sha256(_MODEL_DEV_DIR / "fmd07_model_input_schema.json") == "02774a883a35008225c5b8b8ed89204a42121c0e29d6e9aefa60659f920131c7"


def test_fmd07a_r2_fmd07a_provenance_still_reports_extraction_not_run():
    provenance = json.loads((_MODEL_DEV_DIR / "fmd07a_provenance.json").read_text(encoding="utf-8"))
    assert provenance["overall_status"] == "BLOCKED_PENDING_FULL_CORPUS_FEATURE_EXTRACTION"


def test_fmd07a_r2_no_predictor_value_was_populated_or_fabricated():
    import csv

    rows = list(csv.DictReader((_MODEL_DEV_DIR / "fmd07_development_feature_matrix.csv").open(encoding="utf-8", newline="")))
    assert len(rows) == 3761
    sample = rows[:50]
    for row in sample:
        for key, value in row.items():
            if key.endswith("_value") and not key.startswith("audit_only") and key != "risk_target_label":
                assert value == ""
            if key.endswith("_status") and key.startswith(("weather_", "elevation_", "host_density_", "landcover_", "distance_to_nearest_river_km")):
                assert value == "EXTRACTION_NOT_RUN"

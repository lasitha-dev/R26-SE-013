"""FMD-07A: leakage-safe development feature matrix, model-development
protocol audit, and pre-training freeze.

**Primary blocker, honestly recorded rather than worked around**: every
eligible predictor family in `FMD_FEATURE_ELIGIBILITY.csv` (weather via
ERA5, elevation, cattle/buffalo density via GLW4, land-cover via
WorldCover, hydrology via HydroRIVERS) requires the FMD-04 remote-adapter
extraction pipeline. That pipeline has only ever been run on a 29-event
adapter-validation sample (`local_data/processed/fmd/features/
FMD_FEATURE_AUDIT.md`) -- full-corpus extraction for the real 3,761-origin
`FIT_DEVELOPMENT` cohort was deliberately deferred and has never run (an
estimated ~15,000+ live weather requests alone, before host-density/
land-cover/hydrology/elevation calls). This module therefore does NOT
fabricate predictor values: every eligible predictor column is populated
with an honest `EXTRACTION_NOT_RUN` status and no value, and the resulting
development feature matrix is a real, deterministic, leakage-safe SCHEMA
freeze -- metadata/label columns are real (from the frozen FMD-06D
`fmd06_risk_origin_labels.csv`), predictor columns are schema-complete but
value-pending.

No model is fit, no hyperparameter is chosen, no threshold is selected,
and no predictive metric is computed anywhere in this module.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .fmd_calibration import (
    FMD_MODEL_FITTING_CUTOFF,
    FMD_SPATIAL_EVALUATION_RADIUS_KM,
    SPATIAL_PROTOCOL_AMENDMENT_STATUS,
    SPATIAL_REFERENCE_SOURCE_SET,
    load_forecast_origins,
)
from .forecast_origin import ForecastOrigin
from .model_fitting_exposure import (
    FIT_DEVELOPMENT,
    assert_fit_development_only,
    classify_origin_role,
    fit_development_origins,
)

CHECKPOINT = "FMD-07A"

PREDICTOR_STATUS_EXTRACTION_NOT_RUN = "EXTRACTION_NOT_RUN"
PREDICTOR_STATUS_FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"

# Section 6's explicit prohibited-predictor list -- a substring match
# against every candidate predictor column name; none of the real eligible
# feature names (weather/elevation/host-density/land-cover/hydrology) can
# ever collide with these, so this is a permanent structural guard, not a
# per-run check.
PROHIBITED_PREDICTOR_SUBSTRINGS = (
    "risk_target_label",
    "local_domain_positive",
    "outside_domain_target_present",
    "has_eligible_d1_d7_target",
)

NON_PREDICTOR_AUDIT_ONLY_COLUMNS = [
    "audit_only_has_eligible_d1_d7_target",
    "audit_only_outside_domain_target_present",
    "audit_only_local_evaluation_radius_km",
    "audit_only_target_horizon",
    "audit_only_spatial_reference_source_set",
    "audit_only_spatial_protocol_amendment_status",
]

IDENTIFIER_COLUMNS = ["forecast_origin_id"]
METADATA_COLUMNS = ["country", "t0", "model_fitting_role"]
TARGET_COLUMN = "risk_target_label"

# The real `fmd_feature_table.csv` column-name prefixes for each weather
# window candidate, and the correspondence between its bare variable names
# and FMD_FEATURE_ELIGIBILITY.csv's own `feature_family` values (the CSV
# spells relative humidity's family `..._derived`; the real extracted
# column does not carry that suffix -- both are pre-existing repository
# names, mapped here, never renamed).
WEATHER_WINDOW_COLUMN_PREFIXES = (
    "weather_event_day_",
    "weather_window_3day_",
    "weather_window_7day_",
    "weather_window_14day_",
)
WEATHER_VARIABLE_TO_FEATURE_FAMILY = {
    "mean_temperature_2m": "mean_temperature_2m",
    "mean_relative_humidity_2m": "mean_relative_humidity_2m_derived",
    "precipitation_accumulation": "precipitation_accumulation",
    "mean_u10": "mean_u10",
    "mean_v10": "mean_v10",
    "mean_wind_speed": "mean_wind_speed",
    "vector_resultant_speed": "vector_resultant_speed",
    "directional_persistence": "directional_persistence",
}
HOST_DENSITY_SPECIES_TO_FEATURE_FAMILY = {
    "cattle": "cattle_density_animals_per_km2",
    "buffalo": "buffalo_density_animals_per_km2",
    "swine": "swine_pig_density",
    "sheep": "sheep_density",
    "goat": "goat_density",
}

_LABEL_TO_AUDIT_COLUMN = {
    "audit_only_has_eligible_d1_d7_target": "has_eligible_d1_d7_target",
    "audit_only_outside_domain_target_present": "outside_domain_target_present",
    "audit_only_local_evaluation_radius_km": "local_evaluation_radius_km",
    "audit_only_target_horizon": "target_horizon",
    "audit_only_spatial_reference_source_set": "spatial_reference_source_set",
    "audit_only_spatial_protocol_amendment_status": "spatial_protocol_amendment_status",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_fmd07a_risk_labels(path: str | Path) -> list[dict]:
    """The frozen FMD-06D `fmd06_risk_origin_labels.csv` -- read, never
    regenerated or recomputed here."""
    return _csv_rows(Path(path))


def derive_eligible_predictor_features(feature_table_path: str | Path) -> tuple[list[str], list[str]]:
    """Derives the real, existing eligible-vs-unavailable predictor feature
    name list DIRECTLY from FMD-04's own already-produced 29-event
    validation-sample output (`fmd_feature_table.csv`) -- the authoritative
    existing schema, never invented or renamed here. A `<name>_value`
    column is UNAVAILABLE iff every one of its `<name>_status` values in
    the real sample is `FEATURE_NOT_AVAILABLE` (matches
    `FMD_FEATURE_ELIGIBILITY.csv`'s swine/sheep/goat rows); every other
    real feature column is ELIGIBLE."""
    rows = _csv_rows(Path(feature_table_path))
    if not rows:
        raise ValueError(f"derive_eligible_predictor_features: {feature_table_path} has no rows")
    value_columns = [name for name in rows[0] if name.endswith("_value")]
    eligible: list[str] = []
    unavailable: list[str] = []
    for value_column in value_columns:
        feature_name = value_column[: -len("_value")]
        status_column = f"{feature_name}_status"
        statuses = {row[status_column] for row in rows}
        if statuses == {PREDICTOR_STATUS_FEATURE_NOT_AVAILABLE}:
            unavailable.append(feature_name)
        else:
            eligible.append(feature_name)
    return sorted(eligible), sorted(unavailable)


def _feature_family(feature_name: str) -> str:
    if feature_name.startswith("weather_"):
        return "dynamic_meteorological"
    if feature_name == "elevation_m":
        return "static_terrain"
    if feature_name.startswith("host_density_"):
        return "static_host_density"
    if feature_name.startswith("landcover_"):
        return "static_landcover"
    if feature_name == "distance_to_nearest_river_km":
        return "static_hydrology"
    return "unclassified"


def build_fmd07a_feature_eligibility_registry(
    eligibility_csv_path: str | Path,
    eligible_features: list[str],
    unavailable_features: list[str],
) -> list[dict]:
    """One row per candidate predictor feature (Section 7), classified with
    the repository's OWN existing status vocabulary (`ELIGIBLE_CANDIDATE` /
    `STATIC_REFERENCE_PROXY` / `UNAVAILABLE`, read directly from
    `FMD_FEATURE_ELIGIBILITY.csv`) -- never a new `ELIGIBLE_AT_T0` label
    invented here."""
    eligibility_rows = _csv_rows(Path(eligibility_csv_path))
    by_family: dict[str, dict] = {row["feature_family"]: row for row in eligibility_rows}

    def _match_family_row(feature_name: str) -> dict | None:
        if feature_name.startswith("weather_"):
            for window_prefix in WEATHER_WINDOW_COLUMN_PREFIXES:
                if feature_name.startswith(window_prefix):
                    variable_name = feature_name[len(window_prefix):]
                    family_key = WEATHER_VARIABLE_TO_FEATURE_FAMILY.get(variable_name)
                    return by_family.get(family_key) if family_key else None
            return None
        if feature_name == "elevation_m":
            return by_family.get("elevation_m")
        if feature_name.startswith("host_density_"):
            species = feature_name[len("host_density_") :]
            family_key = HOST_DENSITY_SPECIES_TO_FEATURE_FAMILY.get(species)
            return by_family.get(family_key) if family_key else None
        if feature_name.startswith("landcover_"):
            return by_family.get("land_cover_class_fractions")
        if feature_name == "distance_to_nearest_river_km":
            return by_family.get("distance_to_nearest_river_km")
        return None

    registry: list[dict] = []
    for feature_name in sorted(set(eligible_features) | set(unavailable_features)):
        source_row = _match_family_row(feature_name)
        is_unavailable = feature_name in unavailable_features
        registry.append({
            "feature_name": feature_name,
            "feature_family": _feature_family(feature_name),
            "source": source_row["source"] if source_row else "UNKNOWN_SOURCE",
            "temporal_availability_rule": (
                "HISTORICAL_REANALYSIS, strictly pre-t0 (backward-looking window ending at t0)"
                if feature_name.startswith("weather_")
                else "STATIC_REFERENCE_PROXY, time-invariant / single reference year (available regardless of t0)"
            ),
            "static_or_dynamic": "dynamic" if feature_name.startswith("weather_") else "static",
            "reference_year_if_static": (
                None if feature_name.startswith("weather_")
                else ("2015" if feature_name.startswith("host_density_") else
                      ("2020_or_2021" if feature_name.startswith("landcover_") else None))
            ),
            "missingness": (
                "FEATURE_NOT_AVAILABLE (no validated adapter, never fabricated)"
                if is_unavailable
                else f"{PREDICTOR_STATUS_EXTRACTION_NOT_RUN} (full-corpus FIT_DEVELOPMENT extraction not yet run)"
            ),
            "eligibility_status": (
                "UNAVAILABLE" if is_unavailable
                else (source_row["status"] if source_row else "ELIGIBLE_CANDIDATE")
            ),
            "exclusion_reason": (
                (source_row["coverage_note"] if source_row else "no validated adapter integrated")
                if is_unavailable else None
            ),
            "leakage_risk": "NONE -- feature value never derives from D1-D7 target/outcome information",
        })
    return registry


def build_fmd07a_development_feature_matrix(
    all_origins: list[ForecastOrigin],
    risk_label_rows: list[dict],
    eligible_predictor_features: list[str],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[dict]:
    """Section 11: ONE ROW PER FORECAST ORIGIN, joined to the frozen
    FMD-06D labels by `forecast_origin_id` only. Firewalled independently
    of the label file's own recorded role (Section 15) -- every label row
    is re-classified here via `classify_origin_role`, never trusting the
    row's own `model_fitting_role` field; a `HELD_OUT_FROM_MODEL_FITTING`
    or `SRI_LANKA_TRANSFER_CASE_STUDY` origin is rejected in full before
    any predictor/label join, and no feature row is ever generated for one.

    Predictor columns are schema-complete but VALUE-PENDING (Section 11's
    module docstring) -- populated deterministically as
    `EXTRACTION_NOT_RUN`, never fabricated. Metadata/label/audit-only
    columns are real, sourced unchanged from the frozen label file."""
    origin_by_id = {origin.forecast_origin_id: origin for origin in all_origins}

    offending: list[tuple[str, str]] = []
    for row in risk_label_rows:
        origin = origin_by_id.get(row["forecast_origin_id"])
        if origin is None:
            offending.append((row["forecast_origin_id"], "UNKNOWN_ORIGIN"))
            continue
        role = classify_origin_role(origin, cutoff=cutoff)
        if role != FIT_DEVELOPMENT:
            offending.append((row["forecast_origin_id"], role))
    if offending:
        raise ValueError(
            "build_fmd07a_development_feature_matrix: received "
            f"{len(offending)} non-FIT_DEVELOPMENT label row(s), rejected before any predictor/label "
            f"join -- held-out and Sri Lanka outcomes must never enter this matrix: {offending[:5]}"
        )

    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="build_fmd07a_development_feature_matrix")
    fit_ids = {origin.forecast_origin_id for origin in fit_origins}
    label_ids = {row["forecast_origin_id"] for row in risk_label_rows}
    if fit_ids != label_ids:
        missing = sorted(fit_ids - label_ids)
        extra = sorted(label_ids - fit_ids)
        raise ValueError(
            "build_fmd07a_development_feature_matrix: FIT_DEVELOPMENT origins do not exactly match the "
            f"frozen risk-label rows -- {len(missing)} missing (e.g. {missing[:5]}), {len(extra)} extra "
            f"(e.g. {extra[:5]})"
        )

    rows: list[dict] = []
    for label_row in sorted(risk_label_rows, key=lambda r: r["forecast_origin_id"]):
        matrix_row = {
            "forecast_origin_id": label_row["forecast_origin_id"],
            "country": label_row["country"],
            "t0": label_row["t0"],
            "model_fitting_role": label_row["model_fitting_role"],
            "risk_target_label": label_row["risk_target_label"],
        }
        for audit_column, source_column in _LABEL_TO_AUDIT_COLUMN.items():
            matrix_row[audit_column] = label_row[source_column]
        for feature_name in eligible_predictor_features:
            matrix_row[f"{feature_name}_value"] = ""
            matrix_row[f"{feature_name}_status"] = PREDICTOR_STATUS_EXTRACTION_NOT_RUN
        rows.append(matrix_row)
    return rows


def matrix_fieldnames(eligible_predictor_features: list[str]) -> list[str]:
    fieldnames = list(IDENTIFIER_COLUMNS) + list(METADATA_COLUMNS) + [TARGET_COLUMN] + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
    for feature_name in eligible_predictor_features:
        fieldnames.append(f"{feature_name}_value")
        fieldnames.append(f"{feature_name}_status")
    return fieldnames


def predictor_columns(eligible_predictor_features: list[str]) -> list[str]:
    columns: list[str] = []
    for feature_name in eligible_predictor_features:
        columns.append(f"{feature_name}_value")
        columns.append(f"{feature_name}_status")
    return columns


def audit_predictor_columns_for_leakage(columns: list[str]) -> dict:
    """Section 16: a permanent structural guard, never a per-run
    coincidence -- no real eligible feature name can ever contain one of
    the prohibited outcome-derived substrings."""
    violations = [name for name in columns if any(term in name for term in PROHIBITED_PREDICTOR_SUBSTRINGS)]
    return {
        "predictor_leakage_status": "BLOCKED" if violations else "PASS",
        "violating_columns": violations,
    }


def _quantile_bool_true(rows: list[dict], column: str) -> int:
    return sum(1 for row in rows if row[column] == "True")


def build_fmd07a_feature_matrix_audit(
    matrix_rows: list[dict],
    eligible_predictor_features: list[str],
    unavailable_predictor_features: list[str],
) -> dict:
    """Section 12's exact minimum content."""
    row_count = len(matrix_rows)
    unique_origins = len({row["forecast_origin_id"] for row in matrix_rows})
    positive_count = sum(1 for row in matrix_rows if row["risk_target_label"] == "1")
    negative_count = sum(1 for row in matrix_rows if row["risk_target_label"] == "0")

    metadata_columns = list(IDENTIFIER_COLUMNS) + list(METADATA_COLUMNS) + [TARGET_COLUMN] + list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS)
    predictor_cols = predictor_columns(eligible_predictor_features)
    leakage = audit_predictor_columns_for_leakage(predictor_cols)

    missingness_by_predictor = {}
    for feature_name in eligible_predictor_features:
        status_col = f"{feature_name}_status"
        statuses = Counter(row[status_col] for row in matrix_rows)
        missingness_by_predictor[feature_name] = {
            "missing_fraction": round(statuses.get(PREDICTOR_STATUS_EXTRACTION_NOT_RUN, 0) / row_count, 6) if row_count else None,
            "status_counts": dict(statuses),
        }

    constant_columns = []
    for column in metadata_columns:
        if column == "forecast_origin_id":
            continue
        values = {row[column] for row in matrix_rows}
        if len(values) == 1:
            constant_columns.append(column)
    for feature_name in eligible_predictor_features:
        value_col = f"{feature_name}_value"
        if len({row[value_col] for row in matrix_rows}) == 1:
            constant_columns.append(value_col)

    feature_family_counts = Counter(_feature_family(name) for name in eligible_predictor_features)

    countries = sorted({row["country"] for row in matrix_rows})
    t0_values = sorted(row["t0"] for row in matrix_rows)

    return {
        "checkpoint": CHECKPOINT,
        "row_count": row_count,
        "unique_origin_count": unique_origins,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "reconciliation_ok": positive_count + negative_count == row_count == 3761,
        "feature_count_total": len(eligible_predictor_features) + len(unavailable_predictor_features),
        "predictor_feature_count": len(eligible_predictor_features),
        "predictor_column_count": len(predictor_cols),
        "metadata_column_count": len(metadata_columns),
        "excluded_feature_count": len(unavailable_predictor_features),
        "predictor_feature_names": eligible_predictor_features,
        "excluded_non_predictor_feature_names_and_reasons": {
            name: "UNAVAILABLE: no validated adapter integrated (see FMD_FEATURE_ELIGIBILITY.csv)"
            for name in unavailable_predictor_features
        },
        "feature_family_counts": dict(sorted(feature_family_counts.items())),
        "missingness_by_predictor": missingness_by_predictor,
        "constant_columns": sorted(constant_columns),
        "near_constant_columns": "NO_REPOSITORY_NEAR_CONSTANT_RULE_DEFINED",
        "duplicate_columns": [],
        "categorical_numeric_types": {
            "identifier_columns": "string",
            "metadata_columns": "string/categorical",
            "target_column": "binary_int_as_string",
            "non_predictor_audit_only_columns": "string/categorical",
            "predictor_value_columns": "numeric_or_null (all null pending extraction)",
            "predictor_status_columns": "categorical",
        },
        "date_range": {"min_t0": t0_values[0] if t0_values else None, "max_t0": t0_values[-1] if t0_values else None},
        "country_coverage_count": len(countries),
        "temporal_availability_validation_result": "PASS -- no predictor value is populated yet, so none can carry post-t0 information; weather features are defined strictly pre-t0 by construction once extracted (FEATURE_ASSEMBLY_PROTOCOL.md sec 6)",
        "label_leakage_audit_status": leakage["predictor_leakage_status"],
        "label_leakage_violating_columns": leakage["violating_columns"],
        "held_out_rows_present": False,
        "sri_lanka_rows_present": False,
        "predictor_value_population_status": "EXTRACTION_NOT_RUN_FULL_CORPUS",
        "predictor_value_population_note": (
            "Every eligible predictor requires the FMD-04 remote-adapter extraction pipeline (ERA5/GLW4/"
            "WorldCover/HydroRIVERS), which has only been run on a 29-event adapter-validation sample -- "
            "never fabricated here. See local_data/processed/fmd/features/FMD_FEATURE_AUDIT.md."
        ),
    }


def build_fmd07a_model_input_schema(
    eligible_predictor_features: list[str],
    unavailable_predictor_features: list[str],
) -> dict:
    """Section 13's exact minimum content."""
    predictor_cols = predictor_columns(eligible_predictor_features)
    return {
        "checkpoint": CHECKPOINT,
        "identifier_columns": list(IDENTIFIER_COLUMNS),
        "metadata_columns": list(METADATA_COLUMNS),
        "non_predictor_audit_only_columns": list(NON_PREDICTOR_AUDIT_ONLY_COLUMNS),
        "target_column": TARGET_COLUMN,
        "predictor_columns_ordered": predictor_cols,
        "predictor_dtypes": {
            f"{name}_value": "float64_or_null" for name in eligible_predictor_features
        } | {
            f"{name}_status": "categorical_string" for name in eligible_predictor_features
        },
        "predictor_feature_family": {name: _feature_family(name) for name in eligible_predictor_features},
        "excluded_unavailable_features": unavailable_predictor_features,
        "transformation_responsibility": {
            "imputation": "FMD-07B, train-fold-only -- never globally prefit (FMD_EVALUATION_PROTOCOL.md sec 2)",
            "scaling_normalization": "FMD-07B, train-fold-only",
            "encoding": "FMD-07B, train-fold-only",
            "feature_selection": "FMD-07B, FIT_DEVELOPMENT folds only (FMD_EVALUATION_PROTOCOL.md sec 2)",
            "dimensionality_reduction": "FMD-07B, train-fold-only, if used",
            "imbalance_treatment": "FMD-07B, FIT_DEVELOPMENT only, if motivated (natural balance 58.9%/41.1%, not severely imbalanced)",
            "probability_calibration": "FMD-07B, train-fold-only; Brier score + reliability curve required before any 'probability' claim (FMD_EVALUATION_PROTOCOL.md sec 5)",
        },
        "missing_value_handling_responsibility": (
            "UNAVAILABLE feature families are permanently excluded, never imputed into existence "
            "(FMD_EVALUATION_PROTOCOL.md sec 2). Per-row MISSING/BLOCKED values on an eligible feature "
            "are never zero-filled or globally imputed; any imputation is FMD-07B's train-fold-only "
            "responsibility."
        ),
        "availability_at_t0_rule": (
            "Every predictor must be derivable from information timestamped <= t0 (Section 6). Dynamic "
            "weather features are backward-looking windows ending at t0 (never crossing it, "
            "FEATURE_ASSEMBLY_PROTOCOL.md sec 6). Static features (elevation/host-density/land-cover/"
            "hydrology) are time-invariant or single-reference-year proxies, available regardless of t0."
        ),
    }


def verify_fmd07a_cv_folds(
    fold_rows: list[dict],
    exposure_rows: list[dict],
    risk_label_rows: list[dict],
) -> dict:
    """Section 4: verifies (never regenerates) the existing frozen
    `fmd_calendar_year_folds.json` -- train dates precede validation dates,
    purge/embargo is respected (a fold's own `purged_origin_ids` field is
    reused, never recomputed), no origin appears in both train and
    validation within one fold, no held-out/Sri-Lanka origin appears
    anywhere, and every fold with insufficient training history or a
    single-class validation set is reported explicitly, never silently
    dropped."""
    role_by_id = {row["forecast_origin_id"]: row["role"] for row in exposure_rows}
    label_by_id = {row["forecast_origin_id"]: row["risk_target_label"] for row in risk_label_rows}

    overlap_violations: list[str] = []
    role_violations: list[tuple[str, str, str]] = []
    date_order_violations: list[str] = []
    insufficient_folds: list[dict] = []

    for fold in fold_rows:
        train_ids = set(fold["training_origin_ids"])
        val_ids = set(fold["validation_origin_ids"])
        purged_ids = set(fold["purged_origin_ids"])

        if train_ids & val_ids:
            overlap_violations.append(fold["fold_id"])

        for origin_id in train_ids | val_ids | purged_ids:
            role = role_by_id.get(origin_id)
            if role != FIT_DEVELOPMENT:
                role_violations.append((fold["fold_id"], origin_id, str(role)))

        if not (fold["training_date_range_end"] <= fold["validation_date_range_start"]):
            date_order_violations.append(fold["fold_id"])

        val_labels = [label_by_id.get(origin_id) for origin_id in val_ids]
        n_positive = sum(1 for label in val_labels if label == "1")
        n_negative = sum(1 for label in val_labels if label == "0")
        reasons = []
        if not train_ids:
            reasons.append("INSUFFICIENT_PRIOR_TRAINING_HISTORY")
        if not val_ids:
            reasons.append("EMPTY_VALIDATION_SET")
        elif n_positive == 0:
            reasons.append("NO_POSITIVE_CLASS_IN_VALIDATION")
        elif n_negative == 0:
            reasons.append("NO_NEGATIVE_CLASS_IN_VALIDATION")
        if reasons:
            insufficient_folds.append({
                "fold_id": fold["fold_id"],
                "training_origin_count": len(train_ids),
                "validation_origin_count": len(val_ids),
                "validation_positive_count": n_positive,
                "validation_negative_count": n_negative,
                "reasons": reasons,
            })

    return {
        "fold_count": len(fold_rows),
        "overlap_violations": overlap_violations,
        "role_violations": role_violations,
        "date_order_violations": date_order_violations,
        "insufficient_folds": insufficient_folds,
        "usable_fold_count": len(fold_rows) - len(insufficient_folds),
        "verification_status": (
            "PASS"
            if not (overlap_violations or role_violations or date_order_violations)
            else "FAIL"
        ),
    }


def build_fmd07a_development_protocol_freeze(experiment_registry: dict, cv_fold_verification: dict | None = None) -> dict:
    """Section 14: exact, pre-existing values only -- every genuinely
    unresolved item is marked `UNRESOLVED_PROTOCOL_GAP`, never populated by
    guess (Section 3)."""
    experiments = experiment_registry.get("experiments", [])
    candidate_model_families = [
        {
            "experiment_id": experiment["experiment_id"],
            "model_family": experiment["model_family"],
            "status": experiment["status"],
        }
        for experiment in experiments
        if experiment.get("task") == "RISK" and experiment.get("cohort", "").startswith("FIT_DEVELOPMENT")
    ]

    hyperparameter_candidates = {
        "FMD-EXP-01_naive_statistical_baseline": {
            "status": "FULLY_SPECIFIED",
            "definition": (
                "historical FMD occurrence rate/prevalence per country (FIT_DEVELOPMENT only), a "
                "persistence-style baseline ('risk today ~ risk in the immediately preceding period at "
                "this origin's country') -- no hyperparameters to search"
            ),
            "source": "FMD_EVALUATION_PROTOCOL.md sec 6 item 1",
        },
        "FMD-EXP-02_spatial_distance_baseline": {
            "status": "PARTIALLY_SPECIFIED",
            "mechanism": (
                "services/model_development/baseline_registry.py B0_DISTANCE_ONLY/B1_HOST_DISTANCE_LOG1P/"
                "B2_HOST_DISTANCE_ECDF x kernel family EXPONENTIAL/GAUSSIAN (services/hazard/kernels.py) "
                "-- reused mechanism, 'refit from FMD FIT_DEVELOPMENT data, never LSD's fitted C0 "
                "candidate' (FMD_EVALUATION_PROTOCOL.md sec 6 item 2)"
            ),
            "kernel_scale_candidates_km": "FMD07_PROTOCOL_GAP_SPATIAL_BASELINE_KERNEL_SCALE_CANDIDATES",
            "gap_detail": (
                "LSD's own KERNEL_SCALE_CANDIDATES_KM=(5.0,10.0,15.0,25.0) (BASELINE_MODEL_DEVELOPMENT_"
                "PROTOCOL.md sec 5) is tied to LSD's own PRIMARY_LOCAL_EVALUATION_DISTANCE_KM=25.0 "
                "literature-derived envelope -- not transferable to FMD's own, differently-derived, "
                "200.0km POST_FEASIBILITY_PROTOCOL_AMENDMENT local domain without a new, deliberate, "
                "FMD-specific kernel-scale candidate freeze. No such freeze exists yet."
            ),
        },
        "FMD-EXP-03_pistes_hazard_model": {
            "status": "PARTIALLY_SPECIFIED",
            "definition": (
                "disease-agnostic hazard-engine mathematics (HAZARD_ENGINE_PROTOCOL.md) with FMD-06-"
                "calibrated ST-DBSCAN parameters (eps_space_km=0.236038, eps_time_days=13.5, "
                "min_core_supports=4 -- frozen, never LSD-copied)"
            ),
            "coefficient_candidates": "FMD07_PROTOCOL_GAP_PISTES_HAZARD_COEFFICIENT_CANDIDATES",
            "gap_detail": (
                "source_strength_factor/environmental_suitability_factor/water_context_factor all remain "
                "NOT_YET_SCIENTIFICALLY_DEFINED (FEATURE_ASSEMBLY_PROTOCOL.md Checkpoint 6C/6D) -- no "
                "candidate coefficient/kernel-scale registry exists for the full PISTES equation."
            ),
        },
        "FMD-EXP-04_ml_candidate": {
            "status": "UNRESOLVED_PROTOCOL_GAP",
            "gap_name": "FMD07_PROTOCOL_GAP_ML_CANDIDATE_HYPERPARAMETER_SPACE",
            "gap_detail": (
                "'architecture unspecified here, deliberately' (FMD_EVALUATION_PROTOCOL.md sec 6 item 4) "
                "-- no algorithm family or hyperparameter search space is frozen anywhere in the repository."
            ),
        },
        "FMD-EXP-05_hybrid_candidate": {
            "status": "UNRESOLVED_PROTOCOL_GAP",
            "gap_name": "FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE",
            "gap_detail": (
                "'architecture unspecified' (FMD_EVALUATION_PROTOCOL.md sec 6 item 5); depends on both "
                "FMD-EXP-03's and FMD-EXP-04's own unresolved candidate spaces."
            ),
        },
    }

    return {
        "checkpoint": CHECKPOINT,
        "candidate_model_families": candidate_model_families,
        "hyperparameter_candidates": hyperparameter_candidates,
        "primary_selection_metric": {
            "value": "PR-AUC",
            "source": "FMD_EVALUATION_PROTOCOL.md sec 5 (table row 'Primary'); FMD_EXPERIMENT_REGISTRY.json every experiment's primary_metric",
        },
        "secondary_metrics": {
            "value": ["sensitivity_recall", "specificity", "precision", "F1", "Brier_score", "reliability_calibration_curve", "AUROC"],
            "source": "FMD_EVALUATION_PROTOCOL.md sec 5",
        },
        "weather_window_candidates": {
            "value": ["event_day", "window_3day", "window_7day", "window_14day"],
            "status": "CANDIDATES_ONLY_NO_WINNER_SELECTED",
            "source": "FMD_FEATURE_ELIGIBILITY.csv; FMD_EVALUATION_PROTOCOL.md sec 3",
        },
        "cv_scheme": {
            "value": "calendar-year expanding-window folds (23 real folds, years 2002-2025)",
            "source": "FMD_SPLIT_PROTOCOL.md sec 5; services.model_fitting_exposure.build_calendar_year_folds; local_data/processed/fmd/cohort/fmd_calendar_year_folds.json",
            "verification": cv_fold_verification,
        },
        "purge_embargo": {
            "value": "PURGED_7_DAY_HORIZON_POLICY: a development origin is eligible for the earlier partition only when t0 + 7 < boundary; otherwise purged, never clipped-and-kept",
            "source": "services/split_embargo.py; VALIDATION_PROTOCOL.md sec 2; FMD_SPLIT_PROTOCOL.md sec 5",
        },
        "inner_outer_selection_responsibility": {
            "value": "OUTER = calendar-year expanding-window walk-forward folds; INNER = nested chronological validation inside each development fold for any parameter tuning (e.g. weather-window selection), never substituting for the outer structure and never touching held-out/Sri-Lanka data",
            "source": "VALIDATION_PROTOCOL.md sec 1; FMD_EVALUATION_PROTOCOL.md sec 3",
        },
        "threshold_policy": {
            "value": "decision threshold selected on FIT_DEVELOPMENT/validation folds only -- no specific numeric threshold frozen yet (none should be, before a model exists)",
            "source": "FMD_EVALUATION_PROTOCOL.md sec 5",
        },
        "probability_calibration_policy": {
            "value": "Brier score + reliability/calibration curve REQUIRED before any risk score is described as a 'probability'; the calibration FITTING method itself is not prescribed and is FMD-07B's train-fold-only responsibility",
            "source": "FMD_EVALUATION_PROTOCOL.md sec 5",
        },
        "imbalance_policy": {
            "value": "class-balancing/weighting decisions, if motivated, must be derived from FIT_DEVELOPMENT data only; natural class balance is now known (2,215 positive / 1,546 negative = 58.9%/41.1%, not severely imbalanced) -- no specific technique is mandated",
            "source": "FMD_EVALUATION_PROTOCOL.md sec 2; local_data/processed/fmd/calibration/fmd06_calibration_manifest.json",
        },
        "preprocessing_policy": {
            "value": "any learned preprocessing parameter (scaler mean/std, imputation median/mode, encoding) must be fit on FIT_DEVELOPMENT data only, then applied unchanged to held-out/Sri-Lanka rows; UNAVAILABLE features are never imputed into existence",
            "source": "FMD_EVALUATION_PROTOCOL.md sec 2",
        },
        "unresolved_protocol_gap_count": sum(
            1 for entry in hyperparameter_candidates.values()
            if entry["status"] in ("UNRESOLVED_PROTOCOL_GAP",) or "gap_detail" in entry
        ),
    }


def run_fmd07a(
    origins_csv_path: str | Path,
    risk_labels_csv_path: str | Path,
    feature_eligibility_csv_path: str | Path,
    feature_table_csv_path: str | Path,
    experiment_registry_json_path: str | Path,
    calendar_year_folds_json_path: str | Path,
    exposure_manifest_csv_path: str | Path,
    out_dir: str | Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> dict:
    """Builds all four FMD-07A artifacts deterministically. Never trains a
    model, never selects a hyperparameter, never computes a predictive
    metric."""
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    all_origins = load_forecast_origins(origins_csv_path)
    risk_label_rows = load_fmd07a_risk_labels(risk_labels_csv_path)
    eligible_features, unavailable_features = derive_eligible_predictor_features(feature_table_csv_path)

    # Defense-in-depth: the frozen FMD-06 spatial provenance carried on
    # every label row must match the module's own frozen constants -- a
    # drifted/edited label file is rejected here rather than silently
    # propagated into the FMD-07A matrix.
    for row in risk_label_rows:
        if float(row["local_evaluation_radius_km"]) != FMD_SPATIAL_EVALUATION_RADIUS_KM:
            raise ValueError(
                f"run_fmd07a: label row {row['forecast_origin_id']} carries "
                f"local_evaluation_radius_km={row['local_evaluation_radius_km']!r}, expected "
                f"{FMD_SPATIAL_EVALUATION_RADIUS_KM}"
            )
        if row["spatial_protocol_amendment_status"] != SPATIAL_PROTOCOL_AMENDMENT_STATUS:
            raise ValueError(
                f"run_fmd07a: label row {row['forecast_origin_id']} carries "
                f"spatial_protocol_amendment_status={row['spatial_protocol_amendment_status']!r}, expected "
                f"{SPATIAL_PROTOCOL_AMENDMENT_STATUS!r}"
            )
        if row["spatial_reference_source_set"] != SPATIAL_REFERENCE_SOURCE_SET:
            raise ValueError(
                f"run_fmd07a: label row {row['forecast_origin_id']} carries "
                f"spatial_reference_source_set={row['spatial_reference_source_set']!r}, expected "
                f"{SPATIAL_REFERENCE_SOURCE_SET!r}"
            )

    matrix_rows = build_fmd07a_development_feature_matrix(
        all_origins, risk_label_rows, eligible_features, cutoff=cutoff,
    )
    fieldnames = matrix_fieldnames(eligible_features)
    matrix_path = output / "fmd07_development_feature_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matrix_rows)

    eligibility_registry = build_fmd07a_feature_eligibility_registry(
        feature_eligibility_csv_path, eligible_features, unavailable_features,
    )
    audit = build_fmd07a_feature_matrix_audit(matrix_rows, eligible_features, unavailable_features)
    audit["feature_eligibility_registry"] = eligibility_registry
    audit_path = output / "fmd07_feature_matrix_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")

    schema = build_fmd07a_model_input_schema(eligible_features, unavailable_features)
    schema_path = output / "fmd07_model_input_schema.json"
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")

    experiment_registry = json.loads(Path(experiment_registry_json_path).read_text(encoding="utf-8"))
    fold_rows = json.loads(Path(calendar_year_folds_json_path).read_text(encoding="utf-8"))
    exposure_rows = _csv_rows(Path(exposure_manifest_csv_path))
    cv_fold_verification = verify_fmd07a_cv_folds(fold_rows, exposure_rows, risk_label_rows)
    protocol = build_fmd07a_development_protocol_freeze(experiment_registry, cv_fold_verification)
    protocol_path = output / "fmd07_development_protocol.json"
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True), encoding="utf-8")

    artifact_names = [
        "fmd07_development_feature_matrix.csv",
        "fmd07_feature_matrix_audit.json",
        "fmd07_model_input_schema.json",
        "fmd07_development_protocol.json",
    ]
    provenance = {
        "checkpoint": CHECKPOINT,
        "overall_status": "BLOCKED_PENDING_FULL_CORPUS_FEATURE_EXTRACTION",
        "blocker": (
            "Every eligible predictor feature requires the FMD-04 remote-adapter extraction pipeline, "
            "which has only been run on a 29-event validation sample. Full-corpus FIT_DEVELOPMENT "
            "extraction (3,761 origins) has never been run and is infeasible as an unattended in-session "
            "operation (~15,000+ live weather requests alone). No predictor value is fabricated; the "
            "development feature matrix is a real, deterministic, leakage-safe SCHEMA freeze only."
        ),
        "secondary_blockers": [
            "FMD07_PROTOCOL_GAP_SPATIAL_BASELINE_KERNEL_SCALE_CANDIDATES",
            "FMD07_PROTOCOL_GAP_PISTES_HAZARD_COEFFICIENT_CANDIDATES",
            "FMD07_PROTOCOL_GAP_ML_CANDIDATE_HYPERPARAMETER_SPACE",
            "FMD07_PROTOCOL_GAP_HYBRID_CANDIDATE_HYPERPARAMETER_SPACE",
        ],
        "artifact_sha256": {name: _sha256(output / name) for name in artifact_names},
    }
    provenance_path = output / "fmd07a_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "matrix_rows": matrix_rows,
        "audit": audit,
        "schema": schema,
        "protocol": protocol,
        "provenance": provenance,
    }

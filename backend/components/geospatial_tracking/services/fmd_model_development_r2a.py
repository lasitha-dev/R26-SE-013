"""FMD-07A-R2A: transparent pre-extraction forecast-origin feature-assembly
protocol amendment and freeze.

**`PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT`** -- explicitly
NOT preregistered. FMD-07A-R2 found (`fmd07a_r2_origin_feature_assembly_
audit.json`, preserved unchanged) that no pre-existing rule mapped
event/source-level feature values into one forecast-origin predictor row.
This module freezes that rule, introduced AFTER the R2 preflight and
BEFORE any full-corpus remote extraction or predictive model.

The primary modelling unit remains ONE FORECAST ORIGIN. Source events are
feature-construction inputs only, never independent model rows.

No network call is made anywhere in this module -- it operates only on
already-existing local source-selection code
(`services.source_selector.get_eligible_sources`) and, for aggregation
itself, on already-existing or synthetic source-level feature records
supplied by the caller.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..data_processing.fmd_feature_status import ALL_STATUSES, SOURCE_VALUE_AVAILABLE
from ..domain.enums import RecordDomainScope
from ..schemas import ValidationMode
from .source_selector import EligibleSource, get_eligible_sources

CHECKPOINT = "FMD-07A-R2A"
AMENDMENT_STATUS = "PRE_EXTRACTION_ORIGIN_FEATURE_ASSEMBLY_PROTOCOL_AMENDMENT"
ORIGINAL_R2_STATUS = "FORECAST_ORIGIN_FEATURE_ASSEMBLY_RULE_UNDEFINED"

PRIMARY_MODEL_UNIT = "FORECAST_ORIGIN"
SOURCE_SET_DEFINITION = "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
FROZEN_ACTIVE_WINDOW_DAYS = 14  # FMD-06B-R calibrated value -- read from the frozen manifest at runtime, never redeclared as a second source of truth
SOURCE_SPATIAL_REFERENCE = "SOURCE_EVENT_OWN_COORDINATE"
CENTROID_USED = False
TRIGGER_ONLY_USED = False
NUMERIC_AGGREGATION_RULE = "UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES"

ORIGIN_AGGREGATE_ALL_VALID = "ORIGIN_AGGREGATE_ALL_VALID"
ORIGIN_AGGREGATE_PARTIAL_VALID = "ORIGIN_AGGREGATE_PARTIAL_VALID"
ORIGIN_AGGREGATE_NO_VALID_VALUE = "ORIGIN_AGGREGATE_NO_VALID_VALUE"
NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0 = "NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0"

FMD07_FEATURE_VALUE_STATUS = "FULL_CORPUS_EXTRACTION_NOT_RUN"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Section 4: frozen source set (thin wrapper over the already-frozen
# FMD source-selection implementation -- no new filtering logic).
# ---------------------------------------------------------------------------


def get_eligible_active_sources_for_origin(
    repo, *, disease: str, t0: str, country: str, active_window_days: int = FROZEN_ACTIVE_WINDOW_DAYS,
) -> list[EligibleSource]:
    """`ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0` for one forecast origin --
    reuses `source_selector.get_eligible_sources` unchanged (the same
    call signature FMD-06's own `build_fmd06c_spatial_target_distance_audit`
    and `services/model_development/domain_design.py` use). Inclusive
    `t0 - active_window_days <= effective_availability_date <= t0`
    boundary is enforced entirely by that existing, frozen implementation
    -- never re-implemented here."""
    result = get_eligible_sources(
        repo, disease=disease, t0=t0, active_window_days=active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=country,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    return result.sources


# ---------------------------------------------------------------------------
# Section 5: deduplication by canonical source identity.
# ---------------------------------------------------------------------------


def deduplicate_sources_by_canonical_id(source_records: list[dict], *, id_field: str = "source_id") -> list[dict]:
    """The SAME real event/source must never receive multiple weight
    merely because it appears more than once in the supplied list. Keeps
    the FIRST occurrence per canonical id (`source_id`, i.e. the
    repository's own `source_record_id` -- `EligibleSource.source_id`,
    `source_selector.py`), never invents a new identity field."""
    seen: dict[str, dict] = {}
    for record in source_records:
        key = record[id_field]
        if key not in seen:
            seen[key] = record
    return list(seen.values())


# ---------------------------------------------------------------------------
# Sections 8-12: the frozen numeric aggregation rule.
# ---------------------------------------------------------------------------


def aggregate_origin_feature_status(total_source_count: int, valid_source_count: int) -> str:
    """Pure status-decision helper (Section 10 A/B/C + Section 12)."""
    if total_source_count == 0:
        return NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0
    if valid_source_count == 0:
        return ORIGIN_AGGREGATE_NO_VALID_VALUE
    if valid_source_count == total_source_count:
        return ORIGIN_AGGREGATE_ALL_VALID
    return ORIGIN_AGGREGATE_PARTIAL_VALID


def aggregate_source_feature_values_for_origin(
    source_records: list[dict], feature_name: str, *, id_field: str = "source_id",
) -> dict:
    """Section 8: `x_o,f = mean(x_s,f for every unique eligible active
    source s at t0 having a valid numeric value for feature f)` --
    UNWEIGHTED_ARITHMETIC_MEAN_OF_VALID_ACTIVE_SOURCE_VALUES. Every valid
    source contributes exactly `1/N_valid` weight; no label/target/
    distance/DQS/recency/cluster/learned weighting of any kind. Never
    reads any key other than `id_field` and
    `{feature_name}_value`/`{feature_name}_status` -- a `risk_target_label`
    or any other key present on a source record is silently ignored by
    construction (Section 14 firewall).

    Deterministic regardless of input order (Section 19 items 15-16):
    sources are deduplicated then sorted by their own canonical id before
    summation, so the same set always sums in the same order."""
    value_key = f"{feature_name}_value"
    status_key = f"{feature_name}_status"

    deduped = deduplicate_sources_by_canonical_id(source_records, id_field=id_field)
    deduped_sorted = sorted(deduped, key=lambda record: record[id_field])

    total = len(deduped_sorted)
    valid_values: list[float] = []
    underlying_status_counts: dict[str, int] = {}
    for record in deduped_sorted:
        status = record[status_key]
        underlying_status_counts[status] = underlying_status_counts.get(status, 0) + 1
        if status == SOURCE_VALUE_AVAILABLE:
            raw_value = record[value_key]
            if raw_value is None or raw_value == "":
                raise ValueError(
                    f"aggregate_source_feature_values_for_origin: source {record[id_field]!r} feature "
                    f"{feature_name!r} has status={SOURCE_VALUE_AVAILABLE!r} but no numeric value -- "
                    "SOURCE_VALUE_AVAILABLE must always carry a real value (fmd_feature_status.py contract)"
                )
            valid_values.append(float(raw_value))

    n_valid = len(valid_values)
    n_invalid = total - n_valid
    status = aggregate_origin_feature_status(total, n_valid)
    value = (sum(valid_values) / n_valid) if n_valid else None

    return {
        "value": value,
        "status": status,
        "total_source_count": total,
        "valid_source_count": n_valid,
        "invalid_source_count": n_invalid,
        "valid_source_fraction": round(n_valid / total, 6) if total else None,
        "underlying_status_counts": underlying_status_counts,
    }


def build_origin_feature_row_from_source_features(
    forecast_origin_id: str, source_records: list[dict], eligible_predictor_features: list[str], *, id_field: str = "source_id",
) -> dict:
    """Applies `aggregate_source_feature_values_for_origin` identically to
    every eligible predictor feature (Section 9 -- weather, elevation,
    host density, land cover, and hydrology all use the SAME generic
    rule; none is special-cased). Produces exactly ONE forecast-origin
    predictor row (Section 3) -- `source_records` (however many sources)
    are feature-construction inputs only, never independent output rows."""
    row: dict = {"forecast_origin_id": forecast_origin_id}
    audit: dict = {}
    for feature_name in eligible_predictor_features:
        result = aggregate_source_feature_values_for_origin(source_records, feature_name, id_field=id_field)
        row[f"{feature_name}_value"] = result["value"] if result["value"] is not None else ""
        row[f"{feature_name}_status"] = result["status"]
        audit[feature_name] = {
            "total_source_count": result["total_source_count"],
            "valid_source_count": result["valid_source_count"],
            "invalid_source_count": result["invalid_source_count"],
            "valid_source_fraction": result["valid_source_fraction"],
            "underlying_status_counts": result["underlying_status_counts"],
        }
    return {"row": row, "audit": audit}


# ---------------------------------------------------------------------------
# Section 16: machine-readable protocol artifact.
# ---------------------------------------------------------------------------


def build_origin_feature_assembly_protocol(existing_r2_audit: dict, eligible_predictor_features: list[str]) -> dict:
    if existing_r2_audit["overall_rule_status"] != "UNDEFINED" or existing_r2_audit["block_name"] != ORIGINAL_R2_STATUS:
        raise ValueError(
            "build_origin_feature_assembly_protocol: fmd07a_r2_origin_feature_assembly_audit.json's "
            f"overall_rule_status/block_name changed from the expected 'UNDEFINED'/{ORIGINAL_R2_STATUS!r} -- "
            "R2's original finding must be preserved unchanged"
        )
    return {
        "checkpoint": CHECKPOINT,
        "amendment_status": AMENDMENT_STATUS,
        "original_r2_status": ORIGINAL_R2_STATUS,
        "introduced_after_r2_preflight": True,
        "introduced_before_full_feature_extraction": True,
        "introduced_before_any_predictive_model": True,
        "predictive_metrics_used_to_define_rule": False,
        "held_out_outcomes_used": False,
        "sri_lanka_outcomes_used": False,
        "weather_winner_used": False,
        "not_preregistered_statement": (
            "This rule was introduced AFTER FMD-07A-R2 identified the missing semantics and BEFORE "
            "full-corpus feature extraction or model development. It is explicitly NOT preregistered."
        ),
        "primary_model_unit": PRIMARY_MODEL_UNIT,
        "source_set": SOURCE_SET_DEFINITION,
        "active_window_days": FROZEN_ACTIVE_WINDOW_DAYS,
        "source_spatial_reference": SOURCE_SPATIAL_REFERENCE,
        "centroid_used": CENTROID_USED,
        "trigger_only_used": TRIGGER_ONLY_USED,
        "source_deduplication_rule": (
            "Deduplicate by the canonical source identity field 'source_id' "
            "(services.source_selector.EligibleSource.source_id, == the repository's source_record_id) "
            "before aggregation -- the same real event/source never receives multiple weight."
        ),
        "weather_source_level_semantics": (
            "Each eligible active source retains its OWN FMD-04 event-level retrospective weather windows "
            "(event_day/window_3day/window_7day/window_14day, data_processing/build_fmd_features.py "
            "WEATHER_WINDOWS_HOURS, unchanged) -- strictly backward-looking from that source's own "
            "effective_availability_date, which is itself already <= t0 by construction of "
            "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0. No new future date is queried; no weather-window winner is "
            "selected here."
        ),
        "numeric_aggregation_rule": NUMERIC_AGGREGATION_RULE,
        "numeric_aggregation_formula": "x_o,f = mean(x_s,f for every unique eligible active source s at t0 having a valid numeric value for feature f)",
        "missing_value_aggregation_rule": {
            "ORIGIN_AGGREGATE_ALL_VALID": "N_valid == N_total > 0: origin value = arithmetic mean of all source values",
            "ORIGIN_AGGREGATE_PARTIAL_VALID": "0 < N_valid < N_total: origin value = arithmetic mean of VALID values only",
            "ORIGIN_AGGREGATE_NO_VALID_VALUE": "N_valid == 0 < N_total: origin value = blank/null",
            "NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0": "N_total == 0: origin value = blank/null for every predictor; origin row retained, never deleted",
        },
        "aggregate_status_rule": (
            "aggregate_origin_feature_status(total_source_count, valid_source_count) is a pure function of "
            "those two counts only -- never of any label, target, or predictive score."
        ),
        "zero_source_rule": (
            "An origin with zero eligible active sources retains its row; every remote-derived predictor is "
            "blank with status NO_ELIGIBLE_ACTIVE_SOURCE_AT_T0. No centroid or fallback event is fabricated."
        ),
        "trigger_multiplicity_rule": (
            "Trigger status confers no extra weight. A trigger source that is also an eligible active source "
            "enters exactly once (post-deduplication); a non-trigger eligible active source is included on "
            "equal footing. aggregate_source_feature_values_for_origin has no trigger-related parameter at "
            "all -- structurally incapable of trigger-weighting."
        ),
        "predictor_audit_count_fields": ["total_source_count", "valid_source_count", "invalid_source_count", "valid_source_fraction", "underlying_status_counts"],
        "predictor_audit_fields_are_predictors": False,
        "eligible_predictor_feature_count": len(eligible_predictor_features),
        "eligible_predictor_features": eligible_predictor_features,
        "model_trained": False,
        "predictive_metrics_computed": False,
        "weather_winner_selected": False,
        "threshold_selected": False,
        "feature_value_status": FMD07_FEATURE_VALUE_STATUS,
        "provenance": {
            "r2_audit_source": "local_data/processed/fmd/model_development/fmd07a_r2_origin_feature_assembly_audit.json",
            "source_selection_implementation": "services.source_selector.get_eligible_sources (unchanged)",
            "weather_semantics_source": "data_processing/build_fmd_features.py WEATHER_WINDOWS_HOURS (unchanged)",
            "status_vocabulary_source": "data_processing/fmd_feature_status.py (unchanged): " + ", ".join(sorted(ALL_STATUSES)),
            "active_window_days_source": "local_data/processed/fmd/calibration/fmd06_calibration_manifest.json (FMD-06B-R, unchanged)",
        },
        "limitations": [
            "The arithmetic mean is a computational forecast-origin representation, not a biological "
            "transmission equation, a source-strength model, a movement/contact model, or a quarantine "
            "radius. It assumes no scientifically-justified differential source weighting exists yet -- a "
            "future, separately-scoped, explicitly frozen protocol could introduce one if scientific "
            "evidence supports it.",
            "This amendment resolves ASSEMBLY SEMANTICS only. All 47 eligible predictor features remain "
            "FULL_CORPUS_EXTRACTION_NOT_RUN -- no remote extraction occurred in this checkpoint.",
            "Land-cover fractions are averaged independently per class; floating-point summation means the "
            "averaged vector may not sum to exactly 1.0 bit-for-bit (bounded by ordinary float64 tolerance), "
            "never renormalized using label/outcome information.",
        ],
    }


def run_fmd07a_r2a(model_dev_dir: str | Path, eligible_predictor_features: list[str]) -> dict:
    """Reads (never rewrites) the frozen FMD-07A-R2 audit, builds the
    Section 16 protocol artifact, and writes it. Never touches
    `fmd07_development_feature_matrix.csv` or any FMD-06/FMD-07A-R1
    artifact."""
    output = Path(model_dev_dir)
    r2_audit = json.loads((output / "fmd07a_r2_origin_feature_assembly_audit.json").read_text(encoding="utf-8"))
    protocol = build_origin_feature_assembly_protocol(r2_audit, eligible_predictor_features)
    protocol_path = output / "fmd07_origin_feature_assembly_protocol.json"
    protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True), encoding="utf-8")
    return {"protocol": protocol, "protocol_path": str(protocol_path)}

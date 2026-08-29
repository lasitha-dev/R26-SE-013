"""Checkpoint 6D Part 17: water context — raw preserved, factor
undefined.

`distance_to_river` (HydroRIVERS) is preserved as a raw real value, but
`water_context_factor` remains `NOT_YET_SCIENTIFICALLY_DEFINED` — this
checkpoint does NOT assume "closer to river = greater LSD transmission"
and does NOT invent an exponential-decay (or any other) transform
merely because a distance is available. Checkpoint 6C already left the
real mapping undefined; 6D keeps it that way pending a defensible,
pre-registered transformation protocol.
"""

from __future__ import annotations

from .contracts import MISSING, NOT_SELECTED, NOT_YET_SCIENTIFICALLY_DEFINED, RAW_REAL_COMPONENT, TransformedFactorProvenance


def build_water_context_status(*, cell: dict, feature_snapshot_id: str) -> TransformedFactorProvenance:
    hydro = cell.get("hydrology")
    if hydro is None:
        return TransformedFactorProvenance(
            factor_or_component_name="water_context_factor", raw_feature_names=(), raw_values=(), raw_units=(),
            raw_feature_statuses=(), source_dataset_versions=(), feature_snapshot_id=feature_snapshot_id,
            transform_id=None, transform_config_hash=None, reference_profile_hash=None, transformed_value=None,
            candidate_status=NOT_SELECTED, clipping=None,
            notes="hydrology not included in this FeaturePolicy (hydrology_include=False)",
        )

    status = hydro.get("status", MISSING)
    raw_value = hydro.get("value") if status == "REAL" else None
    return TransformedFactorProvenance(
        factor_or_component_name="water_context_factor", raw_feature_names=(hydro.get("feature_name"),),
        raw_values=(raw_value,), raw_units=(hydro.get("units"),), raw_feature_statuses=(status,),
        source_dataset_versions=(hydro.get("dataset_version"),), feature_snapshot_id=feature_snapshot_id,
        transform_id=None, transform_config_hash=None, reference_profile_hash=None, transformed_value=None,
        candidate_status=NOT_YET_SCIENTIFICALLY_DEFINED, clipping=None,
        notes="distance_to_river preserved as raw context only; NEVER automatically converted into a risk factor "
              "-- no 'closer = higher transmission' assumption, no invented exponential decay (6D Part 17)",
    )

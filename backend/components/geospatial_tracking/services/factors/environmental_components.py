"""Checkpoint 6D Parts 13-16: environmental COMPONENT preservation —
never an invented weighted suitability score.

**Critical rule (Part 13)**: this module NEVER constructs something like
`0.3*humidity + 0.3*precipitation + 0.2*temperature + 0.2*landcover`.
It never copies feature-importance/percentage-contribution/odds-ratio
numbers from published literature and uses them as PISTES weights —
literature may justify VARIABLE CANDIDACY, never supply fitted
coefficients. `EnvironmentalComponentVector` preserves each raw
variable as its OWN component; `environmental_suitability_factor`
remains `NOT_YET_SCIENTIFICALLY_DEFINED` in this checkpoint (Part 14,
ENV-07) — no separate aggregation protocol has been approved.

Temperature/humidity/precipitation components are preserved as raw
values (`RAW_REAL_COMPONENT`) — no assumed monotonic direction (higher
temperature/humidity/rain != higher risk) is encoded (Part 15).
Land-cover fractions are preserved individually, never hand-combined
into a suitability rule (Part 16) — WorldCover version/comparability
group travel with them so an incompatible pool is never silently mixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import BLOCKED, MISSING, NOT_YET_SCIENTIFICALLY_DEFINED, RAW_REAL_COMPONENT, TransformedFactorProvenance

_WEATHER_COMPONENT_FEATURES = {
    "temperature_component": "mean_temperature_2m",
    "humidity_component": "mean_relative_humidity_2m",
    "precipitation_component": "precipitation_accumulation",
}


def _raw_component_from_weather(weather_results: dict, *, component_name: str, raw_feature_name: str, feature_snapshot_id: str) -> TransformedFactorProvenance:
    fr = (weather_results or {}).get(raw_feature_name) or {}
    status = fr.get("status", MISSING)
    return TransformedFactorProvenance(
        factor_or_component_name=component_name, raw_feature_names=(raw_feature_name,), raw_values=(fr.get("value"),),
        raw_units=(fr.get("units"),), raw_feature_statuses=(status,), source_dataset_versions=(fr.get("dataset_name"),),
        feature_snapshot_id=feature_snapshot_id, transform_id=None, transform_config_hash=None, reference_profile_hash=None,
        transformed_value=fr.get("value") if status == "REAL" else None,
        candidate_status=RAW_REAL_COMPONENT if status == "REAL" else status,
        clipping=None, notes="raw component preserved -- no assumed monotonic risk direction, never combined into a weighted sum",
    )


def _raw_component_from_landcover(landcover: dict, *, class_name: str, feature_snapshot_id: str) -> TransformedFactorProvenance:
    # `class_name` here is already the full GridCellFeatures.landcover
    # dict key, e.g. "landcover_tree_cover_fraction" (Checkpoint 5/6A
    # naming), not a bare class label.
    fr = landcover.get(class_name) or {}
    status = fr.get("status", MISSING)
    return TransformedFactorProvenance(
        factor_or_component_name=class_name, raw_feature_names=(fr.get("feature_name", class_name),),
        raw_values=(fr.get("value"),), raw_units=(fr.get("units"),), raw_feature_statuses=(status,),
        source_dataset_versions=(fr.get("dataset_version"),), feature_snapshot_id=feature_snapshot_id,
        transform_id=None, transform_config_hash=None, reference_profile_hash=None,
        transformed_value=fr.get("value") if status == "REAL" else None,
        candidate_status=RAW_REAL_COMPONENT if status == "REAL" else status,
        clipping=None, notes="individual WorldCover class fraction preserved -- never hand-combined into a suitability rule",
    )


@dataclass(frozen=True)
class EnvironmentalComponentVector:
    grid_cell_id: str
    temperature_component: TransformedFactorProvenance
    humidity_component: TransformedFactorProvenance
    precipitation_component: TransformedFactorProvenance
    landcover_components: dict  # class_name -> TransformedFactorProvenance
    landcover_comparability_group: str | None
    environmental_suitability_factor_status: str = NOT_YET_SCIENTIFICALLY_DEFINED

    def as_dict(self) -> dict:
        return {
            "grid_cell_id": self.grid_cell_id,
            "temperature_component": self.temperature_component.as_dict(),
            "humidity_component": self.humidity_component.as_dict(),
            "precipitation_component": self.precipitation_component.as_dict(),
            "landcover_components": {k: v.as_dict() for k, v in self.landcover_components.items()},
            "landcover_comparability_group": self.landcover_comparability_group,
            "environmental_suitability_factor_status": self.environmental_suitability_factor_status,
        }


def build_environmental_component_vector(*, cell: dict, snapshot: dict, feature_snapshot_id: str) -> EnvironmentalComponentVector:
    weather_results = (snapshot.get("weather") or {}).get("results") or {}
    landcover = cell.get("landcover") or {}
    return EnvironmentalComponentVector(
        grid_cell_id=cell["grid_cell_id"],
        temperature_component=_raw_component_from_weather(weather_results, component_name="temperature_component", raw_feature_name="mean_temperature_2m", feature_snapshot_id=feature_snapshot_id),
        humidity_component=_raw_component_from_weather(weather_results, component_name="humidity_component", raw_feature_name="mean_relative_humidity_2m", feature_snapshot_id=feature_snapshot_id),
        precipitation_component=_raw_component_from_weather(weather_results, component_name="precipitation_component", raw_feature_name="precipitation_accumulation", feature_snapshot_id=feature_snapshot_id),
        landcover_components={class_name: _raw_component_from_landcover(landcover, class_name=class_name, feature_snapshot_id=feature_snapshot_id) for class_name in sorted(landcover.keys())},
        landcover_comparability_group=snapshot.get("landcover_comparability_group"),
    )

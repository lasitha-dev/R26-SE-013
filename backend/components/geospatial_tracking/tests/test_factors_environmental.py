"""Checkpoint 6D Part 35: environmental component tests — ENV-01..07."""

from __future__ import annotations

import inspect

from components.geospatial_tracking.services.factors.contracts import NOT_YET_SCIENTIFICALLY_DEFINED
from components.geospatial_tracking.services.factors.environmental_components import (
    EnvironmentalComponentVector,
    build_environmental_component_vector,
)


def _real_fr(value, *, feature_name, dataset_name="ERA5", units="degC"):
    return {"feature_name": feature_name, "value": value, "units": units, "status": "REAL", "dataset_name": dataset_name, "dataset_version": "v1"}


def _snapshot(*, temperature=28.0, humidity=80.0, precipitation=1.0):
    return {
        "weather": {"results": {
            "mean_temperature_2m": _real_fr(temperature, feature_name="mean_temperature_2m"),
            "mean_relative_humidity_2m": _real_fr(humidity, feature_name="mean_relative_humidity_2m", units="%"),
            "precipitation_accumulation": _real_fr(precipitation, feature_name="precipitation_accumulation", units="mm"),
        }},
        "landcover_comparability_group": "WORLDCOVER_V200",
    }


def _cell():
    return {
        "grid_cell_id": "C1",
        "landcover": {
            "landcover_tree_cover_fraction": _real_fr(0.3, feature_name="landcover_tree_cover_fraction", dataset_name="WorldCover", units="fraction"),
            "landcover_cropland_fraction": _real_fr(0.5, feature_name="landcover_cropland_fraction", dataset_name="WorldCover", units="fraction"),
        },
    }


def test_env_01_temperature_preserved_separately():
    vec = build_environmental_component_vector(cell=_cell(), snapshot=_snapshot(temperature=31.5), feature_snapshot_id="SNAPSHOT:abc")
    assert vec.temperature_component.transformed_value == 31.5
    assert vec.temperature_component.factor_or_component_name == "temperature_component"


def test_env_02_relative_humidity_preserved_separately():
    vec = build_environmental_component_vector(cell=_cell(), snapshot=_snapshot(humidity=77.0), feature_snapshot_id="SNAPSHOT:abc")
    assert vec.humidity_component.transformed_value == 77.0


def test_env_03_precipitation_preserved_separately():
    vec = build_environmental_component_vector(cell=_cell(), snapshot=_snapshot(precipitation=4.2), feature_snapshot_id="SNAPSHOT:abc")
    assert vec.precipitation_component.transformed_value == 4.2


def test_env_04_landcover_fractions_preserved_separately():
    vec = build_environmental_component_vector(cell=_cell(), snapshot=_snapshot(), feature_snapshot_id="SNAPSHOT:abc")
    assert vec.landcover_components["landcover_tree_cover_fraction"].transformed_value == 0.3
    assert vec.landcover_components["landcover_cropland_fraction"].transformed_value == 0.5


def test_env_05_no_arbitrary_weighted_environmental_sum():
    # structural: build_environmental_component_vector's signature has
    # no weight/coefficient parameter, and EnvironmentalComponentVector
    # has no combined-score field.
    params = set(inspect.signature(build_environmental_component_vector).parameters)
    assert not any("weight" in p.lower() or "coefficient" in p.lower() for p in params)
    field_names = {n.lower() for n in EnvironmentalComponentVector.__dataclass_fields__}
    assert "suitability_score" not in field_names
    assert "combined_score" not in field_names


def test_env_06_no_literature_percentage_encoded_as_coefficient():
    # Structural check via `ast` over actual CODE only (not the module
    # docstring, which legitimately shows the forbidden pattern as an
    # example of what NOT to do -- a raw-text search would false-positive
    # on that explanatory prose). No multiplication of a numeric literal
    # against another expression appears anywhere in the real code.
    import ast
    import pathlib

    import components.geospatial_tracking.services.factors.environmental_components as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    # drop the module docstring node so only real code is inspected
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body = tree.body[1:]

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            operands = (node.left, node.right)
            assert not any(isinstance(o, ast.Constant) and isinstance(o.value, (int, float)) for o in operands), \
                "found a numeric-literal multiplication in real code -- looks like a hand-coded weighted-sum coefficient"


def test_env_07_environmental_suitability_factor_not_yet_scientifically_defined():
    vec = build_environmental_component_vector(cell=_cell(), snapshot=_snapshot(), feature_snapshot_id="SNAPSHOT:abc")
    assert vec.environmental_suitability_factor_status == NOT_YET_SCIENTIFICALLY_DEFINED

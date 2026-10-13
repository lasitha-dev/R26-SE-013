"""Checkpoint 6C Part 38: no-forbidden-modeling tests — NOFIT-01..08."""

from __future__ import annotations

import inspect
import pathlib

import pytest

from components.geospatial_tracking.services import hazard as hazard_pkg
from components.geospatial_tracking.services.hazard.contracts import CellHazardFactors, HazardFactors, SourceGeometry, SourceHazardFactors
from components.geospatial_tracking.services.hazard.kernels import evaluate_kernel
from components.geospatial_tracking.services.hazard.snapshot import HazardSnapshot
from components.geospatial_tracking.services.hazard.source_hazard import SourceHazardContribution, compute_source_hazard


def _hazard_package_files():
    pkg_dir = pathlib.Path(hazard_pkg.__file__).parent
    return sorted(pkg_dir.glob("*.py"))


def test_nofit_01_no_sklearn_import():
    for path in _hazard_package_files():
        text = path.read_text(encoding="utf-8")
        assert "sklearn" not in text, f"{path.name} references sklearn"


def test_nofit_02_no_future_target_parameter():
    # structural: no public hazard function accepts a "target"/"future"
    # coordinate parameter at all.
    import components.geospatial_tracking.services.hazard.source_hazard as source_hazard_mod
    import components.geospatial_tracking.services.hazard.snapshot as snapshot_mod

    for mod in (source_hazard_mod, snapshot_mod):
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            params = set(inspect.signature(fn).parameters)
            assert not any("target" in p.lower() or "future" in p.lower() for p in params), f"{mod.__name__}.{name} has a forbidden parameter"


def test_nofit_03_no_outcome_label_parameter():
    import components.geospatial_tracking.services.hazard.source_hazard as source_hazard_mod

    for name, fn in inspect.getmembers(source_hazard_mod, inspect.isfunction):
        params = set(inspect.signature(fn).parameters)
        assert not any("outcome" in p.lower() or "label" in p.lower() for p in params)


def test_nofit_04_no_affected_animals_derivation():
    field_names = set(HazardFactors.__dataclass_fields__)
    assert "affected_animals" not in field_names
    with pytest.raises(TypeError):
        HazardFactors(
            host_factor=None, environmental_suitability_factor=None, water_context_factor=None,
            source_strength_factor=None, affected_animals=100,
        )


def test_nofit_05_no_dqs_field():
    forbidden = {"dqs", "data_quality_score", "affected_animals", "case_count", "cluster_role", "cluster_membership", "gps_quality"}
    field_names = {name.lower() for name in HazardFactors.__dataclass_fields__}
    assert not (field_names & forbidden)


def test_nofit_06_no_st_cluster_role_multiplier():
    forbidden = {"cluster_role", "is_noise", "is_core", "is_border", "cluster_id"}
    for cls in (SourceGeometry, HazardFactors, SourceHazardContribution, HazardSnapshot):
        field_names = {name.lower() for name in cls.__dataclass_fields__}
        assert not (field_names & forbidden), f"{cls.__name__} leaked ST-cluster field {field_names & forbidden}"


def test_nofit_07_no_hard_reach_cutoff():
    # a distance many multiples of the kernel scale still yields a small
    # positive kernel value -- never a hard-zeroed cutoff (as opposed to
    # an astronomically large distance, where exp() legitimately
    # underflows to 0.0 in float64 -- that is precision, not a
    # scientifically imposed reach limit).
    assert evaluate_kernel(500.0, family="EXPONENTIAL", distance_scale_km=5.0) > 0.0


def test_index_07_primary_api_does_not_accept_combined_source_indexed_factors():
    # Checkpoint 6C.5 Part 5: the primary hazard path
    # (`compute_source_hazard`) must require the split
    # `cell_factors`/`source_factors` contracts -- it must NOT accept a
    # single combined `factors=` (legacy `HazardFactors`) parameter at
    # all.
    params = set(inspect.signature(compute_source_hazard).parameters)
    assert "factors" not in params
    assert {"cell_factors", "source_factors"} <= params


def test_cell_and_source_factors_have_no_forbidden_field():
    forbidden = {"dqs", "data_quality_score", "affected_animals", "case_count", "cluster_role", "cluster_membership", "gps_quality"}
    for cls in (CellHazardFactors, SourceHazardFactors):
        field_names = {name.lower() for name in cls.__dataclass_fields__}
        assert not (field_names & forbidden)


def test_nofit_08_no_raw_feature_snapshot_import():
    """The hazard package must never IMPORT the features contracts
    module (structural check via `ast`, not a raw-text search — this
    module's own docstrings legitimately NAME `features.contracts` while
    explaining that it is never imported, which would false-positive a
    substring search)."""
    import ast

    for path in _hazard_package_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "features" not in module.split("."), f"{path.name} imports from {module!r}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "features" not in alias.name.split("."), f"{path.name} imports {alias.name!r}"

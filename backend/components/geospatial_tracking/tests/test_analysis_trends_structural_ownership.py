"""GEO-ANALYSIS-01 Section 38: structural proof, by static AST
inspection, that every new Analysis & Trends file:

  - imports no other research component and no `core.database`/
    `core.security` (Section 0);
  - calls no scientific-repository WRITE method, no model-fitting/
    retraining call (Section 25/27/38).

Mirrors `test_my_area_structural_ownership.py`'s exact technique.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ANALYSIS_TRENDS_FILES = [
    "domain/analysis_trends_enums.py",
    "domain/analysis_trends_models.py",
    "repositories/scientific_read_port.py",
    "services/analysis_trends/historical_trend.py",
    "services/analysis_trends/score_distribution.py",
    "services/analysis_trends/context_service.py",
    "api/analysis_trends_router_factory.py",
]

_FORBIDDEN_OTHER_COMPONENT_PREFIXES = (
    "components.health_anomaly",
    "components.smart_diagnostics",
    "components.risk_forecasting",
    "core.database",
    "core.security",
)

_FORBIDDEN_SCIENTIFIC_WRITE_METHOD_NAMES = {
    "add_animal_report",
    "add_outbreak_episode",
    "add_historical_record",
    "add_prediction_run",
    "init_schema",
}

_FORBIDDEN_MODEL_FITTING_CALL_NAMES = {
    "fit",
    "train",
    "retrain",
    "run_bootstrap",
    "compute_bootstrap_uncertainty",
    "assert_frozen_c0_model",
}

_COMPONENT_ROOT = Path(__file__).resolve().parents[1]  # backend/components/geospatial_tracking/


def _imported_module_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def _called_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


class TestNoForeignComponentImports:
    def test_no_analysis_trends_file_imports_another_component_or_core(self):
        violations = []
        for relative_path in _ANALYSIS_TRENDS_FILES:
            path = _COMPONENT_ROOT / relative_path
            for module_name in _imported_module_names(path):
                if module_name.startswith(_FORBIDDEN_OTHER_COMPONENT_PREFIXES):
                    violations.append((relative_path, module_name))
        assert violations == []


class TestNoScientificWriteOrModelFittingSurface:
    def test_no_analysis_trends_file_calls_a_scientific_repository_write_method(self):
        violations = []
        for relative_path in _ANALYSIS_TRENDS_FILES:
            path = _COMPONENT_ROOT / relative_path
            hit = _called_names(path) & _FORBIDDEN_SCIENTIFIC_WRITE_METHOD_NAMES
            if hit:
                violations.append((relative_path, hit))
        assert violations == []

    def test_no_analysis_trends_file_calls_a_model_fitting_or_retraining_function(self):
        violations = []
        for relative_path in _ANALYSIS_TRENDS_FILES:
            path = _COMPONENT_ROOT / relative_path
            hit = _called_names(path) & _FORBIDDEN_MODEL_FITTING_CALL_NAMES
            if hit:
                violations.append((relative_path, hit))
        assert violations == []

    def test_context_service_never_imports_the_outbreak_repository_or_sqlite_backend_directly(self):
        imported = _imported_module_names(_COMPONENT_ROOT / "services/analysis_trends/context_service.py")
        assert not any("sqlite_repository" in name for name in imported)
        assert not any(name.endswith("repositories.base") or name == "repositories.base" for name in imported)

    def test_historical_trend_and_score_distribution_are_pure_no_repository_import_at_all(self):
        for relative_path in ("services/analysis_trends/historical_trend.py", "services/analysis_trends/score_distribution.py"):
            imported = _imported_module_names(_COMPONENT_ROOT / relative_path)
            assert not any("repositories" in name for name in imported)


class TestAllAnalysisTrendsFilesExistUnderGeospatialTracking:
    def test_listed_files_are_all_under_this_component(self):
        for relative_path in _ANALYSIS_TRENDS_FILES:
            path = _COMPONENT_ROOT / relative_path
            assert path.is_file(), f"expected {path} to exist"
            assert "geospatial_tracking" in path.parts

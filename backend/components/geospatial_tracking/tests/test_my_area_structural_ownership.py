"""GEO-AREA-01 Section 34: structural proof, by static AST inspection,
that every new My Area file:

  - imports no other research component and no `core.database`/
    `core.security` (Section 4/24);
  - calls no scientific-repository WRITE method
    (`add_animal_report`/`add_outbreak_episode`/`add_historical_record`/
    `add_prediction_run`/`init_schema`) anywhere -- this checkpoint is
    read-only with respect to scientific data (Section 3).

Mirrors `test_operational_structural_ownership.py`'s exact technique
(GEO-INT-01), extended with the new files.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MY_AREA_FILES = [
    "domain/my_area_enums.py",
    "domain/my_area_models.py",
    "repositories/scientific_read_port.py",
    "services/my_area/relevant_origins.py",
    "services/my_area/nearest_source.py",
    "services/my_area/nominal_reach_context.py",
    "services/my_area/relative_spatial_score.py",
    "services/my_area/context_service.py",
    "api/my_area_router_factory.py",
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


def _called_attribute_names(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


class TestNoForeignComponentImports:
    def test_no_my_area_file_imports_another_component_or_core(self):
        violations = []
        for relative_path in _MY_AREA_FILES:
            path = _COMPONENT_ROOT / relative_path
            for module_name in _imported_module_names(path):
                if module_name.startswith(_FORBIDDEN_OTHER_COMPONENT_PREFIXES):
                    violations.append((relative_path, module_name))
        assert violations == []


class TestNoScientificWriteSurface:
    def test_no_my_area_file_calls_a_scientific_repository_write_method(self):
        violations = []
        for relative_path in _MY_AREA_FILES:
            path = _COMPONENT_ROOT / relative_path
            called = _called_attribute_names(path)
            hit = called & _FORBIDDEN_SCIENTIFIC_WRITE_METHOD_NAMES
            if hit:
                violations.append((relative_path, hit))
        assert violations == []

    def test_scientific_read_port_only_calls_read_methods_on_the_repository(self):
        # The concrete adapter is the ONE place a real OutbreakRepository
        # is touched -- every call on it must be a read (list_*/get_*),
        # never an add_*/init_schema.
        source = (_COMPONENT_ROOT / "repositories/scientific_read_port.py").read_text(encoding="utf-8")
        called = _called_attribute_names(_COMPONENT_ROOT / "repositories/scientific_read_port.py")
        repo_like_calls = {name for name in called if name.startswith(("get_", "list_", "add_", "init_"))}
        assert repo_like_calls.issubset({"get_historical_record"})

    def test_context_service_never_imports_the_outbreak_repository_or_sqlite_backend_directly(self):
        imported = _imported_module_names(_COMPONENT_ROOT / "services/my_area/context_service.py")
        assert not any("sqlite_repository" in name for name in imported)
        assert not any(name.endswith("repositories.base") or name == "repositories.base" for name in imported)


class TestAllMyAreaFilesExistUnderGeospatialTracking:
    def test_listed_files_are_all_under_this_component(self):
        for relative_path in _MY_AREA_FILES:
            path = _COMPONENT_ROOT / relative_path
            assert path.is_file(), f"expected {path} to exist"
            assert "geospatial_tracking" in path.parts

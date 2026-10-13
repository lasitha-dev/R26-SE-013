"""GEO-LIVE-05 Section 14: structural proof, by static AST inspection (same
technique as `test_operational_structural_ownership.py`), that the new
live-event boundary files:

  - import no other research component or the shared `core.database`/
    `core.security` modules;
  - import nothing that could perform a write to scientific storage (the
    SQLite repository, model-development/historical-import/retraining
    services) -- Section 14 "a new verified operational case DOES NOT
    mutate ... scientific SQLite model records", "No automatic
    retraining".

Import absence is the proof, not a runtime mock -- there is nothing to
mock: this boundary never receives an `OutbreakRepository`/SQLite
connection at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

_EVENT_BOUNDARY_FILES = [
    "domain/operational_events.py",
    "repositories/case_event_port.py",
    "repositories/mongo_case_event_source.py",
    "services/operational/event_normalization.py",
    "services/operational/event_dedup.py",
    "services/operational/event_stream_service.py",
    "api/operational_events_router_factory.py",
]

_FORBIDDEN_OTHER_COMPONENT_PREFIXES = (
    "components.health_anomaly",
    "components.smart_diagnostics",
    "components.risk_forecasting",
    "core.database",
    "core.security",
)

_FORBIDDEN_SCIENTIFIC_WRITE_MODULES = (
    "repositories.sqlite_repository",
    "repositories.base",
    "repositories.provider",
    "services.historical_import",
    "services.fmd_model_development",
    "services.fmd_model_development_7b",
    "services.fmd_model_development_8_heldout",
    "services.model_fitting_exposure",
    "services.seed_dev_db",
    "services.dataset_freeze",
    "services.build_historical_replay",
)

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


class TestNoForeignComponentImports:
    def test_no_event_boundary_file_imports_another_component_or_core(self):
        violations = []
        for relative_path in _EVENT_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            imported = _imported_module_names(path)
            for module_name in imported:
                if module_name.startswith(_FORBIDDEN_OTHER_COMPONENT_PREFIXES):
                    violations.append((relative_path, module_name))
        assert violations == []


class TestNoScientificWriteSurface:
    def test_no_event_boundary_file_imports_a_scientific_write_capable_module(self):
        violations = []
        for relative_path in _EVENT_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            imported = _imported_module_names(path)
            for module_name in imported:
                if any(forbidden in module_name for forbidden in _FORBIDDEN_SCIENTIFIC_WRITE_MODULES):
                    violations.append((relative_path, module_name))
        assert violations == []

    def test_no_event_boundary_file_calls_insert_update_or_delete(self):
        """AST-level check that none of these files even contain a call
        whose method name looks like a Mongo/SQL mutation -- belt-and-
        suspenders alongside the import-absence proof above."""
        forbidden_call_names = {"insert_one", "insert_many", "update_one", "update_many", "delete_one", "delete_many", "replace_one", "add_outbreak_episode"}
        violations = []
        for relative_path in _EVENT_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in forbidden_call_names:
                    violations.append((relative_path, node.attr))
        assert violations == []


class TestAllEventFilesExistUnderGeospatialTracking:
    def test_listed_files_are_all_under_this_component(self):
        for relative_path in _EVENT_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            assert path.is_file(), f"expected {path} to exist"
            assert "geospatial_tracking" in path.parts

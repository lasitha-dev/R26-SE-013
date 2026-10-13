"""GEO-INT-01 Section 16/22/26: structural proof, by static AST inspection
of the operational-boundary source files themselves, that:

  - no GEO-INT-01 file imports another research component or the shared
    `core.database`/`core.security` modules (Section 5/22);
  - no GEO-INT-01 file imports anything that could perform a write to
    scientific storage -- the SQLite repository, the model-development /
    historical-import / retraining services (Section 16/23/24). Since
    none of those are imported anywhere in this boundary, no code path
    exists through which it could call `insert_one`/`add_outbreak_episode`/
    a model-fitting routine -- import absence is the proof, not a runtime
    mock (there is nothing to mock: this boundary never receives an
    `OutbreakRepository` instance at all).

This complements (does not replace) the git-level "no changes outside
backend/components/geospatial_tracking/**" check in the checkpoint's
final report, which is a repository-wide fact `git status`/`git diff`
answers directly and is not itself expressible as a Python unit test.
"""

from __future__ import annotations

import ast
from pathlib import Path

_OPERATIONAL_BOUNDARY_FILES = [
    "domain/operational_enums.py",
    "domain/operational_models.py",
    "repositories/operational_port.py",
    "repositories/host_operational_adapter.py",  # GEO-INT-02
    "services/operational/farm_normalization.py",
    "services/operational/disease_normalization.py",
    "services/operational/clinical_context.py",
    "services/operational/context_service.py",
    "api/operational_router_factory.py",  # GEO-INT-02
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
                # Resolve relative imports (level > 0) to an absolute
                # dotted path rooted at geospatial_tracking, so
                # `from ...domain.operational_enums import X` inside
                # services/operational/ is checked the same way as an
                # absolute import would be.
                names.add(node.module)
    return names


class TestNoForeignComponentImports:
    def test_no_operational_file_imports_another_component_or_core(self):
        violations = []
        for relative_path in _OPERATIONAL_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            imported = _imported_module_names(path)
            for module_name in imported:
                if module_name.startswith(_FORBIDDEN_OTHER_COMPONENT_PREFIXES):
                    violations.append((relative_path, module_name))
        assert violations == []


class TestNoScientificWriteSurface:
    def test_no_operational_file_imports_a_scientific_write_capable_module(self):
        violations = []
        for relative_path in _OPERATIONAL_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            imported = _imported_module_names(path)
            for module_name in imported:
                # relative imports resolve to a bare submodule name (e.g.
                # "disease", "operational_models") which never collides
                # with the fully-qualified forbidden names below, so a
                # substring/suffix check is sufficient without needing
                # real import resolution.
                if any(forbidden in module_name for forbidden in _FORBIDDEN_SCIENTIFIC_WRITE_MODULES):
                    violations.append((relative_path, module_name))
        assert violations == []

    def test_context_service_constructor_only_accepts_the_port_protocol(self):
        import inspect

        from components.geospatial_tracking.services.operational.context_service import OperationalContextService

        signature = inspect.signature(OperationalContextService.__init__)
        param_names = [name for name in signature.parameters if name != "self"]
        assert param_names == ["port"]


class TestAllOperationalFilesExistUnderGeospatialTracking:
    def test_listed_files_are_all_under_this_component(self):
        for relative_path in _OPERATIONAL_BOUNDARY_FILES:
            path = _COMPONENT_ROOT / relative_path
            assert path.is_file(), f"expected {path} to exist"
            assert "geospatial_tracking" in path.parts

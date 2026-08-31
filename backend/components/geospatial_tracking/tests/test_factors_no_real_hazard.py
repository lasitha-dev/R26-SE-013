"""Checkpoint 6D Part 39: no-real-hazard tests — NO-REAL-HAZARD-01..02."""

from __future__ import annotations

import ast
import inspect
import pathlib

import components.geospatial_tracking.services.factors as factors_pkg
import components.geospatial_tracking.services.hazard as hazard_pkg
from components.geospatial_tracking.services.factors.factor_snapshot import FactorSnapshot
from components.geospatial_tracking.services.hazard.contracts import CellHazardFactors, FactorValue, SourceHazardFactors


def test_no_real_hazard_01_no_path_from_factor_snapshot_to_real_hazard_snapshot():
    """No function anywhere in `services/factors/` imports
    `services.hazard.snapshot.build_hazard_snapshot` (or any hazard
    accumulation/relative-risk function) -- structurally verified via
    `ast`, not text search."""
    pkg_dir = pathlib.Path(factors_pkg.__file__).parent
    forbidden_hazard_symbols = {"build_hazard_snapshot", "accumulate_cell_hazard", "compute_relative_risk_index", "compute_source_hazard"}
    for path in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)
        overlap = imported_names & forbidden_hazard_symbols
        assert not overlap, f"{path.name} imports hazard-computation symbol(s) {overlap} -- would let a FactorSnapshot bypass the freeze/selection firewall"


def test_no_real_hazard_01b_hazard_contracts_structurally_refuse_real_factors():
    # Reinforces the firewall from the hazard side: constructing a
    # CellHazardFactors/SourceHazardFactors/FactorValue with a REAL
    # (non-SOFTWARE_FIXTURE_ONLY) usable status must fail.
    import pytest

    with pytest.raises(ValueError):
        CellHazardFactors(
            "CELL1", host_factor=FactorValue(0.5, "REAL"),
            environmental_suitability_factor=FactorValue(0.5, "SOFTWARE_FIXTURE_ONLY"),
            water_context_factor=FactorValue(0.5, "SOFTWARE_FIXTURE_ONLY"),
        )
    with pytest.raises(ValueError):
        SourceHazardFactors("A", source_strength_factor=FactorValue(0.5, "REAL"))


def test_no_real_hazard_02_no_field_named_infection_probability_or_lsd_probability():
    forbidden = {"infection_probability", "lsd_probability", "chance_of_infection", "probability"}
    field_names = {n.lower() for n in FactorSnapshot.__dataclass_fields__}
    assert not (field_names & forbidden)

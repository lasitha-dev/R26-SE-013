"""Checkpoint 9C: deterministic nominal-reach derivation and frozen
scientific component integration contract.

No 7B-9B rerun, no bootstrap rerun, no `d_min`/`v_obs` rebuild, no
held-out/Sri Lanka rate inspection anywhere in this file. Every
assertion here reads frozen constants/already-frozen sibling protocol
identities -- nothing queries the outbreak database or the gitignored
`local_data` tree (those checks live in the separate, skip-guarded
evidence-summary tests)."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from components.geospatial_tracking.services.direction.c0_cell_local_tendency_8b3 import CellDirectionTendency8B3
from components.geospatial_tracking.services.integration import (
    geospatial_intelligence_contract_9c,
    geospatial_intelligence_protocol_9c,
    nominal_reach_9c,
)
from components.geospatial_tracking.services.integration.geospatial_intelligence_contract_9c import (
    NEAREST_SOURCE_SEMANTICS_9C,
    OPERATIONAL_EVALUATION_ENVELOPE_KM_9C,
    RESEARCH_EVIDENCE_STATUS_9C,
    RISK_SCORE_SEMANTICS_9C,
    RISK_SURFACE_TEMPORAL_SEMANTICS_9C,
    DirectionComponent9C,
    build_frozen_geospatial_intelligence_contract_9c,
    default_apparent_rate_component_9c,
    direction_component_from_tendency_9c,
)
from components.geospatial_tracking.services.integration.geospatial_intelligence_protocol_9c import (
    RATE_CANONICAL_PAYLOAD_SHA256_9C,
    RATE_INPUT_CSV_SHA256_9C,
    S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
    integration_protocol_dict_9c,
    integration_protocol_hash_9c,
)
from components.geospatial_tracking.services.integration.nominal_reach_9c import (
    FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C,
    FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C,
    FROZEN_S0_RATE_KM_DAY_9C,
    PRIMARY_HORIZON_DAYS_9C,
    build_nominal_reach_by_day_9c,
    derived_nominal_reach_interval,
    nominal_reach_km,
)
from components.geospatial_tracking.services.model_development.direction_protocol_8b import direction_method_protocol_hash_8b3
from components.geospatial_tracking.services.model_development.heldout_protocol_7d import FROZEN_7C_SPEC_HASH, SELECTED_CANDIDATE_ID
from components.geospatial_tracking.services.model_development.local_evaluation_scope import PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
from components.geospatial_tracking.services.model_development.rate_protocol_9b import (
    HISTORICAL_9A_PROTOCOL_HASH_9B,
    NINE_A1_EXPOSURE_CLASSIFICATION_9B,
)

_INTEGRATION_MODULES = (nominal_reach_9c, geospatial_intelligence_contract_9c, geospatial_intelligence_protocol_9c)


def _direct_imports(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def _fake_tendency(*, bearing_deg, directional_clarity) -> CellDirectionTendency8B3:
    return CellDirectionTendency8B3(
        scientific_cell_id="CELL::TEST", direction_status="DIRECTIONAL_RESULTANT_DEFINED",
        method_id="C0_CELL_LOCAL_NEGATIVE_GRADIENT_TENDENCY", method_version="8B.3",
        direction_semantics="C0_DERIVED_CELL_LOCAL_NEGATIVE_GRADIENT_GEOMETRIC_TENDENCY",
        coordinate_frame="CELL_LOCAL_EAST_NORTH_TANGENT_FRAME", temporal_scope="T0_STATIC_NOT_DAY_SPECIFIC",
        direction_evaluation_truth_status="DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
        predictive_spread_direction_status="NOT_PREDICTIVE_SPREAD_DIRECTION",
        bearing_deg=bearing_deg, resultant_east=0.1, resultant_north=0.2, resultant_magnitude=0.223606797749979,
        directional_clarity=directional_clarity, total_scalar_c0_mass=5.0, directionally_defined_mass=5.0,
        directional_input_coverage=1.0, directional_mass_coverage_status="COMPLETE_DIRECTIONAL_MASS_COVERAGE",
        n_total_eligible_sources=3, n_positive_c0_weight_sources=3, n_directionally_defined_sources=3,
        n_zero_distance_undefined_direction_sources=0, n_positive_weight_directionally_defined_sources=3,
        source_terms=(), limitations=(),
    )


def _built_contract():
    return build_frozen_geospatial_intelligence_contract_9c(
        risk_score=1.2345, candidate_id=SELECTED_CANDIDATE_ID, frozen_spec_hash=FROZEN_7C_SPEC_HASH,
        direction_tendency=_fake_tendency(bearing_deg=90.0, directional_clarity=0.5),
        direction_method_protocol_hash_8b3=direction_method_protocol_hash_8b3(),
        direction_evaluation_truth_status="DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
        historical_9a_protocol_hash=HISTORICAL_9A_PROTOCOL_HASH_9B,
        nine_a1_exposure_classification=NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        s0_bootstrap_protocol_hash_9b=S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
        rate_input_csv_sha256=RATE_INPUT_CSV_SHA256_9C, rate_canonical_payload_sha256=RATE_CANONICAL_PAYLOAD_SHA256_9C,
        limitations=("TEST_LIMITATION",),
    )


# ---------------------------------------------------------------------------
# 9C-PARENT-01..05
# ---------------------------------------------------------------------------


def test_9c_parent_01_c0_candidate_exact():
    assert SELECTED_CANDIDATE_ID == "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"


def test_9c_parent_02_frozen_7c_spec_hash_exact():
    assert FROZEN_7C_SPEC_HASH == "ef3511d3527da6d85598846c0d828509ed07f134ac8d987c3d5702b507505a6d"


def test_9c_parent_03_direction_hash_8b3_exact():
    assert direction_method_protocol_hash_8b3() == "dc3b245aa8ea6748c8abf8bcf0c56db75aca34a6118b02776b9c5490fa6c0282"


def test_9c_parent_04_historical_9a_hash_exact():
    assert HISTORICAL_9A_PROTOCOL_HASH_9B == "326427b08f5c43b9708409ae112460e8f0804db0c972a007caaae8ffca3b58ac"


def test_9c_parent_05_9b_protocol_hash_exact():
    assert S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C == "969161e318508edfa2465d2f4598dbca17fcf29ef01bba2df42bec8093835d28"


# ---------------------------------------------------------------------------
# 9C-RATE-01/02
# ---------------------------------------------------------------------------


def test_9c_rate_01_rate_exact():
    assert FROZEN_S0_RATE_KM_DAY_9C == 3.946421443154751
    assert default_apparent_rate_component_9c().apparent_rate_km_day == 3.946421443154751


def test_9c_rate_02_rate_ci_exact():
    assert FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C == 3.5491046170907765
    assert FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C == 4.343077329563724
    rate = default_apparent_rate_component_9c()
    assert rate.rate_interval_lower_km_day == 3.5491046170907765
    assert rate.rate_interval_upper_km_day == 4.343077329563724


# ---------------------------------------------------------------------------
# 9C-REACH-01..06
# ---------------------------------------------------------------------------


def test_9c_reach_01_reach_equals_rate_times_day_for_every_day():
    for day_h in range(1, 8):
        assert nominal_reach_km(day_h) == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C * day_h)
    for entry in build_nominal_reach_by_day_9c():
        assert entry.nominal_reach_km == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C * entry.day)


def test_9c_reach_02_d7_nominal_reach_exceeds_25km_and_is_accepted():
    d7 = nominal_reach_km(7)
    assert d7 > 25.0
    # no exception, no clipping -- the raw value is returned unchanged
    assert d7 == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C * 7)


def test_9c_reach_03_operational_envelope_remains_exactly_25km():
    assert OPERATIONAL_EVALUATION_ENVELOPE_KM_9C == 25.0
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM == 25.0


def test_9c_reach_04_nominal_reach_never_changes_evaluation_envelope():
    before = PRIMARY_LOCAL_EVALUATION_DISTANCE_KM
    _ = nominal_reach_km(100)  # a deliberately large day, far outside D1-D7
    _ = build_nominal_reach_by_day_9c()
    assert PRIMARY_LOCAL_EVALUATION_DISTANCE_KM == before == 25.0
    assert OPERATIONAL_EVALUATION_ENVELOPE_KM_9C == 25.0
    # structural: nominal_reach_9c never even imports the envelope constant/module
    imports = _direct_imports(nominal_reach_9c)
    assert not any("local_evaluation_scope" in m for m in imports), imports


def test_9c_reach_05_nominal_reach_never_modifies_c0_score():
    contract_a = _built_contract()
    contract_b = build_frozen_geospatial_intelligence_contract_9c(
        risk_score=999.999, candidate_id=SELECTED_CANDIDATE_ID, frozen_spec_hash=FROZEN_7C_SPEC_HASH,
        direction_tendency=None, direction_method_protocol_hash_8b3=direction_method_protocol_hash_8b3(),
        direction_evaluation_truth_status="DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
        historical_9a_protocol_hash=HISTORICAL_9A_PROTOCOL_HASH_9B,
        nine_a1_exposure_classification=NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        s0_bootstrap_protocol_hash_9b=S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
        rate_input_csv_sha256=RATE_INPUT_CSV_SHA256_9C, rate_canonical_payload_sha256=RATE_CANONICAL_PAYLOAD_SHA256_9C,
        limitations=(),
    )
    assert contract_a.risk.risk_score == 1.2345
    assert contract_b.risk.risk_score == 999.999
    # both risk scores pass through unchanged even though nominal_reach_by_day is identical in both
    assert contract_a.nominal_reach_by_day == contract_b.nominal_reach_by_day
    # structural: nominal_reach_9c never imports any C0-scoring module
    imports = _direct_imports(nominal_reach_9c)
    for forbidden in ("baseline_scoring", "wind_scoring_7c", "candidate_registry_7c", "hazard"):
        assert not any(forbidden in m for m in imports), imports


def test_9c_reach_06_no_d8_d14_values_generated():
    days = [entry.day for entry in build_nominal_reach_by_day_9c()]
    assert days == [1, 2, 3, 4, 5, 6, 7]
    assert PRIMARY_HORIZON_DAYS_9C == (1, 2, 3, 4, 5, 6, 7)
    assert max(days) <= 7


# ---------------------------------------------------------------------------
# 9C-UNC-01
# ---------------------------------------------------------------------------


def test_9c_unc_01_derived_interval_is_pure_multiplication_no_bootstrap_call():
    for day_h in range(1, 8):
        lower, upper = derived_nominal_reach_interval(day_h)
        assert lower == pytest.approx(FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C * day_h)
        assert upper == pytest.approx(FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C * day_h)
    # structural: nominal_reach_9c never imports the bootstrap implementation module
    imports = _direct_imports(nominal_reach_9c)
    assert not any("rate_s0_bootstrap_9b" in m for m in imports), imports
    src = inspect.getsource(nominal_reach_9c)
    assert "run_bootstrap(" not in src and "compute_bootstrap_uncertainty(" not in src
    assert "random.Random(" not in src and "randrange(" not in src


# ---------------------------------------------------------------------------
# 9C-RISK-01..03
# ---------------------------------------------------------------------------


def test_9c_risk_01_risk_semantics_forbid_probability_interpretation():
    assert RISK_SCORE_SEMANTICS_9C == "RELATIVE_SPATIAL_SCORE_NOT_INFECTION_PROBABILITY"
    for module in (geospatial_intelligence_contract_9c, geospatial_intelligence_protocol_9c):
        src = inspect.getsource(module).lower()
        for forbidden in ('"infection_probability"', '"probability_of_infection"', '"transmission_probability"'):
            assert forbidden not in src


def test_9c_risk_02_no_rate_or_reach_variable_enters_c0_scoring():
    for module in (nominal_reach_9c, geospatial_intelligence_contract_9c):
        imports = _direct_imports(module)
        for forbidden in ("baseline_scoring", "wind_scoring_7c", "candidate_registry_7c", "hazard.kernels", "hazard.snapshot"):
            assert not any(forbidden in m for m in imports), (module.__name__, imports)


def test_9c_risk_03_static_t0_c0_semantics_explicit_no_fabricated_daily_risk():
    contract = _built_contract()
    assert contract.risk.risk_surface_temporal_semantics == "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"
    assert RISK_SURFACE_TEMPORAL_SEMANTICS_9C == "STATIC_T0_FROZEN_C0_SPATIAL_RANK_CONTEXT"
    # the risk component has no per-day field at all -- no D1..D7 risk_score_day_N
    field_names = {f.name for f in dataclasses.fields(contract.risk)}
    assert not any("day" in name for name in field_names)


# ---------------------------------------------------------------------------
# 9C-DIR-01..04
# ---------------------------------------------------------------------------


def test_9c_dir_01_direction_independent_of_rate():
    rate_with_direction = default_apparent_rate_component_9c()
    contract = build_frozen_geospatial_intelligence_contract_9c(
        risk_score=1.0, candidate_id=SELECTED_CANDIDATE_ID, frozen_spec_hash=FROZEN_7C_SPEC_HASH,
        direction_tendency=_fake_tendency(bearing_deg=359.9, directional_clarity=0.999),
        direction_method_protocol_hash_8b3=direction_method_protocol_hash_8b3(),
        direction_evaluation_truth_status="DIRECTION_EVALUATION_TRUTH_NOT_YET_FROZEN",
        historical_9a_protocol_hash=HISTORICAL_9A_PROTOCOL_HASH_9B,
        nine_a1_exposure_classification=NINE_A1_EXPOSURE_CLASSIFICATION_9B,
        s0_bootstrap_protocol_hash_9b=S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
        rate_input_csv_sha256=RATE_INPUT_CSV_SHA256_9C, rate_canonical_payload_sha256=RATE_CANONICAL_PAYLOAD_SHA256_9C,
        limitations=(),
    )
    # a wildly different bearing/clarity input never changes the rate component
    assert contract.apparent_rate == rate_with_direction
    # structural: the rate-component builder takes zero arguments -- it
    # cannot possibly read a bearing/clarity value
    assert len(inspect.signature(default_apparent_rate_component_9c).parameters) == 0


def test_9c_dir_02_clarity_is_not_called_confidence():
    field_names = [f.name for f in dataclasses.fields(DirectionComponent9C)]
    assert "directional_clarity" in field_names
    assert not any("confidence" in name for name in field_names)


def test_9c_dir_03_bearing_zero_retained_as_valid_north():
    tendency = _fake_tendency(bearing_deg=0.0, directional_clarity=0.8)
    component = direction_component_from_tendency_9c(tendency)
    assert component.bearing_deg is not None
    assert component.bearing_deg == 0.0


def test_9c_dir_04_bearing_none_remains_unavailable_never_replaced_by_zero():
    component = direction_component_from_tendency_9c(None)
    assert component.bearing_deg is None
    assert component.directional_clarity is None
    src = inspect.getsource(geospatial_intelligence_contract_9c)
    assert "if bearing:" not in src and "if tendency.bearing_deg:" not in src


# ---------------------------------------------------------------------------
# 9C-SOURCE-01
# ---------------------------------------------------------------------------


def test_9c_source_01_nearest_source_geometric_reference_only():
    assert NEAREST_SOURCE_SEMANTICS_9C == "NEAREST_KNOWN_ELIGIBLE_SOURCE_GEOMETRIC_REFERENCE"
    for module in (geospatial_intelligence_contract_9c, geospatial_intelligence_protocol_9c):
        src = inspect.getsource(module).lower()
        for forbidden in ("causal transmission source", "parent outbreak", "infection origin", "confirmed causal parent"):
            assert forbidden not in src


# ---------------------------------------------------------------------------
# 9C-PROV-01
# ---------------------------------------------------------------------------


def test_9c_prov_01_all_frozen_parent_hashes_appear_in_integration_identity():
    identity = integration_protocol_dict_9c()
    for expected in (
        SELECTED_CANDIDATE_ID, FROZEN_7C_SPEC_HASH, direction_method_protocol_hash_8b3(),
        HISTORICAL_9A_PROTOCOL_HASH_9B, NINE_A1_EXPOSURE_CLASSIFICATION_9B, S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C,
        RATE_INPUT_CSV_SHA256_9C, RATE_CANONICAL_PAYLOAD_SHA256_9C,
    ):
        assert expected in identity.values(), expected
    assert identity["research_evidence_status"] == RESEARCH_EVIDENCE_STATUS_9C


# ---------------------------------------------------------------------------
# 9C-HASH-01
# ---------------------------------------------------------------------------


def test_9c_hash_01_no_timestamp_or_absolute_path_influences_hash():
    hash_a = integration_protocol_hash_9c()
    hash_b = integration_protocol_hash_9c()
    assert hash_a == hash_b
    dict_a = integration_protocol_dict_9c()
    for key in dict_a:
        assert "generated_at" not in key and "timestamp" not in key
    src = inspect.getsource(geospatial_intelligence_protocol_9c)
    for forbidden in ("import datetime", "import time", "os.getcwd", "Path.cwd", "__file__"):
        assert forbidden not in src


# ---------------------------------------------------------------------------
# 9C-FIREWALL-01..03
# ---------------------------------------------------------------------------


def test_9c_firewall_01_no_held_out_or_sri_lanka_rate_run_dependency():
    forbidden_modules = ("heldout_run_7d", "sri_lanka_run_7e", "sri_lanka_protocol_7e")
    for module in _INTEGRATION_MODULES:
        imports = _direct_imports(module)
        for forbidden in forbidden_modules:
            assert not any(forbidden in m for m in imports), (module.__name__, imports)
        src = inspect.getsource(module)
        assert "heldout_run_7d" not in src
        assert "sri_lanka_run_7e" not in src and "sri_lanka_protocol_7e" not in src


def test_9c_firewall_02_no_database_rate_derivation():
    for module in _INTEGRATION_MODULES:
        imports = _direct_imports(module)
        for forbidden in ("repositories", "repository", "sqlite", "rate_readiness_9a", "rate_input_identity_9b"):
            assert not any(forbidden in m for m in imports), (module.__name__, imports)


def test_9c_firewall_03_no_9b_bootstrap_rerun():
    for module in _INTEGRATION_MODULES:
        imports = _direct_imports(module)
        assert not any("rate_s0_bootstrap_9b" in m for m in imports), (module.__name__, imports)


# ---------------------------------------------------------------------------
# tracked evidence summary
# ---------------------------------------------------------------------------


def test_9c_evidence_summary_internally_consistent():
    """Never skips -- tracked evidence summary consistency check."""
    path = Path(__file__).resolve().parents[1] / "CHECKPOINT_9C_EVIDENCE_SUMMARY.json"
    assert path.exists(), "CHECKPOINT_9C_EVIDENCE_SUMMARY.json must be tracked alongside source"
    d = json.loads(path.read_text(encoding="utf-8"))

    assert d["frozen_c0_candidate_id"] == SELECTED_CANDIDATE_ID
    assert d["frozen_7c_spec_hash"] == FROZEN_7C_SPEC_HASH
    assert d["direction_method_protocol_hash_8b3"] == direction_method_protocol_hash_8b3()
    assert d["historical_9a_protocol_hash"] == HISTORICAL_9A_PROTOCOL_HASH_9B
    assert d["nine_a1_exposure_classification"] == NINE_A1_EXPOSURE_CLASSIFICATION_9B
    assert d["s0_bootstrap_protocol_hash_9b"] == S0_BOOTSTRAP_PROTOCOL_HASH_9B_9C
    assert d["rate_input_csv_sha256"] == RATE_INPUT_CSV_SHA256_9C
    assert d["rate_canonical_payload_sha256"] == RATE_CANONICAL_PAYLOAD_SHA256_9C
    assert d["integration_protocol_hash_9c"] == integration_protocol_hash_9c()
    assert d["apparent_rate_km_day"] == FROZEN_S0_RATE_KM_DAY_9C
    assert d["apparent_rate_interval_km_day"]["lower"] == FROZEN_BOOTSTRAP_LOWER_RATE_KM_DAY_9C
    assert d["apparent_rate_interval_km_day"]["upper"] == FROZEN_BOOTSTRAP_UPPER_RATE_KM_DAY_9C
    assert d["operational_evaluation_envelope_km"] == 25.0
    for day_h in range(1, 8):
        assert d["nominal_reach_by_day_km"][f"day_{day_h}"] == pytest.approx(FROZEN_S0_RATE_KM_DAY_9C * day_h)
    assert d["day_7_exceeds_operational_envelope"] is True
    assert d["nominal_reach_by_day_km"]["day_7"] > d["operational_evaluation_envelope_km"]
    assert d["s1_status"] == "NOT_SELECTED"
    assert d["sri_lanka_rate_status"] == "NOT_EVALUATED"
    assert d["final_classification"] == "FROZEN_GEOSPATIAL_RISK_DIRECTION_APPARENT_RATE_AND_NOMINAL_REACH_INTEGRATION_CONTRACT_READY_FOR_API"

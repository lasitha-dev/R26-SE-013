"""Checkpoint 8A: spread-risk direction identifiability, mathematical
semantics, source-specific vector geometry, pre-t0 directional-input
readiness, and protocol freeze audit.

READINESS/SEMANTICS ONLY. No direction model is fit, no direction
parameter is tuned, and no held-out/Sri Lanka direction performance is
scored anywhere in this file. C0/CW candidate scoring is imported only
to prove it is unchanged (8A-C0-01) -- never executed predictively."""

from __future__ import annotations

import math
import re
from types import SimpleNamespace

import pytest

from components.geospatial_tracking.services.geospatial.distance import source_to_cell_unit_vector
from components.geospatial_tracking.services.geospatial.source_geometry import (
    EligibleSourcePoint,
    build_geometry_by_source,
)
from components.geospatial_tracking.services.geospatial.weather.wind import wind_components_from_speed_direction
from components.geospatial_tracking.services.hazard.anisotropy import compute_meteorological_alignment
from components.geospatial_tracking.services.hazard.contracts import WindVector
from components.geospatial_tracking.services.model_development.candidate_registry_7c import (
    C0_FAMILY,
    build_candidate_registry_7c,
)
from components.geospatial_tracking.services.model_development.direction_protocol_8a import (
    DIRECTION_METHOD_CANDIDATES,
    FROZEN_C0_DIRECTIONAL_STATUS,
    TEMPORAL_FIREWALL,
    direction_readiness_protocol_dict_8a,
    direction_readiness_protocol_hash_8a,
)
from components.geospatial_tracking.services.model_development.direction_readiness_8a import (
    DirectionalMassTerm,
    bearing_deg_from_components,
    compute_resultant_vector,
    wind_from_bearing_deg,
    wind_to_bearing_from_components,
)

_SELECTED_C0_CANDIDATE_ID = "C7C:C0_FROZEN_B0_ISOTROPIC:830bf1e62664bcc8"


def _cell(lat: float, lon: float):
    """`build_geometry_by_source` reads only `centroid_lat`/`centroid_lon`
    off its `cell` argument -- a minimal stand-in avoids depending on
    every unrelated `GridCell` field this readiness test doesn't need."""
    return SimpleNamespace(centroid_lat=lat, centroid_lon=lon)


# ---------------------------------------------------------------------------
# Bearing convention (Part 6)
# ---------------------------------------------------------------------------


def test_8a_bear_01_north_vector_zero_degrees():
    assert bearing_deg_from_components(east=0.0, north=1.0) == pytest.approx(0.0)


def test_8a_bear_02_east_vector_ninety_degrees():
    assert bearing_deg_from_components(east=1.0, north=0.0) == pytest.approx(90.0)


def test_8a_bear_03_south_vector_180_degrees():
    assert bearing_deg_from_components(east=0.0, north=-1.0) == pytest.approx(180.0)


def test_8a_bear_04_west_vector_270_degrees():
    assert bearing_deg_from_components(east=-1.0, north=0.0) == pytest.approx(270.0)


def test_8a_bear_05_bearing_zero_is_not_missing():
    bearing = bearing_deg_from_components(east=0.0, north=1.0)
    assert bearing is not None
    assert bearing == 0.0
    # the ONLY missing sentinel is None -- 0.0 must never be conflated with it
    assert bearing is not None and not (bearing is None)


# ---------------------------------------------------------------------------
# Zero-resultant (Part 14)
# ---------------------------------------------------------------------------


def test_8a_zero_01_zero_resultant_bearing_unavailable_not_north():
    terms = [
        DirectionalMassTerm("S1", weight=1.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=10.0),
        DirectionalMassTerm("S2", weight=1.0, t_hat_east=-1.0, t_hat_north=0.0, distance_km=10.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.magnitude == pytest.approx(0.0, abs=1e-9)
    assert result.bearing_deg is None  # never 0.0 (which would falsely mean North)


# ---------------------------------------------------------------------------
# Source->cell geometry orientation (Part 5)
# ---------------------------------------------------------------------------


def test_8a_geo_01_source_to_cell_orientation_correct():
    # source due south of the cell -> unit vector should point ~North
    vec = source_to_cell_unit_vector(source_lat=0.0, source_lon=0.0, cell_lat=1.0, cell_lon=0.0)
    assert vec.t_hat_north == pytest.approx(1.0, abs=1e-6)
    assert vec.t_hat_east == pytest.approx(0.0, abs=1e-6)


def test_8a_geo_02_cell_to_source_reversal_is_detected():
    forward = source_to_cell_unit_vector(source_lat=0.0, source_lon=0.0, cell_lat=1.0, cell_lon=0.0)
    reversed_ = source_to_cell_unit_vector(source_lat=1.0, source_lon=0.0, cell_lat=0.0, cell_lon=0.0)
    # swapping source/cell must flip the vector -- proves the module is
    # orientation-sensitive and a reversal bug would be caught
    assert reversed_.t_hat_north == pytest.approx(-forward.t_hat_north, abs=1e-6)
    assert reversed_.t_hat_east == pytest.approx(-forward.t_hat_east, abs=1e-6)


# ---------------------------------------------------------------------------
# Multi-source conflict (Part 15)
# ---------------------------------------------------------------------------


def test_8a_multi_01_two_equal_opposing_vectors_cancel():
    terms = [
        DirectionalMassTerm("A", weight=2.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=2.0, t_hat_east=0.0, t_hat_north=-1.0, distance_km=5.0),
    ]
    result = compute_resultant_vector(terms)
    assert result.resultant_east == pytest.approx(0.0, abs=1e-9)
    assert result.resultant_north == pytest.approx(0.0, abs=1e-9)
    assert result.directional_clarity == pytest.approx(0.0, abs=1e-9)


def test_8a_multi_02_clarity_decreases_under_disagreement():
    aligned = compute_resultant_vector([
        DirectionalMassTerm("A", weight=1.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
    ])
    perpendicular = compute_resultant_vector([
        DirectionalMassTerm("A", weight=1.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0, t_hat_east=1.0, t_hat_north=0.0, distance_km=5.0),
    ])
    opposing = compute_resultant_vector([
        DirectionalMassTerm("A", weight=1.0, t_hat_east=0.0, t_hat_north=1.0, distance_km=5.0),
        DirectionalMassTerm("B", weight=1.0, t_hat_east=0.0, t_hat_north=-1.0, distance_km=5.0),
    ])
    assert aligned.directional_clarity == pytest.approx(1.0)
    assert opposing.directional_clarity == pytest.approx(0.0, abs=1e-9)
    assert opposing.directional_clarity < perpendicular.directional_clarity < aligned.directional_clarity


# ---------------------------------------------------------------------------
# Meteorological wind FROM/TO semantics (Part 7)
# ---------------------------------------------------------------------------


def test_8a_wind_01_eastward_component_is_motion_to_east():
    assert wind_to_bearing_from_components(u10=5.0, v10=0.0) == pytest.approx(90.0)


def test_8a_wind_02_northward_component_is_motion_to_north():
    assert wind_to_bearing_from_components(u10=0.0, v10=5.0) == pytest.approx(0.0)


def test_8a_wind_03_from_to_conversion_is_exactly_180():
    assert wind_from_bearing_deg(90.0) == pytest.approx(270.0)
    assert wind_from_bearing_deg(0.0) == pytest.approx(180.0)
    assert wind_from_bearing_deg(270.0) == pytest.approx(90.0)


@pytest.mark.parametrize("from_deg", [0.0, 90.0, 180.0, 270.0])
def test_8a_wind_04_no_double_from_to_conversion(from_deg):
    u10, v10 = wind_components_from_speed_direction(speed_m_s=5.0, direction_from_deg=from_deg)
    to_bearing = wind_to_bearing_from_components(u10, v10)
    assert to_bearing == pytest.approx((from_deg + 180.0) % 360.0)
    # converting back must land exactly on the original FROM bearing --
    # applying the +180 conversion a second time would NOT do this
    assert wind_from_bearing_deg(to_bearing) == pytest.approx(from_deg % 360.0)


def test_8a_wind_05_zero_wind_cannot_fabricate_direction():
    assert wind_to_bearing_from_components(0.0, 0.0) is None
    alignment = compute_meteorological_alignment(t_hat_east=1.0, t_hat_north=0.0, wind=WindVector(u10=0.0, v10=0.0))
    assert alignment.status == "CALM_NEUTRAL"
    assert alignment.alignment is None


# ---------------------------------------------------------------------------
# Source-specific geometry before aggregation (Part 5, 9)
# ---------------------------------------------------------------------------


def test_8a_source_01_directional_contribution_remains_source_specific():
    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.0, longitude=0.0),
        EligibleSourcePoint(source_id="S2", latitude=1.0, longitude=1.0),
    ]
    geometry = build_geometry_by_source(_cell(0.5, 0.5), sources)
    assert set(geometry.keys()) == {"S1", "S2"}
    # distinct sources at distinct positions must carry distinct geometry
    assert geometry["S1"].t_hat_east != geometry["S2"].t_hat_east or geometry["S1"].t_hat_north != geometry["S2"].t_hat_north


def test_8a_source_02_nearest_source_replacement_is_impossible():
    import inspect

    from components.geospatial_tracking.services.model_development import wind_scoring_7c

    src = inspect.getsource(wind_scoring_7c)
    assert "nearest_source_id" not in src
    assert "nearest_source" not in src

    sources = [
        EligibleSourcePoint(source_id="S1", latitude=0.0, longitude=0.0),
        EligibleSourcePoint(source_id="S2", latitude=2.0, longitude=2.0),
        EligibleSourcePoint(source_id="S3", latitude=-2.0, longitude=-2.0),
    ]
    geometry = build_geometry_by_source(_cell(0.0, 0.0), sources)
    assert len(geometry) == 3  # never collapsed to one nearest-source entry


# ---------------------------------------------------------------------------
# Terminology discipline (Part 2, 8, 12)
# ---------------------------------------------------------------------------


def _assert_only_negated(src: str, phrase: str, window: int = 150) -> None:
    for match in re.finditer(re.escape(phrase), src, flags=re.IGNORECASE):
        preceding = src[max(0, match.start() - window):match.start()].lower()
        assert "never" in preceding or "not" in preceding, (
            f"{phrase!r} appears without a preceding negation: ...{preceding!r}[{phrase}]"
        )


def test_8a_sem_01_raw_wind_never_labelled_spread_direction():
    import inspect
    import json as _json

    from components.geospatial_tracking.services.geospatial.weather import wind as wind_module
    from components.geospatial_tracking.services.hazard import anisotropy as anisotropy_module

    for module in (wind_module, anisotropy_module):
        src = inspect.getsource(module)
        _assert_only_negated(src, "disease spread direction")

    candidates_blob = _json.dumps(DIRECTION_METHOD_CANDIDATES, default=str)
    assert "SPREAD_DIRECTION" not in candidates_blob
    assert "spread_direction" not in candidates_blob.lower()


def test_8a_sem_02_directional_clarity_never_labelled_confidence():
    import inspect

    from components.geospatial_tracking.services.model_development import direction_protocol_8a, direction_readiness_8a

    for module in (direction_readiness_8a, direction_protocol_8a):
        src = inspect.getsource(module)
        _assert_only_negated(src, "confidence")


# ---------------------------------------------------------------------------
# Temporal firewall (Part 16, 19)
# ---------------------------------------------------------------------------


def test_8a_time_01_future_target_forbidden_from_direction_inputs():
    assert "FUTURE_TARGET_POSITION_FORBIDDEN_AS_INPUT" in TEMPORAL_FIREWALL
    import inspect

    from components.geospatial_tracking.services.model_development import direction_readiness_8a

    src = inspect.getsource(direction_readiness_8a)
    assert "target" not in src.lower()  # no target/future-position parameter anywhere in the readiness primitives


def test_8a_time_02_future_realized_weather_forbidden_as_primary_input():
    assert "REALIZED_D1_D7_WEATHER_FORBIDDEN_AS_PRIMARY_INPUT_ORACLE_SENSITIVITY_ONLY" in TEMPORAL_FIREWALL
    import inspect

    from components.geospatial_tracking.services.model_development import wind_readiness_7c

    src = inspect.getsource(wind_readiness_7c)
    assert "build_pre_t0_weather_summary" in src
    assert "target" not in src.lower()


# ---------------------------------------------------------------------------
# Frozen C0 unchanged, no directional parameter (Part 4, 9)
# ---------------------------------------------------------------------------


def test_8a_c0_01_frozen_c0_unchanged_no_directional_parameter():
    registry = build_candidate_registry_7c()
    c0 = next(c for c in registry if c.family == C0_FAMILY)
    assert c0.candidate_id == _SELECTED_C0_CANDIDATE_ID
    assert c0.anisotropy_mode is None
    assert c0.anisotropy_kappa is None
    assert FROZEN_C0_DIRECTIONAL_STATUS == "FROZEN_C0_HAS_NO_INTRINSIC_DIRECTIONAL_TRANSMISSION_PARAMETER"


# ---------------------------------------------------------------------------
# Protocol hash determinism (Part 25) -- never binds generated_at
# ---------------------------------------------------------------------------


def test_8a_protocol_hash_deterministic_and_excludes_timestamp():
    d = direction_readiness_protocol_dict_8a()
    assert "generated_at" not in d
    assert "timestamp" not in d
    assert direction_readiness_protocol_hash_8a() == direction_readiness_protocol_hash_8a()

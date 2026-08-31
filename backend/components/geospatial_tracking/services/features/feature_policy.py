"""Checkpoint 6A / 6A.5 Parts 1, 6, 12, 20: the explicit, hashable
scientific configuration for one feature-assembly run.

`FeaturePolicy` is the ONLY place scientific feature-assembly parameters
live — the assembler never hardcodes a land-cover mode, a species list,
a lookback duration, or a hydrology search radius internally. Two
assemblies run with the same `FeaturePolicy` always produce the same
`feature_policy_hash` (Part 20); changing any one scientific parameter
changes the hash. `generated_at` is deliberately never part of this
configuration or its hash.

**Checkpoint 6A.5 permanent rule (Part 1)**: if changing a `FeaturePolicy`
field changes the hash, that field must either (A) actually change
feature-assembly behavior, or (B) be rejected as unsupported by
`__post_init__` below. No field may exist purely to be hashed — the two
fields that were previously hash-only no-ops
(`environment_temporal_mode`, and `elevation_include=True`) are now
either removed or hard-rejected; see the field-by-field notes below.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

FEATURE_PROTOCOL_VERSION = "6A.5"

# Checkpoint 6A.5 Part 2: ERA5 is the ONLY historical weather model this
# pipeline has actually investigated/verified (Checkpoint 5.5's full
# model-selection evidence — see era5.py's module docstring). No other
# model string is accepted here, not because the code can't technically
# format a request for one, but because no other model's provenance
# (resolution, temporal coverage, variable coherence) has been verified,
# and era5.py itself now refuses to silently substitute a different
# model than declared (Checkpoint 6A.5 Part 2 fix).
SUPPORTED_WEATHER_MODELS = frozenset({"era5"})

# Checkpoint 6A.5 Part 3: the ONLY legal weather temporal role for
# Checkpoint 6A/6A.5 historical assembly. Not a `FeaturePolicy` field —
# there being only one legal value makes it a fixed fact of this
# checkpoint's assembler, not a configuration choice (a configurable
# field here would be exactly the "changes the hash but not the
# assembled features" no-op Part 1 forbids). A future live-weather
# adapter uses a genuinely different code path (`weather/base.py`'s
# `LiveWeatherAdapter`) and this constant does not apply to it.
PRIMARY_WEATHER_TEMPORAL_ROLE = "RETROSPECTIVE_REANALYSIS_STATE_PROXY"

# Checkpoint 6A.5 Part 4: elevation has a real adapter
# (geospatial/elevation/terrain_tiles.py) but the assembler does not yet
# assemble it into any FeatureSnapshot field — status stays
# AVAILABLE_NOT_YET_SELECTED (Checkpoint 5 Part 14). Kept as an explicit
# field (rather than removed) so a future checkpoint can flip the
# default once assembly support actually exists, but `True` is rejected
# at construction time so it can never silently produce a different
# hash while generating an identical (elevation-free) snapshot.
ELEVATION_NOT_YET_IMPLEMENTED_MESSAGE = "Elevation is not selected/implemented in FeatureSnapshot assembly."

_SUPPORTED_HOST_DENSITY_SPECIES = frozenset({"cattle", "buffalo"})
_SUPPORTED_FROZEN_WORLDCOVER_YEARS = frozenset({"2020", "2021"})

# Part 12: land-cover modes. No mode silently invents a match — an AOI
# whose real event year isn't 2020/2021 gets NOT_SELECTED under
# YEAR_MATCHED_REFERENCE, never a guessed match.
LANDCOVER_MODE_OMIT = "OMIT"
LANDCOVER_MODE_YEAR_MATCHED_REFERENCE = "YEAR_MATCHED_REFERENCE"
LANDCOVER_MODE_FROZEN_STATIC_REFERENCE = "FROZEN_STATIC_REFERENCE"
_LANDCOVER_MODES = {
    LANDCOVER_MODE_OMIT,
    LANDCOVER_MODE_YEAR_MATCHED_REFERENCE,
    LANDCOVER_MODE_FROZEN_STATIC_REFERENCE,
}

# Checkpoint 6A.5 Part 5: labeled explicitly as a GEOSPATIAL_QUERY_LIMIT
# (how far the HydroRIVERS search window looks), never a biological
# spread-distance claim. Only meaningful when `hydrology_include=True`.
DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM = 25.0
HYDRORIVERS_SEARCH_RADIUS_LABEL = "GEOSPATIAL_QUERY_LIMIT"


@dataclass(frozen=True)
class LandCoverFeaturePolicy:
    mode: str = LANDCOVER_MODE_OMIT
    frozen_worldcover_year: str | None = None  # required only for FROZEN_STATIC_REFERENCE

    def __post_init__(self) -> None:
        if self.mode not in _LANDCOVER_MODES:
            raise ValueError(f"unknown land-cover mode {self.mode!r}; expected one of {sorted(_LANDCOVER_MODES)}")
        if self.mode == LANDCOVER_MODE_FROZEN_STATIC_REFERENCE:
            if self.frozen_worldcover_year not in _SUPPORTED_FROZEN_WORLDCOVER_YEARS:
                raise ValueError(
                    f"FROZEN_STATIC_REFERENCE requires frozen_worldcover_year to be exactly one of "
                    f"{sorted(_SUPPORTED_FROZEN_WORLDCOVER_YEARS)}, got {self.frozen_worldcover_year!r}"
                )

    def as_dict(self) -> dict:
        return {"mode": self.mode, "frozen_worldcover_year": self.frozen_worldcover_year}


@dataclass(frozen=True)
class FeaturePolicy:
    """Every scientific parameter a `FeatureSnapshot` depends on, besides
    `t0` and the eligible-source set themselves. Required fields have no
    defaults deliberately — see `source_selector.get_eligible_sources`'s
    same convention for `active_window_days`/`domain_scope`: an implicit
    default here would let a caller accidentally assemble features under
    an unstated scientific configuration.

    `__post_init__` rejects every scientifically invalid or unsupported
    configuration BEFORE it can reach `assembler.py` (Checkpoint 6A.5
    Part 6) — an invalid `FeaturePolicy` cannot be constructed at all."""

    disease: str
    active_window_days: int
    grid_half_extent_km: float
    grid_cell_size_km: float
    weather_model: str
    weather_lookback_hours: float
    landcover_policy: LandCoverFeaturePolicy
    host_density_species: tuple[str, ...] = ("cattle", "buffalo")
    hydrology_include: bool = False
    hydrorivers_search_radius_km: float = DEFAULT_HYDRORIVERS_SEARCH_RADIUS_KM
    elevation_include: bool = False

    def __post_init__(self) -> None:
        if self.active_window_days < 0:
            raise ValueError(f"active_window_days must be >= 0, got {self.active_window_days}")
        if not (math.isfinite(self.grid_half_extent_km) and self.grid_half_extent_km > 0):
            raise ValueError(f"grid_half_extent_km must be a positive finite number, got {self.grid_half_extent_km}")
        if not (math.isfinite(self.grid_cell_size_km) and self.grid_cell_size_km > 0):
            raise ValueError(f"grid_cell_size_km must be a positive finite number, got {self.grid_cell_size_km}")
        if not (math.isfinite(self.weather_lookback_hours) and self.weather_lookback_hours > 0):
            raise ValueError(f"weather_lookback_hours must be a positive finite number, got {self.weather_lookback_hours}")
        if self.weather_model not in SUPPORTED_WEATHER_MODELS:
            raise ValueError(
                f"unsupported weather_model {self.weather_model!r}; only {sorted(SUPPORTED_WEATHER_MODELS)} is "
                "investigated/verified for this pipeline (Checkpoint 5.5 model-selection evidence) — no fake "
                "support for other models is created here"
            )
        unsupported_species = set(self.host_density_species) - _SUPPORTED_HOST_DENSITY_SPECIES
        if unsupported_species:
            raise ValueError(
                f"unsupported host_density_species {sorted(unsupported_species)}; only "
                f"{sorted(_SUPPORTED_HOST_DENSITY_SPECIES)} are real GLW4 species this pipeline extracts"
            )
        if self.hydrology_include:
            if not (math.isfinite(self.hydrorivers_search_radius_km) and self.hydrorivers_search_radius_km > 0):
                raise ValueError(
                    f"hydrorivers_search_radius_km must be a positive finite number when hydrology_include=True, "
                    f"got {self.hydrorivers_search_radius_km}"
                )
        if self.elevation_include:
            raise ValueError(ELEVATION_NOT_YET_IMPLEMENTED_MESSAGE)

    def config_dict(self) -> dict:
        """Canonical, JSON-serializable, hash-stable configuration —
        deliberately excludes nothing time-varying because nothing
        time-varying (like `generated_at`) is a field of this class at
        all (Part 20). Every field here either changes real assembly
        behavior or is rejected by `__post_init__` (Part 1) — there is
        no hash-only no-op field."""
        return {
            "disease": self.disease,
            "active_window_days": self.active_window_days,
            "grid_half_extent_km": self.grid_half_extent_km,
            "grid_cell_size_km": self.grid_cell_size_km,
            "weather_model": self.weather_model,
            "weather_temporal_role": PRIMARY_WEATHER_TEMPORAL_ROLE,
            "weather_lookback_hours": self.weather_lookback_hours,
            "landcover_policy": self.landcover_policy.as_dict(),
            "host_density_species": list(self.host_density_species),
            "hydrology_include": self.hydrology_include,
            "hydrorivers_search_radius_km": self.hydrorivers_search_radius_km if self.hydrology_include else None,
            "elevation_include": self.elevation_include,
        }

    def protocol_hash(self) -> str:
        """`feature_policy_hash` (Checkpoint 6A.5 Part 7): what the
        researcher DECLARED/configured. Deterministic (ASSEMBLY-02):
        identical config -> identical hash. Sensitive to every
        scientific parameter (ASSEMBLY-03/04, HYDRO-POLICY-02): changing
        `weather_lookback_hours`, `landcover_policy`, or
        `hydrorivers_search_radius_km` changes this hash. Includes
        `FEATURE_PROTOCOL_VERSION` so a future breaking change to the
        protocol itself also changes every hash. This is declared
        configuration only — see `resolved_data_signature.py` for what
        ACTUALLY resolved for one particular snapshot."""
        payload = {"feature_protocol_version": FEATURE_PROTOCOL_VERSION, "config": self.config_dict()}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

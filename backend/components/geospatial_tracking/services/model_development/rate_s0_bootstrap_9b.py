"""Checkpoint 9B: formal S0 estimator and target-event-level percentile
bootstrap machinery.

**Dependency-minimal by design** (Part 6): no DB, geospatial, direction,
or weather dependency anywhere in this module. Every function here
operates on a plain `list[float]` of already-persisted target-level
apparent rates -- it never queries the outbreak database, never calls
`distance_km`/`pyproj.Geod`, and never rebuilds `d_min`/`v_obs`. The
sole scientific input is the Checkpoint 9A `target_level_v` dataset,
read elsewhere (`rate_input_identity_9b.py`) and passed in here as
plain numbers.

**Estimator** (frozen, Checkpoint 9A Part 9 / Checkpoint 9B Part 1):
`S0 = MEDIAN(target_level_v across UNIQUE target_event_id)` -- the same
estimator already exposed diagnostically in Checkpoint 9A/9A.1
(`PRE_9B_S0_NUMERIC_ESTIMATOR_EXPOSURE_IN_9A_DIAGNOSTIC_DISCLOSED`).
This module does not choose or fit an estimator; it formally executes
the one already predeclared.

**Bootstrap unit is `target_event_id`, never an origin-target row, grid
cell, or country** (Part 6-7). RNG: Python standard-library
`random.Random(seed)`, sampling primitive `Random.randrange(n)` -- no
NumPy, no weighted/Bayesian/BCa/studentized/cluster/hierarchical
bootstrap.

**Quantile endpoint method frozen explicitly** (Part 8): standard
linear-interpolation empirical quantile,
`Q(q) = b[floor(pos)] + frac*(b[ceil(pos)]-b[floor(pos)])`,
`pos=(B-1)*q` -- never an unspecified library default.
"""

from __future__ import annotations

import math
import random
import statistics
import sys
from dataclasses import dataclass

S0_ESTIMATOR_9B = "MEDIAN_ACROSS_UNIQUE_TARGET_LEVEL_APPARENT_RATES"
BOOTSTRAP_UNIT_9B = "UNIQUE_TARGET_EVENT_ID"
BOOTSTRAP_SEED_9B = 42
BOOTSTRAP_N_RESAMPLES_9B = 1000
BOOTSTRAP_SAMPLE_SIZE_RULE_9B = "N_TARGET_EVENTS"  # sample size per replicate == len(target_level_rates)
BOOTSTRAP_INTERVAL_LEVEL_9B = 0.95
BOOTSTRAP_CI_TYPE_9B = "PERCENTILE_INTERVAL"
BOOTSTRAP_WITH_REPLACEMENT_9B = True

QUANTILE_METHOD_9B = "LINEAR_INTERPOLATION_EMPIRICAL_QUANTILE"
QUANTILE_FORMULA_9B = (
    "position=(B-1)*q; lower=floor(position); upper=ceil(position); "
    "fraction=position-lower; Q(q)=b[lower]+fraction*(b[upper]-b[lower]) "
    "over the SORTED bootstrap estimates b[0..B-1]"
)
Q_LOWER_9B = 0.025
Q_UPPER_9B = 0.975

RNG_LIBRARY_9B = "python_stdlib_random"
RNG_CLASS_9B = "random.Random"
SAMPLING_PRIMITIVE_9B = "random.Random.randrange"
NUMPY_VERSION_9B = "NOT_USED"
MEDIAN_IMPLEMENTATION_9B = "statistics.median"
BOOTSTRAP_HELPER_MODULE_9B = "services.model_development.rate_s0_bootstrap_9b"
BOOTSTRAP_HELPER_FUNCTION_9B = "run_bootstrap"
BOOTSTRAP_HELPER_VERSION_9B = "9B.1"


def bootstrap_implementation_identity() -> dict:
    return {
        "rng_library": RNG_LIBRARY_9B,
        "rng_class": RNG_CLASS_9B,
        "sampling_primitive": SAMPLING_PRIMITIVE_9B,
        "python_version": sys.version.split()[0],
        "numpy_version": NUMPY_VERSION_9B,
        "median_implementation": MEDIAN_IMPLEMENTATION_9B,
        "bootstrap_helper_module": BOOTSTRAP_HELPER_MODULE_9B,
        "bootstrap_helper_function": BOOTSTRAP_HELPER_FUNCTION_9B,
        "bootstrap_helper_version": BOOTSTRAP_HELPER_VERSION_9B,
    }


def linear_quantile(sorted_values: list[float], q: float) -> float:
    """Frozen linear-interpolation empirical quantile (Part 8). `sorted_values`
    must already be sorted ascending. Never NumPy/statistics.quantiles'
    unspecified-by-default interpolation."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("linear_quantile: empty input")
    if n == 1:
        return sorted_values[0]
    position = (n - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def run_bootstrap(target_level_rates: list[float], *, seed: int = BOOTSTRAP_SEED_9B, n_resamples: int = BOOTSTRAP_N_RESAMPLES_9B) -> list[float]:
    """Draws `n_resamples` bootstrap replicates, each resampling exactly
    `len(target_level_rates)` UNIQUE-target-event indexes WITH
    REPLACEMENT (never origin-target rows, grid cells, or countries),
    and computes `statistics.median` of each replicate. Deterministic
    for a fixed `seed`."""
    n = len(target_level_rates)
    if n == 0:
        raise ValueError("run_bootstrap: empty target_level_rates")
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(n_resamples):
        resample = [target_level_rates[rng.randrange(n)] for _ in range(n)]
        draws.append(statistics.median(resample))
    return draws


@dataclass(frozen=True)
class BootstrapUncertaintyResult:
    point_estimate: float
    ci_lower: float
    ci_upper: float
    n_target_events: int
    n_resamples: int
    seed: int
    draws_min: float
    draws_median: float
    draws_max: float


def compute_bootstrap_uncertainty(target_level_rates: list[float], *, seed: int = BOOTSTRAP_SEED_9B, n_resamples: int = BOOTSTRAP_N_RESAMPLES_9B) -> tuple[BootstrapUncertaintyResult, list[float]]:
    """Returns the frozen point estimate (`statistics.median` of the real
    target-level rates -- never recomputed from origin-target rows),
    the 1000-replicate bootstrap draws, and the 95% percentile interval
    (`Q_LOWER_9B`/`Q_UPPER_9B`, `linear_quantile`)."""
    point_estimate = statistics.median(target_level_rates)
    draws = run_bootstrap(target_level_rates, seed=seed, n_resamples=n_resamples)
    sorted_draws = sorted(draws)
    ci_lower = linear_quantile(sorted_draws, Q_LOWER_9B)
    ci_upper = linear_quantile(sorted_draws, Q_UPPER_9B)
    result = BootstrapUncertaintyResult(
        point_estimate=point_estimate, ci_lower=ci_lower, ci_upper=ci_upper,
        n_target_events=len(target_level_rates), n_resamples=n_resamples, seed=seed,
        draws_min=sorted_draws[0], draws_median=statistics.median(sorted_draws), draws_max=sorted_draws[-1],
    )
    return result, draws

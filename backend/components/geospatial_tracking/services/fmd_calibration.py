"""FMD-06B development-only temporal and ST-DBSCAN calibration.

This module is a thin FMD workflow around the existing generic services.  It
does not add a second exposure taxonomy or a second clustering algorithm:

* ``model_fitting_exposure.assert_fit_development_only`` is the entry firewall;
* ``stdbscan.development_source_universe`` builds the validated source set;
* ``stdbscan.parameter_candidates`` supplies country-scoped descriptive
  geometry/time statistics;
* ``stdbscan.core_support`` and ``stdbscan.cluster`` perform the existing
  deterministic ST-DBSCAN-style classification.

All outputs are structural software/data diagnostics.  No target, label,
prediction, or held-out/case-study record is read by the calibration logic.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Iterable

from ..data_processing.fmd_forecast_bridge import import_fmd_canonical_csv
from ..domain.enums import RecordDomainScope
from ..domain.models import HistoricalOutbreakRecord
from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..schemas import ValidationMode
from ..services.dates import parse_flexible_date
from .forecast_origin import ForecastOrigin
from .forecast_target import build_forecast_targets
from .geospatial.distance import distance_km
from .model_development.domain_design import (
    DOMAIN_RULE_BLOCKED,
    FROZEN_EVALUATION_DOMAIN_RULE,
    PREDECLARED_DOMAIN_CANDIDATES_KM,
    DomainCandidateAudit,
    TargetDomainCoverage,
    build_development_domain_candidate_audit,
    select_frozen_domain_distance,
)
from .model_fitting_exposure import (
    assert_fit_development_only,
    classify_origin_role,
    fit_development_origins,
)
from .source_selector import get_eligible_sources
from .stdbscan.candidate_constants import (
    ACTIVE_WINDOW_DAY_CANDIDATES,
    MAX_ACTIVE_WINDOW_DAYS,
    MIN_CORE_SUPPORT_CANDIDATES,
)
from .stdbscan.cluster import run_st_clustering
from .stdbscan.config import GpsCorePolicy, STDBSCANConfig, UNFROZEN_DEVELOPMENT_CANDIDATE
from .stdbscan.core_support import compute_core_support_assignments
from .stdbscan.development_source_universe import (
    DevelopmentSource,
    DevelopmentSourceUniverseResult,
    build_fit_development_source_universe,
)
from .stdbscan.event_date import ST_USABLE, resolve_cluster_event_date
from .stdbscan.parameter_candidates import build_country_scoped_parameter_candidates

FMD_DISEASE = "Foot and mouth disease"
FMD_MODEL_FITTING_CUTOFF = "2026-01-01"

ACTIVE_WINDOW_STATUS_GO = "GO"
ACTIVE_WINDOW_STATUS_NO_GO = "NO-GO"
STDBSCAN_STATUS_GO = "GO"
STDBSCAN_STATUS_NO_GO = "NO-GO"
SPATIAL_DOMAIN_NOT_STARTED = "NOT_STARTED_FMD06C"
PRIMARY_GPS_CORE_POLICY = GpsCorePolicy.PRIMARY_CORE_SUPPORT.value
NEAR_ALL_NOISE_FRACTION = 0.90
NEAR_GIANT_CLUSTER_FRACTION = 0.90

PRE_REPAIR_ACTIVE_WINDOW_SELECTION_RULE = (
    "Use the existing fixed candidates (7,14,21,28). Reject a candidate set if every candidate "
    "leaves every development origin empty. Otherwise retain candidates with the minimum zero-source "
    "origin fraction and select the smallest retained window. This minimizes the temporal data window "
    "subject to the best available origin coverage; neighbouring deltas and country/year distributions "
    "are reported but never use target or outcome information."
)

ACTIVE_WINDOW_SELECTION_RULE = (
    "FMD-06B-R: using FIT_DEVELOPMENT sources only, sort unique effective-availability dates within "
    "each country, calculate positive gaps to the immediately preceding date, take each eligible "
    "country's median gap, then take the median across country medians. Select the smallest "
    "preregistered candidate in (7,14,21,28) that is greater than or equal to "
    "COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS; return NO-GO rather than cap when no "
    "candidate qualifies. No target, label, outcome, or predictive metric is used."
)

ACTIVE_WINDOW_ZERO_SOURCE_NON_DISCRIMINATIVE = "NON_DISCRIMINATIVE"
ACTIVE_WINDOW_ZERO_SOURCE_DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
TEMPORAL_THRESHOLD_ELIGIBLE = "ELIGIBLE_BINDING_TEMPORAL_THRESHOLD"
TEMPORAL_THRESHOLD_NON_BINDING = "INELIGIBLE_NON_BINDING_TEMPORAL_THRESHOLD"
TEMPORAL_THRESHOLD_NON_POSITIVE = "INELIGIBLE_NON_POSITIVE_TEMPORAL_THRESHOLD"

STDBSCAN_CANDIDATE_DEFINITION = (
    "eps_space_km and eps_time_days are the six-decimal rounded p25/p50/p75 values of the "
    "per-country median within-country nearest-neighbour distances and positive temporal gaps. "
    "This gives each country one vote in candidate derivation; the existing pooled within-country "
    "registry distributions are retained as audit evidence. min_core_supports reuses the existing "
    "fixed registry (2,3,4)."
)

STDBSCAN_SELECTION_RULE = (
    "FMD-06B-R: first restrict predictor-facing configurations to 0 < eps_time_days <= "
    "active_window_days. Reject all-noise, near-all-noise (noise fraction >= 0.90), and near-giant "
    "(largest cluster fraction >= 0.90) configurations. For each remaining configuration, "
    "compare its global noise fraction, largest-cluster fraction, and origin cluster-coverage fraction "
    "to one-step neighbouring candidates that differ in exactly one axis; select the highest mean "
    "neighbour agreement (1 minus mean absolute structural deltas). Ties are resolved by smallest "
    "eps_space_km, then eps_time_days, then min_core_supports."
)

DEVELOPMENT_SOURCE_FIELDNAMES = [
    "source_id", "country", "first_fit_origin_t0_seen", "last_fit_origin_t0_seen",
    "effective_availability_date", "availability_quality", "cluster_event_date",
    "cluster_event_date_quality", "cluster_event_date_source_field", "latitude", "longitude",
    "gps_quality", "dedup_status", "model_candidate",
]

ACTIVE_WINDOW_FIELDNAMES = [
    "candidate_window_days", "n_evaluated_forecast_origins", "mean_active_source_count",
    "median_active_source_count", "p90_active_source_count", "p95_active_source_count",
    "zero_source_origin_count", "single_source_origin_count", "maximum_snapshot_size",
    "very_large_snapshot_count",
    "very_large_definition", "country_distribution_json", "year_distribution_json",
    "delta_mean_to_previous", "delta_mean_to_next", "relative_mean_change_to_previous",
    "relative_mean_change_to_next", "previous_zero_source_criterion_status",
    "country_balanced_median_preceding_source_gap_days",
    "n_countries_contributing_preceding_source_gap_median",
    "selection_eligible", "selection_reason",
]

STDBSCAN_CANDIDATE_FIELDNAMES = [
    "eps_space_km", "eps_time_days", "min_core_supports", "active_window_days",
    "gps_core_policy", "parameter_status", "config_hash", "temporal_eligibility_status",
    "predictor_facing_eligible", "eligibility_reason", "candidate_definition",
]

SPATIAL_DOMAIN_STATUS_GO = "GO"
SPATIAL_DOMAIN_STATUS_NO_GO = "NO-GO"

# FMD-06C reuses the pre-existing, pre-registered Checkpoint 7A domain-design
# candidate registry and selection rule VERBATIM (imported above, never
# redefined/appended/reordered here) -- see
# `services/model_development/domain_design.py` and the frozen
# `SPATIAL_TARGET_REFERENCE_SOURCE_SET = ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0`
# declaration in `data_processing/build_fmd_cohort.py` (FMD-05R), which names
# `get_eligible_sources` as the reference source set this reuses.
SPATIAL_RADIUS_CANDIDATE_SOURCE = "services.model_development.domain_design.PREDECLARED_DOMAIN_CANDIDATES_KM"
SPATIAL_RADIUS_CANDIDATES_KM = PREDECLARED_DOMAIN_CANDIDATES_KM
SPATIAL_REFERENCE_SOURCE_SET = "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
SPATIAL_PARAMETER_CLASSIFICATION = "DEVELOPMENT_CALIBRATED_GEOSPATIAL_EVALUATION_PARAMETER"

SPATIAL_RADIUS_SELECTION_RULE = (
    "services.model_development.domain_design.select_frozen_domain_distance (pre-existing, predeclared "
    "before FMD-06C candidate outcomes were generated): the smallest candidate in "
    "PREDECLARED_DOMAIN_CANDIDATES_KM whose FIT_DEVELOPMENT D1-D7 risk_target_eligible target-appearance "
    "coverage -- geodesic distance from the target to the nearest ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0 "
    "source <= candidate_km -- reaches exactly 100% of evaluated target appearances. A transparent rule "
    "fixed before any model-score computation, never chosen using predictive accuracy/capture, held-out "
    "data, or Sri Lanka case-study data. Returns DOMAIN_RULE_BLOCKED (NO-GO) rather than silently "
    "expanding past the predeclared candidates or dropping outliers if no candidate achieves full "
    "coverage."
)

SPATIAL_PROTOCOL_AMENDMENT_STATUS = "POST_FEASIBILITY_PROTOCOL_AMENDMENT"
SPATIAL_PROTOCOL_AMENDMENT_REASON = "ORIGINAL_100_PERCENT_COVERAGE_RULE_INFEASIBLE_WITHIN_PREDECLARED_CANDIDATES"
AMENDED_SPATIAL_DOMAIN_STATUS = "GO_WITH_TRANSPARENT_AMENDMENT"
AMENDED_SPATIAL_SELECTION_RULE = "MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN"
AMENDED_SPATIAL_PARAMETER_CLASSIFICATION = "FIXED_LOCAL_COMPUTATIONAL_EVALUATION_DOMAIN"
OUTSIDE_LOCAL_EVALUATION_DOMAIN = "OUTSIDE_LOCAL_EVALUATION_DOMAIN"

# FMD-06C-PA (POST_FEASIBILITY_PROTOCOL_AMENDMENT -- explicitly NOT preregistered):
# introduced only AFTER the original predeclared 100%-coverage rule
# (`SPATIAL_RADIUS_SELECTION_RULE` above) returned NO-GO on real FIT_DEVELOPMENT
# data. `MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN` fixes the LOCAL geospatial
# prediction domain at the LARGEST radius that was ALREADY present in the
# predeclared `PREDECLARED_DOMAIN_CANDIDATES_KM` registry -- never a new value
# invented after seeing development results, never extended past that
# predeclared maximum, and never chosen using held-out data, Sri Lanka data, or
# predictive-model performance.
FMD_SPATIAL_EVALUATION_RADIUS_KM = max(PREDECLARED_DOMAIN_CANDIDATES_KM)

AMENDED_SPATIAL_SELECTION_RATIONALE = (
    "FMD-06C-PA (POST_FEASIBILITY_PROTOCOL_AMENDMENT, NOT preregistered): the original predeclared rule "
    "-- select_frozen_domain_distance's smallest PREDECLARED_DOMAIN_CANDIDATES_KM candidate reaching "
    "100% FIT_DEVELOPMENT D1-D7 target-appearance coverage -- returned NO-GO because no candidate up to "
    "200km reached full coverage. To avoid inventing a new radius after seeing development results, "
    "extending the candidate search beyond the predeclared maximum, or using held-out data, Sri Lanka "
    "case-study data, or predictive-model performance to pick a radius, this amendment fixes the LOCAL "
    "geospatial prediction domain at FMD_SPATIAL_EVALUATION_RADIUS_KM = 200.0 -- the maximum radius "
    "already present in the predeclared candidate registry, never a newly introduced value. 200km is a "
    "fixed COMPUTATIONAL local evaluation domain only: not a universal biological distance, an inferred "
    "transmission distance, an ST-DBSCAN distance, a quarantine/protection distance, or an intervention "
    "recommendation. The predictive question becomes: for a forecast origin t0, is there at least one "
    "eligible historical D1-D7 target event within the fixed 200km local evaluation domain of "
    "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0?"
)

PA_LOCAL_DOMAIN_AUDIT_FIELDNAMES = [
    "forecast_origin_id", "country", "t0",
    "has_eligible_d1_d7_target", "n_eligible_d1_d7_targets",
    "n_targets_within_local_domain", "n_targets_outside_local_domain",
    "local_domain_positive", "outside_domain_target_present",
]

# FMD-06D: deterministic development-label freeze. The predictive-model
# unit stays the forecast origin (never a target-appearance row); the
# label is a pure projection of the already-frozen FMD-06C-PA local-domain
# audit -- no radius/domain/distance/clustering/window parameter is
# recomputed here.
PRIMARY_TARGET_HORIZON = "D1-D7"

RISK_LABEL_FIELDNAMES = [
    "forecast_origin_id", "country", "t0", "model_fitting_role",
    "risk_target_label", "has_eligible_d1_d7_target", "outside_domain_target_present",
    "local_evaluation_radius_km", "target_horizon", "spatial_reference_source_set",
    "spatial_protocol_amendment_status",
]

# FMD_TARGET_PROTOCOL.md Section 4: direction/speed are NO-GO because
# Tier A (gps_quality == EXACT) is structurally unreachable in the FMD
# corpus (0 of 31,658 target rows) -- a data-quality gap, not a modelling
# choice -- and this is explicitly NON-BLOCKING for the primary D1-D7
# binary risk task, which never requires Tier A.
DIRECTION_SPEED_STATUS = "NO-GO"
DIRECTION_SPEED_STATUS_REASON = (
    "Tier A (gps_quality == EXACT) is structurally unreachable for the FMD corpus (0 of 31,658 "
    "target rows; FMD_TARGET_PROTOCOL.md Section 4) -- a data-quality gap in the EMPRES-i BigQuery "
    "export, not a modelling choice. This is NON-BLOCKING for the primary binary D1-D7 risk task, "
    "which never requires Tier A. No direction/speed label or model is created here."
)

# FMD_EVALUATION_PROTOCOL.md Section 3: weather-window selection is a
# development-only decision that must be cross-validated inside
# FIT_DEVELOPMENT folds -- it is explicitly deferred to FMD-07, never made
# in FMD-06.
WEATHER_WINDOW_SELECTION_STATUS = "DEFERRED_TO_FMD07_DEVELOPMENT_SELECTION"

FMD06_OVERALL_STATUS_GO = "GO"
FMD06_OVERALL_STATUS_BLOCKED = "BLOCKED"

SPATIAL_TARGET_DISTANCE_FIELDNAMES = [
    "forecast_origin_id", "country", "t0", "target_id", "target_event_id", "target_date",
    "target_horizon", "active_source_count", "nearest_active_source_event_id",
    "nearest_active_source_distance_km", "containing_origin_model_fitting_role", "inclusion_status",
]

SPATIAL_DOMAIN_CANDIDATE_FIELDNAMES = [
    "candidate_radius_km", "evaluated_forecast_origin_count", "origins_with_eligible_target",
    "origins_with_target_within_radius", "origins_without_target_within_radius",
    "origin_capture_fraction", "target_event_appearance_count", "target_appearances_within_radius",
    "unique_target_event_count", "unique_targets_within_radius",
    "nearest_distance_p50_km", "nearest_distance_p75_km", "nearest_distance_p90_km", "nearest_distance_p95_km",
    "country_distribution_json", "year_distribution_json",
    "selection_eligible", "selection_reason",
]

STDBSCAN_SENSITIVITY_FIELDNAMES = [
    "eps_space_km", "eps_time_days", "min_core_supports", "active_window_days",
    "gps_core_policy", "parameter_status", "config_hash", "temporal_eligibility_status",
    "predictor_facing_eligible", "eligibility_reason", "unique_source_event_count", "n_evaluated_forecast_origins",
    "n_active_source_appearances", "n_cluster_usable_source_appearances",
    "n_temporal_unusable_source_appearances", "snapshot_source_timestamp_span_max_days",
    "cluster_count", "clustered_snapshot_event_appearance_count",
    "noise_snapshot_event_appearance_count", "noise_fraction", "origin_cluster_coverage",
    "cluster_size_p50", "cluster_size_p90", "cluster_size_p95", "cluster_size_max",
    "temporal_span_p50_days", "temporal_span_p90_days", "temporal_span_p95_days",
    "temporal_span_max_days", "spatial_compactness_p50_km", "spatial_compactness_p95_km",
    "spatial_compactness_max_km", "country_distribution_json", "year_distribution_json",
    "stability_score", "all_noise", "near_all_noise", "near_giant_cluster",
    "selection_eligible", "selection_reason",
]


@dataclass(frozen=True)
class ActiveWindowAudit:
    candidate_window_days: int
    n_evaluated_forecast_origins: int
    mean_active_source_count: float
    median_active_source_count: float
    p90_active_source_count: float
    p95_active_source_count: float
    zero_source_origin_count: int
    single_source_origin_count: int
    maximum_snapshot_size: int
    very_large_snapshot_count: int
    very_large_definition: str
    country_distribution_json: str
    year_distribution_json: str
    delta_mean_to_previous: float | None = None
    delta_mean_to_next: float | None = None
    relative_mean_change_to_previous: float | None = None
    relative_mean_change_to_next: float | None = None
    previous_zero_source_criterion_status: str = ACTIVE_WINDOW_ZERO_SOURCE_DIAGNOSTIC_ONLY
    country_balanced_median_preceding_source_gap_days: float | None = None
    n_countries_contributing_preceding_source_gap_median: int = 0
    selection_eligible: bool = False
    selection_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "candidate_window_days": self.candidate_window_days,
            "n_evaluated_forecast_origins": self.n_evaluated_forecast_origins,
            "mean_active_source_count": self.mean_active_source_count,
            "median_active_source_count": self.median_active_source_count,
            "p90_active_source_count": self.p90_active_source_count,
            "p95_active_source_count": self.p95_active_source_count,
            "zero_source_origin_count": self.zero_source_origin_count,
            "single_source_origin_count": self.single_source_origin_count,
            "maximum_snapshot_size": self.maximum_snapshot_size,
            "very_large_snapshot_count": self.very_large_snapshot_count,
            "very_large_definition": self.very_large_definition,
            "country_distribution_json": self.country_distribution_json,
            "year_distribution_json": self.year_distribution_json,
            "delta_mean_to_previous": self.delta_mean_to_previous,
            "delta_mean_to_next": self.delta_mean_to_next,
            "relative_mean_change_to_previous": self.relative_mean_change_to_previous,
            "relative_mean_change_to_next": self.relative_mean_change_to_next,
            "previous_zero_source_criterion_status": self.previous_zero_source_criterion_status,
            "country_balanced_median_preceding_source_gap_days": self.country_balanced_median_preceding_source_gap_days,
            "n_countries_contributing_preceding_source_gap_median": self.n_countries_contributing_preceding_source_gap_median,
            "selection_eligible": self.selection_eligible,
            "selection_reason": self.selection_reason,
        }


@dataclass(frozen=True)
class CountryBalancedPrecedingSourceGapAudit:
    statistic_name: str
    source_date_field: str
    country_balanced_median_preceding_source_gap_days: float | None
    n_countries_in_source_universe: int
    n_countries_contributing_median: int
    per_country: tuple[dict, ...]

    def as_dict(self) -> dict:
        return {
            "statistic_name": self.statistic_name,
            "source_date_field": self.source_date_field,
            "country_balanced_median_preceding_source_gap_days": self.country_balanced_median_preceding_source_gap_days,
            "n_countries_in_source_universe": self.n_countries_in_source_universe,
            "n_countries_contributing_median": self.n_countries_contributing_median,
            "country_weighting": "ONE_COUNTRY_MEDIAN_ONE_VOTE",
            "per_country": list(self.per_country),
        }


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = q * (len(ordered) - 1)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _finite_float(value: float | None, *, places: int = 6) -> float | None:
    if value is None or not math.isfinite(value) or value <= 0:
        return None
    return round(float(value), places)


def _quantile_values(values: Iterable[float], *, places: int = 6) -> list[float]:
    result = {
        rounded
        for value in values
        if (rounded := _finite_float(value, places=places)) is not None
    }
    return sorted(result)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_forecast_origins(path: str | Path) -> list[ForecastOrigin]:
    """Load the frozen origin ledger without reading targets or labels."""
    origins: list[ForecastOrigin] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            trigger_ids = [value for value in row["trigger_source_ids_at_t0"].split(";") if value]
            origins.append(
                ForecastOrigin(
                    forecast_origin_id=row["forecast_origin_id"],
                    country=row["country"],
                    t0=row["t0"],
                    temporal_mode=row["temporal_mode"],
                    trigger_source_ids_at_t0=trigger_ids,
                    trigger_source_count=int(row["trigger_source_count"]),
                )
            )
    return origins


def build_fmd06_development_source_universe(
    repo,
    forecast_origins: list[ForecastOrigin],
    *,
    disease: str = FMD_DISEASE,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> DevelopmentSourceUniverseResult:
    """Strict FMD-06B source-universe entry point.

    The existing source-universe builder intentionally reports exclusions for
    an administrative mixed ledger. Calibration must be stricter: it rejects
    a mixed role list before any repository query, then delegates the actual
    validated-source construction unchanged.
    """
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_fmd06_development_source_universe")
    return build_fit_development_source_universe(
        repo,
        forecast_origins,
        disease=disease,
        max_active_window_days=MAX_ACTIVE_WINDOW_DAYS,
        cutoff=cutoff,
    )


def _active_sources_for_origin(
    origin: ForecastOrigin,
    sources_by_country: dict[str, list[DevelopmentSource]],
    *,
    active_window_days: int,
) -> list[DevelopmentSource]:
    t0 = parse_flexible_date(origin.t0)
    if t0 is None:
        raise ValueError(f"unparseable forecast-origin t0: {origin.t0!r}")
    start = t0.fromordinal(t0.toordinal() - active_window_days)
    active: list[DevelopmentSource] = []
    for source in sources_by_country.get(origin.country, []):
        availability = parse_flexible_date(source.effective_availability_date)
        if availability is not None and start <= availability <= t0:
            active.append(source)
    return sorted(active, key=lambda source: source.source_id)


def _source_index(sources: list[DevelopmentSource]) -> dict[str, list[DevelopmentSource]]:
    by_country: dict[str, list[DevelopmentSource]] = defaultdict(list)
    for source in sources:
        by_country[source.country].append(source)
    for values in by_country.values():
        values.sort(key=lambda source: source.source_id)
    return dict(by_country)


def _origin_distribution(origins: list[ForecastOrigin], counts: list[int], key_fn) -> dict:
    grouped: dict[str, list[int]] = defaultdict(list)
    for origin, count in zip(origins, counts):
        grouped[str(key_fn(origin))].append(count)
    result: dict[str, dict] = {}
    for key in sorted(grouped):
        values = grouped[key]
        result[key] = {
            "n_origins": len(values),
            "mean_active_source_count": round(mean(values), 6),
            "median_active_source_count": round(float(median(values)), 6),
            "zero_source_origin_count": sum(value == 0 for value in values),
            "single_source_origin_count": sum(value == 1 for value in values),
        }
    return result


def _assert_development_sources_only(
    sources: list[DevelopmentSource],
    *,
    cutoff: str,
    caller: str,
) -> None:
    """Reject source rows whose development provenance is not auditable.

    ``DevelopmentSource`` intentionally carries the first/last development
    origin where it was observed.  Those fields let source-only chronology
    calculations enforce the same held-out/Sri-Lanka firewall even though no
    target or exposure table is an input to the calculation.
    """
    cutoff_date = parse_flexible_date(cutoff)
    if cutoff_date is None:
        raise ValueError(f"{caller}: cutoff is not a parseable date: {cutoff!r}")
    offending: list[str] = []
    for source in sources:
        first_seen = parse_flexible_date(source.first_fit_origin_t0_seen)
        last_seen = parse_flexible_date(source.last_fit_origin_t0_seen)
        if source.country == "Sri Lanka":
            offending.append(f"{source.source_id}=SRI_LANKA_TRANSFER_CASE_STUDY")
        elif first_seen is None or last_seen is None:
            offending.append(f"{source.source_id}=UNPARSEABLE_FIT_DEVELOPMENT_PROVENANCE")
        elif first_seen >= cutoff_date or last_seen >= cutoff_date:
            offending.append(f"{source.source_id}=HELD_OUT_FROM_MODEL_FITTING")
    if offending:
        raise ValueError(
            f"{caller}: received {len(offending)} non-FIT_DEVELOPMENT source(s): "
            + ", ".join(offending)
        )


def build_country_balanced_preceding_source_gap_audit(
    sources: list[DevelopmentSource],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> CountryBalancedPrecedingSourceGapAudit:
    """Compute the FMD-06B-R source-chronology window statistic.

    Dates are deduplicated within country before consecutive positive gaps
    are calculated.  Each eligible country contributes exactly one median,
    so adding more dated rows to a dense country cannot give it more weight
    in the final cross-country median.
    """
    _assert_development_sources_only(
        sources,
        cutoff=cutoff,
        caller="build_country_balanced_preceding_source_gap_audit",
    )
    by_country: dict[str, set] = defaultdict(set)
    for source in sources:
        source_date = parse_flexible_date(source.effective_availability_date)
        if source_date is not None:
            by_country[source.country].add(source_date)

    per_country: list[dict] = []
    country_medians: list[float] = []
    for country in sorted(by_country):
        dates = sorted(by_country[country])
        positive_gaps = [
            float((current - previous).days)
            for previous, current in zip(dates, dates[1:])
            if (current - previous).days > 0
        ]
        if len(dates) < 2 or not positive_gaps:
            continue
        country_median = float(median(positive_gaps))
        country_medians.append(country_median)
        per_country.append({
            "country": country,
            "n_unique_source_dates": len(dates),
            "n_positive_preceding_source_gaps": len(positive_gaps),
            "median_positive_preceding_source_gap_days": round(country_median, 6),
        })

    overall = round(float(median(country_medians)), 6) if country_medians else None
    return CountryBalancedPrecedingSourceGapAudit(
        statistic_name="COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS",
        source_date_field="effective_availability_date",
        country_balanced_median_preceding_source_gap_days=overall,
        n_countries_in_source_universe=len(by_country),
        n_countries_contributing_median=len(country_medians),
        per_country=tuple(per_country),
    )


def audit_trigger_sources_at_t0(
    forecast_origins: list[ForecastOrigin],
    sources: list[DevelopmentSource],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> dict:
    """Audit why positive FMD windows cannot distinguish empty origins."""
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="audit_trigger_sources_at_t0")
    _assert_development_sources_only(sources, cutoff=cutoff, caller="audit_trigger_sources_at_t0")
    sources_by_id = {source.source_id: source for source in sources}
    missing_references = 0
    date_mismatches = 0
    origins_with_valid_trigger_at_t0 = 0
    trigger_reference_count = 0
    for origin in forecast_origins:
        valid_at_t0 = False
        for source_id in origin.trigger_source_ids_at_t0:
            trigger_reference_count += 1
            source = sources_by_id.get(source_id)
            if source is None:
                missing_references += 1
                continue
            if source.country != origin.country or source.effective_availability_date != origin.t0:
                date_mismatches += 1
                continue
            valid_at_t0 = True
        if valid_at_t0:
            origins_with_valid_trigger_at_t0 += 1
    return {
        "development_forecast_origin_count": len(forecast_origins),
        "trigger_source_reference_count": trigger_reference_count,
        "origins_with_valid_trigger_source_at_t0_count": origins_with_valid_trigger_at_t0,
        "origins_without_valid_trigger_source_at_t0_count": len(forecast_origins) - origins_with_valid_trigger_at_t0,
        "missing_trigger_source_reference_count": missing_references,
        "trigger_source_country_or_date_mismatch_count": date_mismatches,
        "all_development_origins_have_trigger_source_at_t0": bool(forecast_origins)
        and origins_with_valid_trigger_at_t0 == len(forecast_origins),
    }


def temporal_threshold_eligibility(eps_time_days: float, active_window_days: int) -> tuple[str, bool, str]:
    if eps_time_days <= 0:
        return (
            TEMPORAL_THRESHOLD_NON_POSITIVE,
            False,
            "predictor-facing temporal epsilon must be strictly positive",
        )
    if eps_time_days > active_window_days:
        return (
            TEMPORAL_THRESHOLD_NON_BINDING,
            False,
            "eps_time_days exceeds active_window_days and is non-binding within an inclusive predictor snapshot",
        )
    return (
        TEMPORAL_THRESHOLD_ELIGIBLE,
        True,
        "satisfies predictor-facing invariant 0 < eps_time_days <= active_window_days",
    )


def assert_predictor_facing_temporal_epsilon(eps_time_days: float, active_window_days: int) -> None:
    status, eligible, reason = temporal_threshold_eligibility(eps_time_days, active_window_days)
    if not eligible:
        raise ValueError(
            "predictor-facing FMD ST-DBSCAN invariant violated: "
            f"0 < eps_time_days <= active_window_days; got eps_time_days={eps_time_days}, "
            f"active_window_days={active_window_days}, status={status}: {reason}"
        )


def build_active_window_sensitivity(
    forecast_origins: list[ForecastOrigin],
    sources: list[DevelopmentSource],
    *,
    candidate_windows: Iterable[int] = ACTIVE_WINDOW_DAY_CANDIDATES,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[ActiveWindowAudit]:
    """Compute temporal-window structure from development sources only."""
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_active_window_sensitivity")
    _assert_development_sources_only(sources, cutoff=cutoff, caller="build_active_window_sensitivity")
    candidates = sorted({int(value) for value in candidate_windows})
    if any(value < 0 for value in candidates):
        raise ValueError(f"active-window candidates must be >= 0, got {candidates}")
    by_country = _source_index(sources)
    counts_by_window: dict[int, list[int]] = {
        window: [len(_active_sources_for_origin(origin, by_country, active_window_days=window)) for origin in forecast_origins]
        for window in candidates
    }
    audits: list[ActiveWindowAudit] = []
    for window in candidates:
        counts = counts_by_window[window]
        p95 = float(_quantile([float(value) for value in counts], 0.95) or 0.0)
        audits.append(
            ActiveWindowAudit(
                candidate_window_days=window,
                n_evaluated_forecast_origins=len(forecast_origins),
                mean_active_source_count=round(mean(counts), 6) if counts else 0.0,
                median_active_source_count=round(float(median(counts)), 6) if counts else 0.0,
                p90_active_source_count=round(float(_quantile([float(value) for value in counts], 0.90) or 0.0), 6),
                p95_active_source_count=round(p95, 6),
                zero_source_origin_count=sum(value == 0 for value in counts),
                single_source_origin_count=sum(value == 1 for value in counts),
                maximum_snapshot_size=max(counts) if counts else 0,
                very_large_snapshot_count=sum(value > p95 for value in counts),
                very_large_definition="active_source_count > candidate-specific p95 active_source_count",
                country_distribution_json=_json(_origin_distribution(forecast_origins, counts, lambda origin: origin.country)),
                year_distribution_json=_json(_origin_distribution(forecast_origins, counts, lambda origin: parse_flexible_date(origin.t0).year)),
            )
        )

    for index, audit in enumerate(audits):
        previous = audits[index - 1] if index else None
        following = audits[index + 1] if index + 1 < len(audits) else None
        delta_previous = round(audit.mean_active_source_count - previous.mean_active_source_count, 6) if previous else None
        delta_next = round(following.mean_active_source_count - audit.mean_active_source_count, 6) if following else None
        relative_previous = round(delta_previous / previous.mean_active_source_count, 6) if previous and previous.mean_active_source_count else None
        relative_next = round(delta_next / audit.mean_active_source_count, 6) if following and audit.mean_active_source_count else None
        audits[index] = ActiveWindowAudit(
            **{
                **audit.__dict__,
                "delta_mean_to_previous": delta_previous,
                "delta_mean_to_next": delta_next,
                "relative_mean_change_to_previous": relative_previous,
                "relative_mean_change_to_next": relative_next,
            }
        )

    if not audits:
        return []

    gap_audit = build_country_balanced_preceding_source_gap_audit(sources, cutoff=cutoff)
    gap_statistic = gap_audit.country_balanced_median_preceding_source_gap_days
    zero_source_status = (
        ACTIVE_WINDOW_ZERO_SOURCE_NON_DISCRIMINATIVE
        if len({audit.zero_source_origin_count for audit in audits}) == 1
        else ACTIVE_WINDOW_ZERO_SOURCE_DIAGNOSTIC_ONLY
    )
    selected_window: int | None = None
    if gap_statistic is not None:
        qualifying = [audit.candidate_window_days for audit in audits if audit.candidate_window_days >= gap_statistic]
        if qualifying:
            selected_window = min(qualifying)
    result: list[ActiveWindowAudit] = []
    for audit in audits:
        if gap_statistic is None:
            eligible = False
            reason = "NO-GO: no country has at least two unique effective availability dates"
        elif selected_window is None:
            eligible = False
            reason = (
                "NO-GO: COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS exceeds the largest "
                f"candidate ({max(candidates) if candidates else 0})"
            )
        elif audit.candidate_window_days == selected_window:
            eligible = True
            reason = "GO candidate: smallest allowed window >= COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS"
        elif audit.candidate_window_days < gap_statistic:
            eligible = False
            reason = "not selected: candidate is smaller than the country-balanced preceding-source-gap statistic"
        else:
            eligible = False
            reason = "not selected: larger candidate than the deterministic smallest qualifying window"
        result.append(
            ActiveWindowAudit(
                **{
                    **audit.__dict__,
                    "previous_zero_source_criterion_status": zero_source_status,
                    "country_balanced_median_preceding_source_gap_days": gap_statistic,
                    "n_countries_contributing_preceding_source_gap_median": gap_audit.n_countries_contributing_median,
                    "selection_eligible": eligible,
                    "selection_reason": reason,
                }
            )
        )
    return result


def select_active_window(audits: list[ActiveWindowAudit]) -> tuple[str, int | None, str]:
    if not audits:
        return ACTIVE_WINDOW_STATUS_NO_GO, None, "NO-GO: no active-window candidates were supplied"
    eligible = [audit for audit in audits if audit.selection_eligible]
    if not eligible:
        return ACTIVE_WINDOW_STATUS_NO_GO, None, audits[0].selection_reason or "NO-GO: no candidate passed the coverage rule"
    selected = min(eligible, key=lambda audit: audit.candidate_window_days)
    return ACTIVE_WINDOW_STATUS_GO, selected.candidate_window_days, ACTIVE_WINDOW_SELECTION_RULE


def derive_stdbscan_candidates(
    sources: list[DevelopmentSource],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> tuple[list[float], list[float], list[int], dict]:
    """Derive country-balanced geometry/time candidates from the existing registry."""
    _assert_development_sources_only(sources, cutoff=cutoff, caller="derive_stdbscan_candidates")
    report = build_country_scoped_parameter_candidates(sources)
    spatial_pooled = report.pooled_within_country_nn_distance_km_quantiles
    temporal_pooled = report.pooled_within_country_temporal_gap_days_quantiles
    country_spatial_medians = [
        item["p50"] for item in report.per_country_nn_distance if item["p50"] is not None
    ]
    country_temporal_medians = [
        item["p50"] for item in report.per_country_temporal_gap if item["p50"] is not None
    ]
    spatial_country_quantiles = [_quantile(country_spatial_medians, q) for q in (0.25, 0.50, 0.75)]
    temporal_country_quantiles = [_quantile(country_temporal_medians, q) for q in (0.25, 0.50, 0.75)]
    spatial_candidates = _quantile_values(spatial_country_quantiles)
    temporal_candidates = _quantile_values(temporal_country_quantiles)
    if not spatial_candidates:
        spatial_candidates = _quantile_values(spatial_pooled.get(key) for key in ("p25", "p50", "p75"))
    if not temporal_candidates:
        temporal_candidates = _quantile_values(temporal_pooled.get(key) for key in ("p25", "p50", "p75"))
    if not spatial_candidates or not temporal_candidates:
        raise ValueError("NO-GO: country-scoped development data did not yield positive ST-DBSCAN candidates")
    evidence = {
        "country_scoped_parameter_report": report.as_dict(),
        "spatial_candidates_km": spatial_candidates,
        "temporal_candidates_days": temporal_candidates,
        "min_core_support_candidates": list(MIN_CORE_SUPPORT_CANDIDATES),
        "candidate_definition": STDBSCAN_CANDIDATE_DEFINITION,
    }
    return spatial_candidates, temporal_candidates, list(MIN_CORE_SUPPORT_CANDIDATES), evidence


def _cluster_distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "p50": round(float(_quantile(values, 0.50)), 6) if values else None,
        "p90": round(float(_quantile(values, 0.90)), 6) if values else None,
        "p95": round(float(_quantile(values, 0.95)), 6) if values else None,
        "max": round(max(values), 6) if values else None,
    }


def _evaluate_configuration(
    forecast_origins: list[ForecastOrigin],
    sources_by_country: dict[str, list[DevelopmentSource]],
    records_by_id: dict[str, HistoricalOutbreakRecord],
    *,
    config: STDBSCANConfig,
) -> dict:
    cluster_sizes: list[float] = []
    temporal_spans: list[float] = []
    compactness: list[float] = []
    snapshot_source_timestamp_spans: list[float] = []
    n_active = 0
    n_usable = 0
    n_temporal_unusable = 0
    n_clusters = 0
    clustered_events = 0
    noise_events = 0
    clustered_origin_count = 0
    active_source_ids: set[str] = set()
    country_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"n_origins": 0, "origins_with_cluster": 0, "clustered_snapshot_event_appearance_count": 0})
    year_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"n_origins": 0, "origins_with_cluster": 0, "clustered_snapshot_event_appearance_count": 0})

    for origin in forecast_origins:
        active = _active_sources_for_origin(origin, sources_by_country, active_window_days=config.active_window_days)
        usable: list[DevelopmentSource] = []
        event_date_by_id: dict[str, str] = {}
        for source in active:
            record = records_by_id.get(source.source_id)
            if record is None:
                n_temporal_unusable += 1
                continue
            event_date = resolve_cluster_event_date(record, t0=origin.t0)
            if event_date.usability == ST_USABLE and event_date.cluster_event_date:
                usable.append(source)
                event_date_by_id[source.source_id] = event_date.cluster_event_date
            else:
                n_temporal_unusable += 1

        n_active += len(active)
        active_source_ids.update(source.source_id for source in active)
        availability_dates = [
            parse_flexible_date(source.effective_availability_date)
            for source in active
        ]
        availability_dates = [value for value in availability_dates if value is not None]
        if len(availability_dates) >= 2:
            snapshot_source_timestamp_spans.append(float((max(availability_dates) - min(availability_dates)).days))
        n_usable += len(usable)
        core_support = compute_core_support_assignments(usable, gps_core_policy=config.gps_core_policy)
        points = [(s.source_id, s.latitude, s.longitude, event_date_by_id[s.source_id]) for s in usable]
        assignments, summaries = run_st_clustering(
            usable_points=points,
            core_support_by_id=core_support,
            eps_space_km=config.eps_space_km,
            eps_time_days=config.eps_time_days,
            min_core_supports=config.min_core_supports,
            config_hash=config.config_hash(),
            forecast_origin_id=origin.forecast_origin_id,
        )
        n_clusters += len(summaries)
        if summaries:
            clustered_origin_count += 1
        clustered_events += sum(summary.member_count for summary in summaries)
        noise_events += sum(assignment.is_noise for assignment in assignments.values())
        country = origin.country
        year = str(parse_flexible_date(origin.t0).year)
        country_stats[country]["n_origins"] += 1
        year_stats[year]["n_origins"] += 1
        if summaries:
            country_stats[country]["origins_with_cluster"] += 1
            year_stats[year]["origins_with_cluster"] += 1
        country_stats[country]["clustered_snapshot_event_appearance_count"] += sum(summary.member_count for summary in summaries)
        year_stats[year]["clustered_snapshot_event_appearance_count"] += sum(summary.member_count for summary in summaries)

        for summary in summaries:
            cluster_sizes.append(float(summary.member_count))
            temporal_start = parse_flexible_date(summary.cluster_start_date)
            temporal_end = parse_flexible_date(summary.cluster_end_date)
            if temporal_start is not None and temporal_end is not None:
                temporal_spans.append(float((temporal_end - temporal_start).days))
            centroid_distances = [
                _distance_km(summary.centroid_lat, summary.centroid_lon, records_by_id[source_id].latitude, records_by_id[source_id].longitude)
                for source_id in summary.member_source_ids
            ]
            compactness.extend(centroid_distances)

    def _coverage(stats: dict[str, dict[str, int]]) -> dict:
        result = {}
        for key in sorted(stats):
            row = stats[key]
            result[key] = {
                **row,
                "cluster_coverage_fraction": round(row["origins_with_cluster"] / row["n_origins"], 6) if row["n_origins"] else 0.0,
            }
        return result

    largest = max(cluster_sizes) if cluster_sizes else 0.0
    noise_fraction = noise_events / n_usable if n_usable else None
    cluster_coverage = clustered_origin_count / len(forecast_origins) if forecast_origins else 0.0
    largest_cluster_fraction = largest / n_usable if n_usable else None
    near_all_noise = bool(noise_fraction is not None and noise_fraction >= NEAR_ALL_NOISE_FRACTION)
    near_giant = bool(largest_cluster_fraction is not None and largest_cluster_fraction >= NEAR_GIANT_CLUSTER_FRACTION)
    all_noise = n_clusters == 0
    return {
        "eps_space_km": config.eps_space_km,
        "eps_time_days": config.eps_time_days,
        "min_core_supports": config.min_core_supports,
        "active_window_days": config.active_window_days,
        "gps_core_policy": config.gps_core_policy,
        "parameter_status": config.parameter_status,
        "config_hash": config.config_hash(),
        "n_evaluated_forecast_origins": len(forecast_origins),
        "n_active_source_appearances": n_active,
        "n_cluster_usable_source_appearances": n_usable,
        "n_temporal_unusable_source_appearances": n_temporal_unusable,
        "cluster_count": n_clusters,
        "snapshot_source_timestamp_span_max_days": max(snapshot_source_timestamp_spans) if snapshot_source_timestamp_spans else 0.0,
        "unique_source_event_count": len(active_source_ids),
        "clustered_snapshot_event_appearance_count": clustered_events,
        "noise_snapshot_event_appearance_count": noise_events,
        "noise_fraction": round(noise_fraction, 6) if noise_fraction is not None else None,
        "origin_cluster_coverage": round(cluster_coverage, 6),
        "cluster_size_p50": _cluster_distribution(cluster_sizes)["p50"],
        "cluster_size_p90": _cluster_distribution(cluster_sizes)["p90"],
        "cluster_size_p95": _cluster_distribution(cluster_sizes)["p95"],
        "cluster_size_max": _cluster_distribution(cluster_sizes)["max"],
        "temporal_span_p50_days": _cluster_distribution(temporal_spans)["p50"],
        "temporal_span_p90_days": _cluster_distribution(temporal_spans)["p90"],
        "temporal_span_p95_days": _cluster_distribution(temporal_spans)["p95"],
        "temporal_span_max_days": _cluster_distribution(temporal_spans)["max"],
        "spatial_compactness_p50_km": _cluster_distribution(compactness)["p50"],
        "spatial_compactness_p95_km": _cluster_distribution(compactness)["p95"],
        "spatial_compactness_max_km": _cluster_distribution(compactness)["max"],
        "country_distribution_json": _json(_coverage(country_stats)),
        "year_distribution_json": _json(_coverage(year_stats)),
        "stability_score": None,
        "all_noise": all_noise,
        "near_all_noise": near_all_noise,
        "near_giant_cluster": near_giant,
        "selection_eligible": not all_noise and not near_all_noise and not near_giant,
        "selection_reason": "eligible structural configuration" if not all_noise and not near_all_noise and not near_giant else "degenerate structural configuration",
    }


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from .geospatial.distance import distance_km

    return distance_km(lat1, lon1, lat2, lon2)


def _ineligible_configuration_audit(
    config: STDBSCANConfig,
    *,
    status: str,
    reason: str,
) -> dict:
    """Return an audit row without running clustering for an ineligible epsilon."""
    row = {
        "eps_space_km": config.eps_space_km,
        "eps_time_days": config.eps_time_days,
        "min_core_supports": config.min_core_supports,
        "active_window_days": config.active_window_days,
        "gps_core_policy": config.gps_core_policy,
        "parameter_status": config.parameter_status,
        "config_hash": config.config_hash(),
        "temporal_eligibility_status": status,
        "predictor_facing_eligible": False,
        "eligibility_reason": reason,
        "unique_source_event_count": None,
        "n_evaluated_forecast_origins": None,
        "n_active_source_appearances": None,
        "n_cluster_usable_source_appearances": None,
        "n_temporal_unusable_source_appearances": None,
        "snapshot_source_timestamp_span_max_days": None,
        "cluster_count": None,
        "clustered_snapshot_event_appearance_count": None,
        "noise_snapshot_event_appearance_count": None,
        "noise_fraction": None,
        "origin_cluster_coverage": None,
        "cluster_size_p50": None,
        "cluster_size_p90": None,
        "cluster_size_p95": None,
        "cluster_size_max": None,
        "temporal_span_p50_days": None,
        "temporal_span_p90_days": None,
        "temporal_span_p95_days": None,
        "temporal_span_max_days": None,
        "spatial_compactness_p50_km": None,
        "spatial_compactness_p95_km": None,
        "spatial_compactness_max_km": None,
        "country_distribution_json": "{}",
        "year_distribution_json": "{}",
        "stability_score": None,
        "all_noise": None,
        "near_all_noise": None,
        "near_giant_cluster": None,
        "selection_eligible": False,
        "selection_reason": reason,
    }
    return row


def build_stdbscan_sensitivity(
    forecast_origins: list[ForecastOrigin],
    sources: list[DevelopmentSource],
    records_by_id: dict[str, HistoricalOutbreakRecord],
    *,
    active_window_days: int,
    eps_space_candidates: Iterable[float],
    eps_time_candidates: Iterable[float],
    min_core_support_candidates: Iterable[int],
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> tuple[list[dict], dict | None]:
    """Evaluate deterministic structural configurations on FIT_DEVELOPMENT."""
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_stdbscan_sensitivity")
    _assert_development_sources_only(sources, cutoff=cutoff, caller="build_stdbscan_sensitivity")
    spatial = sorted({float(value) for value in eps_space_candidates})
    temporal = sorted({float(value) for value in eps_time_candidates})
    min_core = sorted({int(value) for value in min_core_support_candidates})
    if not spatial or not temporal or not min_core:
        return [], None
    by_country = _source_index(sources)
    rows: list[dict] = []
    for eps_space, eps_time, min_support in itertools.product(spatial, temporal, min_core):
        config = STDBSCANConfig(
            eps_space_km=eps_space,
            eps_time_days=eps_time,
            min_core_supports=min_support,
            active_window_days=active_window_days,
            gps_core_policy=PRIMARY_GPS_CORE_POLICY,
            parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
        )
        temporal_status, temporal_eligible, temporal_reason = temporal_threshold_eligibility(
            eps_time,
            active_window_days,
        )
        if not temporal_eligible:
            rows.append(
                _ineligible_configuration_audit(
                    config,
                    status=temporal_status,
                    reason=temporal_reason,
                )
            )
            continue
        row = _evaluate_configuration(forecast_origins, by_country, records_by_id, config=config)
        row.update(
            {
                "temporal_eligibility_status": temporal_status,
                "predictor_facing_eligible": True,
                "eligibility_reason": temporal_reason,
            }
        )
        rows.append(row)

    eligible_rows = [row for row in rows if row["predictor_facing_eligible"]]
    by_key = {(row["eps_space_km"], row["eps_time_days"], row["min_core_supports"]): row for row in eligible_rows}
    for row in eligible_rows:
        key = (row["eps_space_km"], row["eps_time_days"], row["min_core_supports"])
        neighbours: list[dict] = []
        for axis, values in enumerate((spatial, temporal, min_core)):
            position = values.index(key[axis])
            for neighbour_position in (position - 1, position + 1):
                if 0 <= neighbour_position < len(values):
                    neighbour_key = list(key)
                    neighbour_key[axis] = values[neighbour_position]
                    candidate = by_key.get(tuple(neighbour_key))
                    if candidate is not None:
                        neighbours.append(candidate)
        if neighbours:
            agreements = []
            for neighbour in neighbours:
                deltas = [
                    abs((row["noise_fraction"] or 0.0) - (neighbour["noise_fraction"] or 0.0)),
                    abs(row["origin_cluster_coverage"] - neighbour["origin_cluster_coverage"]),
                    abs((row["cluster_size_p95"] or 0.0) / max(row["n_cluster_usable_source_appearances"], 1) - (neighbour["cluster_size_p95"] or 0.0) / max(neighbour["n_cluster_usable_source_appearances"], 1)),
                ]
                agreements.append(1.0 - (sum(deltas) / len(deltas)))
            row["stability_score"] = round(mean(agreements), 6)
        else:
            row["stability_score"] = 1.0

    eligible = [row for row in eligible_rows if row["selection_eligible"] and row["stability_score"] is not None]
    selected = None
    if eligible:
        selected = min(
            eligible,
            key=lambda row: (
                -(row["stability_score"] if row["stability_score"] is not None else -1.0),
                row["eps_space_km"], row["eps_time_days"], row["min_core_supports"],
            ),
        )
        for row in rows:
            if row is selected:
                row["selection_reason"] = STDBSCAN_SELECTION_RULE
            elif row["selection_eligible"]:
                row["selection_reason"] = "eligible but lower local structural stability or tie-break rank"
    return rows, selected


def _origin_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _freeze_hashes(out_dir: Path, names: list[str]) -> dict[str, str]:
    return {name: _sha256(out_dir / name) for name in names}


def build_fmd06c_spatial_target_distance_audit(
    repo,
    forecast_origins: list[ForecastOrigin],
    *,
    disease: str = FMD_DISEASE,
    active_window_days: int,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[dict]:
    """FMD-06C nearest-source distance audit (one row per FIT_DEVELOPMENT
    forecast-origin/D1-D7 `risk_target_eligible` target appearance).

    Reuses the exact FMD-05R-frozen `ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0`
    reference set (`source_selector.get_eligible_sources`, the same call
    signature `services/model_development/domain_design.py` and
    `services/forecast_origin.py:build_source_snapshot` already use) and the
    existing WGS84 geodesic helper (`geospatial.distance.distance_km`). An
    origin with zero eligible active sources still contributes one row per
    eligible target, explicitly marked `EXCLUDED_NO_ELIGIBLE_ACTIVE_SOURCE`
    rather than being silently dropped.
    """
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_fmd06c_spatial_target_distance_audit")
    rows: list[dict] = []
    for origin in sorted(forecast_origins, key=lambda o: o.forecast_origin_id):
        result = get_eligible_sources(
            repo, disease=disease, t0=origin.t0, active_window_days=active_window_days,
            temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=origin.country,
            domain_scope=RecordDomainScope.HISTORICAL_ONLY,
        )
        sources = sorted(result.sources, key=lambda s: s.source_id)
        targets = build_forecast_targets(
            repo, origin, disease=disease, source_ids_at_origin={s.source_id for s in sources},
        )
        for target in sorted(targets, key=lambda t: t.target_id):
            if not target.risk_target_eligible:
                continue
            nearest_id, nearest_d = None, None
            for source in sources:
                d = distance_km(source.latitude, source.longitude, target.latitude, target.longitude)
                if nearest_d is None or d < nearest_d:
                    nearest_d, nearest_id = d, source.source_id
            rows.append({
                "forecast_origin_id": origin.forecast_origin_id,
                "country": origin.country,
                "t0": origin.t0,
                "target_id": target.target_id,
                "target_event_id": target.target_event_id,
                "target_date": target.historical_event_date,
                "target_horizon": target.lead_days,
                "active_source_count": len(sources),
                "nearest_active_source_event_id": nearest_id,
                "nearest_active_source_distance_km": nearest_d,
                "containing_origin_model_fitting_role": classify_origin_role(origin, cutoff=cutoff),
                "inclusion_status": "EVALUATED" if sources else "EXCLUDED_NO_ELIGIBLE_ACTIVE_SOURCE",
            })
    return rows


def _capture_distribution(
    forecast_origins: list[ForecastOrigin],
    by_origin: dict[str, list[TargetDomainCoverage]],
    *,
    candidate: float,
    key_fn,
) -> dict:
    origins_by_key: dict[str, list[ForecastOrigin]] = defaultdict(list)
    for origin in forecast_origins:
        if origin.forecast_origin_id in by_origin:
            origins_by_key[str(key_fn(origin))].append(origin)
    result: dict[str, dict] = {}
    for key in sorted(origins_by_key):
        group = origins_by_key[key]
        within = sum(
            any(row.covered_by_candidate_km[candidate] for row in by_origin[o.forecast_origin_id])
            for o in group
        )
        result[key] = {
            "origins_with_eligible_target": len(group),
            "origins_with_target_within_radius": within,
        }
    return result


def build_fmd06c_domain_candidate_audit(
    forecast_origins: list[ForecastOrigin],
    audits: list[DomainCandidateAudit],
    coverage_rows: list[TargetDomainCoverage],
    *,
    candidates_km: tuple = SPATIAL_RADIUS_CANDIDATES_KM,
) -> tuple[list[dict], float | None, str]:
    """FMD-06C candidate-radius reporting layer.

    R2: now that `domain_design.build_development_domain_candidate_audit`
    accepts an explicit `model_fitting_cutoff` (R1), this no longer
    recomputes candidate coverage or constructs `DomainCandidateAudit`
    rows itself. `audits` and `coverage_rows` are the UNCHANGED return
    values of that generic call (made once in `run_fmd06c` under the
    explicit `model_fitting_cutoff=FMD_MODEL_FITTING_CUTOFF`), and
    `select_frozen_domain_distance` (imported unchanged from the same
    module) alone makes the GO/NO-GO selection decision. This function
    only adds FMD-specific reporting context on top of that
    already-decided coverage: origin capture fractions, distance
    percentiles, and country/year distributions."""
    selected_radius, rule_status = select_frozen_domain_distance(audits)

    by_origin: dict[str, list[TargetDomainCoverage]] = defaultdict(list)
    for row in coverage_rows:
        by_origin[row.forecast_origin_id].append(row)
    origins_with_eligible_target = set(by_origin)
    distances = [
        row.min_distance_to_eligible_source_km
        for row in coverage_rows
        if row.min_distance_to_eligible_source_km is not None
    ]
    percentiles = {
        label: (round(value, 6) if (value := _quantile(distances, q)) is not None else None)
        for label, q in (("p50", 0.50), ("p75", 0.75), ("p90", 0.90), ("p95", 0.95))
    }
    unique_target_event_count = len({row.target_event_id for row in coverage_rows})

    audit_by_candidate = {audit.candidate_distance_km: audit for audit in audits}
    candidate_rows: list[dict] = []
    for candidate in sorted(candidates_km):
        audit = audit_by_candidate[candidate]
        origins_within = {
            origin_id
            for origin_id, rows in by_origin.items()
            if any(row.covered_by_candidate_km[candidate] for row in rows)
        }
        targets_within = {
            row.target_event_id
            for row in coverage_rows
            if row.covered_by_candidate_km[candidate]
        }
        full_coverage = bool(audit.n_targets_total) and audit.n_targets_covered == audit.n_targets_total
        if full_coverage and candidate == selected_radius:
            selection_reason = SPATIAL_RADIUS_SELECTION_RULE
        elif full_coverage:
            selection_reason = "eligible (full FIT_DEVELOPMENT target coverage) but not the smallest predeclared candidate achieving it"
        else:
            selection_reason = "not selected: does not achieve full FIT_DEVELOPMENT target-appearance coverage"
        candidate_rows.append({
            "candidate_radius_km": candidate,
            "evaluated_forecast_origin_count": len(forecast_origins),
            "origins_with_eligible_target": len(origins_with_eligible_target),
            "origins_with_target_within_radius": len(origins_within),
            "origins_without_target_within_radius": len(origins_with_eligible_target) - len(origins_within),
            "origin_capture_fraction": round(len(origins_within) / len(origins_with_eligible_target), 6) if origins_with_eligible_target else None,
            "target_event_appearance_count": audit.n_targets_total,
            "target_appearances_within_radius": audit.n_targets_covered,
            "unique_target_event_count": unique_target_event_count,
            "unique_targets_within_radius": len(targets_within),
            "nearest_distance_p50_km": percentiles["p50"],
            "nearest_distance_p75_km": percentiles["p75"],
            "nearest_distance_p90_km": percentiles["p90"],
            "nearest_distance_p95_km": percentiles["p95"],
            "country_distribution_json": _json(_capture_distribution(forecast_origins, by_origin, candidate=candidate, key_fn=lambda o: o.country)),
            "year_distribution_json": _json(_capture_distribution(forecast_origins, by_origin, candidate=candidate, key_fn=lambda o: parse_flexible_date(o.t0).year)),
            "selection_eligible": full_coverage,
            "selection_reason": selection_reason,
        })
    return candidate_rows, selected_radius, rule_status


def build_fmd06c_pa_local_domain_audit(
    forecast_origins: list[ForecastOrigin],
    coverage_rows: list[TargetDomainCoverage],
    *,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
) -> list[dict]:
    """FMD-06C-PA local-domain audit: ONE ROW PER FORECAST ORIGIN (Section 4
    -- the primary modelling unit stays the forecast origin, never a target
    appearance). `forecast_origins`/`coverage_rows` must already be
    `FIT_DEVELOPMENT`-only (Section 7 hard firewall enforced here, not just
    trusted from the caller); `coverage_rows` must come UNCHANGED from
    `domain_design.build_development_domain_candidate_audit` so the covered/
    uncovered-at-200km decision is never recomputed here (single source of
    truth, same as R2).

    An origin with zero eligible D1-D7 targets is still one row here,
    explicitly `has_eligible_d1_d7_target=False`, contributing a LOCAL
    negative -- never silently dropped. An origin whose only eligible
    target(s) sit beyond `radius_km` is `outside_domain_target_present=True`
    but still `local_domain_positive=False` (Section 6): distinguishable
    from a true no-eligible-target negative, never merged into it."""
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_fmd06c_pa_local_domain_audit")

    by_origin: dict[str, list[TargetDomainCoverage]] = defaultdict(list)
    for row in coverage_rows:
        by_origin[row.forecast_origin_id].append(row)

    rows: list[dict] = []
    for origin in sorted(forecast_origins, key=lambda o: o.forecast_origin_id):
        target_rows = by_origin.get(origin.forecast_origin_id, [])
        n_within = sum(1 for row in target_rows if row.covered_by_candidate_km[radius_km])
        n_outside = len(target_rows) - n_within
        rows.append({
            "forecast_origin_id": origin.forecast_origin_id,
            "country": origin.country,
            "t0": origin.t0,
            "has_eligible_d1_d7_target": bool(target_rows),
            "n_eligible_d1_d7_targets": len(target_rows),
            "n_targets_within_local_domain": n_within,
            "n_targets_outside_local_domain": n_outside,
            "local_domain_positive": n_within > 0,
            "outside_domain_target_present": n_outside > 0,
        })
    return rows


def summarize_fmd06c_pa_local_domain_audit(
    origin_rows: list[dict],
    coverage_rows: list[TargetDomainCoverage],
    *,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
) -> dict:
    """Section 5's exact aggregate report, plus Section 5's closing
    requirement -- the origin-level positive fraction FMD-06D would
    produce under the amended LOCAL-domain definition -- computed over
    every `FIT_DEVELOPMENT` origin (the primary unit), never over target
    appearances."""
    n_origins = len(origin_rows)
    origins_with_eligible_target = sum(row["has_eligible_d1_d7_target"] for row in origin_rows)
    origins_positive_within = sum(row["local_domain_positive"] for row in origin_rows)
    origins_only_outside = sum(
        row["has_eligible_d1_d7_target"] and not row["local_domain_positive"] for row in origin_rows
    )
    origins_without_eligible_target = n_origins - origins_with_eligible_target

    appearance_count = len(coverage_rows)
    appearances_within = sum(1 for row in coverage_rows if row.covered_by_candidate_km[radius_km])
    appearances_outside = appearance_count - appearances_within
    unique_target_event_count = len({row.target_event_id for row in coverage_rows})
    unique_within = len({row.target_event_id for row in coverage_rows if row.covered_by_candidate_km[radius_km]})
    unique_outside = len({row.target_event_id for row in coverage_rows if not row.covered_by_candidate_km[radius_km]})

    return {
        "local_evaluation_radius_km": radius_km,
        "fit_development_origin_count": n_origins,
        "origins_with_eligible_d1_d7_target": origins_with_eligible_target,
        "origins_with_target_within_local_domain": origins_positive_within,
        "origins_with_eligible_target_all_outside_local_domain": origins_only_outside,
        "origins_without_eligible_d1_d7_target": origins_without_eligible_target,
        "target_event_appearance_count": appearance_count,
        "target_appearances_within_local_domain": appearances_within,
        "target_appearances_outside_local_domain": appearances_outside,
        "unique_target_event_count": unique_target_event_count,
        "unique_targets_within_local_domain": unique_within,
        "unique_targets_outside_local_domain": unique_outside,
        "origin_level_positive_fraction": round(origins_positive_within / n_origins, 6) if n_origins else None,
    }


def run_fmd06c(
    canonical_csv_path: str | Path,
    origins_csv_path: str | Path,
    calibration_dir: str | Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    disease: str = FMD_DISEASE,
) -> dict:
    """Build the FMD-06C spatial-domain artifacts and extend the existing
    FMD-06B-R `fmd06_calibration_freeze.json` in place -- every existing key
    is preserved unchanged, only the `spatial_*` keys documented in
    FMD-06C are added/updated."""
    canonical_path = Path(canonical_csv_path)
    origins_path = Path(origins_csv_path)
    output = Path(calibration_dir)
    output.mkdir(parents=True, exist_ok=True)

    freeze_path = output / "fmd06_calibration_freeze.json"
    existing_freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    active_window_days = existing_freeze.get("active_window_days")
    if existing_freeze.get("active_window_status") != ACTIVE_WINDOW_STATUS_GO or not active_window_days:
        raise ValueError("run_fmd06c: FMD-06B-R active-window calibration must be GO before FMD-06C spatial calibration")

    all_origins = load_forecast_origins(origins_path)
    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="run_fmd06c")

    with tempfile.TemporaryDirectory(prefix="fmd06c_db_") as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "fmd06c.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, canonical_path)

        distance_rows = build_fmd06c_spatial_target_distance_audit(
            repo, fit_origins, disease=disease, active_window_days=active_window_days, cutoff=cutoff,
        )
        # R2: the generic domain-design implementation is the single source
        # of truth for candidate coverage/selection -- called here with FMD's
        # own frozen cutoff, now that R1 lets the generic entry point accept
        # a caller-supplied model_fitting_cutoff instead of always applying
        # its generic 2024-01-01 default.
        audits, coverage_rows = build_development_domain_candidate_audit(
            repo, fit_development_origins=fit_origins, disease=disease, active_window_days=active_window_days,
            candidates_km=SPATIAL_RADIUS_CANDIDATES_KM, model_fitting_cutoff=cutoff,
        )
        repo.close()
        candidate_rows, selected_radius, rule_status = build_fmd06c_domain_candidate_audit(
            fit_origins, audits, coverage_rows,
        )

    _write_csv(output / "fmd06_spatial_target_distance_audit.csv", distance_rows, SPATIAL_TARGET_DISTANCE_FIELDNAMES)
    _write_csv(output / "fmd06_spatial_domain_candidate_audit.csv", candidate_rows, SPATIAL_DOMAIN_CANDIDATE_FIELDNAMES)

    spatial_status = SPATIAL_DOMAIN_STATUS_GO if rule_status == FROZEN_EVALUATION_DOMAIN_RULE else SPATIAL_DOMAIN_STATUS_NO_GO
    assert rule_status in (FROZEN_EVALUATION_DOMAIN_RULE, DOMAIN_RULE_BLOCKED)

    freeze = dict(existing_freeze)
    freeze.update({
        "spatial_domain_status": spatial_status,
        "spatial_reference_source_set": SPATIAL_REFERENCE_SOURCE_SET,
        "spatial_radius_candidate_source": SPATIAL_RADIUS_CANDIDATE_SOURCE,
        "spatial_radius_candidates_km": list(SPATIAL_RADIUS_CANDIDATES_KM),
        "spatial_radius_selection_rule": SPATIAL_RADIUS_SELECTION_RULE,
        "spatial_evaluation_radius_km": selected_radius,
        "spatial_parameter_classification": SPATIAL_PARAMETER_CLASSIFICATION if selected_radius is not None else None,
    })
    artifact_names = [
        "fmd06_development_source_universe.csv", "fmd06_active_window_candidate_audit.csv",
        "fmd06_stdbscan_candidate_audit.csv", "fmd06_stdbscan_sensitivity.csv",
        "fmd06_spatial_target_distance_audit.csv", "fmd06_spatial_domain_candidate_audit.csv",
    ]
    freeze["calibration_artifact_sha256"] = _freeze_hashes(output, artifact_names)
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True), encoding="utf-8")
    return freeze


def run_fmd06c_pa(
    canonical_csv_path: str | Path,
    origins_csv_path: str | Path,
    calibration_dir: str | Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    disease: str = FMD_DISEASE,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
) -> dict:
    """FMD-06C-PA: build the `POST_FEASIBILITY_PROTOCOL_AMENDMENT` local-
    domain audit and extend the existing frozen `fmd06_calibration_freeze.json`
    in place. `run_fmd06c` must have already run and recorded a NO-GO --
    this amendment exists only because the original predeclared 100%-
    coverage rule (`spatial_radius_selection_rule`) was infeasible on real
    FIT_DEVELOPMENT data, and it must never be used to override a GO. The
    original `spatial_domain_status`/`spatial_evaluation_radius_km` keys are
    copied into `dict(existing_freeze)` UNCHANGED (never overwritten here) --
    only `original_*`/`amended_*`/`spatial_protocol_amendment_*` keys are
    added, documented in
    `FMD06_SPATIAL_DOMAIN_PROTOCOL_AMENDMENT.md`."""
    canonical_path = Path(canonical_csv_path)
    origins_path = Path(origins_csv_path)
    output = Path(calibration_dir)
    output.mkdir(parents=True, exist_ok=True)

    freeze_path = output / "fmd06_calibration_freeze.json"
    existing_freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    original_status = existing_freeze.get("spatial_domain_status")
    original_radius = existing_freeze.get("spatial_evaluation_radius_km")
    if original_status != SPATIAL_DOMAIN_STATUS_NO_GO or original_radius is not None:
        raise ValueError(
            "run_fmd06c_pa: the amendment is only valid after the original predeclared FMD-06C rule "
            f"recorded NO-GO/null (found spatial_domain_status={original_status!r}, "
            f"spatial_evaluation_radius_km={original_radius!r}) -- run_fmd06c must run first"
        )
    if radius_km not in PREDECLARED_DOMAIN_CANDIDATES_KM:
        raise ValueError(
            f"run_fmd06c_pa: radius_km={radius_km} is not in the pre-existing predeclared candidate "
            f"registry {PREDECLARED_DOMAIN_CANDIDATES_KM} -- the amendment must never introduce a new radius"
        )
    if radius_km != max(PREDECLARED_DOMAIN_CANDIDATES_KM):
        raise ValueError(
            f"run_fmd06c_pa: radius_km={radius_km} is not MAXIMUM_PREDECLARED_LOCAL_EVALUATION_DOMAIN "
            f"({max(PREDECLARED_DOMAIN_CANDIDATES_KM)})"
        )
    active_window_days = existing_freeze.get("active_window_days")
    if existing_freeze.get("active_window_status") != ACTIVE_WINDOW_STATUS_GO or not active_window_days:
        raise ValueError("run_fmd06c_pa: FMD-06B-R active-window calibration must be GO before the amendment")

    all_origins = load_forecast_origins(origins_path)
    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="run_fmd06c_pa")

    with tempfile.TemporaryDirectory(prefix="fmd06c_pa_db_") as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "fmd06c_pa.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, canonical_path)

        # Same generic single-source-of-truth call as R2's run_fmd06c --
        # coverage decisions (including at 200km) are never recomputed here.
        _audits, coverage_rows = build_development_domain_candidate_audit(
            repo, fit_development_origins=fit_origins, disease=disease, active_window_days=active_window_days,
            candidates_km=SPATIAL_RADIUS_CANDIDATES_KM, model_fitting_cutoff=cutoff,
        )
        repo.close()

    origin_rows = build_fmd06c_pa_local_domain_audit(fit_origins, coverage_rows, radius_km=radius_km, cutoff=cutoff)
    summary = summarize_fmd06c_pa_local_domain_audit(origin_rows, coverage_rows, radius_km=radius_km)

    _write_csv(output / "fmd06_pa_local_domain_audit.csv", origin_rows, PA_LOCAL_DOMAIN_AUDIT_FIELDNAMES)

    summary_payload = {
        "checkpoint": "FMD-06C-PA",
        "spatial_protocol_amendment_status": SPATIAL_PROTOCOL_AMENDMENT_STATUS,
        "spatial_protocol_amendment_reason": SPATIAL_PROTOCOL_AMENDMENT_REASON,
        "amended_spatial_selection_rule": AMENDED_SPATIAL_SELECTION_RULE,
        "amended_spatial_selection_rationale": AMENDED_SPATIAL_SELECTION_RATIONALE,
        "amended_spatial_evaluation_radius_km": radius_km,
        "amended_spatial_parameter_classification": AMENDED_SPATIAL_PARAMETER_CLASSIFICATION,
        "held_out_data_used_for_amendment": False,
        "sri_lanka_data_used_for_amendment": False,
        "predictive_metrics_used_for_amendment": False,
        **summary,
    }
    (output / "fmd06_pa_amendment_summary.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8",
    )

    freeze = dict(existing_freeze)
    freeze.update({
        "original_spatial_domain_status": original_status,
        "original_spatial_evaluation_radius_km": original_radius,
        "original_spatial_radius_candidates_km": existing_freeze.get("spatial_radius_candidates_km"),
        "original_spatial_radius_selection_rule": existing_freeze.get("spatial_radius_selection_rule"),
        "spatial_protocol_amendment_status": SPATIAL_PROTOCOL_AMENDMENT_STATUS,
        "spatial_protocol_amendment_reason": SPATIAL_PROTOCOL_AMENDMENT_REASON,
        "amended_spatial_domain_status": AMENDED_SPATIAL_DOMAIN_STATUS,
        "amended_spatial_selection_rule": AMENDED_SPATIAL_SELECTION_RULE,
        "amended_spatial_evaluation_radius_km": radius_km,
        "amended_spatial_parameter_classification": AMENDED_SPATIAL_PARAMETER_CLASSIFICATION,
        "held_out_data_used_for_amendment": False,
        "sri_lanka_data_used_for_amendment": False,
        "predictive_metrics_used_for_amendment": False,
        "amended_local_domain_audit_summary": summary,
    })
    artifact_names = [
        "fmd06_development_source_universe.csv", "fmd06_active_window_candidate_audit.csv",
        "fmd06_stdbscan_candidate_audit.csv", "fmd06_stdbscan_sensitivity.csv",
        "fmd06_spatial_target_distance_audit.csv", "fmd06_spatial_domain_candidate_audit.csv",
        "fmd06_pa_local_domain_audit.csv", "fmd06_pa_amendment_summary.json",
    ]
    freeze["calibration_artifact_sha256"] = _freeze_hashes(output, artifact_names)
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True), encoding="utf-8")
    return freeze


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def build_fmd06d_risk_origin_labels(
    forecast_origins: list[ForecastOrigin],
    local_domain_audit_rows: list[dict],
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
) -> list[dict]:
    """FMD-06D: deterministic ONE-ROW-PER-FORECAST-ORIGIN projection of the
    already-frozen FMD-06C-PA local-domain audit into the risk-origin label
    artifact FMD-07 will consume. No candidate radius, spatial-domain
    selection, nearest-source distance, ST-DBSCAN parameter, or
    active-window parameter is recomputed here -- `local_domain_audit_rows`
    (`fmd06_pa_local_domain_audit.csv`'s rows, either freshly built or read
    back from that frozen CSV) is trusted UNCHANGED as the sole source of
    each origin's `local_domain_positive`/`outside_domain_target_present`
    decision.

    `assert_fit_development_only` firewalls `forecast_origins` at this
    function's own entry point -- `HELD_OUT_FROM_MODEL_FITTING` and
    `SRI_LANKA_TRANSFER_CASE_STUDY` origins can never enter this label
    artifact; their outcomes remain unopened until FMD-08. Raises
    `ValueError` if the firewalled origin set does not exactly match the
    audit rows -- never silently drops or invents a row."""
    assert_fit_development_only(forecast_origins, cutoff=cutoff, caller="build_fmd06d_risk_origin_labels")

    origin_by_id = {o.forecast_origin_id: o for o in forecast_origins}
    audit_by_id = {row["forecast_origin_id"]: row for row in local_domain_audit_rows}
    origin_ids = set(origin_by_id)
    audit_ids = set(audit_by_id)
    if origin_ids != audit_ids:
        missing = sorted(origin_ids - audit_ids)
        extra = sorted(audit_ids - origin_ids)
        raise ValueError(
            "build_fmd06d_risk_origin_labels: FIT_DEVELOPMENT origins do not exactly match the frozen "
            f"fmd06_pa_local_domain_audit.csv rows -- {len(missing)} missing from audit "
            f"(e.g. {missing[:5]}), {len(extra)} extra in audit (e.g. {extra[:5]})"
        )

    rows: list[dict] = []
    for origin_id in sorted(origin_ids):
        origin = origin_by_id[origin_id]
        audit_row = audit_by_id[origin_id]
        positive = _as_bool(audit_row["local_domain_positive"])
        rows.append({
            "forecast_origin_id": origin_id,
            "country": origin.country,
            "t0": origin.t0,
            "model_fitting_role": classify_origin_role(origin, cutoff=cutoff),
            "risk_target_label": 1 if positive else 0,
            "has_eligible_d1_d7_target": _as_bool(audit_row["has_eligible_d1_d7_target"]),
            "outside_domain_target_present": _as_bool(audit_row["outside_domain_target_present"]),
            "local_evaluation_radius_km": radius_km,
            "target_horizon": PRIMARY_TARGET_HORIZON,
            "spatial_reference_source_set": SPATIAL_REFERENCE_SOURCE_SET,
            "spatial_protocol_amendment_status": SPATIAL_PROTOCOL_AMENDMENT_STATUS,
        })
    return rows


def summarize_fmd06d_risk_origin_labels(label_rows: list[dict]) -> dict:
    """Section 6/7's exact reconciliation report: positive/negative counts
    and the two distinguishable negative subtypes (no eligible target vs.
    eligible-but-all-outside-domain), computed purely from the already
    materialized label rows -- no recomputation of coverage."""
    n = len(label_rows)
    positive = sum(row["risk_target_label"] == 1 for row in label_rows)
    negative = n - positive
    no_target = sum(not row["has_eligible_d1_d7_target"] for row in label_rows)
    outside_only = sum(
        row["has_eligible_d1_d7_target"] and row["risk_target_label"] == 0 for row in label_rows
    )
    return {
        "risk_label_row_count": n,
        "risk_label_positive_count": positive,
        "risk_label_negative_count": negative,
        "negative_no_target_count": no_target,
        "negative_outside_domain_only_count": outside_only,
        "positive_fraction": round(positive / n, 6) if n else None,
    }


def run_fmd06d(
    origins_csv_path: str | Path,
    calibration_dir: str | Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    radius_km: float = FMD_SPATIAL_EVALUATION_RADIUS_KM,
) -> dict:
    """FMD-06D: materialize the deterministic `FIT_DEVELOPMENT` risk-origin
    label artifact (`fmd06_risk_origin_labels.csv`) FMD-07 will consume,
    plus the final FMD-06 manifest (`fmd06_calibration_manifest.json`).

    Reuses the already-frozen `fmd06_pa_local_domain_audit.csv` (built by
    `run_fmd06c_pa`) as the SOLE source of per-origin coverage truth -- no
    candidate radius, spatial-domain selection, nearest-source distance,
    ST-DBSCAN parameter, or active-window parameter is recomputed.
    `HELD_OUT_FROM_MODEL_FITTING` and `SRI_LANKA_TRANSFER_CASE_STUDY`
    outcomes are never materialized, inspected, or summarized here -- that
    remains FMD-08 work. Raises `ValueError` (BLOCKED, never silently
    adjusted) if the deterministic projection does not reproduce the
    frozen FMD-06C-PA reconciliation counts exactly."""
    origins_path = Path(origins_csv_path)
    output = Path(calibration_dir)

    freeze_path = output / "fmd06_calibration_freeze.json"
    existing_freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if existing_freeze.get("spatial_protocol_amendment_status") != SPATIAL_PROTOCOL_AMENDMENT_STATUS:
        raise ValueError(
            "run_fmd06d: run_fmd06c_pa must run first -- spatial_protocol_amendment_status is missing/mismatched "
            f"(found {existing_freeze.get('spatial_protocol_amendment_status')!r})"
        )
    if existing_freeze.get("amended_spatial_evaluation_radius_km") != radius_km:
        raise ValueError(
            "run_fmd06d: frozen amended_spatial_evaluation_radius_km "
            f"({existing_freeze.get('amended_spatial_evaluation_radius_km')!r}) does not match radius_km={radius_km!r}"
        )
    if existing_freeze.get("spatial_domain_status") != SPATIAL_DOMAIN_STATUS_NO_GO or existing_freeze.get("spatial_evaluation_radius_km") is not None:
        raise ValueError(
            "run_fmd06d: the original spatial_domain_status/spatial_evaluation_radius_km NO-GO/null record "
            "must remain preserved and untouched -- found spatial_domain_status="
            f"{existing_freeze.get('spatial_domain_status')!r}, spatial_evaluation_radius_km="
            f"{existing_freeze.get('spatial_evaluation_radius_km')!r}"
        )

    audit_path = output / "fmd06_pa_local_domain_audit.csv"
    with audit_path.open(encoding="utf-8", newline="") as handle:
        local_domain_audit_rows = list(csv.DictReader(handle))

    all_origins = load_forecast_origins(origins_path)
    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="run_fmd06d")

    label_rows = build_fmd06d_risk_origin_labels(fit_origins, local_domain_audit_rows, cutoff=cutoff, radius_km=radius_km)
    summary = summarize_fmd06d_risk_origin_labels(label_rows)

    expected_reconciliation = {
        "risk_label_row_count": 3761,
        "risk_label_positive_count": 2215,
        "risk_label_negative_count": 1546,
        "negative_no_target_count": 1402,
        "negative_outside_domain_only_count": 144,
    }
    mismatches = {key: (summary[key], expected) for key, expected in expected_reconciliation.items() if summary[key] != expected}
    if mismatches:
        raise ValueError(
            "run_fmd06d: BLOCKED -- deterministic label projection does not reproduce the frozen "
            f"FMD-06C-PA reconciliation counts exactly. (actual, expected) mismatches: {mismatches}"
        )

    _write_csv(output / "fmd06_risk_origin_labels.csv", label_rows, RISK_LABEL_FIELDNAMES)

    freeze = dict(existing_freeze)
    freeze.update({
        "risk_origin_labels_generated": True,
        "risk_origin_label_row_count": summary["risk_label_row_count"],
        "risk_origin_label_positive_count": summary["risk_label_positive_count"],
        "risk_origin_label_negative_count": summary["risk_label_negative_count"],
        "risk_origin_label_negative_no_target_count": summary["negative_no_target_count"],
        "risk_origin_label_negative_outside_domain_only_count": summary["negative_outside_domain_only_count"],
        "risk_origin_label_positive_fraction": summary["positive_fraction"],
        "direction_speed_status": DIRECTION_SPEED_STATUS,
        "direction_speed_status_reason": DIRECTION_SPEED_STATUS_REASON,
        "weather_window_selection_status": WEATHER_WINDOW_SELECTION_STATUS,
        "held_out_outcomes_used": False,
        "sri_lanka_outcomes_used": False,
        "predictive_model_trained": False,
    })
    freeze_artifact_names = [
        "fmd06_development_source_universe.csv", "fmd06_active_window_candidate_audit.csv",
        "fmd06_stdbscan_candidate_audit.csv", "fmd06_stdbscan_sensitivity.csv",
        "fmd06_spatial_target_distance_audit.csv", "fmd06_spatial_domain_candidate_audit.csv",
        "fmd06_pa_local_domain_audit.csv", "fmd06_pa_amendment_summary.json",
        "fmd06_risk_origin_labels.csv",
    ]
    freeze["calibration_artifact_sha256"] = _freeze_hashes(output, freeze_artifact_names)
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "checkpoint": "FMD-06",
        "overall_status": FMD06_OVERALL_STATUS_GO,
        "development_origin_count": len(fit_origins),
        "risk_label_row_count": summary["risk_label_row_count"],
        "risk_label_positive_count": summary["risk_label_positive_count"],
        "risk_label_negative_count": summary["risk_label_negative_count"],
        "negative_no_target_count": summary["negative_no_target_count"],
        "negative_outside_domain_only_count": summary["negative_outside_domain_only_count"],
        "positive_fraction": summary["positive_fraction"],
        "target_horizon": PRIMARY_TARGET_HORIZON,
        "active_window_days": freeze.get("active_window_days"),
        "stdbscan_eps_space_km": freeze.get("stdbscan_eps_space_km"),
        "stdbscan_eps_time_days": freeze.get("stdbscan_eps_time_days"),
        "stdbscan_min_core_supports": freeze.get("stdbscan_min_core_supports"),
        "spatial_reference_source_set": freeze.get("spatial_reference_source_set"),
        "original_spatial_domain_status": freeze.get("original_spatial_domain_status"),
        "original_spatial_evaluation_radius_km": freeze.get("original_spatial_evaluation_radius_km"),
        "original_spatial_radius_candidates_km": freeze.get("original_spatial_radius_candidates_km"),
        "spatial_protocol_amendment_status": freeze.get("spatial_protocol_amendment_status"),
        "amended_spatial_domain_status": freeze.get("amended_spatial_domain_status"),
        "amended_spatial_selection_rule": freeze.get("amended_spatial_selection_rule"),
        "amended_spatial_evaluation_radius_km": freeze.get("amended_spatial_evaluation_radius_km"),
        "amended_spatial_parameter_classification": freeze.get("amended_spatial_parameter_classification"),
        "direction_speed_status": DIRECTION_SPEED_STATUS,
        "direction_speed_status_reason": DIRECTION_SPEED_STATUS_REASON,
        "weather_window_selection_status": WEATHER_WINDOW_SELECTION_STATUS,
        "held_out_outcomes_used": False,
        "sri_lanka_outcomes_used": False,
        "predictive_model_trained": False,
        "input_artifact_sha256": freeze.get("input_artifact_sha256", {}),
    }
    manifest_artifact_names = freeze_artifact_names + ["fmd06_calibration_freeze.json"]
    manifest["artifact_sha256"] = _freeze_hashes(output, manifest_artifact_names)
    (output / "fmd06_calibration_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8",
    )

    return {"freeze": freeze, "manifest": manifest, "label_rows": label_rows}


def run_fmd06b(
    canonical_csv_path: str | Path,
    origins_csv_path: str | Path,
    out_dir: str | Path,
    *,
    cutoff: str = FMD_MODEL_FITTING_CUTOFF,
    disease: str = FMD_DISEASE,
) -> dict:
    """Build all deterministic FMD-06B artifacts and return the freeze dict."""
    canonical_path = Path(canonical_csv_path)
    origins_path = Path(origins_csv_path)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    all_origins = load_forecast_origins(origins_path)
    fit_origins = fit_development_origins(all_origins, cutoff=cutoff)
    assert_fit_development_only(fit_origins, cutoff=cutoff, caller="run_fmd06b")

    with tempfile.TemporaryDirectory(prefix="fmd06b_db_") as temp_dir:
        repo = SQLiteOutbreakRepository(Path(temp_dir) / "fmd06b.sqlite")
        repo.init_schema()
        import_fmd_canonical_csv(repo, canonical_path)
        universe = build_fmd06_development_source_universe(repo, fit_origins, disease=disease, cutoff=cutoff)
        records = {record.source_record_id: record for record in repo.list_historical_records(disease=disease)}
        repo.close()

    sources = sorted(universe.sources, key=lambda source: source.source_id)
    _write_csv(output / "fmd06_development_source_universe.csv", [source.as_dict() for source in sources], DEVELOPMENT_SOURCE_FIELDNAMES)
    active_audits = build_active_window_sensitivity(fit_origins, sources, cutoff=cutoff)
    _write_csv(output / "fmd06_active_window_candidate_audit.csv", [audit.as_dict() for audit in active_audits], ACTIVE_WINDOW_FIELDNAMES)
    active_status, active_window, active_rule = select_active_window(active_audits)

    std_candidates: list[dict] = []
    sensitivity: list[dict] = []
    selected_stdbscan = None
    candidate_evidence = {}
    if active_status == ACTIVE_WINDOW_STATUS_GO:
        eps_space, eps_time, min_core, candidate_evidence = derive_stdbscan_candidates(sources, cutoff=cutoff)
        for eps_space_value, eps_time_value, min_core_value in itertools.product(eps_space, eps_time, min_core):
            config = STDBSCANConfig(
                eps_space_km=eps_space_value,
                eps_time_days=eps_time_value,
                min_core_supports=min_core_value,
                active_window_days=active_window,
                gps_core_policy=PRIMARY_GPS_CORE_POLICY,
                parameter_status=UNFROZEN_DEVELOPMENT_CANDIDATE,
            )
            temporal_status, temporal_eligible, temporal_reason = temporal_threshold_eligibility(
                config.eps_time_days,
                active_window,
            )
            std_candidates.append({
                "eps_space_km": config.eps_space_km,
                "eps_time_days": config.eps_time_days,
                "min_core_supports": config.min_core_supports,
                "active_window_days": config.active_window_days,
                "gps_core_policy": config.gps_core_policy,
                "parameter_status": config.parameter_status,
                "config_hash": config.config_hash(),
                "temporal_eligibility_status": temporal_status,
                "predictor_facing_eligible": temporal_eligible,
                "eligibility_reason": temporal_reason,
                "candidate_definition": STDBSCAN_CANDIDATE_DEFINITION,
            })
        sensitivity, selected_stdbscan = build_stdbscan_sensitivity(
            fit_origins,
            sources,
            records,
            active_window_days=active_window,
            eps_space_candidates=eps_space,
            eps_time_candidates=eps_time,
            min_core_support_candidates=min_core,
            cutoff=cutoff,
        )
    _write_csv(output / "fmd06_stdbscan_candidate_audit.csv", std_candidates, STDBSCAN_CANDIDATE_FIELDNAMES)
    _write_csv(output / "fmd06_stdbscan_sensitivity.csv", sensitivity, STDBSCAN_SENSITIVITY_FIELDNAMES)

    std_status = STDBSCAN_STATUS_GO if selected_stdbscan is not None else STDBSCAN_STATUS_NO_GO
    temporal_threshold_audit = [
        {
            "eps_time_days": row["eps_time_days"],
            "temporal_eligibility_status": row["temporal_eligibility_status"],
            "predictor_facing_eligible": row["predictor_facing_eligible"],
            "eligibility_reason": row["eligibility_reason"],
        }
        for row in std_candidates
    ]
    input_hashes = {
        "fmd_canonical_outbreaks_conservative.csv": _sha256(canonical_path),
        "fmd_historical_forecast_origins.csv": _sha256(origins_path),
    }
    for name in (
        "FMD_COHORT_MANIFEST.json", "fmd_model_fitting_exposure_manifest.csv", "FMD_COHORT_AUDIT.csv",
        "fmd_historical_forecast_targets.csv", "fmd_calendar_year_folds.json",
    ):
        sibling = origins_path.parent / name
        if sibling.exists():
            input_hashes[name] = _sha256(sibling)

    freeze = {
        "checkpoint": "FMD-06B",
        "development_origin_count": len(fit_origins),
        "development_source_event_count": universe.n_validated_sources,
        "unique_source_event_count": universe.n_validated_sources,
        "source_event_unit": "UNIQUE_SOURCE_EVENT_ID",
        "development_source_universe_count": universe.n_validated_sources,
        "snapshot_event_appearance_count": selected_stdbscan["n_active_source_appearances"] if selected_stdbscan else None,
        "snapshot_event_appearance_unit": "SNAPSHOT_EVENT_APPEARANCE",
        "development_country_count": len({source.country for source in sources}),
        "active_window_status": active_status,
        "active_window_days": active_window,
        "active_window_candidates": list(ACTIVE_WINDOW_DAY_CANDIDATES),
        "active_window_selection_rule": active_rule,
        "active_window_gap_statistic_name": "COUNTRY_BALANCED_MEDIAN_PRECEDING_SOURCE_GAP_DAYS",
        "active_window_gap_statistic_days": active_audits[0].country_balanced_median_preceding_source_gap_days if active_audits else None,
        "active_window_gap_country_count": active_audits[0].n_countries_contributing_preceding_source_gap_median if active_audits else 0,
        "previous_zero_source_selector_status": active_audits[0].previous_zero_source_criterion_status if active_audits else None,
        "active_window_classification": "DEVELOPMENT_CALIBRATED_TEMPORAL_DATA_PARAMETER" if active_window is not None else None,
        "stdbscan_status": std_status,
        "stdbscan_eps_space_km": selected_stdbscan["eps_space_km"] if selected_stdbscan else None,
        "stdbscan_eps_time_days": selected_stdbscan["eps_time_days"] if selected_stdbscan else None,
        "stdbscan_temporal_threshold_status": selected_stdbscan["temporal_eligibility_status"] if selected_stdbscan else None,
        "stdbscan_temporal_threshold_audit": temporal_threshold_audit,
        "stdbscan_ineligible_temporal_candidate_count": sum(
            not row["predictor_facing_eligible"] for row in std_candidates
        ),
        "stdbscan_min_core_supports": selected_stdbscan["min_core_supports"] if selected_stdbscan else None,
        "stdbscan_candidate_definition": STDBSCAN_CANDIDATE_DEFINITION,
        "stdbscan_selection_rule": STDBSCAN_SELECTION_RULE,
        "stdbscan_classification": "DEVELOPMENT_CALIBRATED_SOFTWARE_PARAMETERS" if selected_stdbscan else None,
        "clusters_terminology": "descriptive historical geospatial-temporal clusters",
        "spatial_domain_status": SPATIAL_DOMAIN_NOT_STARTED,
        "risk_origin_labels_generated": False,
        "predictive_metrics_used": False,
        "held_out_data_used": False,
        "sri_lanka_case_study_data_used": False,
        "ml_model_trained": False,
        "input_artifact_sha256": input_hashes,
        "candidate_derivation_evidence": candidate_evidence,
    }
    artifact_names = [
        "fmd06_development_source_universe.csv", "fmd06_active_window_candidate_audit.csv",
        "fmd06_stdbscan_candidate_audit.csv", "fmd06_stdbscan_sensitivity.csv",
    ]
    freeze["calibration_artifact_sha256"] = _freeze_hashes(output, artifact_names)
    (output / "fmd06_calibration_freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True), encoding="utf-8")
    return freeze


def _main(argv: list[str]) -> None:
    canonical = argv[0] if len(argv) > 0 else "../local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    origins = argv[1] if len(argv) > 1 else "../local_data/processed/fmd/cohort/fmd_historical_forecast_origins.csv"
    out_dir = argv[2] if len(argv) > 2 else "../local_data/processed/fmd/calibration"
    print(json.dumps(run_fmd06b(canonical, origins, out_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    _main(sys.argv[1:])

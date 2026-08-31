"""Checkpoint 6B Part 17 / Checkpoint 6B.5 Parts 6-9: development-only
ST-DBSCAN parameter-candidate registry.

**`build_legacy_parameter_candidate_report` below is SUPERSEDED_BY_6B5 for real
pipeline use.** It computes candidate geometry directly from raw
`HistoricalOutbreakRecord`s, comparing every record against every OTHER
record regardless of country, and admits a record via
`historical_event_date < cutoff` alone — Checkpoint 6B.5 found both of
these unsafe: (1) "model_candidate/dedup filtering is the caller's
responsibility" is not a hard gate, and (2) real ST-DBSCAN clustering
always runs country-scoped (`source_selector.get_eligible_sources` is
always called with a `country_scope`), so a cross-country
nearest-neighbor distance was never representative of what the
clustering engine actually computes, and a raw event-date cutoff
confuses availability (WHETHER a source may be used) with occurrence
(WHERE it lies on the temporal axis) — see
`development_source_universe.py`'s module docstring. This function is
kept ONLY as a pure, lower-level function for tests/historical
comparison (Checkpoint 6B Part 6 Option A) — it is never called from
the real pipeline (`smoke_tests/run_stdbscan_smoke.py`) as of 6B.5.

**The real, safe entry point is `build_country_scoped_parameter_candidates`**,
which operates on an already-validated
`development_source_universe.DevelopmentSource` list (built via
`build_fit_development_source_universe`, which hard-gates
model_candidate/dedup/coordinates/availability-window through the
existing `source_selector.get_eligible_sources`, never raw records) and
computes NN-distance/temporal-gap candidates strictly WITHIN each
country, never comparing a source against another country's source
(Part 7-8).

Everything this module returns is a PARAMETER CANDIDATE, never a frozen
scientific constant (`STDBSCANConfig.parameter_status` for anything
built from these values must be `UNFROZEN_DEVELOPMENT_CANDIDATE`, never
`FROZEN_REFERENCE` — enforced structurally by `config.py`). Never chosen
to make clusters "look nicer," and never silently capped/altered if the
resulting quantiles are pathological (reported via `pathological_note`
instead).

`ACTIVE_WINDOW_DAY_CANDIDATES = (7, 14, 21, 28)` (re-exported from
`candidate_constants.py`) are fixed PARAMETER CANDIDATES (Part 17) —
not derived from data, not claimed as epidemiological truth.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from ...domain.models import HistoricalOutbreakRecord
from ..dates import parse_flexible_date
from ..geospatial.distance import distance_km
from ..historical_event_date import derive_historical_event_date
from ..model_fitting_exposure import MODEL_FITTING_CUTOFF
from .candidate_constants import ACTIVE_WINDOW_DAY_CANDIDATES, MAX_ACTIVE_WINDOW_DAYS, MIN_CORE_SUPPORT_CANDIDATES  # re-exported

_SRI_LANKA_COUNTRY_NAME = "Sri Lanka"


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute a quantile of an empty sequence")
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _quantiles(values: list[float]) -> dict:
    if not values:
        return {"p25": None, "p50": None, "p75": None}
    return {"p25": _quantile(values, 0.25), "p50": _quantile(values, 0.5), "p75": _quantile(values, 0.75)}


def _is_fit_development_record(*, country: str | None, event_date, cutoff_date) -> bool:
    if country == _SRI_LANKA_COUNTRY_NAME:
        return False
    if event_date is None:
        return False
    return event_date < cutoff_date


@dataclass
class ParameterCandidateReport:
    n_records_considered: int
    n_fit_development_usable_records: int
    nearest_neighbor_distance_km_quantiles: dict
    positive_temporal_gap_days_quantiles: dict
    active_window_day_candidates: list
    pathological_note: str | None

    def as_dict(self) -> dict:
        return {
            "n_records_considered": self.n_records_considered,
            "n_fit_development_usable_records": self.n_fit_development_usable_records,
            "nearest_neighbor_distance_km_quantiles": self.nearest_neighbor_distance_km_quantiles,
            "positive_temporal_gap_days_quantiles": self.positive_temporal_gap_days_quantiles,
            "active_window_day_candidates": self.active_window_day_candidates,
            "pathological_note": self.pathological_note,
        }


def build_legacy_parameter_candidate_report(
    records: list[HistoricalOutbreakRecord], *, cutoff: str = MODEL_FITTING_CUTOFF
) -> ParameterCandidateReport:
    """SUPERSEDED_BY_6B5 for real pipeline use — see module docstring.
    Kept as a pure, lower-level function (Checkpoint 6B Part 6 Option A)
    for tests and old-vs-new comparison only.

    `records`: real `HistoricalOutbreakRecord`s — model_candidate/dedup
    filtering is the caller's own responsibility (this was the exact gap
    6B.5 closed for the real path — see `development_source_universe.py`).
    This function itself always filters to `FIT_DEVELOPMENT` role
    (non-Sri-Lanka, real `historical_event_date` strictly before
    `cutoff`) before computing anything descriptive, and never
    country-scopes its nearest-neighbor/temporal-gap comparisons."""
    cutoff_date = parse_flexible_date(cutoff)
    if cutoff_date is None:
        raise ValueError(f"cutoff is not a parseable date: {cutoff!r}")

    usable: list[tuple[HistoricalOutbreakRecord, object]] = []
    for r in records:
        if r.latitude is None or r.longitude is None:
            continue
        derived = derive_historical_event_date(r)
        event_date = parse_flexible_date(derived.historical_event_date) if derived.historical_event_date else None
        if _is_fit_development_record(country=r.country, event_date=event_date, cutoff_date=cutoff_date):
            usable.append((r, event_date))

    nn_distances: list[float] = []
    for i, (r_i, _) in enumerate(usable):
        best = None
        for j, (r_j, _) in enumerate(usable):
            if i == j:
                continue
            d = distance_km(r_i.latitude, r_i.longitude, r_j.latitude, r_j.longitude)
            if best is None or d < best:
                best = d
        if best is not None:
            nn_distances.append(best)
    nn_distances.sort()

    event_dates_sorted = sorted(d for _, d in usable if d is not None)
    gaps: list[float] = []
    for i in range(1, len(event_dates_sorted)):
        gap = (event_dates_sorted[i] - event_dates_sorted[i - 1]).days
        if gap > 0:
            gaps.append(float(gap))
    gaps.sort()

    pathological_note = None
    if len(usable) < 2:
        pathological_note = "fewer than 2 FIT_DEVELOPMENT records with usable coordinates+event dates — no candidate geometry/time distribution could be computed"
    elif not nn_distances:
        pathological_note = "no nearest-neighbor spatial distances could be computed"
    elif not gaps:
        pathological_note = "no positive inter-event temporal gaps exist in this corpus (all usable records share one event date, or fewer than 2 distinct dates)"

    return ParameterCandidateReport(
        n_records_considered=len(records),
        n_fit_development_usable_records=len(usable),
        nearest_neighbor_distance_km_quantiles=_quantiles(nn_distances),
        positive_temporal_gap_days_quantiles=_quantiles(gaps),
        active_window_day_candidates=list(ACTIVE_WINDOW_DAY_CANDIDATES),
        pathological_note=pathological_note,
    )


# ============================================================
# Checkpoint 6B.5 Parts 7-9: COUNTRY-SCOPED candidate registry —
# the real, safe entry point.
# ============================================================


@dataclass
class CountryNNStats:
    country: str
    n_unique_sources: int
    nn_distance_km_quantiles: dict

    def as_dict(self) -> dict:
        return {
            "country": self.country,
            "n_unique_sources": self.n_unique_sources,
            "p25": self.nn_distance_km_quantiles["p25"],
            "p50": self.nn_distance_km_quantiles["p50"],
            "p75": self.nn_distance_km_quantiles["p75"],
        }


@dataclass
class CountryTemporalStats:
    country: str
    n_unique_sources_with_event_date: int
    positive_temporal_gap_days_quantiles: dict

    def as_dict(self) -> dict:
        return {
            "country": self.country,
            "n_unique_sources_with_event_date": self.n_unique_sources_with_event_date,
            "p25": self.positive_temporal_gap_days_quantiles["p25"],
            "p50": self.positive_temporal_gap_days_quantiles["p50"],
            "p75": self.positive_temporal_gap_days_quantiles["p75"],
        }


@dataclass
class CountryScopedParameterCandidateReport:
    """Part 7-9: NEVER a cross-country nearest-neighbor distance or a
    cross-country temporal gap anywhere in this report — every distance/
    gap that feeds a quantile was computed between two sources sharing
    the same `country` (mirroring what `source_selector.get_eligible_sources`
    /real ST-DBSCAN clustering actually scope to, Part 7). Sparse
    single-source countries are reported with `n_unique_sources=1` and
    `None` quantiles — never merged into another country's distribution
    or silently dropped (Part 7 "do not hide sparse countries")."""

    n_sources_considered: int
    n_countries: int
    per_country_nn_distance: list  # CountryNNStats.as_dict()
    pooled_within_country_nn_distance_km_quantiles: dict
    per_country_temporal_gap: list  # CountryTemporalStats.as_dict()
    pooled_within_country_temporal_gap_days_quantiles: dict
    temporally_local_nn_distance_audit_km_quantiles: dict
    temporally_local_nn_audit_max_window_days: int
    active_window_day_candidates: list
    min_core_support_candidates: list
    pathological_note: str | None

    def as_dict(self) -> dict:
        return {
            "n_sources_considered": self.n_sources_considered,
            "n_countries": self.n_countries,
            "per_country_nn_distance": self.per_country_nn_distance,
            "pooled_within_country_nn_distance_km_quantiles": self.pooled_within_country_nn_distance_km_quantiles,
            "per_country_temporal_gap": self.per_country_temporal_gap,
            "pooled_within_country_temporal_gap_days_quantiles": self.pooled_within_country_temporal_gap_days_quantiles,
            "temporally_local_nn_distance_audit_km_quantiles": self.temporally_local_nn_distance_audit_km_quantiles,
            "temporally_local_nn_audit_max_window_days": self.temporally_local_nn_audit_max_window_days,
            "active_window_day_candidates": self.active_window_day_candidates,
            "min_core_support_candidates": self.min_core_support_candidates,
            "pathological_note": self.pathological_note,
        }


def build_country_scoped_parameter_candidates(sources: list) -> CountryScopedParameterCandidateReport:
    """`sources`: a `development_source_universe.DevelopmentSource` list
    (already validated — model_candidate/dedup/coordinates/availability-
    window/Sri-Lanka/held-out already excluded upstream by
    `build_fit_development_source_universe`). This function itself adds
    no further eligibility filtering — its only job is country-scoped
    descriptive geometry/time statistics (Part 7-9). Duck-typed on
    `.source_id/.country/.latitude/.longitude/.cluster_event_date` so it
    never needs to import `development_source_universe` (no import
    cycle)."""
    by_country: dict[str, list] = defaultdict(list)
    for s in sources:
        by_country[s.country].append(s)

    per_country_nn: list[CountryNNStats] = []
    pooled_nn: list[float] = []
    per_country_temporal: list[CountryTemporalStats] = []
    pooled_gaps: list[float] = []
    audit_distances: list[float] = []

    for country in sorted(by_country):
        group = by_country[country]

        # -- Part 7: within-country NN distance only --------------------
        country_nn: list[float] = []
        for i, s_i in enumerate(group):
            best = None
            for j, s_j in enumerate(group):
                if i == j:
                    continue
                d = distance_km(s_i.latitude, s_i.longitude, s_j.latitude, s_j.longitude)
                if best is None or d < best:
                    best = d
            if best is not None:
                country_nn.append(best)
        per_country_nn.append(
            CountryNNStats(country=country, n_unique_sources=len(group), nn_distance_km_quantiles=_quantiles(sorted(country_nn)))
        )
        pooled_nn.extend(country_nn)

        # -- Part 8: within-country positive temporal gaps only ---------
        dated = [(s, parse_flexible_date(s.cluster_event_date)) for s in group if s.cluster_event_date]
        dated = [(s, d) for s, d in dated if d is not None]
        dated_sorted = sorted(dated, key=lambda pair: pair[1])
        country_gaps: list[float] = []
        for i in range(1, len(dated_sorted)):
            gap = (dated_sorted[i][1] - dated_sorted[i - 1][1]).days
            if gap > 0:
                country_gaps.append(float(gap))
        per_country_temporal.append(
            CountryTemporalStats(
                country=country, n_unique_sources_with_event_date=len(dated_sorted),
                positive_temporal_gap_days_quantiles=_quantiles(sorted(country_gaps)),
            )
        )
        pooled_gaps.extend(country_gaps)

        # -- Part 9: TEMPORALLY_LOCAL_NN_DISTANCE_AUDIT (descriptive
        # audit only — never replaces the ordinary within-country NN
        # distribution above) --------------------------------------------
        for s_i, d_i in dated:
            best = None
            for s_j, d_j in dated:
                if s_j.source_id == s_i.source_id:
                    continue
                if abs((d_i - d_j).days) > MAX_ACTIVE_WINDOW_DAYS:
                    continue
                dist = distance_km(s_i.latitude, s_i.longitude, s_j.latitude, s_j.longitude)
                if best is None or dist < best:
                    best = dist
            if best is not None:
                audit_distances.append(best)

    pooled_nn.sort()
    pooled_gaps.sort()
    audit_distances.sort()

    notes = []
    if not sources:
        notes.append("no validated development sources supplied — no candidate geometry/time distribution could be computed")
    if sources and not pooled_nn:
        notes.append("no within-country nearest-neighbor spatial distance could be computed (every country has <2 sources)")
    if sources and not pooled_gaps:
        notes.append("no within-country positive temporal gap exists (every country's sources share one event date, or <2 dated sources)")
    if sources and not audit_distances:
        notes.append(f"no temporally-local ({MAX_ACTIVE_WINDOW_DAYS}-day) same-country neighbor existed for any dated source")
    pathological_note = "; ".join(notes) if notes else None

    return CountryScopedParameterCandidateReport(
        n_sources_considered=len(sources),
        n_countries=len(by_country),
        per_country_nn_distance=[c.as_dict() for c in per_country_nn],
        pooled_within_country_nn_distance_km_quantiles=_quantiles(pooled_nn),
        per_country_temporal_gap=[c.as_dict() for c in per_country_temporal],
        pooled_within_country_temporal_gap_days_quantiles=_quantiles(pooled_gaps),
        temporally_local_nn_distance_audit_km_quantiles=_quantiles(audit_distances),
        temporally_local_nn_audit_max_window_days=MAX_ACTIVE_WINDOW_DAYS,
        active_window_day_candidates=list(ACTIVE_WINDOW_DAY_CANDIDATES),
        min_core_support_candidates=list(MIN_CORE_SUPPORT_CANDIDATES),
        pathological_note=pathological_note,
    )

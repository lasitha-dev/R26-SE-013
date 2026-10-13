"""Checkpoint 6B Parts 1-4: model-fitting exposure freeze.

Freezes which forecast origins may ever be touched by ST-DBSCAN
parameter development, feature selection, active-window selection,
weather-lookback selection, or (later) risk-coefficient fitting —
BEFORE any of that development happens, and BEFORE any predictive
performance exists to be tempted by.

Three mutually exclusive roles, one per forecast origin:

    FIT_DEVELOPMENT               t0 < MODEL_FITTING_CUTOFF, non-Sri-Lanka
    HELD_OUT_FROM_MODEL_FITTING   t0 >= MODEL_FITTING_CUTOFF, non-Sri-Lanka
    SRI_LANKA_TRANSFER_CASE_STUDY country == "Sri Lanka", regardless of date

**`HELD_OUT_FROM_MODEL_FITTING` is not "blind," "untouched," or
"unseen"** — every record in this corpus has already been audited
(Checkpoints 1-5). It specifically means: excluded from parameter/
coefficient FITTING. This checkpoint's own code never inspects
held-out-role origins' outcomes for anything beyond administrative
counting (Part 4) — no held-out risk capture, direction error, speed
error, or model accuracy of any kind is computed here, because no risk/
direction/speed model exists yet at all.

**Sri Lanka stays `SRI_LANKA_TRANSFER_CASE_STUDY` even for its pre-2024
Event_3473 records** — its outcomes are excluded from every fitting
decision (ST-DBSCAN parameters, feature selection, active-window
selection, weather-lookback selection, risk-coefficient/normalization
fitting) regardless of whether its t0 would otherwise fall inside
`FIT_DEVELOPMENT`. It may be run later only after development decisions
made from `FIT_DEVELOPMENT` are already frozen.

The `MODEL_FITTING_CUTOFF` boundary is fixed now, before any PISTES/
ST-DBSCAN predictive performance exists, and must never be moved later
because results looked poor on one side of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dates import parse_flexible_date
from .forecast_origin import ForecastOrigin
from .split_embargo import assess_embargo, assess_validation_block

MODEL_FITTING_CUTOFF = "2024-01-01"

FIT_DEVELOPMENT = "FIT_DEVELOPMENT"
HELD_OUT_FROM_MODEL_FITTING = "HELD_OUT_FROM_MODEL_FITTING"
SRI_LANKA_TRANSFER_CASE_STUDY = "SRI_LANKA_TRANSFER_CASE_STUDY"

_SRI_LANKA_COUNTRY_NAME = "Sri Lanka"


def classify_origin_role(origin: ForecastOrigin, *, cutoff: str = MODEL_FITTING_CUTOFF) -> str:
    """Pure: the single source of truth for a forecast origin's
    model-fitting-exposure role (SPLIT-6B-01..03). Sri Lanka is checked
    FIRST — it is `SRI_LANKA_TRANSFER_CASE_STUDY` unconditionally, even
    for a pre-cutoff `t0`."""
    if origin.country == _SRI_LANKA_COUNTRY_NAME:
        return SRI_LANKA_TRANSFER_CASE_STUDY
    cutoff_date = parse_flexible_date(cutoff)
    t0_date = parse_flexible_date(origin.t0)
    if cutoff_date is None or t0_date is None:
        raise ValueError(f"unparseable date: cutoff={cutoff!r} t0={origin.t0!r}")
    if t0_date < cutoff_date:
        return FIT_DEVELOPMENT
    return HELD_OUT_FROM_MODEL_FITTING


@dataclass
class ExposureRow:
    forecast_origin_id: str
    t0: str
    country: str
    role: str
    purged_by_7_day_rule: bool
    reason: str

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "country": self.country,
            "role": self.role,
            "purged_by_7_day_rule": self.purged_by_7_day_rule,
            "reason": self.reason,
        }


def build_model_fitting_exposure_manifest(
    origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF
) -> list[ExposureRow]:
    """One row per origin, role-classified (Part 1-2) plus whether the
    frozen `PURGED_7_DAY_HORIZON_POLICY` (Part 3) would purge it from the
    `FIT_DEVELOPMENT`-vs-cutoff boundary specifically — reported for
    every origin (including Sri Lanka and held-out ones) so nothing is
    hidden (Part 21: "Do not hide exclusions"), even though the purge
    rule is only actually APPLIED when building development folds
    (`build_calendar_year_folds`)."""
    embargo_by_id = {a.forecast_origin_id: a for a in assess_embargo(origins, boundary=cutoff)}

    rows: list[ExposureRow] = []
    for origin in origins:
        role = classify_origin_role(origin, cutoff=cutoff)
        embargo = embargo_by_id.get(origin.forecast_origin_id)
        purged = bool(embargo and embargo.embargoed)
        if role == SRI_LANKA_TRANSFER_CASE_STUDY:
            reason = "Sri Lanka: excluded from all fitting/tuning regardless of t0 (GEOGRAPHIC_TRANSFER_CASE_STUDY)"
        elif role == HELD_OUT_FROM_MODEL_FITTING:
            reason = f"t0 >= {cutoff}: reserved for evaluation, excluded from parameter/coefficient fitting"
        elif purged:
            reason = embargo.reason if embargo else "target window reaches/crosses the model-fitting cutoff"
        else:
            reason = f"t0 < {cutoff}, non-Sri-Lanka: eligible for FIT_DEVELOPMENT"
        rows.append(
            ExposureRow(
                forecast_origin_id=origin.forecast_origin_id,
                t0=origin.t0,
                country=origin.country,
                role=role,
                purged_by_7_day_rule=purged,
                reason=reason,
            )
        )
    return rows


def fit_development_origins(origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF) -> list[ForecastOrigin]:
    """The ONLY origins ST-DBSCAN parameter-development functions may
    receive (Part 4's held-out firewall) — Sri Lanka and
    `HELD_OUT_FROM_MODEL_FITTING` origins are never returned here."""
    return [o for o in origins if classify_origin_role(o, cutoff=cutoff) == FIT_DEVELOPMENT]


def assert_fit_development_only(
    origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF, caller: str = ""
) -> None:
    """Checkpoint 6B.5 Part 12 hard firewall: a development-only analysis
    function must call this at its OWN entry point, rather than trusting
    that its caller already pre-filtered to `fit_development_origins`.
    Raises `ValueError` — never silently filters — the moment ANY
    supplied origin is not `FIT_DEVELOPMENT`, naming every offending
    origin and its actual role so the caller can see exactly what leaked
    in. A mixed development+held-out list is rejected in full, not
    partially accepted."""
    offending = [(o.forecast_origin_id, classify_origin_role(o, cutoff=cutoff)) for o in origins]
    offending = [(oid, role) for oid, role in offending if role != FIT_DEVELOPMENT]
    if offending:
        detail = ", ".join(f"{oid}={role}" for oid, role in offending)
        prefix = f"{caller}: " if caller else ""
        raise ValueError(
            f"{prefix}received {len(offending)} non-FIT_DEVELOPMENT origin(s): {detail} — this is a "
            "development-only function and must never receive HELD_OUT_FROM_MODEL_FITTING or "
            "SRI_LANKA_TRANSFER_CASE_STUDY origins, even mixed into an otherwise-valid list "
            "(Checkpoint 6B.5 Part 12 hard firewall)"
        )


def held_out_from_model_fitting_origins(origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF) -> list[ForecastOrigin]:
    """Checkpoint 7D Part 3: the ONLY origins a held-out-from-fitting
    EVALUATION function may receive — the exact symmetric counterpart of
    `fit_development_origins`. Sri Lanka and `FIT_DEVELOPMENT` origins
    are never returned here."""
    return [o for o in origins if classify_origin_role(o, cutoff=cutoff) == HELD_OUT_FROM_MODEL_FITTING]


def assert_held_out_only(origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF, caller: str = "") -> None:
    """Checkpoint 7D Part 3 hard firewall: the exact symmetric counterpart
    of `assert_fit_development_only` — a held-out-evaluation-only function
    must call this at its OWN entry point. Raises `ValueError` — never
    silently filters — the moment ANY supplied origin is not
    `HELD_OUT_FROM_MODEL_FITTING`, naming every offending origin and its
    actual role. A mixed development+held-out+Sri-Lanka list is rejected
    in full, not partially accepted."""
    offending = [(o.forecast_origin_id, classify_origin_role(o, cutoff=cutoff)) for o in origins]
    offending = [(oid, role) for oid, role in offending if role != HELD_OUT_FROM_MODEL_FITTING]
    if offending:
        detail = ", ".join(f"{oid}={role}" for oid, role in offending)
        prefix = f"{caller}: " if caller else ""
        raise ValueError(
            f"{prefix}received {len(offending)} non-HELD_OUT_FROM_MODEL_FITTING origin(s): {detail} — this is a "
            "held-out-evaluation-only function and must never receive FIT_DEVELOPMENT or "
            "SRI_LANKA_TRANSFER_CASE_STUDY origins, even mixed into an otherwise-valid list "
            "(Checkpoint 7D Part 3 hard firewall)"
        )


def sri_lanka_transfer_case_study_origins(origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF) -> list[ForecastOrigin]:
    """Checkpoint 7E Part 3: the ONLY origins a Sri Lanka geographic-
    transfer case-study function may receive -- the third symmetric
    counterpart alongside `fit_development_origins`/
    `held_out_from_model_fitting_origins`."""
    return [o for o in origins if classify_origin_role(o, cutoff=cutoff) == SRI_LANKA_TRANSFER_CASE_STUDY]


def assert_sri_lanka_transfer_case_study_only(origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF, caller: str = "") -> None:
    """Checkpoint 7E Part 3 hard firewall: the third symmetric counterpart
    of `assert_fit_development_only`/`assert_held_out_only` -- a Sri Lanka
    case-study-only function must call this at its OWN entry point.
    Raises `ValueError` -- never silently filters -- the moment ANY
    supplied origin is not `SRI_LANKA_TRANSFER_CASE_STUDY`."""
    offending = [(o.forecast_origin_id, classify_origin_role(o, cutoff=cutoff)) for o in origins]
    offending = [(oid, role) for oid, role in offending if role != SRI_LANKA_TRANSFER_CASE_STUDY]
    if offending:
        detail = ", ".join(f"{oid}={role}" for oid, role in offending)
        prefix = f"{caller}: " if caller else ""
        raise ValueError(
            f"{prefix}received {len(offending)} non-SRI_LANKA_TRANSFER_CASE_STUDY origin(s): {detail} -- this is a "
            "Sri-Lanka-case-study-only function and must never receive FIT_DEVELOPMENT or "
            "HELD_OUT_FROM_MODEL_FITTING origins, even mixed into an otherwise-valid list "
            "(Checkpoint 7E Part 3 hard firewall)"
        )


@dataclass
class CalendarYearFold:
    fold_id: str
    validation_year: int
    training_date_range_end: str
    validation_date_range_start: str
    validation_date_range_end: str
    training_origin_ids: list[str] = field(default_factory=list)
    validation_origin_ids: list[str] = field(default_factory=list)
    purged_origin_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "validation_year": self.validation_year,
            "training_date_range_end": self.training_date_range_end,
            "validation_date_range_start": self.validation_date_range_start,
            "validation_date_range_end": self.validation_date_range_end,
            "training_origin_count": len(self.training_origin_ids),
            "validation_origin_count": len(self.validation_origin_ids),
            "purged_origin_count": len(self.purged_origin_ids),
            "training_origin_ids": self.training_origin_ids,
            "validation_origin_ids": self.validation_origin_ids,
            "purged_origin_ids": self.purged_origin_ids,
        }


def build_calendar_year_folds(
    origins: list[ForecastOrigin], *, cutoff: str = MODEL_FITTING_CUTOFF
) -> list[CalendarYearFold]:
    """Deterministic CALENDAR-YEAR expanding-window folds (Part 3) —
    never random shuffle (SPLIT-6B-06). Built ONLY from
    `fit_development_origins` (Sri Lanka and held-out origins never
    enter any fold). For each calendar year Y with at least one eligible
    `FIT_DEVELOPMENT` origin: training = all `FIT_DEVELOPMENT` origins
    with `t0 < Y-01-01`, purge-filtered by the frozen
    `PURGED_7_DAY_HORIZON_POLICY` (`t0 + 7 < Y-01-01`); validation =
    `FIT_DEVELOPMENT` origins with `t0` inside calendar year Y, restricted
    to those with a COMPLETE D1-D7 window inside that year
    (`split_embargo.assess_validation_block`) — an origin whose D1-D7
    window crosses into the next year is not silently included with a
    truncated horizon, it is excluded from that year's complete set.
    Sparse/empty years are reported honestly, never dropped or merged
    with a neighboring year to look fuller."""
    dev_origins = fit_development_origins(origins, cutoff=cutoff)

    years = sorted({parse_flexible_date(o.t0).year for o in dev_origins if parse_flexible_date(o.t0) is not None})

    folds: list[CalendarYearFold] = []
    for year in years:
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"

        embargo = assess_embargo(dev_origins, boundary=year_start)
        training_ids = [
            a.forecast_origin_id
            for a in embargo
            if a.partition == "BEFORE_BOUNDARY" and not a.embargoed
        ]
        purged_ids = [a.forecast_origin_id for a in embargo if a.partition == "BEFORE_BOUNDARY" and a.embargoed]

        block = assess_validation_block(dev_origins, block_start=year_start, block_end=year_end)
        validation_ids = [b.forecast_origin_id for b in block if b.complete]

        folds.append(
            CalendarYearFold(
                fold_id=f"FOLD:{year}",
                validation_year=year,
                training_date_range_end=year_start,
                validation_date_range_start=year_start,
                validation_date_range_end=year_end,
                training_origin_ids=sorted(training_ids),
                validation_origin_ids=sorted(validation_ids),
                purged_origin_ids=sorted(purged_ids),
            )
        )
    return folds

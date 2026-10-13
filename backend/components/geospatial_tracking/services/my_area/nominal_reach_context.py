"""GEO-AREA-01H Section 4/6: builds the D0/D+N nominal-reach context for
one selected origin/day. Pure -- operates on the real
`nominal_reach_by_day` entries already fetched by the existing scientific
read path (`NominalReachDaySchema.as_dict()`-shaped dicts:
`{day, nominal_reach_km, derived_interval_lower_km,
derived_interval_upper_km}`), never recomputes a reach value.

GEO-AREA-01H correction (superseding GEO-AREA-01's original version):
this module no longer accepts or compares against a "distance to
origin" parameter. Evidence (`services/integration/nominal_reach_9c.py`,
verified read-only): `nominal_reach_km(day_h) = frozen_S0_rate_km_day *
day_h` is a pure function of `day_h` alone -- no coordinate, source, or
origin appears anywhere in that module's inputs. The frontend's own
`nominalReachRing.js` (verified read-only) independently reached the
same conclusion, explicitly avoiding picking any one source as "the"
ring center. There is therefore no scientifically defensible anchor to
measure the area's distance against, so `relation` is always
`NOT_APPLICABLE`, with `anchor_basis` stating why -- never a fabricated
`WITHIN_`/`OUTSIDE_NOMINAL_VISUALIZATION_REACH`.
"""

from __future__ import annotations

from ...domain.my_area_enums import (
    NOMINAL_REACH_DISCLAIMER,
    ForecastDayBasis,
    NominalReachAnchorBasis,
    NominalReachRelation,
)
from ...domain.my_area_models import NominalReachContext


def build_nominal_reach_context(
    *,
    day: int,
    t0: str,
    nominal_reach_entries: list[dict],
) -> NominalReachContext | None:
    """Returns `None` for a requested D+N day (1..7) with no matching
    real entry in `nominal_reach_entries` -- the caller maps that to
    `MyAreaStatus.FORECAST_FRAME_UNAVAILABLE` (never interpolated, never
    a fabricated day-0-style `None` swapped in silently).

    Section 15: D0 NEVER fabricates `nominal_reach_km = 0` -- it is
    `None`, with `relation = NOT_APPLICABLE` and `basis =
    OBSERVED_ORIGIN_CONTEXT`, using the real origin `t0` as its
    `forecast_date` (the one day this function can state a real date for
    without inventing day-arithmetic).
    """
    if day == 0:
        return NominalReachContext(
            day=0,
            forecast_date=t0,
            basis=ForecastDayBasis.OBSERVED_ORIGIN_CONTEXT.value,
            nominal_reach_km=None,
            relation=NominalReachRelation.NOT_APPLICABLE.value,
            anchor_basis=NominalReachAnchorBasis.NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR.value,
            disclaimer=NOMINAL_REACH_DISCLAIMER,
        )

    entry = next((e for e in nominal_reach_entries if e.get("day") == day), None)
    if entry is None:
        return None

    reach_km = entry.get("nominal_reach_km")

    return NominalReachContext(
        day=day,
        # Section 15: no real per-day calendar date exists anywhere in
        # the current backend contract -- `SelectedOriginContext.t0`
        # (GEO-AREA-01H Section 12) carries the real origin date instead,
        # so the frontend's own tested day-arithmetic utility can derive
        # a D+N date without this backend reimplementing it.
        forecast_date=None,
        basis=ForecastDayBasis.FORECAST.value,
        nominal_reach_km=reach_km,
        # Section 4/6: no scientifically defined reach anchor exists --
        # never WITHIN_/OUTSIDE_NOMINAL_VISUALIZATION_REACH this checkpoint.
        relation=NominalReachRelation.NOT_APPLICABLE.value,
        anchor_basis=NominalReachAnchorBasis.NO_SCIENTIFICALLY_DEFINED_REACH_ANCHOR.value,
        disclaimer=NOMINAL_REACH_DISCLAIMER,
    )

"""Checkpoint 7A.5 Parts 6-9, 21-22: local target-scope classification —
FOR EVALUATION SCOPE ONLY, never a causal-parent claim.

Uses ONLY the pre-existing ST-DBSCAN joint spatiotemporal neighborhood
rule (`services.stdbscan.neighborhood.joint_neighbors`, unchanged) to
decide whether a future D1-D7 target is associated with a
`LocalForecastContext` — this rule existed and was coded (Checkpoint
6B) long before this checkpoint's own target-distance findings, so
reusing it is not the same as inventing a new local-distance number in
response to Checkpoint 7A's coverage failure (Part 7). The future
target's own coordinates/date MAY be read here — this is
development/evaluation TRUTH CONSTRUCTION, not prediction — but the
ASSOCIATION RULE itself (`eps_space_km`/`eps_time_days` from a supplied
`STDBSCANConfig`) is never selected or adjusted using how many targets
it happens to label local (Part 8: forbidden — no model score, kernel
scale, or domain-distance candidate may ever influence this label,
enforced structurally: none of those concepts has a parameter on this
module's functions at all).

Because the underlying `STDBSCANConfig` can never itself be
`FROZEN_REFERENCE` (see `local_context.py`'s module docstring), every
label produced here is a real, descriptive classification under an
explicitly-named UNFROZEN candidate config — never presented as a
scientifically finalized evaluation-scope decision.

**Permanent distinction (Parts 21-22)**: a `NONLOCAL_FUTURE_EVENT` is
OUTSIDE the local spread-risk model's scientific claim entirely — it is
NOT counted as an out-of-domain failure of the local model, but it
DOES remain in the audit ledger (Part 21). A target already classified
`LOCAL_SCOPE_TARGET` that later falls outside the frozen scientific
evaluation domain keeps a SEPARATE label,
`TARGET_OUTSIDE_EVALUATION_DOMAIN` — a real model-coverage failure,
never reclassified as nonlocal just because the domain missed it
(Part 22).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geospatial.distance import distance_km
from ..stdbscan.config import STDBSCANConfig
from ..stdbscan.neighborhood import joint_neighbors
from .local_context import LocalForecastContext

LOCAL_SCOPE_TARGET = "LOCAL_SCOPE_TARGET"
NONLOCAL_FUTURE_EVENT = "NONLOCAL_FUTURE_EVENT"
LOCAL_SCOPE_UNRESOLVED = "LOCAL_SCOPE_UNRESOLVED"


@dataclass(frozen=True)
class LocalTargetScopeResult:
    target_id: str
    target_event_id: str
    forecast_origin_id: str
    local_context_id: str | None
    scope_status: str
    nearest_member_source_id: str | None
    min_spatial_distance_km: float | None

    def as_dict(self) -> dict:
        return {
            "target_id": self.target_id, "target_event_id": self.target_event_id, "forecast_origin_id": self.forecast_origin_id,
            "local_context_id": self.local_context_id, "scope_status": self.scope_status,
            "nearest_member_source_id": self.nearest_member_source_id, "min_spatial_distance_km": self.min_spatial_distance_km,
        }


def classify_target_local_scope(
    *, target, local_contexts: list[LocalForecastContext], member_points_by_context: dict, st_config: STDBSCANConfig,
) -> LocalTargetScopeResult:
    """`target`: a `ForecastTarget`-shaped object. `member_points_by_context`:
    `{local_context_id: [(source_id, lat, lon, cluster_event_date), ...]}`
    (see `local_context.member_points`). No model score, kernel scale,
    or domain-distance parameter exists on this signature at all
    (LOCAL-TGT-05/06/07)."""
    if not local_contexts:
        return LocalTargetScopeResult(
            target_id=target.target_id, target_event_id=target.target_event_id, forecast_origin_id=target.forecast_origin_id,
            local_context_id=None, scope_status=LOCAL_SCOPE_UNRESOLVED, nearest_member_source_id=None, min_spatial_distance_km=None,
        )

    best_nonlocal: tuple | None = None  # (context_id, source_id, spatial_km)
    for ctx in sorted(local_contexts, key=lambda c: c.local_context_id):
        points = sorted(member_points_by_context.get(ctx.local_context_id, []), key=lambda p: p[0])
        for source_id, lat, lon, event_date in points:
            try:
                is_local = joint_neighbors(
                    lat_a=lat, lon_a=lon, date_a=event_date,
                    lat_b=target.latitude, lon_b=target.longitude, date_b=target.historical_event_date,
                    eps_space_km=st_config.eps_space_km, eps_time_days=st_config.eps_time_days,
                )
            except ValueError:
                continue  # unparseable date on either side -- this pair can't judge; try others
            spatial_km = distance_km(lat, lon, target.latitude, target.longitude)
            if is_local:
                return LocalTargetScopeResult(
                    target_id=target.target_id, target_event_id=target.target_event_id, forecast_origin_id=target.forecast_origin_id,
                    local_context_id=ctx.local_context_id, scope_status=LOCAL_SCOPE_TARGET,
                    nearest_member_source_id=source_id, min_spatial_distance_km=spatial_km,
                )
            if best_nonlocal is None or spatial_km < best_nonlocal[2]:
                best_nonlocal = (ctx.local_context_id, source_id, spatial_km)

    if best_nonlocal is None:
        return LocalTargetScopeResult(
            target_id=target.target_id, target_event_id=target.target_event_id, forecast_origin_id=target.forecast_origin_id,
            local_context_id=None, scope_status=LOCAL_SCOPE_UNRESOLVED, nearest_member_source_id=None, min_spatial_distance_km=None,
        )
    ctx_id, source_id, spatial_km = best_nonlocal
    return LocalTargetScopeResult(
        target_id=target.target_id, target_event_id=target.target_event_id, forecast_origin_id=target.forecast_origin_id,
        local_context_id=ctx_id, scope_status=NONLOCAL_FUTURE_EVENT, nearest_member_source_id=source_id, min_spatial_distance_km=spatial_km,
    )

"""Checkpoint 7A.5 Parts 1-5: `LocalForecastContext` — a trigger-anchored
ST-spatial context, never a causal/transmission claim.

**Why ST-DBSCAN cannot be used as a FROZEN local-context rule (Part
1)**: `services/stdbscan/config.py`'s `STDBSCANConfig.__post_init__`
structurally forbids `parameter_status=FROZEN_REFERENCE` — "no held-out
prediction performance exists yet to justify freezing any ST-DBSCAN
parameter" (`STDBSCAN_PROTOCOL.md` §8/9). `SPLIT_USAGE_FREEZE.md` §7
confirms explicitly: "This freeze governs exposure only. It does not
select an ST-DBSCAN [parameter/constant]." No `eps_space_km`,
`eps_time_days`, or `min_core_supports` value has ever been selected —
only quantile-derived CANDIDATES exist (`candidate_constants.py`), and
the one real sensitivity result on record (`STDBSCAN_PROTOCOL.md` §10)
found essentially 100% noise at the tightest data-derived candidates
for a real country sample. Consequently `LocalForecastContext` here is
built from an EXPLICITLY SUPPLIED, caller-labeled `STDBSCANConfig`
candidate — never a value invented in response to this checkpoint's own
findings — and `context_status` always reports
`LOCAL_CONTEXT_UNFROZEN_ST_DBSCAN_CANDIDATE_BASIS`: this module never
claims a scientifically finalized local context, only a real, testable,
descriptive one under a named unfrozen config. See
`MODEL_DEVELOPMENT_PROTOCOL.md` for the resulting freeze status of
everything built on top of it.

**Trigger-anchored construction (Parts 2-4)**: for each forecast-origin
TRIGGER source, this module finds the ST-DBSCAN connected component
(CORE+BORDER cluster, or a NOISE/TEMPORAL_UNUSABLE singleton — a
confirmed trigger is NEVER discarded for being noise, Part 3.5)
containing it, under the supplied `STDBSCANConfig`. Two triggers landing
in the SAME component collapse into ONE `LocalForecastContext`;
triggers in geographically disconnected components become SEPARATE
contexts sharing only `forecast_origin_id` — never merged into one
country-wide domain (Part 4).

**Nothing is deleted (Part 5)**: every country-eligible source at t0
is preserved in `country_eligible_source_ids`; a source not in any
trigger's context is retained in `excluded_country_source_ids` with an
explicit, specific reason — never silently dropped from the source
selector or database.

Correct terminology only: "LOCAL SOURCE CONTEXT" / "TRIGGER-ANCHORED
ST-SPATIAL CONTEXT" — never "causal transmission chain," "infectious
chain," or "true parent-child chain" (mirrors `STDBSCAN_PROTOCOL.md`
§1's own permanent framing rule).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field

from ..model_fitting_exposure import assert_fit_development_only
from ..stdbscan.config import STDBSCANConfig
from ..stdbscan.event_date import ST_USABLE, resolve_cluster_event_date
from ..stdbscan.snapshot import STClusterSnapshot, build_st_cluster_snapshot

LOCAL_CONTEXT_PROTOCOL_VERSION = "7A.5.1"
CONTEXT_METHOD_TRIGGER_ANCHORED = "TRIGGER_ANCHORED_ST_SPATIAL_CONTEXT"
CONTEXT_STATUS_UNFROZEN = "LOCAL_CONTEXT_UNFROZEN_ST_DBSCAN_CANDIDATE_BASIS"

EXCLUDED_OUTSIDE_TRIGGER_LOCAL_CONTEXT = "OUTSIDE_TRIGGER_LOCAL_CONTEXT"
EXCLUDED_TEMPORAL_UNUSABLE_NOT_CLUSTERED = "TEMPORAL_UNUSABLE_NOT_CLUSTERED"


def local_context_protocol_hash(st_dbscan_config_hash: str) -> str:
    """Method-level identity: the SAME for every context built with the
    same underlying `STDBSCANConfig` — changing the config, or the
    context-construction method itself, changes this hash."""
    payload = {
        "protocol_version": LOCAL_CONTEXT_PROTOCOL_VERSION,
        "context_method": CONTEXT_METHOD_TRIGGER_ANCHORED,
        "st_dbscan_config_hash": st_dbscan_config_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LocalForecastContext:
    local_context_id: str
    forecast_origin_id: str
    t0: str
    country: str | None
    trigger_source_ids: tuple
    country_eligible_source_ids: tuple
    local_source_ids: tuple
    excluded_country_source_ids: tuple
    excluded_source_reasons: dict
    context_method: str
    context_protocol_hash: str
    st_dbscan_config_hash_if_used: str
    context_status: str
    generated_at: str = ""

    def as_dict(self) -> dict:
        return {
            "local_context_id": self.local_context_id, "forecast_origin_id": self.forecast_origin_id, "t0": self.t0,
            "country": self.country, "trigger_source_ids": list(self.trigger_source_ids),
            "country_eligible_source_ids": list(self.country_eligible_source_ids),
            "local_source_ids": list(self.local_source_ids),
            "excluded_country_source_ids": list(self.excluded_country_source_ids),
            "excluded_source_reasons": dict(self.excluded_source_reasons),
            "context_method": self.context_method, "context_protocol_hash": self.context_protocol_hash,
            "st_dbscan_config_hash_if_used": self.st_dbscan_config_hash_if_used, "context_status": self.context_status,
            "generated_at": self.generated_at,
        }


def _local_context_id(*, forecast_origin_id: str, member_ids: list, protocol_hash: str) -> str:
    payload = "|".join(sorted(member_ids)) + "||" + forecast_origin_id + "||" + protocol_hash
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"LOCALCTX:{digest[:24]}"


def build_local_forecast_contexts(
    repo, *, origin, disease: str, st_config: STDBSCANConfig, generated_at: str = "",
) -> list[LocalForecastContext]:
    """T0-safe by construction — no parameter here can carry a future
    target coordinate (LOCAL-SRC-07): this signature accepts only a
    repo, a `ForecastOrigin` (t0/trigger/country), a disease string, and
    an `STDBSCANConfig`. Deterministic (LOCAL-SRC-08): identical
    inputs against identical repo state always produce identical
    `local_context_id`s, because every grouping/sorting step here is by
    sorted source_id, exactly mirroring `services.stdbscan.cluster`'s
    own determinism discipline."""
    snap: STClusterSnapshot = build_st_cluster_snapshot(
        repo, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, country_scope=origin.country,
        disease=disease, config=st_config,
    )
    country_eligible_ids = set(snap.active_source_ids)
    proto_hash = local_context_protocol_hash(snap.config_hash)

    trigger_ids = sorted(origin.trigger_source_ids_at_t0)
    group_key_by_trigger: dict[str, tuple] = {}
    for tid in trigger_ids:
        assignment = snap.assignments.get(tid)
        if assignment is None:
            # defensive: a confirmed trigger somehow absent from this
            # config's active-source set -- never discarded, its own
            # singleton context (Part 3.5's spirit extended defensively).
            group_key_by_trigger[tid] = ("SINGLETON_MISSING", tid)
            continue
        cluster_id = assignment.get("cluster_id")
        if cluster_id:
            group_key_by_trigger[tid] = ("CLUSTER", cluster_id)
        else:
            # NOISE or TEMPORAL_UNUSABLE trigger -> its own singleton
            # (Part 3.4-3.5: never discard a confirmed trigger for being noise).
            group_key_by_trigger[tid] = ("SINGLETON", tid)

    groups: dict[tuple, list] = {}
    for tid, key in group_key_by_trigger.items():
        groups.setdefault(key, []).append(tid)

    cluster_by_id = {c["cluster_id"]: c for c in snap.clusters}

    contexts: list[LocalForecastContext] = []
    all_context_members: set = set()
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        group_triggers = sorted(groups[key])
        kind, ident = key
        if kind == "CLUSTER":
            member_ids = sorted(cluster_by_id[ident]["member_source_ids"])
        else:
            member_ids = sorted(set(group_triggers))
        all_context_members |= set(member_ids)
        local_context_id = _local_context_id(forecast_origin_id=origin.forecast_origin_id, member_ids=member_ids, protocol_hash=proto_hash)
        contexts.append(LocalForecastContext(
            local_context_id=local_context_id, forecast_origin_id=origin.forecast_origin_id, t0=origin.t0, country=origin.country,
            trigger_source_ids=tuple(group_triggers), country_eligible_source_ids=tuple(sorted(country_eligible_ids)),
            local_source_ids=tuple(member_ids), excluded_country_source_ids=(), excluded_source_reasons={},
            context_method=CONTEXT_METHOD_TRIGGER_ANCHORED, context_protocol_hash=proto_hash,
            st_dbscan_config_hash_if_used=snap.config_hash, context_status=CONTEXT_STATUS_UNFROZEN, generated_at=generated_at,
        ))

    excluded_reasons: dict = {}
    for sid in sorted(country_eligible_ids - all_context_members):
        role = (snap.assignments.get(sid) or {}).get("cluster_role")
        excluded_reasons[sid] = EXCLUDED_TEMPORAL_UNUSABLE_NOT_CLUSTERED if role == "TEMPORAL_UNUSABLE" else EXCLUDED_OUTSIDE_TRIGGER_LOCAL_CONTEXT
    excluded_ids = tuple(sorted(excluded_reasons.keys()))

    return [dataclasses.replace(c, excluded_country_source_ids=excluded_ids, excluded_source_reasons=dict(excluded_reasons)) for c in contexts]


def build_local_forecast_context_development_report(
    repo, *, fit_development_origins: list, disease: str, st_config: STDBSCANConfig, generated_at: str = "",
) -> dict:
    """Checkpoint 7A.5 Part 9/31 (LOCAL-SRC-05/06): the ONLY safe entry
    point for real, multi-origin local-context DEVELOPMENT statistics —
    `assert_fit_development_only` is called here, at this function's
    OWN entry point (never trusting a caller to have pre-filtered),
    mirroring every other `services/model_development/` and
    `services/factors/` development-report function. Returns
    `{forecast_origin_id: [LocalForecastContext, ...]}` plus summary
    counts — never a predictive score, never a target/outcome field."""
    assert_fit_development_only(fit_development_origins, caller="build_local_forecast_context_development_report")

    contexts_by_origin: dict = {}
    n_singleton_noise = 0
    n_contexts = 0
    for origin in sorted(fit_development_origins, key=lambda o: o.forecast_origin_id):
        contexts = build_local_forecast_contexts(repo, origin=origin, disease=disease, st_config=st_config, generated_at=generated_at)
        contexts_by_origin[origin.forecast_origin_id] = contexts
        n_contexts += len(contexts)
        for ctx in contexts:
            if len(ctx.local_source_ids) == 1:
                n_singleton_noise += 1

    return {
        "contexts_by_origin": contexts_by_origin,
        "n_origins": len(fit_development_origins),
        "n_local_contexts": n_contexts,
        "n_singleton_contexts": n_singleton_noise,
        "st_dbscan_config_hash": st_config.config_hash(),
        "context_status": CONTEXT_STATUS_UNFROZEN,
    }


def member_points(repo, *, source_ids, t0: str) -> list:
    """`[(source_id, lat, lon, cluster_event_date), ...]` for real
    `ST_USABLE` members of a local context — the same tuple shape
    `services.stdbscan` already uses, reused so
    `local_target_scope.classify_target_local_scope` needs no separate
    date-resolution logic of its own."""
    points = []
    for sid in sorted(source_ids):
        record = repo.get_historical_record(sid)
        if record is None or record.latitude is None or record.longitude is None:
            continue
        ced = resolve_cluster_event_date(record, t0=t0)
        if ced.usability != ST_USABLE:
            continue
        points.append((sid, record.latitude, record.longitude, ced.cluster_event_date))
    return points

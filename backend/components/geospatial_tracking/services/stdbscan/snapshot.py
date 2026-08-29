"""Checkpoint 6B Part 16: STClusterSnapshot — the ST-DBSCAN orchestrator.

    forecast_origin (t0)
        -> eligible active-source set (source_selector.get_eligible_sources, Part 6)
        -> cluster_event_date per source (event_date.py, Part 7)
        -> core_support_id per ST_USABLE source (core_support.py, Parts 9-11)
        -> deterministic clustering (cluster.py, Parts 12-15)
        -> STClusterSnapshot

No field here is `risk`, `probability`, `direction`, `speed`,
`prediction_accuracy`, or any future-target identifier (Part 16) —
`build_st_cluster_snapshot`'s signature accepts no such parameter; there
is structurally nothing a caller could pass that would leak a future
outcome into this function (mirrors `services.features.assembler.assemble_feature_snapshot`'s
same guarantee, ST-18).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...domain.enums import RecordDomainScope
from ...schemas import ValidationMode
from ..source_selector import get_eligible_sources
from .cluster import ClusterAssignment, ClusterSummary, TEMPORAL_UNUSABLE, run_st_clustering
from .config import STDBSCANConfig
from .core_support import compute_core_support_assignments
from .event_date import ST_TEMPORAL_UNUSABLE, ST_USABLE, resolve_cluster_event_date


@dataclass
class STClusterSnapshot:
    forecast_origin_id: str
    t0: str
    disease: str
    country_scope: str | None
    active_source_ids: list[str] = field(default_factory=list)
    cluster_usable_source_ids: list[str] = field(default_factory=list)
    temporal_unusable_source_ids: list[str] = field(default_factory=list)
    assignments: dict = field(default_factory=dict)  # source_id -> ClusterAssignment.as_dict()
    clusters: list = field(default_factory=list)  # list[ClusterSummary.as_dict()]
    noise_source_ids: list[str] = field(default_factory=list)
    # Checkpoint 6B Part 19: real per-source provenance needed for the
    # development-sensitivity report (GPS-quality composition,
    # approximate-coordinate support-collapse counts) without a second
    # redundant query layer re-deriving it.
    source_gps_quality: dict = field(default_factory=dict)  # source_id -> gps_quality (cluster_usable sources only)
    source_core_support_id: dict = field(default_factory=dict)  # source_id -> core_support_id or None
    config: dict = field(default_factory=dict)
    config_hash: str = ""
    gps_core_policy: str = ""
    generated_at: str = ""

    def as_dict(self) -> dict:
        return {
            "forecast_origin_id": self.forecast_origin_id,
            "t0": self.t0,
            "disease": self.disease,
            "country_scope": self.country_scope,
            "active_source_ids": self.active_source_ids,
            "cluster_usable_source_ids": self.cluster_usable_source_ids,
            "temporal_unusable_source_ids": self.temporal_unusable_source_ids,
            "assignments": self.assignments,
            "clusters": self.clusters,
            "noise_source_ids": self.noise_source_ids,
            "source_gps_quality": self.source_gps_quality,
            "source_core_support_id": self.source_core_support_id,
            "config": self.config,
            "config_hash": self.config_hash,
            "gps_core_policy": self.gps_core_policy,
            "generated_at": self.generated_at,
        }


def build_st_cluster_snapshot(
    repo,
    *,
    forecast_origin_id: str,
    t0: str,
    country_scope: str | None,
    disease: str,
    config: STDBSCANConfig,
) -> STClusterSnapshot:
    """Depends ONLY on `t0`, the eligible active-source set AT that `t0`
    (Part 6 — `get_eligible_sources` already enforces the T0 invariant),
    and the declared `config`. No target/label/lead_days/outcome
    parameter exists on this signature at all (ST-18).
    """
    eligible_result = get_eligible_sources(
        repo,
        disease=disease,
        t0=t0,
        active_window_days=config.active_window_days,
        temporal_mode=ValidationMode.RETROSPECTIVE_PROXY,
        country_scope=country_scope,
        domain_scope=RecordDomainScope.HISTORICAL_ONLY,
    )
    active_sources = eligible_result.sources
    active_source_ids = [s.source_id for s in active_sources]

    # Part 7: a SEPARATE historical event/occurrence date, never conflated
    # with the availability date that made the source eligible above.
    usable_sources = []
    temporal_unusable_ids: list[str] = []
    event_date_by_id = {}
    for s in active_sources:
        record = repo.get_historical_record(s.source_id)
        if record is None:
            temporal_unusable_ids.append(s.source_id)
            continue
        ced = resolve_cluster_event_date(record, t0=t0)
        event_date_by_id[s.source_id] = ced
        if ced.usability == ST_USABLE:
            usable_sources.append(s)
        else:
            temporal_unusable_ids.append(s.source_id)

    core_support_by_id = compute_core_support_assignments(usable_sources, gps_core_policy=config.gps_core_policy)
    usable_points = [
        (s.source_id, s.latitude, s.longitude, event_date_by_id[s.source_id].cluster_event_date)
        for s in usable_sources
    ]

    config_hash = config.config_hash()
    cluster_assignments, cluster_summaries = run_st_clustering(
        usable_points=usable_points,
        core_support_by_id=core_support_by_id,
        eps_space_km=config.eps_space_km,
        eps_time_days=config.eps_time_days,
        min_core_supports=config.min_core_supports,
        config_hash=config_hash,
        forecast_origin_id=forecast_origin_id,
    )

    assignments: dict[str, dict] = {a.as_dict()["source_id"]: a.as_dict() for a in cluster_assignments.values()}
    for source_id in temporal_unusable_ids:
        assignments[source_id] = ClusterAssignment(
            source_id=source_id, cluster_id=None, is_noise=False, cluster_role=TEMPORAL_UNUSABLE
        ).as_dict()

    noise_ids = sorted(sid for sid, a in assignments.items() if a["cluster_role"] == "NOISE")

    source_gps_quality = {csa.source_id: csa.gps_quality for csa in core_support_by_id.values()}
    source_core_support_id = {csa.source_id: csa.core_support_id for csa in core_support_by_id.values()}

    return STClusterSnapshot(
        forecast_origin_id=forecast_origin_id,
        t0=t0,
        disease=disease,
        country_scope=country_scope,
        active_source_ids=sorted(active_source_ids),
        cluster_usable_source_ids=sorted(s.source_id for s in usable_sources),
        temporal_unusable_source_ids=sorted(temporal_unusable_ids),
        assignments=assignments,
        clusters=[c.as_dict() for c in cluster_summaries],
        noise_source_ids=noise_ids,
        source_gps_quality=source_gps_quality,
        source_core_support_id=source_core_support_id,
        config=config.config_dict(),
        config_hash=config_hash,
        gps_core_policy=config.gps_core_policy,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

"""Checkpoint 6B Part 19: development-only sensitivity reporting.

Aggregates real `STClusterSnapshot`s built ONLY from `FIT_DEVELOPMENT`
forecast origins (Part 4's held-out firewall — callers must pass
already-`FIT_DEVELOPMENT`-filtered origins, e.g. via
`model_fitting_exposure.fit_development_origins`) across one or more
candidate `STDBSCANConfig`s. Reports descriptive counts only — **never**
prediction accuracy, held-out risk capture, direction error, or speed
error (none of that exists yet, and this checkpoint does not build it).
Configurations are never ranked against each other using outcome data —
this module has no access to any target/outcome field at all.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..model_fitting_exposure import assert_fit_development_only
from .config import STDBSCANConfig
from .snapshot import build_st_cluster_snapshot

DEFAULT_SCOPE_LABEL = "COUNTRY_SPECIFIC_DEVELOPMENT_SENSITIVITY"


@dataclass
class ConfigSensitivityReport:
    config_hash: str
    config: dict
    n_origins_evaluated: int
    n_usable_sources_total: int
    n_temporal_unusable_total: int
    n_clusters_total: int
    n_noise_total: int
    noise_fraction: float | None
    cluster_size_distribution: list
    largest_cluster_fraction: float | None
    gps_quality_composition: dict
    approximate_support_collapse_count: int
    scope_label: str = DEFAULT_SCOPE_LABEL

    def as_dict(self) -> dict:
        return {
            "scope_label": self.scope_label,
            "config_hash": self.config_hash,
            "config": self.config,
            "n_origins_evaluated": self.n_origins_evaluated,
            "n_usable_sources_total": self.n_usable_sources_total,
            "n_temporal_unusable_total": self.n_temporal_unusable_total,
            "n_clusters_total": self.n_clusters_total,
            "n_noise_total": self.n_noise_total,
            "noise_fraction": self.noise_fraction,
            "cluster_size_distribution": self.cluster_size_distribution,
            "largest_cluster_fraction": self.largest_cluster_fraction,
            "gps_quality_composition": self.gps_quality_composition,
            "approximate_support_collapse_count": self.approximate_support_collapse_count,
        }


def build_config_sensitivity_report(
    repo, *, fit_development_origins: list, disease: str, config: STDBSCANConfig, scope_label: str = DEFAULT_SCOPE_LABEL
) -> ConfigSensitivityReport:
    """Checkpoint 6B.5 Part 12 hard firewall: classifies EVERY supplied
    origin itself at entry via `assert_fit_development_only` — never
    trusts the caller to have pre-filtered to `fit_development_origins`,
    and never silently filters a bad one out. A single
    `HELD_OUT_FROM_MODEL_FITTING` or `SRI_LANKA_TRANSFER_CASE_STUDY`
    origin anywhere in the list rejects the ENTIRE call.

    `scope_label` (Part 13): callers running a country-specific sample
    (e.g. Thailand-only) MUST pass an explicit label such as
    `"THAILAND_DEVELOPMENT_SENSITIVITY"` — this report must never be
    read as international/global evidence when it is not."""
    assert_fit_development_only(fit_development_origins, caller="build_config_sensitivity_report")

    n_usable_total = 0
    n_temporal_unusable_total = 0
    n_clusters_total = 0
    n_noise_total = 0
    cluster_sizes: list[int] = []
    gps_counter: Counter = Counter()
    approx_collapse_count = 0

    for origin in fit_development_origins:
        snap = build_st_cluster_snapshot(
            repo,
            forecast_origin_id=origin.forecast_origin_id,
            t0=origin.t0,
            country_scope=origin.country,
            disease=disease,
            config=config,
        )
        n_usable_total += len(snap.cluster_usable_source_ids)
        n_temporal_unusable_total += len(snap.temporal_unusable_source_ids)
        n_clusters_total += len(snap.clusters)
        n_noise_total += len(snap.noise_source_ids)
        for c in snap.clusters:
            cluster_sizes.append(c["member_count"])

        gps_counter.update(snap.source_gps_quality.values())
        # an "approximate support collapse" happened for this origin's
        # APPROXIMATE/COARSE sources whenever 2+ distinct source_ids
        # share the exact same (non-null) core_support_id -- i.e. the
        # guard actually merged multiple records' density contribution.
        support_groups: dict[str, int] = {}
        for support_id in snap.source_core_support_id.values():
            if support_id is None:
                continue
            support_groups[support_id] = support_groups.get(support_id, 0) + 1
        approx_collapse_count += sum(1 for count in support_groups.values() if count > 1)

    cluster_sizes.sort()
    total_classified = n_usable_total  # usable sources are exactly core+border+noise
    noise_fraction = (n_noise_total / total_classified) if total_classified > 0 else None
    largest_cluster_fraction = (max(cluster_sizes) / total_classified) if cluster_sizes and total_classified > 0 else None

    return ConfigSensitivityReport(
        config_hash=config.config_hash(),
        config=config.config_dict(),
        n_origins_evaluated=len(fit_development_origins),
        n_usable_sources_total=n_usable_total,
        n_temporal_unusable_total=n_temporal_unusable_total,
        n_clusters_total=n_clusters_total,
        n_noise_total=n_noise_total,
        noise_fraction=noise_fraction,
        cluster_size_distribution=cluster_sizes,
        largest_cluster_fraction=largest_cluster_fraction,
        gps_quality_composition=dict(gps_counter),
        approximate_support_collapse_count=approx_collapse_count,
        scope_label=scope_label,
    )

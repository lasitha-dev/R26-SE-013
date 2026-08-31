"""Checkpoint 6B.5 Parts 13-15: INTERNATIONAL development sensitivity —
never silently Thailand-only.

Checkpoint 6B's `development_sensitivity.build_config_sensitivity_report`
was run only against Thailand's 136 `FIT_DEVELOPMENT` origins and its
output was informally described as "the development sensitivity
report" — that is unsafe framing: Thailand alone is not the real
`FIT_DEVELOPMENT` evidence base (579 origins across many countries).

This module runs the real `FIT_DEVELOPMENT` origin set and reports BOTH:

- a MICRO summary — every origin pooled together, exactly like
  `ConfigSensitivityReport` (useful as a single-number sanity check),
- a MACRO country summary — one slice per country, NEVER aggregated
  away (Part 15) — so no single high-origin-count country (Thailand)
  can dominate or hide what other countries look like.

`n_usable_source_appearances` is explicitly named "appearances," not
"sources," because the same real source can appear in many origins'
active-source windows — it is NOT a claim of pseudo-replicated
independent evidence (Part 20's no-pseudo-replication rule; contrast
`development_source_universe.DevelopmentSource`, which is the
de-duplicated unit used for parameter GEOMETRY, not for this
per-origin clustering-outcome sensitivity report).

Same hard firewall as `development_sensitivity.py` (Part 12): every
supplied origin is classified at entry; any non-`FIT_DEVELOPMENT`
origin rejects the whole call.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..model_fitting_exposure import assert_fit_development_only
from .config import STDBSCANConfig
from .snapshot import build_st_cluster_snapshot

SCOPE_LABEL = "INTERNATIONAL_DEVELOPMENT_SENSITIVITY"


@dataclass
class CountrySensitivitySlice:
    country: str
    n_origins_evaluated: int
    n_usable_source_appearances: int
    n_unique_source_ids: int
    n_clusters_total: int
    n_noise_total: int
    noise_fraction: float | None
    gps_quality_composition: dict
    approximate_support_collapse_count: int

    def as_dict(self) -> dict:
        return {
            "country": self.country,
            "n_origins_evaluated": self.n_origins_evaluated,
            "n_usable_source_appearances": self.n_usable_source_appearances,
            "n_unique_source_ids": self.n_unique_source_ids,
            "n_clusters_total": self.n_clusters_total,
            "n_noise_total": self.n_noise_total,
            "noise_fraction": self.noise_fraction,
            "gps_quality_composition": self.gps_quality_composition,
            "approximate_support_collapse_count": self.approximate_support_collapse_count,
        }


@dataclass
class InternationalDevelopmentSensitivityReport:
    scope_label: str
    config_hash: str
    config: dict
    n_origins_evaluated: int
    n_countries: int
    micro_summary: dict
    macro_country_summary: list

    def as_dict(self) -> dict:
        return {
            "scope_label": self.scope_label,
            "config_hash": self.config_hash,
            "config": self.config,
            "n_origins_evaluated": self.n_origins_evaluated,
            "n_countries": self.n_countries,
            "micro_summary": self.micro_summary,
            "macro_country_summary": self.macro_country_summary,
        }


def build_international_development_sensitivity_report(
    repo, *, fit_development_origins: list, disease: str, config: STDBSCANConfig
) -> InternationalDevelopmentSensitivityReport:
    """Part 12 hard firewall applies here too — see
    `development_sensitivity.build_config_sensitivity_report`'s
    docstring for the exact contract. No target/outcome/performance
    field exists anywhere in this module's output (SENS-03)."""
    assert_fit_development_only(fit_development_origins, caller="build_international_development_sensitivity_report")

    by_country: dict[str, list] = defaultdict(list)
    for o in fit_development_origins:
        by_country[o.country].append(o)

    micro_usable = 0
    micro_temporal_unusable = 0
    micro_clusters = 0
    micro_noise = 0
    micro_cluster_sizes: list[int] = []
    micro_gps_counter: Counter = Counter()
    micro_collapse = 0

    macro_slices: list[CountrySensitivitySlice] = []

    for country in sorted(by_country):
        origins = by_country[country]
        n_usable_appearances = 0
        unique_source_ids: set[str] = set()
        n_clusters = 0
        n_noise = 0
        gps_counter: Counter = Counter()
        collapse_count = 0

        for origin in origins:
            snap = build_st_cluster_snapshot(
                repo,
                forecast_origin_id=origin.forecast_origin_id,
                t0=origin.t0,
                country_scope=origin.country,
                disease=disease,
                config=config,
            )
            n_usable_appearances += len(snap.cluster_usable_source_ids)
            unique_source_ids.update(snap.cluster_usable_source_ids)
            n_clusters += len(snap.clusters)
            n_noise += len(snap.noise_source_ids)
            gps_counter.update(snap.source_gps_quality.values())

            support_groups: dict[str, int] = {}
            for support_id in snap.source_core_support_id.values():
                if support_id is None:
                    continue
                support_groups[support_id] = support_groups.get(support_id, 0) + 1
            origin_collapse = sum(1 for count in support_groups.values() if count > 1)
            collapse_count += origin_collapse

            micro_usable += len(snap.cluster_usable_source_ids)
            micro_temporal_unusable += len(snap.temporal_unusable_source_ids)
            micro_clusters += len(snap.clusters)
            micro_noise += len(snap.noise_source_ids)
            for c in snap.clusters:
                micro_cluster_sizes.append(c["member_count"])
            micro_gps_counter.update(snap.source_gps_quality.values())
            micro_collapse += origin_collapse

        noise_fraction = (n_noise / n_usable_appearances) if n_usable_appearances > 0 else None
        macro_slices.append(
            CountrySensitivitySlice(
                country=country,
                n_origins_evaluated=len(origins),
                n_usable_source_appearances=n_usable_appearances,
                n_unique_source_ids=len(unique_source_ids),
                n_clusters_total=n_clusters,
                n_noise_total=n_noise,
                noise_fraction=noise_fraction,
                gps_quality_composition=dict(gps_counter),
                approximate_support_collapse_count=collapse_count,
            )
        )

    micro_cluster_sizes.sort()
    micro_noise_fraction = (micro_noise / micro_usable) if micro_usable > 0 else None
    micro_summary = {
        "n_usable_sources_total": micro_usable,
        "n_temporal_unusable_total": micro_temporal_unusable,
        "n_clusters_total": micro_clusters,
        "n_noise_total": micro_noise,
        "noise_fraction": micro_noise_fraction,
        "cluster_size_distribution": micro_cluster_sizes,
        "gps_quality_composition": dict(micro_gps_counter),
        "approximate_support_collapse_count": micro_collapse,
    }

    return InternationalDevelopmentSensitivityReport(
        scope_label=SCOPE_LABEL,
        config_hash=config.config_hash(),
        config=config.config_dict(),
        n_origins_evaluated=len(fit_development_origins),
        n_countries=len(by_country),
        micro_summary=micro_summary,
        macro_country_summary=[s.as_dict() for s in macro_slices],
    )

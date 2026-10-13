"""Checkpoint 7C Part 16: paired improvement over the frozen C0/B0
anchor, matched on FORECAST ORIGIN, with a paired clustered bootstrap
over origins -- never over grid cells (Part 16 explicit instruction).

A candidate's per-origin summary and C0's per-origin summary already
share the identical `within_targets` set for a given origin (both are
scored against exactly the same real WITHIN-scope targets at that
origin -- `development_run_7c._evaluate_validation_origin_7c` scores
every registered candidate against the same target list). Matching is
therefore on ORIGIN alone: an origin contributes a paired delta only
when BOTH the anchor and the candidate produced a real per-origin
summary there (a wind candidate missing real wind at an origin
contributes no summary there at all, per `summarize_by_cluster`'s own
`None`-percentile skip -- never a fabricated zero delta).
"""

from __future__ import annotations

import random


def compute_paired_delta_vs_anchor(*, anchor_summaries: tuple, candidate_summaries: tuple) -> dict:
    anchor_by_key = {s.cluster_key: s for s in anchor_summaries}
    candidate_by_key = {s.cluster_key: s for s in candidate_summaries}
    matched_keys = sorted(set(anchor_by_key) & set(candidate_by_key))
    n = len(matched_keys)
    if n == 0:
        return {
            "n_matched_origins": 0, "delta_mean_target_percentile_vs_anchor": None,
            "delta_top10_vs_anchor": None, "delta_top5_vs_anchor": None, "per_origin_percentile_deltas": [],
        }
    deltas_pct = [candidate_by_key[k].mean_target_percentile - anchor_by_key[k].mean_target_percentile for k in matched_keys]
    deltas_top5 = [candidate_by_key[k].top5_capture_rate - anchor_by_key[k].top5_capture_rate for k in matched_keys]
    deltas_top10 = [candidate_by_key[k].top10_capture_rate - anchor_by_key[k].top10_capture_rate for k in matched_keys]
    return {
        "n_matched_origins": n,
        "delta_mean_target_percentile_vs_anchor": sum(deltas_pct) / n,
        "delta_top10_vs_anchor": sum(deltas_top10) / n,
        "delta_top5_vs_anchor": sum(deltas_top5) / n,
        "per_origin_percentile_deltas": deltas_pct,
    }


def paired_bootstrap_ci(delta_values: list, *, n_resamples: int = 1000, seed: int = 42, confidence: float = 0.95) -> dict:
    """Resamples whole ORIGINS' paired deltas with replacement -- never
    grid cells (Part 16). Same fixed-seed/percentile-CI convention as
    `selection_7b.clustered_bootstrap_ci`."""
    n = len(delta_values)
    if n == 0:
        return {"n_clusters": 0, "n_resamples": n_resamples, "seed": seed, "confidence": confidence, "delta_mean_target_percentile_ci": None}
    rng = random.Random(seed)
    boot = []
    for _ in range(n_resamples):
        sample = [delta_values[rng.randrange(n)] for _ in range(n)]
        boot.append(sum(sample) / n)
    s = sorted(boot)
    alpha = (1.0 - confidence) / 2.0
    lo = s[max(0, int(alpha * len(s)))]
    hi = s[min(len(s) - 1, int((1.0 - alpha) * len(s)) - 1)]
    return {
        "n_clusters": n, "n_resamples": n_resamples, "seed": seed, "confidence": confidence,
        "delta_mean_target_percentile_ci": {"lower": lo, "upper": hi},
    }

"""Checkpoint 7B Parts 20, 22-27, 30: unique-target aggregation, origin
balancing, the frozen primary selection rule, and clustered-bootstrap
uncertainty.

Grid cells are never an independent-sample denominator (Part 21) -- the
inferential/predictive unit is the forecast task (one target event, seen
from one forecast origin). `summarize_by_cluster` groups already-unique
per-target records (one row per `forecast_origin_id`+`target_event_id`,
Part 22) by a cluster key -- ORIGIN for the primary equal-origin rule
(Part 23), `target_event_id` only for the Part 27 dependence-sensitivity
diagnostic, never used to change the primary selection rule itself.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

PRIMARY_SELECTION_METRIC = "MEAN_ORIGIN_BALANCED_AREA_WEIGHTED_TARGET_PERCENTILE"
SELECTION_PROTOCOL_VERSION = "7B.1"
FOLD_AGGREGATION_RULE = "EQUAL_VALIDATION_ORIGIN_WEIGHTING_ACROSS_FOLDS"
TIE_BREAK_ORDER = ("TOP10_CAPTURE", "TOP5_CAPTURE", "CANDIDATE_ID_LEXICAL_ORDER")
FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION = "FROZEN_AFTER_FIT_DEVELOPMENT_SELECTION"


@dataclass(frozen=True)
class ClusterSummary:
    cluster_key: str
    n_evaluable_targets: int
    mean_target_percentile: float
    top5_capture_rate: float
    top10_capture_rate: float


def summarize_by_cluster(records: list, *, cluster_key_fn) -> tuple[ClusterSummary, ...]:
    """`records`: `TargetEvaluationRecord`-shaped objects/dicts exposing
    `.area_weighted_target_percentile`/`.top5_capture`/`.top10_capture` (or
    dict-key equivalents via `cluster_key_fn`'s own record access -- callers
    pass plain objects here). Only records with a real (non-`None`)
    percentile contribute (UNIT7B-01/02: duplicate ledger rows were already
    collapsed to one row per origin/target_event_id upstream; this function
    itself groups by cluster key, so a duplicate row here would ALSO
    silently double-count -- callers must ensure uniqueness before calling)."""
    buckets: dict[str, list] = {}
    for r in records:
        if r.area_weighted_target_percentile is None:
            continue
        buckets.setdefault(cluster_key_fn(r), []).append(r)
    summaries = []
    for key, rows in buckets.items():
        n = len(rows)
        summaries.append(ClusterSummary(
            cluster_key=key, n_evaluable_targets=n,
            mean_target_percentile=sum(r.area_weighted_target_percentile for r in rows) / n,
            top5_capture_rate=sum(1 for r in rows if r.top5_capture) / n,
            top10_capture_rate=sum(1 for r in rows if r.top10_capture) / n,
        ))
    return tuple(sorted(summaries, key=lambda s: s.cluster_key))


def fold_origin_balanced_metrics(origin_summaries: tuple) -> dict:
    """(Part 23) equal weight per ORIGIN within one fold -- an origin with
    20 targets never outweighs an origin with 1 (UNIT7B-03/04)."""
    n = len(origin_summaries)
    if n == 0:
        return {"n_origins": 0, "mean_target_percentile": None, "top5_capture_rate": None, "top10_capture_rate": None}
    return {
        "n_origins": n,
        "mean_target_percentile": sum(o.mean_target_percentile for o in origin_summaries) / n,
        "top5_capture_rate": sum(o.top5_capture_rate for o in origin_summaries) / n,
        "top10_capture_rate": sum(o.top10_capture_rate for o in origin_summaries) / n,
    }


def overall_equal_origin_weighted(fold_metrics: list) -> dict:
    """(Part 25 step 2) `FOLD_AGGREGATION_RULE`: every validation ORIGIN
    counts equally in the overall figure regardless of which fold (or how
    many origins that fold had) it came from -- a weighted average of each
    fold's origin-balanced mean, weighted by that fold's own origin count,
    never a plain equal-weight-per-fold average."""
    total_origins = sum(fm["n_origins"] for fm in fold_metrics)
    if total_origins == 0:
        return {"n_origins": 0, "mean_target_percentile": None, "top5_capture_rate": None, "top10_capture_rate": None}

    def weighted(key: str) -> float:
        return sum(fm[key] * fm["n_origins"] for fm in fold_metrics if fm["n_origins"] > 0) / total_origins

    return {
        "n_origins": total_origins, "mean_target_percentile": weighted("mean_target_percentile"),
        "top5_capture_rate": weighted("top5_capture_rate"), "top10_capture_rate": weighted("top10_capture_rate"),
    }


def select_candidate(candidate_overall_metrics: dict) -> tuple[str, str]:
    """(Part 25) Highest `PRIMARY_SELECTION_METRIC` wins. Exact-numerical-
    tie tie-breakers ONLY (SELECT7B-03) -- never an invented "approximately
    tied" tolerance: (1) higher origin-balanced TOP_10_PERCENT_CAPTURE, (2)
    higher origin-balanced TOP_5_PERCENT_CAPTURE, (3) candidate_id lexical
    order. Raises if no candidate produced any evaluable validation target
    at all -- never silently picks an arbitrary one."""
    items = [(cid, m) for cid, m in candidate_overall_metrics.items() if m["mean_target_percentile"] is not None]
    if not items:
        raise ValueError("no candidate produced any evaluable validation target -- selection cannot proceed")

    max_metric = max(m["mean_target_percentile"] for _cid, m in items)
    tied = [(cid, m) for cid, m in items if m["mean_target_percentile"] == max_metric]
    if len(tied) == 1:
        return tied[0][0], "UNIQUE_MAXIMUM_PRIMARY_METRIC"

    max_top10 = max(m["top10_capture_rate"] for _cid, m in tied)
    tied = [(cid, m) for cid, m in tied if m["top10_capture_rate"] == max_top10]
    if len(tied) == 1:
        return tied[0][0], "TIE_BROKEN_BY_TOP10_CAPTURE"

    max_top5 = max(m["top5_capture_rate"] for _cid, m in tied)
    tied = [(cid, m) for cid, m in tied if m["top5_capture_rate"] == max_top5]
    if len(tied) == 1:
        return tied[0][0], "TIE_BROKEN_BY_TOP5_CAPTURE"

    return sorted(cid for cid, _m in tied)[0], "TIE_BROKEN_BY_CANDIDATE_ID_LEXICAL_ORDER"


def clustered_bootstrap_ci(*, cluster_summaries: tuple, n_resamples: int = 1000, seed: int = 42, confidence: float = 0.95) -> dict:
    """(Part 26-27) Resamples whole CLUSTERS with replacement (never
    individual grid cells) -- `cluster_summaries` is either the per-origin
    or per-`target_event_id` summary tuple from `summarize_by_cluster`. A
    fixed RNG seed is recorded so the CI is reproducible, never a new
    tuning criterion (uncertainty reporting only)."""
    n = len(cluster_summaries)
    if n == 0:
        return {"n_clusters": 0, "n_resamples": n_resamples, "seed": seed, "confidence": confidence,
                "mean_target_percentile_ci": None, "top5_capture_rate_ci": None, "top10_capture_rate_ci": None}

    rng = random.Random(seed)
    boot_pct, boot_top5, boot_top10 = [], [], []
    for _ in range(n_resamples):
        sample = [cluster_summaries[rng.randrange(n)] for _ in range(n)]
        boot_pct.append(sum(c.mean_target_percentile for c in sample) / n)
        boot_top5.append(sum(c.top5_capture_rate for c in sample) / n)
        boot_top10.append(sum(c.top10_capture_rate for c in sample) / n)

    def _ci(vals: list) -> dict:
        s = sorted(vals)
        alpha = (1.0 - confidence) / 2.0
        lo = s[max(0, int(alpha * len(s)))]
        hi = s[min(len(s) - 1, int((1.0 - alpha) * len(s)) - 1)]
        return {"lower": lo, "upper": hi}

    return {
        "n_clusters": n, "n_resamples": n_resamples, "seed": seed, "confidence": confidence,
        "mean_target_percentile_ci": _ci(boot_pct), "top5_capture_rate_ci": _ci(boot_top5), "top10_capture_rate_ci": _ci(boot_top10),
    }


def selection_protocol_dict() -> dict:
    return {
        "selection_protocol_version": SELECTION_PROTOCOL_VERSION,
        "primary_selection_metric": PRIMARY_SELECTION_METRIC,
        "fold_aggregation_rule": FOLD_AGGREGATION_RULE,
        "tie_break_order": list(TIE_BREAK_ORDER),
        "top5_threshold_percentile": 95.0,
        "top10_threshold_percentile": 90.0,
    }


def selection_protocol_hash() -> str:
    canonical = json.dumps(selection_protocol_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def development_fold_manifest_dict(folds: list) -> dict:
    """`folds`: list of `{fold_id, training_origin_ids, validation_origin_ids, purged_origin_ids}`
    dicts -- never candidate metrics (those change per candidate; the
    manifest hash must describe fold STRUCTURE only)."""
    return {
        "folds": [
            {
                "fold_id": f["fold_id"], "training_origin_ids": sorted(f["training_origin_ids"]),
                "validation_origin_ids": sorted(f["validation_origin_ids"]), "purged_origin_ids": sorted(f["purged_origin_ids"]),
            }
            for f in sorted(folds, key=lambda f: f["fold_id"])
        ]
    }


def development_fold_manifest_hash(folds: list) -> str:
    canonical = json.dumps(development_fold_manifest_dict(folds), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

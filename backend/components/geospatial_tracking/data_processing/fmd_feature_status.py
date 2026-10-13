"""FMD-04 Step 6: explicit missing-data classification for the FMD feature
layer.

The shared `services/geospatial/feature_result.FeatureStatus` enum
(REAL/MISSING/BLOCKED/DEMO) is deliberately coarse — it is the right
granularity for a single adapter call, but FMD-04's spec asks for a finer,
disease-agnostic-reusable taxonomy that separates WHY a value is absent.
This module never widens what an adapter can return; it only classifies
the adapter's own `FeatureResult` (plus, where FMD-04's own orchestration
code short-circuits an adapter call entirely — e.g. a coordinate outside
HydroRIVERS' Asia coverage, or a species with no validated density
adapter at all) into the finer taxonomy.

No status here ever implies a fabricated/imputed value. `SOURCE_VALUE_AVAILABLE`
is the only status that ever carries a non-None `value` — enforced by
`FeatureResult.__post_init__` upstream already; this module adds no new
value-bearing path.
"""

from __future__ import annotations

from ..services.geospatial.feature_result import FeatureResult, FeatureStatus

SOURCE_VALUE_AVAILABLE = "SOURCE_VALUE_AVAILABLE"
SOURCE_VALUE_MISSING = "SOURCE_VALUE_MISSING"
SOURCE_FILE_MISSING = "SOURCE_FILE_MISSING"
OUTSIDE_SOURCE_COVERAGE = "OUTSIDE_SOURCE_COVERAGE"
TEMPORAL_COVERAGE_MISSING = "TEMPORAL_COVERAGE_MISSING"
EXTRACTION_FAILED = "EXTRACTION_FAILED"
FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"

ALL_STATUSES = frozenset(
    {
        SOURCE_VALUE_AVAILABLE,
        SOURCE_VALUE_MISSING,
        SOURCE_FILE_MISSING,
        OUTSIDE_SOURCE_COVERAGE,
        TEMPORAL_COVERAGE_MISSING,
        EXTRACTION_FAILED,
        FEATURE_NOT_AVAILABLE,
    }
)

# Substrings actually observed in this repo's real adapter `quality_notes`
# for a download/local-file failure (fao_glw.py / hydrosheds.py), used only
# to sub-classify an already-BLOCKED FeatureResult more precisely than the
# adapter's own undifferentiated BLOCKED status — never used to change
# REAL/MISSING classification, and defaults conservatively to
# EXTRACTION_FAILED (the safe umbrella) when no such phrase matches.
_FILE_MISSING_PHRASES = ("could not download", "could not read cached")


def classify_feature_availability(result: FeatureResult) -> str:
    """Maps one adapter `FeatureResult` onto the FMD-04 taxonomy. Never
    consulted to change `result.value` — purely a read-side reclassification
    for audit/coverage reporting (Step 8)."""
    if result.status == FeatureStatus.REAL.value:
        return SOURCE_VALUE_AVAILABLE
    if result.status == FeatureStatus.MISSING.value:
        return SOURCE_VALUE_MISSING
    if result.status == FeatureStatus.DEMO.value:
        raise ValueError(
            f"FeatureResult({result.feature_name!r}) is DEMO-status — DEMO must never reach FMD-04 "
            "feature classification (see feature_result.assert_not_demo_for_scientific_use)"
        )
    if result.status == FeatureStatus.BLOCKED.value:
        notes = (result.quality_notes or "").lower()
        if any(phrase in notes for phrase in _FILE_MISSING_PHRASES):
            return SOURCE_FILE_MISSING
        return EXTRACTION_FAILED
    raise ValueError(f"FeatureResult({result.feature_name!r}) has unrecognized status {result.status!r}")


def not_attempted(reason: str) -> str:  # noqa: ARG001 - reason kept for call-site readability/audit text
    """For a feature FMD-04's own orchestration never even attempts to
    extract (no validated adapter exists at all — e.g. swine/sheep/goat
    density, road density) — always `FEATURE_NOT_AVAILABLE`, never
    conflated with a real adapter call that came back MISSING/BLOCKED."""
    return FEATURE_NOT_AVAILABLE


def outside_coverage(reason: str) -> str:  # noqa: ARG001
    """For a feature FMD-04's own orchestration deliberately skips calling
    the adapter for, because the event's own coordinates are known in
    advance to fall outside that source's documented spatial coverage
    (e.g. HydroRIVERS 'as'-region-only vs. an event outside Asia) — saves
    a guaranteed-empty network/file read and reports the correct reason,
    rather than letting it surface as an ordinary SOURCE_VALUE_MISSING."""
    return OUTSIDE_SOURCE_COVERAGE


# ---------------------------------------------------------------------------
# Event-level (not per-feature-value) extraction status, for the full-corpus
# addressability index (`fmd_feature_event_index.csv`). Deliberately a
# SEPARATE, smaller taxonomy from `ALL_STATUSES` above: those classify one
# already-attempted feature VALUE; these two classify whether an EVENT's
# feature row has been produced by `build_fmd_features.py` at all. An event
# with `EXTRACTION_NOT_RUN` may still turn out FEATURE_NOT_AVAILABLE/
# SOURCE_VALUE_MISSING/etc. per-feature once extraction actually runs for
# it — this status carries no claim about what extraction would find, only
# that it has not happened yet (intentionally deferred until FMD-05 freezes
# the final study cohort, not a failure).
# ---------------------------------------------------------------------------

EXTRACTION_NOT_RUN = "EXTRACTION_NOT_RUN"
EXTRACTION_COMPLETE = "EXTRACTION_COMPLETE"

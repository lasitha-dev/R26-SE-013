"""Checkpoint FMD-09: the frozen FMD-08 model identity, promoted to
literal tracked constants -- mirrors `heldout_protocol_7d.py`'s pattern
for LSD's own 7C freeze exactly (Part 2 there: "the exact frozen
selection -- copied from the real, already-persisted outputs, never
recomputed here").

FMD-10B CORRECTED REFREEZE: FMD-10A found and fixed a multi-fold
aggregation defect in the FMD-07B finalizer (`fmd_model_development_7b_finalizer.py`
-- `candidate_aggregates` was keyed by `candidate_id` but the membership
guard checked a `(fold_id, candidate_id)` tuple that could never match,
silently discarding all but the lexically-last fold from every candidate's
aggregate). The corrected, multi-fold-aggregated FMD-07B selection lives
under `local_data/processed/fmd/model_development/fmd10a_corrected_selection/`
and selects a DIFFERENT candidate (GAUSSIAN:100KM, threshold 0.05) than the
original, defective, single-fold selection (EXPONENTIAL:25KM, threshold
0.8, still preserved unchanged as historical PRE_CORRECTION evidence under
the original `fmd07b_*` paths -- never deleted or overwritten). FMD-08 was
then re-run against this corrected candidate only (no candidate search, no
threshold tuning, no held-out fitting) under
`local_data/processed/fmd/model_evaluation/fmd10b_corrected_heldout/`; that
run is protocol-valid and these constants are promoted from it.

Copied verbatim from the real, already-persisted
`local_data/processed/fmd/model_development/fmd10a_corrected_selection/fmd07b_frozen_model_spec.json`
and `local_data/processed/fmd/model_evaluation/fmd10b_corrected_heldout/fmd08_manifest.json`
(gitignored evaluation evidence, re-verified against these literals by
`test_checkpoint_fmd09_api_integration.py`'s freeze test, never against
values recomputed at request time). The API runtime path
(`frozen_fmd_risk_analysis_9.py`) imports these constants directly --
it never re-reads `local_data` on a live request, matching the router's
own no-request-time-artifact-read invariant
(`GEOSPATIAL_API_PROTOCOL.md` Part 4 / 10A-FIREWALL-01) that the
LSD path already honors.
"""

from __future__ import annotations

CHECKPOINT_FMD_09 = "FMD-09"

SELECTED_CANDIDATE_ID_FMD09 = "FMD07B:SPATIAL:B0_DISTANCE_ONLY:GAUSSIAN:100KM:NONE:2de049cf8eefe775"
FROZEN_THRESHOLD_FMD09 = 0.05
FROZEN_MODEL_SPEC_SHA256_FMD09 = "782ff86278a1a8899cf0f42f1aa910ddd993cc5621d12266a734e6349e8bc8f8"

# FMD-10A corrected development-selection provenance (context only -- FMD-09
# performs no selection of its own and never recomputes these).
FMD10A_CORRECTED_MANIFEST_SHA256 = "49999afbf9dff87f84fffb668aca8de04af52e738250af6a981533e14c5a1f0a"
FMD10A_CORRECTED_SELECTION_SUMMARY_SHA256 = "ec27df4679dd8ecc82c7017cac97269117b07b6049a74ff6ec6e19f8e136ea2e"

# FMD-08 locked held-out evaluation provenance (context only -- FMD-09
# performs no evaluation of its own and never recomputes these). This is the
# FMD-10B CORRECTED locked held-out run (541 cohort, 501 scored, 40
# unavailable -- structurally identical cohort to the pre-correction run,
# re-scored only against the corrected candidate above).
HELD_OUT_COHORT_COUNT_FMD08 = 541
HELD_OUT_SCORED_COUNT_FMD08 = 501
HELD_OUT_UNAVAILABLE_COUNT_FMD08 = 40
HELD_OUT_PREDICTIONS_SHA256_FMD08 = "783dbd1d2eb2bbc2526fb3cdc7672df2fd497b8ba7868fcd59ad4341dc4a868c"

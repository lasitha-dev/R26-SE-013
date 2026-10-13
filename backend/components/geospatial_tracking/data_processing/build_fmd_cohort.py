"""FMD-05: study-cohort / forecast-origin / model-fitting-exposure freeze.

Builds, from the frozen FMD-03D canonical corpus alone (no environmental/
host feature is read or written here, no ML model is fit, no ST-DBSCAN
parameter is calibrated), reusing the SAME generic, disease-parameterized
services already frozen for LSD (`forecast_origin.py`, `forecast_target.py`,
`model_fitting_exposure.py`) via `fmd_forecast_bridge.py`:

    <out_dir>/fmd_historical_forecast_origins.csv
    <out_dir>/fmd_historical_forecast_targets.csv
    <out_dir>/fmd_model_fitting_exposure_manifest.csv
    <out_dir>/fmd_calendar_year_folds.json
    <out_dir>/FMD_COHORT_AUDIT.csv
    <out_dir>/FMD_COHORT_MANIFEST.json

Only READS `fmd_canonical_outbreaks_conservative.csv`; never writes to it.
Uses a throwaway, disposable SQLite file (deleted at the end of `run()`)
purely to exercise the repository-shaped generic pipeline — never the
shared LSD dev database (`config.DEFAULT_SQLITE_DB_PATH`), so this can
never race with or mutate any LSD state.

Run locally (never in CI — local_data/ is gitignored, same convention as
`build_fmd_canonical.py` / `build_historical_replay.py`):

    cd backend
    python -m components.geospatial_tracking.data_processing.build_fmd_cohort \\
        ../local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv \\
        ../local_data/processed/fmd/cohort
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from ..repositories.sqlite_repository import SQLiteOutbreakRepository
from ..services.forecast_origin import build_forecast_origin_ledger
from ..services.forecast_target import PRIMARY_HORIZON_DAYS, build_forecast_targets
from ..services.model_fitting_exposure import (
    MODEL_FITTING_CUTOFF as _LSD_MODEL_FITTING_CUTOFF,
    build_calendar_year_folds,
    build_model_fitting_exposure_manifest,
)
from .fmd_forecast_bridge import import_fmd_canonical_csv

FMD_DISEASE = "Foot and mouth disease"

FMD_MODEL_FITTING_CUTOFF = "2026-01-01"
"""FROZEN (FMD-05, re-confirmed at the ORIGIN level in FMD-05R) --
derived from FMD's OWN chronology, never copied from LSD's
`services.model_fitting_exposure.MODEL_FITTING_CUTOFF` literal (imported
above only so a test can assert the two are independent values).

The PRIMARY modelling unit is the FORECAST ORIGIN (`FMD_STUDY_PROTOCOL.md`
§4), so the split must be justified at the origin level, not the
canonical-EVENT level: event-level counts (2002-2025 = 6,819 of 9,311
events, 73.2%; 2026 alone = 2,492, 26.8%) OVERSTATE the held-out
fraction, because 2026's held-out countries (South Africa above all)
have unusually HIGH same-country/same-day trigger multiplicity, so many
2026 events collapse into comparatively few origins. The correct,
ORIGIN-level split (FMD-05R, `forecast_origin_role_counts`, non-Sri-Lanka
origins only): 3,761 `FIT_DEVELOPMENT` / 541 `HELD_OUT_FROM_MODEL_FITTING`
of 4,302 (87.4% / 12.6%). 12.6% is smaller than the event-level figure
suggested, but 541 origins across 19 countries remains a materially
sized, purely-future, multi-country evaluation block -- the cutoff is
RECONFIRMED, not moved, because moving it now to chase a larger
percentage would itself be the exact outcome-driven leakage this freeze
exists to prevent. See FMD_SPLIT_PROTOCOL.md for the full event-level
vs. origin-level evidence table."""

assert FMD_MODEL_FITTING_CUTOFF != _LSD_MODEL_FITTING_CUTOFF, (
    "FMD_MODEL_FITTING_CUTOFF must be independently derived from FMD's own chronology, "
    "never silently inherited from LSD's frozen cutoff"
)

COHORT_INCLUDED = "INCLUDED"

ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0 = "ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0"
TRIGGER_SOURCES_ONLY = "TRIGGER_SOURCES_ONLY"

SPATIAL_TARGET_REFERENCE_SOURCE_SET = ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0
"""FROZEN (FMD-05R) -- resolves an ambiguity FMD-05 left implicit: when a
future spatial-domain radius is eventually applied (FMD-06+, no radius is
selected here), is a D1-D7 target's distance measured against the
origin's own NEW `trigger_source_ids_at_t0` only (`TRIGGER_SOURCES_ONLY`),
or against every source that is ELIGIBLE and ACTIVE at `t0` under
whatever `active_window_days` FMD-06 later freezes
(`ALL_ELIGIBLE_ACTIVE_SOURCES_AT_T0`)?

Resolved by the only already-implemented spatial-scope classifier in
this repository, `services/model_development/local_evaluation_scope.py`
(`classify_target_primary_scope`) -- disease-agnostic, reused unchanged,
never re-implemented for FMD: its own docstring defines PRIMARY SCOPE
TRUTH as `min(WGS84 geodesic distance(source, target) for every eligible
active source)`, and its parameter is typed `sources:
list[EligibleSourcePoint]` -- the ALREADY-ELIGIBLE-AND-ACTIVE set (i.e.
`services.source_selector.get_eligible_sources`'s output, matching a
`services.forecast_origin.build_source_snapshot` call), never a
`trigger_source_ids_at_t0`-only subset. Freezing FMD to the SAME
reference-set concept reuses this existing, tested, disease-agnostic
architecture rather than inventing a second, FMD-only spatial-scope
mechanism.

This freezes WHICH SOURCE SET the eventual distance is measured against
-- it does NOT select `active_window_days` (still
`UNFROZEN_DEVELOPMENT_PARAMETER`) or any spatial radius (still
predeclared-candidates-only, `FMD_TARGET_PROTOCOL.md` §3). No source
snapshot or spatial-scope classification is actually computed anywhere
in FMD-05/FMD-05R."""


def _read_canonical_rows(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_cohort_rows(
    canonical_rows: list[dict],
    *,
    origin_by_source_id: dict[str, str],
    role_by_origin_id: dict[str, str],
) -> list[dict]:
    """One row per canonical FMD event (all 9,526 -- nothing dropped).
    `cohort_disposition` is `INCLUDED` for every `modelling_eligible=True`
    event, else `EXCLUDED_<eligibility_reason>` using FMD-03's own,
    already-computed, fixed-priority-order reason code
    (`fmd_eligibility.py`) -- never a second, independently-invented
    exclusion taxonomy.

    `containing_origin_model_fitting_role` is populated only for INCLUDED
    events (every one of which is a trigger candidate for exactly one
    forecast origin, by construction of
    `services.forecast_origin.build_forecast_origin_ledger`) and is the
    role of the ORIGIN this event triggers -- deliberately NOT named
    "model_fitting_role" or similar, to avoid the FMD-05R-discovered
    defect where an event-level column got silently read as an
    origin-level count downstream (see `run()`'s
    `included_source_event_role_counts` vs. `forecast_origin_role_counts`
    -- the two units must never be confused: an origin with N same-
    country/same-day trigger events contributes N rows here but is
    counted exactly ONCE in `forecast_origin_role_counts`)."""
    rows: list[dict] = []
    for row in canonical_rows:
        eligible = row["modelling_eligible"] == "True"
        disposition = COHORT_INCLUDED if eligible else f"EXCLUDED_{row['eligibility_reason']}"
        origin_id = origin_by_source_id.get(row["source_record_id"], "")
        role = role_by_origin_id.get(origin_id, "") if origin_id else ""
        rows.append(
            {
                "fmd_canonical_event_id": row["fmd_canonical_event_id"],
                "source_record_id": row["source_record_id"],
                "country": row["country"],
                "onset_date": row["onset_date"],
                "diagnosis_status": row["diagnosis_status"],
                "modelling_eligible": row["modelling_eligible"],
                "eligibility_reason": row["eligibility_reason"],
                "cohort_disposition": disposition,
                "forecast_origin_id": origin_id,
                "containing_origin_model_fitting_role": role,
            }
        )
    return rows


COHORT_AUDIT_FIELDNAMES = [
    "fmd_canonical_event_id",
    "source_record_id",
    "country",
    "onset_date",
    "diagnosis_status",
    "modelling_eligible",
    "eligibility_reason",
    "cohort_disposition",
    "forecast_origin_id",
    "containing_origin_model_fitting_role",
]

ORIGIN_FIELDNAMES = ["forecast_origin_id", "country", "t0", "temporal_mode", "trigger_source_ids_at_t0", "trigger_source_count"]

TARGET_FIELDNAMES = [
    "forecast_origin_id",
    "target_id",
    "target_event_id",
    "historical_event_date",
    "lead_days",
    "latitude",
    "longitude",
    "gps_quality",
    "coordinate_collision_status",
    "risk_target_eligible",
    "direction_target_tier_a_strict",
    "direction_target_tier_a_resolved_only",
    "direction_target_tier_b",
    "speed_target_tier_a_strict",
    "speed_target_tier_a_resolved_only",
    "speed_target_tier_b",
    "speed_eligibility_status",
    "country",
    "disease",
    "dedup_status",
    "model_candidate",
]

EXPOSURE_FIELDNAMES = ["forecast_origin_id", "t0", "country", "role", "purged_by_7_day_rule", "reason"]


def run(conservative_csv_path: str, out_dir: str, *, cutoff: str = FMD_MODEL_FITTING_CUTOFF) -> dict:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    canonical_rows = _read_canonical_rows(conservative_csv_path)

    db_path = out_path / "fmd_cohort_dev.db"
    if db_path.exists():
        db_path.unlink()
    repo = SQLiteOutbreakRepository(db_path)
    try:
        repo.init_schema()
        import_fmd_canonical_csv(repo, conservative_csv_path)

        origins = build_forecast_origin_ledger(repo, disease=FMD_DISEASE)

        origin_by_source_id: dict[str, str] = {}
        for origin in origins:
            for sid in origin.trigger_source_ids_at_t0:
                origin_by_source_id[sid] = origin.forecast_origin_id

        exposure_rows = build_model_fitting_exposure_manifest(origins, cutoff=cutoff)
        role_by_origin_id = {r.forecast_origin_id: r.role for r in exposure_rows}

        all_targets = []
        targets_by_origin_id: dict[str, list] = {}
        for origin in origins:
            targets = build_forecast_targets(repo, origin, disease=FMD_DISEASE)
            targets_by_origin_id[origin.forecast_origin_id] = targets
            all_targets.extend(targets)

        folds = build_calendar_year_folds(origins, cutoff=cutoff)
    finally:
        repo.close()
        if db_path.exists():
            db_path.unlink()

    _write_csv(out_path / "fmd_historical_forecast_origins.csv", [o.as_dict() for o in origins], ORIGIN_FIELDNAMES)
    _write_csv(out_path / "fmd_historical_forecast_targets.csv", [t.as_dict() for t in all_targets], TARGET_FIELDNAMES)
    _write_csv(out_path / "fmd_model_fitting_exposure_manifest.csv", [r.as_dict() for r in exposure_rows], EXPOSURE_FIELDNAMES)
    (out_path / "fmd_calendar_year_folds.json").write_text(
        json.dumps([f.as_dict() for f in folds], indent=2, sort_keys=True), encoding="utf-8"
    )

    cohort_rows = build_cohort_rows(canonical_rows, origin_by_source_id=origin_by_source_id, role_by_origin_id=role_by_origin_id)
    _write_csv(out_path / "FMD_COHORT_AUDIT.csv", cohort_rows, COHORT_AUDIT_FIELDNAMES)

    disposition_counts = Counter(r["cohort_disposition"] for r in cohort_rows)
    countries_with_origins = {o.country for o in origins}

    # FMD-05R FIX: two DIFFERENT units, two DIFFERENT counters -- never conflated.
    # `included_source_event_role_counts` is EVENT-level: one tally per
    # canonical INCLUDED event, using the role of the origin it triggers.
    # Sums to `cohort_disposition_counts["INCLUDED"]` (9,311), NOT to
    # `forecast_origin_count` -- an origin with multiple same-country/
    # same-day trigger events is counted once PER EVENT here.
    included_source_event_role_counts = Counter(
        r["containing_origin_model_fitting_role"] for r in cohort_rows if r["containing_origin_model_fitting_role"]
    )
    # `forecast_origin_role_counts` is ORIGIN-level: exactly one tally per
    # forecast origin (`exposure_rows` has exactly `len(origins)` rows by
    # construction of `build_model_fitting_exposure_manifest`). Sums to
    # `forecast_origin_count`. THIS is the correct denominator for the
    # primary risk task, whose unit of analysis is the forecast origin
    # (`FMD_STUDY_PROTOCOL.md` §4) -- never the event-level counter above.
    forecast_origin_role_counts = Counter(r.role for r in exposure_rows)

    assert sum(forecast_origin_role_counts.values()) == len(origins), (
        f"forecast_origin_role_counts must sum to forecast_origin_count "
        f"({sum(forecast_origin_role_counts.values())} != {len(origins)})"
    )
    assert sum(included_source_event_role_counts.values()) == disposition_counts[COHORT_INCLUDED], (
        f"included_source_event_role_counts must sum to the INCLUDED event count "
        f"({sum(included_source_event_role_counts.values())} != {disposition_counts[COHORT_INCLUDED]})"
    )

    trigger_counts_per_origin = Counter(o.trigger_source_count for o in origins)
    origins_with_exactly_one_trigger = sum(v for k, v in trigger_counts_per_origin.items() if k == 1)
    origins_with_multiple_triggers = sum(v for k, v in trigger_counts_per_origin.items() if k > 1)
    max_trigger_source_count = max((o.trigger_source_count for o in origins), default=0)

    manifest = {
        "disease": FMD_DISEASE,
        "primary_horizon_days": PRIMARY_HORIZON_DAYS,
        "model_fitting_cutoff": cutoff,
        "canonical_event_count": len(canonical_rows),
        "cohort_disposition_counts": dict(sorted(disposition_counts.items())),
        "forecast_origin_count": len(origins),
        "unique_countries_with_origins": len(countries_with_origins),
        "forecast_origin_role_counts": dict(sorted(forecast_origin_role_counts.items())),
        "included_source_event_role_counts": dict(sorted(included_source_event_role_counts.items())),
        "origins_with_exactly_one_trigger_source": origins_with_exactly_one_trigger,
        "origins_with_multiple_trigger_sources": origins_with_multiple_triggers,
        "max_trigger_source_count_at_one_origin": max_trigger_source_count,
        "total_target_rows": len(all_targets),
        "risk_target_eligible_count": sum(1 for t in all_targets if t.risk_target_eligible),
        "direction_tier_a_strict_count": sum(1 for t in all_targets if t.direction_target_tier_a_strict),
        "direction_tier_a_resolved_only_count": sum(1 for t in all_targets if t.direction_target_tier_a_resolved_only),
        "direction_tier_b_count": sum(1 for t in all_targets if t.direction_target_tier_b),
        "origins_with_at_least_one_target": sum(1 for ts in targets_by_origin_id.values() if ts),
        "origins_with_zero_target": sum(1 for ts in targets_by_origin_id.values() if not ts),
        "unique_target_events": len({t.target_event_id for t in all_targets}),
        "calendar_year_fold_count": len(folds),
        "source_canonical_csv_sha256": _sha256_file(conservative_csv_path),
        "cohort_audit_sha256": _sha256_file(out_path / "FMD_COHORT_AUDIT.csv"),
    }
    (out_path / "FMD_COHORT_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def print_summary(manifest: dict) -> None:
    for key, value in manifest.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    args = sys.argv[1:]
    csv_path = args[0] if len(args) > 0 else "../local_data/processed/fmd/fmd_canonical_outbreaks_conservative.csv"
    out_dir = args[1] if len(args) > 1 else "../local_data/processed/fmd/cohort"
    print_summary(run(csv_path, out_dir))

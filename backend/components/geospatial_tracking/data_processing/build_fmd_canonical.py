"""FMD-03C orchestrator: FAO EMPRES-i FMD raw export -> normalize -> dedup ->
FMD status/species policy -> eligibility -> FMD canonical dataset + audits.

Reuses the SAME shared, disease-agnostic pipeline primitives the existing
LSD build (`build_canonical.py`) uses — `normalize.py`, `dedup.py`
(already disease-aware and cross-source-capable, see `disease.py`),
`quality.py`, `model_candidate.py` — via a small, FMD-specific
orchestration module, per the architecture:

    shared generic primitives
            |
            +-- existing LSD build (build_canonical.py, unmodified)
            |
            +-- FMD source adapter (fmd_source_adapter.py)
                  |
                  +-- generic normalize (normalize.py, reused)
                  +-- generic dedup (dedup.py, reused)
                  +-- FMD status policy (fmd_status.py)
                  +-- FMD species-category policy (fmd_species.py)
                  +-- FMD eligibility policy (fmd_eligibility.py)
                  +-- canonical serialization (this module)

Never reads, writes, or touches `local_data/processed/canonical_outbreaks*.csv`
(the LSD outputs) — FMD outputs live entirely under a separate
`local_data/processed/fmd/` directory. Never reads any file outside
`local_data/pistes_raw/fmd/` (the LSD raw files live directly under
`local_data/pistes_raw/`, one directory up, and are never globbed here).

Run locally (never in CI — local_data/ is gitignored):

    cd backend
    python -m components.geospatial_tracking.data_processing.build_fmd_canonical \
        ../local_data/pistes_raw/fmd ../local_data/processed/fmd
"""

from __future__ import annotations

import csv
import hashlib
import sys
from collections import Counter
from datetime import date as _date
from pathlib import Path

from ..schemas import DEDUP_RESOLVED_STATUSES, NORMALIZED_FIELD_NAMES, DedupStatus, NormalizedOutbreakRecord
from .dedup import build_duplicate_groups, find_date_conflicts, parse_date, select_canonical
from .disease import normalize_disease
from .fmd_eligibility import DISTINCT_AUTHORITATIVE_EVENT, evaluate_fmd_eligibility, reason_text
from .fmd_identity import fmd_canonical_event_id
from .fmd_source_adapter import parse_fmd_bigquery_csv
from .fmd_species import build_species_normalization_audit, normalize_species_category
from .fmd_status import classify_diagnosis_status
from .model_candidate import build_conservative_rows
from .normalize import assign_spatial_independence, normalize_raw_records

FMD_DISEASE_KEY = "foot and mouth disease"

# Regional groupings for the FMD-03C audit's coverage breakdown. Deliberately
# NOT the plain UN M49 geoscheme for "Southern Asia" (which places Iran
# there) — this project follows the FMD-epidemiology convention (WRLFMD/OIE
# "FMD virus pool" literature groups Iran with the Middle East/West Eurasia,
# not South Asia's Pool 2) and reports Iran's raw count separately rather
# than silently folding it into either region. Southeast Asia DOES match
# the plain UN M49 "South-eastern Asia" membership.
SOUTH_ASIA_COUNTRIES = frozenset(
    {"Afghanistan", "Bangladesh", "Bhutan", "India", "Maldives", "Nepal", "Pakistan", "Sri Lanka"}
)
SOUTHEAST_ASIA_COUNTRIES = frozenset(
    {
        "Brunei Darussalam",
        "Cambodia",
        "Indonesia",
        "Lao People's Democratic Republic",
        "Malaysia",
        "Myanmar",
        "Philippines",
        "Singapore",
        "Thailand",
        "Timor-Leste",
        "Viet Nam",
    }
)
IRAN_COUNTRY_NAME = "Iran (Islamic Republic of)"

FMD_CANONICAL_EXTRA_COLUMNS = [
    "fmd_canonical_event_id",
    "diagnosis_status",
    "species_normalized_category",
    "species_tokens_normalized",
    "duplicate_group_id",
    "member_record_ids",
    "member_count",
    "dedup_confidence",
    "dedup_status",
    "dedup_resolved",
    "review_required",
    "possible_related_event_group_id",
    "possible_related_event_member_ids",
    "modelling_eligible",
    "eligibility_reason",
]

MODEL_CANDIDATE_COLUMNS = [
    "source_record_id",
    "fmd_canonical_event_id",
    "event_id",
    "country",
    "source_system",
    "diagnosis_status",
    "duplicate_group_id",
    "member_record_ids",
    "member_count",
    "dedup_confidence",
    "dedup_status",
    "dedup_resolved",
    "review_required",
    "model_candidate",
    "possible_related_event_group_id",
    "possible_related_event_member_ids",
    "modelling_eligible",
    "eligibility_reason",
    "date_conflict_ids",
]

EXCLUSION_AUDIT_COLUMNS = [
    "source_record_id",
    "fmd_canonical_event_id",
    "event_id",
    "country",
    "diagnosis_status",
    "dedup_status",
    "eligibility_reason",
    "eligibility_reason_text",
]

GEOCODING_REVIEW_COLUMNS = [
    "source_record_id",
    "event_id",
    "country",
    "locality",
    "latitude",
    "longitude",
    "gps_quality",
    "spatial_independence",
    "coordinate_group_size",
    "review_reason",
]

EVENT_METADATA_COLUMNS = [
    "source_record_id",
    "event_id",
    "fmd_canonical_event_id",
    "locality_label",
    "region_continent",
    "display_date",
    "animal_type_list_raw",
    "reporting_source_institution",
    "humans_affected",
    "human_deaths",
    "species_raw",
    "species_normalized_category",
    "serotype_known",
    "serotype_value",
    "linked_wrlfmd_reference",
]

DEDUP_AUDIT_COLUMNS = [
    "duplicate_group_id",
    "canonical_record_id",
    "member_record_ids",
    "member_count",
    "match_rule",
    "match_features",
    "dedup_confidence",
    "review_required",
    "merged",
    "notes",
]

SOURCE_MANIFEST_COLUMNS = [
    "source_file",
    "source_system",
    "data_class",
    "sha256",
    "raw_record_count",
    "requested_date_range_note",
    "observed_date_range_start",
    "observed_date_range_end",
    "country_coverage_count",
    "diagnosis_status_filter_applied",
    "disease_filter_applied",
    "adapter_module",
    "adapter_version",
    "notes",
]

LAB_SAMPLES_COLUMNS = [
    "sample_id",
    "source_document",
    "matched_fmd_canonical_event_id",
    "serotype",
    "lineage",
    "country",
    "sample_period",
    "linkage_rule",
]

FMD_PARSER_VERSION = "fmd03c-2026-08-23"


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_fmd_normalized_records(raw_fmd_dir: str | Path) -> tuple[list[NormalizedOutbreakRecord], list[Path]]:
    """Parses every `*.csv` directly under `raw_fmd_dir` (never recursive,
    never touching sibling LSD raw files one directory up) via the FMD
    BigQuery-CSV adapter, filters defensively to records that actually
    normalize to FMD (a no-op today — the real export is 100% FMD, verified
    below in `run()`'s stats — but never assumed silently), and returns
    (normalized_records, csv_paths_parsed)."""
    raw_fmd_path = Path(raw_fmd_dir)
    csv_paths = sorted(raw_fmd_path.glob("*.csv"))

    raw_records = []
    for p in csv_paths:
        raw_records.extend(parse_fmd_bigquery_csv(p))

    fmd_only = [r for r in raw_records if normalize_disease(r.disease) == FMD_DISEASE_KEY]

    normalized = normalize_raw_records(fmd_only)
    assign_spatial_independence(normalized)
    return normalized, csv_paths


def build_source_manifest_rows(raw_fmd_dir: str | Path, normalized: list[NormalizedOutbreakRecord]) -> list[dict]:
    raw_fmd_path = Path(raw_fmd_dir)
    csv_paths = sorted(raw_fmd_path.glob("*.csv"))
    pdf_paths = sorted(raw_fmd_path.glob("*.pdf"))

    rows: list[dict] = []
    for p in csv_paths:
        dates = sorted(r.onset_date for r in normalized if r.onset_date)
        countries = {r.country for r in normalized if r.country}
        rows.append(
            {
                "source_file": p.name,
                "source_system": "FAO_EMPRESI_BIGQUERY_CSV",
                "data_class": "PRIMARY_STRUCTURED_EVENT_SOURCE",
                "sha256": _sha256(p),
                "raw_record_count": len(normalized),
                "requested_date_range_note": (
                    "filename indicates a requested range of 2002-2026; the actual BigQuery "
                    "query parameters (exact start_date/end_date/diagnosis_status/animal_type/"
                    "country filters submitted to api.data.apps.fao.org/api/v2/bigquery) are not "
                    "captured by this export and are NOT reconstructed or guessed here — only "
                    "the OBSERVED data range and filter values are reported (see the next columns)"
                ),
                "observed_date_range_start": dates[0] if dates else "",
                "observed_date_range_end": dates[-1] if dates else "",
                "country_coverage_count": len(countries),
                "diagnosis_status_filter_applied": "NONE_OBSERVED (Confirmed, Suspected, and Denied all present in the export)",
                "disease_filter_applied": "Foot and mouth disease only (100% of rows, verified)",
                "adapter_module": "data_processing/fmd_source_adapter.py",
                "adapter_version": FMD_PARSER_VERSION,
                "notes": "FAO EMPRES-i public BigQuery-backed CSV export ('Major diseases (by date)' catalog resource on data.apps.fao.org)",
            }
        )

    for p in pdf_paths:
        # WRLFMD reports: supplementary evidence only, never parsed into
        # epidemiological event rows — see fmd_lab_samples.csv / notes below.
        rows.append(
            {
                "source_file": p.name,
                "source_system": "WRLFMD_PDF_REPORT",
                "data_class": "SUPPLEMENTARY_EVIDENCE",
                "sha256": _sha256(p),
                "raw_record_count": 0,
                "requested_date_range_note": "not applicable (narrative laboratory-network report, not a queried event export)",
                "observed_date_range_start": "",
                "observed_date_range_end": "",
                "country_coverage_count": 0,
                "diagnosis_status_filter_applied": "not applicable",
                "disease_filter_applied": "not applicable",
                "adapter_module": "none (no structured extraction performed this checkpoint — see FMD_DATA_PROVENANCE.md)",
                "adapter_version": "",
                "notes": "WOAH/FAO FMD Reference Laboratory Network report — supplementary serotype/lineage evidence only, never auto-promoted to outbreak events",
            }
        )

    return rows


def build_outbreak_events_raw_rows(normalized: list[NormalizedOutbreakRecord]) -> list[dict]:
    rows: list[dict] = []
    for r in normalized:
        species_result = normalize_species_category(r.species)
        row = r.as_dict()
        row.update(
            fmd_canonical_event_id=fmd_canonical_event_id(r.event_id),
            diagnosis_status=classify_diagnosis_status(r.diagnostic_result),
            species_normalized_category=species_result.species_normalized_category,
            species_tokens_normalized=species_result.species_tokens_normalized,
        )
        rows.append(row)
    return rows


def _fmd_status_aware_canonical_id(
    group_member_ids: list[str], by_id: dict[str, NormalizedOutbreakRecord]
) -> str:
    """`dedup.select_canonical` (shared with LSD, correctly status-agnostic
    there — LSD has no diagnosis-status concept at all) picks a merged
    group's canonical representative purely by field-completeness/source-
    richness, with no awareness of FMD's CONFIRMED/SUSPECTED/DENIED status.
    That can pick a SUSPECTED or DENIED member as canonical over a CONFIRMED
    sibling in the same HIGH-confidence group (observed in the real 2002-2026
    export: 2 of 1207 groups) — which would wrongly report a genuinely
    Confirmed event as STATUS_NOT_CONFIRMED just because a differently-typed
    sibling happened to be more "complete".

    This FMD-only correction restricts the pool to CONFIRMED members first
    (reusing dedup.py's own, unmodified tie-break ranking on that restricted
    pool) whenever at least one CONFIRMED member exists in the group, falling
    back to the group's original pick when none do (a non-Confirmed group's
    representative doesn't affect eligibility either way). dedup.py's shared
    `select_canonical` function itself is not modified — LSD's behavior is
    unaffected.
    """
    confirmed_members = [
        by_id[mid] for mid in group_member_ids if classify_diagnosis_status(by_id[mid].diagnostic_result) == "CONFIRMED"
    ]
    if confirmed_members:
        return select_canonical(confirmed_members)
    return select_canonical([by_id[mid] for mid in group_member_ids])


def _group_source_systems(group_member_ids: list[str], by_id: dict[str, NormalizedOutbreakRecord]) -> set[str]:
    return {by_id[mid].source_system for mid in group_member_ids}


def _is_trusted_identifier_group(group) -> bool:
    """True only for a group Level 1 (`dedup.match_pair`'s trusted-identifier
    path) actually matched — i.e. the SAME authoritative identifier
    (`outbreak_id`), which for the FMD BigQuery adapter is never populated
    (only `event_id`/`global_id` is), so this is always False for the real
    2002-2026 export. Kept for correctness/future-proofing: if a future FMD
    source ever populates a trusted, comparable identifier, a Level-1 match
    is genuine Case A (same event, two representations) and should still
    auto-merge, not be split apart by the guard below."""
    return "LEVEL_1_TRUSTED_IDENTIFIER" in group.match_rule


def classify_group_disposition(group, by_id: dict[str, NormalizedOutbreakRecord]) -> str:
    """FMD-03D same-source authoritative-event-identity guard.

    `global_id` is EMPRES-i's own authoritative per-event identifier for
    this source (0 duplicates verified across the real 2002-2026 export).
    `dedup.build_duplicate_groups` (shared with LSD, NOT modified here) can
    still group two records from the SAME source_system with DIFFERENT,
    non-empty `global_id` values purely on Level 2/3 spatiotemporal
    evidence (locality/date/coordinate/species similarity) — that evidence
    describes a POSSIBLE epidemiologically-related event (worth surfacing
    for later ST-DBSCAN/outbreak-chain analysis), never proof that the two
    authoritative EMPRES-i records are the same event. Silently collapsing
    such a group into one canonical row (as the generic LSD-shared
    Checkpoint-2.5 HIGH-auto-merge policy would) would erase a real,
    distinctly-identified EMPRES-i event with no authoritative evidence to
    justify it — confirmed as a real defect in the real corpus (264 HIGH
    groups, all `LEVEL_2_FULL_EVIDENCE`, none `LEVEL_1_TRUSTED_IDENTIFIER`,
    collapsing 344 raw rows before this guard existed).

    Returns one of:
      "TRUSTED_IDENTIFIER_MERGE" — Level 1 fired (same authoritative ID,
          Case A) — a genuine merge, handled via the existing
          status-aware-canonical-selection path below.
      "CROSS_SOURCE_GENERIC_POLICY" — group spans more than one
          source_system (Case D) — cross-source consolidation is left to
          the existing, unmodified, already-tested LSD Checkpoint-2.5
          policy (`model_candidate.build_conservative_rows`); does not fire
          on the real FMD corpus today (0 cross-source groups exist), kept
          unchanged for when/if a second FMD source is added.
      "SAME_SOURCE_DISTINCT_IDENTITY" — Case B: same source_system, no
          trusted-identifier match — every member is preserved as ITS OWN
          distinct canonical event; the fuzzy relationship is retained only
          as an auditable `possible_related_event_group_id` annotation,
          never used to merge or to block eligibility.
    """
    if _is_trusted_identifier_group(group):
        return "TRUSTED_IDENTIFIER_MERGE"
    if len(_group_source_systems(group.member_record_ids, by_id)) > 1:
        return "CROSS_SOURCE_GENERIC_POLICY"
    return "SAME_SOURCE_DISTINCT_IDENTITY"


def _build_distinct_authoritative_event_row(
    record: NormalizedOutbreakRecord,
    *,
    possible_related_event_group_id: str,
    possible_related_event_member_ids: str,
) -> dict:
    species_result = normalize_species_category(record.species)
    diagnosis_status = classify_diagnosis_status(record.diagnostic_result)
    eligibility = evaluate_fmd_eligibility(
        record,
        raw_diagnosis_status=record.diagnostic_result,
        dedup_status=DISTINCT_AUTHORITATIVE_EVENT,
    )
    row = record.as_dict()
    row.update(
        fmd_canonical_event_id=fmd_canonical_event_id(record.event_id),
        diagnosis_status=diagnosis_status,
        species_normalized_category=species_result.species_normalized_category,
        species_tokens_normalized=species_result.species_tokens_normalized,
        duplicate_group_id="",
        member_record_ids=record.source_record_id,
        member_count=1,
        dedup_confidence="",
        dedup_status=DISTINCT_AUTHORITATIVE_EVENT,
        dedup_resolved=True,
        review_required=False,
        possible_related_event_group_id=possible_related_event_group_id,
        possible_related_event_member_ids=possible_related_event_member_ids,
        modelling_eligible=eligibility.modelling_eligible,
        eligibility_reason=eligibility.eligibility_reason,
    )
    return row


def _append_distinct_authoritative_event(
    record: NormalizedOutbreakRecord,
    *,
    possible_related_event_group_id: str,
    possible_related_event_member_ids: str,
    conservative_rows: list[dict],
    candidate_rows: list[dict],
) -> None:
    row = _build_distinct_authoritative_event_row(
        record,
        possible_related_event_group_id=possible_related_event_group_id,
        possible_related_event_member_ids=possible_related_event_member_ids,
    )
    conservative_rows.append(row)
    candidate_rows.append(
        {
            "source_record_id": row["source_record_id"],
            "fmd_canonical_event_id": row["fmd_canonical_event_id"],
            "event_id": row["event_id"],
            "country": row["country"],
            "source_system": row["source_system"],
            "diagnosis_status": row["diagnosis_status"],
            "duplicate_group_id": row["duplicate_group_id"],
            "member_record_ids": row["member_record_ids"],
            "member_count": row["member_count"],
            "dedup_confidence": row["dedup_confidence"],
            "dedup_status": row["dedup_status"],
            "dedup_resolved": row["dedup_resolved"],
            "review_required": row["review_required"],
            "model_candidate": True,  # dedup-resolved (DISTINCT_AUTHORITATIVE_EVENT) regardless of status/date/coordinate eligibility
            "possible_related_event_group_id": row["possible_related_event_group_id"],
            "possible_related_event_member_ids": row["possible_related_event_member_ids"],
            "modelling_eligible": row["modelling_eligible"],
            "eligibility_reason": row["eligibility_reason"],
            "date_conflict_ids": "",
        }
    )


def build_conservative_and_candidate_rows(
    normalized: list[NormalizedOutbreakRecord],
) -> tuple[list[dict], list[dict], list]:
    """Returns (fmd_conservative_rows, model_candidate_rows, duplicate_groups).

    `fmd_conservative_rows` mirrors the LSD `canonical_outbreaks_conservative.csv`
    convention (one row per resolved dedup unit, EVERY diagnosis_status
    included — Suspected/Denied are never silently dropped) but adds the
    FMD-specific `modelling_eligible`/`eligibility_reason` columns so the
    primary positive corpus can be derived by filtering, not by deleting.

    `groups` (from `dedup.build_duplicate_groups`, unmodified/shared) is
    classified per `classify_group_disposition` before deciding how to
    serialize each group — see that function's docstring for the
    same-source authoritative-event-identity guard this implements.

    A SECOND same-source guard applies to `dedup.find_date_conflicts`'s
    separate "near-miss" side channel (`model_candidate.py`'s REVIEW_LOW
    date-conflict path for records with NO formal duplicate_group at all —
    designed for LSD's cross-source chronology-divergence case). When every
    one of a record's flagged date-conflict partners shares its own
    source_system, the same reasoning applies: distinct authoritative
    `global_id`s, not an unresolved duplicate.
    """
    groups = build_duplicate_groups(normalized)
    base_conservative_rows = build_conservative_rows(normalized, groups)
    date_conflicts = find_date_conflicts(normalized)

    by_source_record_id = {r.source_record_id: r for r in normalized}
    group_by_member_id: dict[str, object] = {}
    for g in groups:
        for mid in g.member_record_ids:
            group_by_member_id[mid] = g

    conservative_rows: list[dict] = []
    candidate_rows: list[dict] = []
    guarded_member_ids: set[str] = set()

    # Pass 1: same-source distinct-identity groups (Case B) — bypass the
    # generic base_conservative_rows entirely; every member becomes its own
    # row, never merged, never DUPLICATE_UNRESOLVED.
    for g in groups:
        if classify_group_disposition(g, by_source_record_id) != "SAME_SOURCE_DISTINCT_IDENTITY":
            continue
        for mid in g.member_record_ids:
            record = by_source_record_id[mid]
            _append_distinct_authoritative_event(
                record,
                possible_related_event_group_id=g.duplicate_group_id,
                possible_related_event_member_ids=";".join(g.member_record_ids),
                conservative_rows=conservative_rows,
                candidate_rows=candidate_rows,
            )
            guarded_member_ids.add(mid)

    # Pass 2: everything else (true singletons, TRUSTED_IDENTIFIER_MERGE
    # groups, CROSS_SOURCE_GENERIC_POLICY groups, and the date-conflict
    # side channel) — the existing, unmodified generic Checkpoint-2.5
    # policy, with the FMD status-aware canonical-selection correction
    # still applied to real merges, and the same-source guard also applied
    # to same-source-only date-conflict flags.
    for crow in base_conservative_rows:
        member_ids = crow["member_record_ids"].split(";")
        if any(mid in guarded_member_ids for mid in member_ids):
            continue

        if crow["duplicate_group_id"] == "" and crow["dedup_status"] == DedupStatus.REVIEW_LOW.value:
            # Only reachable via the date-conflict side channel (no formal
            # duplicate_group_id exists at all for this record) — check
            # whether every flagged conflict partner shares this record's
            # own source_system.
            record = by_source_record_id[crow["source_record_id"]]
            conflicts = date_conflicts.get(record.source_record_id, [])
            partner_ids = [c.b_id for c in conflicts]
            partner_source_systems = {by_source_record_id[pid].source_system for pid in partner_ids}
            if partner_source_systems and partner_source_systems <= {record.source_system}:
                _append_distinct_authoritative_event(
                    record,
                    possible_related_event_group_id="",
                    possible_related_event_member_ids=";".join([record.source_record_id] + partner_ids),
                    conservative_rows=conservative_rows,
                    candidate_rows=candidate_rows,
                )
                guarded_member_ids.add(record.source_record_id)
                continue

        if crow["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value:
            group = group_by_member_id[crow["source_record_id"]]
            fmd_canonical_id = _fmd_status_aware_canonical_id(group.member_record_ids, by_source_record_id)
            canonical_record = by_source_record_id[fmd_canonical_id]
        else:
            canonical_record = by_source_record_id[crow["source_record_id"]]
        species_result = normalize_species_category(canonical_record.species)
        diagnosis_status = classify_diagnosis_status(canonical_record.diagnostic_result)
        eligibility = evaluate_fmd_eligibility(
            canonical_record,
            raw_diagnosis_status=canonical_record.diagnostic_result,
            dedup_status=crow["dedup_status"],
        )

        row = canonical_record.as_dict()
        row.update(
            fmd_canonical_event_id=fmd_canonical_event_id(canonical_record.event_id),
            diagnosis_status=diagnosis_status,
            species_normalized_category=species_result.species_normalized_category,
            species_tokens_normalized=species_result.species_tokens_normalized,
            duplicate_group_id=crow["duplicate_group_id"],
            member_record_ids=crow["member_record_ids"],
            member_count=crow["member_count"],
            dedup_confidence=crow["dedup_confidence"],
            dedup_status=crow["dedup_status"],
            dedup_resolved=crow["dedup_resolved"],
            review_required=crow["review_required"],
            possible_related_event_group_id="",
            possible_related_event_member_ids="",
            modelling_eligible=eligibility.modelling_eligible,
            eligibility_reason=eligibility.eligibility_reason,
        )
        conservative_rows.append(row)

        candidate_rows.append(
            {
                "source_record_id": canonical_record.source_record_id,
                "fmd_canonical_event_id": fmd_canonical_event_id(canonical_record.event_id),
                "event_id": canonical_record.event_id,
                "country": crow["country"],
                "source_system": crow["source_system"],
                "diagnosis_status": diagnosis_status,
                "duplicate_group_id": crow["duplicate_group_id"],
                "member_record_ids": crow["member_record_ids"],
                "member_count": crow["member_count"],
                "dedup_confidence": crow["dedup_confidence"],
                "dedup_status": crow["dedup_status"],
                "dedup_resolved": crow["dedup_resolved"],
                "review_required": crow["review_required"],
                "model_candidate": crow["model_candidate"],
                "possible_related_event_group_id": "",
                "possible_related_event_member_ids": "",
                "modelling_eligible": eligibility.modelling_eligible,
                "eligibility_reason": eligibility.eligibility_reason,
                "date_conflict_ids": crow["date_conflict_ids"],
            }
        )

    return conservative_rows, candidate_rows, groups


def build_exclusion_audit_rows(candidate_rows: list[dict]) -> list[dict]:
    return [
        {
            "source_record_id": r["source_record_id"],
            "fmd_canonical_event_id": r["fmd_canonical_event_id"],
            "event_id": r["event_id"],
            "country": r["country"],
            "diagnosis_status": r["diagnosis_status"],
            "dedup_status": r["dedup_status"],
            "eligibility_reason": r["eligibility_reason"],
            "eligibility_reason_text": reason_text(r["eligibility_reason"]),
        }
        for r in candidate_rows
        if not r["modelling_eligible"]
    ]


def compute_repeated_coordinate_stats(normalized: list[NormalizedOutbreakRecord]) -> dict:
    """Two DELIBERATELY DIFFERENT repeated-coordinate metrics, computed and
    reported side by side rather than collapsed into one number:

    - `exact`: groups by the coordinate's own full float precision exactly
      as parsed from the source CSV string — no rounding step at all.
    - `rounded_6dp`: groups by `(round(lat, 6), round(lon, 6))` — the SAME
      rounding `normalize.assign_spatial_independence` already uses for
      `spatial_independence`, so this metric is consistent with that
      existing field.

    These differ in this real corpus (316 raw rows carry more than 6
    decimal digits of source coordinate precision — see
    FMD_DATA_AUDIT.md), so `rounded_6dp` merges a small number of
    full-precision-distinct coordinate pairs that agree only after rounding
    (verified: rounded_6dp = exact + 5 groups in the 2002-2026 export).
    Neither number is "the" repeated-coordinate count — both are reported;
    `rounded_6dp` is used for the per-record `coordinate_group_size` /
    `spatial_independence`-aligned audit columns since it matches the
    field already produced upstream by the shared pipeline.
    """
    exact_counts: Counter[tuple[float, float]] = Counter()
    rounded_counts: Counter[tuple[float, float]] = Counter()
    for r in normalized:
        if r.latitude is not None and r.longitude is not None:
            exact_counts[(r.latitude, r.longitude)] += 1
            rounded_counts[(round(r.latitude, 6), round(r.longitude, 6))] += 1

    def _summarize(counts: Counter) -> dict:
        repeated = [c for c in counts.values() if c > 1]
        return {
            "repeated_coordinate_group_count": len(repeated),
            "max_events_at_one_coordinate": max(counts.values()) if counts else 0,
            "events_in_a_repeated_group": sum(repeated),
        }

    return {
        "repeated_coordinate_groups_exact": _summarize(exact_counts),
        "repeated_coordinate_groups_rounded_6dp": _summarize(rounded_counts),
    }


EVENT_DATE_MIN_PLAUSIBLE = _date(1900, 1, 1)
"""Sanity floor for `onset_date` classification — well before any
electronic FMD surveillance record could plausibly exist. Not a scientific
claim about FMD's own history, only a defensive bound against an obviously
corrupted date string (e.g. a stray "0002-01-01"); never used to exclude a
record from eligibility, only to make an already-parseable-but-nonsensical
date visible in the audit rather than silently counted as an ordinary
valid date."""

MISSING = "MISSING"
MALFORMED = "MALFORMED"
IMPOSSIBLE_FUTURE = "IMPOSSIBLE_FUTURE"
IMPOSSIBLE_TOO_OLD = "IMPOSSIBLE_TOO_OLD"
VALID = "VALID"


def classify_event_date(raw_onset_date: str | None, *, today: _date | None = None) -> str:
    """FMD-03D date-semantics audit: MISSING / MALFORMED / IMPOSSIBLE_FUTURE /
    IMPOSSIBLE_TOO_OLD / VALID classification of the FMD source's own
    `onset_date` string (this source's sole populated event-date field —
    see `fmd_source_adapter.py`).

    A pure read-side classification — never mutates the record, and is
    never consulted by `evaluate_fmd_eligibility` (which already treats
    both MISSING and MALFORMED identically as "no usable date", via
    `dedup.best_match_date`/`dedup.parse_date` returning None for either).
    This function exists purely so the two distinct failure modes are
    separately visible in the audit rather than collapsed into one silent
    "missing" bucket (FMD-03D Step 6: malformed/impossible dates must be
    validated, not treated as ordinary missing data).

    `today` is injectable for deterministic testing; defaults to the real
    current date. Never written into any canonical CSV output/row — this
    is an audit-only statistic (like `compute_repeated_coordinate_stats`),
    so it does not compromise the pipeline's byte-for-byte CSV
    reproducibility guarantee (FMD_DATA_PROVENANCE.md Sec. 9)."""
    if not raw_onset_date or not raw_onset_date.strip():
        return MISSING
    parsed = parse_date(raw_onset_date)
    if parsed is None:
        return MALFORMED
    reference_today = today if today is not None else _date.today()
    if parsed > reference_today:
        return IMPOSSIBLE_FUTURE
    if parsed < EVENT_DATE_MIN_PLAUSIBLE:
        return IMPOSSIBLE_TOO_OLD
    return VALID


def compute_date_validation_stats(normalized: list[NormalizedOutbreakRecord]) -> dict:
    counts = Counter(classify_event_date(r.onset_date) for r in normalized)
    return {
        "missing": counts.get(MISSING, 0),
        "malformed": counts.get(MALFORMED, 0),
        "impossible_future": counts.get(IMPOSSIBLE_FUTURE, 0),
        "impossible_too_old": counts.get(IMPOSSIBLE_TOO_OLD, 0),
        "valid": counts.get(VALID, 0),
    }


def build_geocoding_review_rows(normalized: list[NormalizedOutbreakRecord]) -> list[dict]:
    coord_counts: Counter[tuple[float, float]] = Counter()
    for r in normalized:
        if r.latitude is not None and r.longitude is not None:
            coord_counts[(round(r.latitude, 6), round(r.longitude, 6))] += 1

    rows: list[dict] = []
    for r in normalized:
        if r.latitude is None or r.longitude is None:
            group_size = 0
            reason = "missing coordinate"
        else:
            group_size = coord_counts[(round(r.latitude, 6), round(r.longitude, 6))]
            if group_size > 1:
                reason = f"coordinate shared by {group_size} events — precision UNKNOWN, not automatically a duplicate"
            else:
                reason = "coordinate precision UNKNOWN (source does not mark GPS precision)"
        rows.append(
            {
                "source_record_id": r.source_record_id,
                "event_id": r.event_id,
                "country": r.country,
                "locality": r.locality,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "gps_quality": r.gps_quality,
                "spatial_independence": r.spatial_independence,
                "coordinate_group_size": group_size,
                "review_reason": reason,
            }
        )
    return rows


def build_event_metadata_rows(normalized: list[NormalizedOutbreakRecord], raw_records_by_id: dict) -> list[dict]:
    rows: list[dict] = []
    for r in normalized:
        raw = raw_records_by_id.get(r.source_record_id)
        extra = raw.extra if raw is not None else {}
        species_result = normalize_species_category(r.species)
        rows.append(
            {
                "source_record_id": r.source_record_id,
                "event_id": r.event_id,
                "fmd_canonical_event_id": fmd_canonical_event_id(r.event_id),
                "locality_label": extra.get("location_label"),
                "region_continent": extra.get("region_continent"),
                "display_date": extra.get("display_date"),
                "animal_type_list_raw": extra.get("animal_type_list"),
                "reporting_source_institution": extra.get("reporting_source_institution"),
                "humans_affected": extra.get("humans_affected"),
                "human_deaths": extra.get("human_deaths"),
                "species_raw": r.species,
                "species_normalized_category": species_result.species_normalized_category,
                "serotype_known": False,
                "serotype_value": "",
                "linked_wrlfmd_reference": "",
            }
        )
    return rows


def run(raw_fmd_dir: str, processed_fmd_dir: str) -> dict:
    raw_fmd_path = Path(raw_fmd_dir)
    processed_fmd_path = Path(processed_fmd_dir)

    normalized, csv_paths = load_fmd_normalized_records(raw_fmd_path)

    # Re-parse raw records (kept alongside, keyed by the same deterministic
    # source_record_id assignment order) so event_metadata can reach into
    # `extra` — normalize.py deliberately does not carry `extra` forward
    # onto NormalizedOutbreakRecord (it is not part of the shared canonical
    # schema), so it is looked up here from the raw parse instead of
    # re-fabricating it.
    raw_records = []
    for p in csv_paths:
        raw_records.extend(parse_fmd_bigquery_csv(p))
    fmd_only_raw = [r for r in raw_records if normalize_disease(r.disease) == FMD_DISEASE_KEY]
    raw_records_by_id = {n.source_record_id: raw for n, raw in zip(normalized, fmd_only_raw)}

    manifest_rows = build_source_manifest_rows(raw_fmd_path, normalized)
    outbreak_events_raw_rows = build_outbreak_events_raw_rows(normalized)
    conservative_rows, candidate_rows, groups = build_conservative_and_candidate_rows(normalized)
    exclusion_rows = build_exclusion_audit_rows(candidate_rows)
    geocoding_rows = build_geocoding_review_rows(normalized)
    event_metadata_rows = build_event_metadata_rows(normalized, raw_records_by_id)
    dedup_audit_rows = [
        {
            "duplicate_group_id": g.duplicate_group_id,
            "canonical_record_id": g.canonical_record_id,
            "member_record_ids": ";".join(g.member_record_ids),
            "member_count": len(g.member_record_ids),
            "match_rule": g.match_rule,
            "match_features": g.match_features,
            "dedup_confidence": g.dedup_confidence,
            "review_required": g.review_required,
            "merged": g.merged,
            "notes": g.notes,
        }
        for g in groups
    ]
    species_audit_rows = build_species_normalization_audit([r.species for r in normalized])

    _write_csv(processed_fmd_path / "fmd_source_manifest.csv", manifest_rows, SOURCE_MANIFEST_COLUMNS)
    _write_csv(
        processed_fmd_path / "fmd_outbreak_events_raw.csv",
        outbreak_events_raw_rows,
        NORMALIZED_FIELD_NAMES + ["fmd_canonical_event_id", "diagnosis_status", "species_normalized_category", "species_tokens_normalized"],
    )
    _write_csv(processed_fmd_path / "fmd_lab_samples.csv", [], LAB_SAMPLES_COLUMNS)
    _write_csv(
        processed_fmd_path / "fmd_canonical_outbreaks_conservative.csv",
        conservative_rows,
        NORMALIZED_FIELD_NAMES + FMD_CANONICAL_EXTRA_COLUMNS,
    )
    _write_csv(processed_fmd_path / "fmd_event_metadata.csv", event_metadata_rows, EVENT_METADATA_COLUMNS)
    _write_csv(processed_fmd_path / "fmd_dedup_audit.csv", dedup_audit_rows, DEDUP_AUDIT_COLUMNS)
    _write_csv(processed_fmd_path / "fmd_geocoding_review.csv", geocoding_rows, GEOCODING_REVIEW_COLUMNS)
    _write_csv(processed_fmd_path / "fmd_exclusion_audit.csv", exclusion_rows, EXCLUSION_AUDIT_COLUMNS)
    _write_csv(processed_fmd_path / "fmd_model_candidate_events.csv", candidate_rows, MODEL_CANDIDATE_COLUMNS)
    _write_csv(
        processed_fmd_path / "fmd_species_normalization_audit.csv",
        species_audit_rows,
        ["raw_species_value", "normalized_species_category", "species_tokens_normalized",
         "domestic_context_present", "wild_context_present", "captive_context_present", "row_count"],
    )

    status_counts = Counter(classify_diagnosis_status(r.diagnostic_result) for r in normalized)
    eligible_count = sum(1 for r in candidate_rows if r["modelling_eligible"])
    reason_counts = Counter(r["eligibility_reason"] for r in candidate_rows if not r["modelling_eligible"])
    repeated_coord_stats = compute_repeated_coordinate_stats(normalized)
    date_validation_stats = compute_date_validation_stats(normalized)

    species_category_counts = Counter()
    for row in species_audit_rows:
        species_category_counts[row["normalized_species_category"]] += row["row_count"]
    context_counts = {
        "domestic_context_present": sum(r["domestic_context_present"] * r["row_count"] for r in species_audit_rows),
        "wild_context_present": sum(r["wild_context_present"] * r["row_count"] for r in species_audit_rows),
        "captive_context_present": sum(r["captive_context_present"] * r["row_count"] for r in species_audit_rows),
    }

    dates = sorted(r.onset_date for r in normalized if r.onset_date)
    countries = sorted({r.country for r in normalized if r.country})

    eligible_rows = [r for r in conservative_rows if r["modelling_eligible"]]
    sri_lanka_eligible = sum(1 for r in eligible_rows if r["country"] == "Sri Lanka")
    south_asia_eligible = sum(1 for r in eligible_rows if r["country"] in SOUTH_ASIA_COUNTRIES)
    southeast_asia_eligible = sum(1 for r in eligible_rows if r["country"] in SOUTHEAST_ASIA_COUNTRIES)
    iran_eligible = sum(1 for r in eligible_rows if r["country"] == IRAN_COUNTRY_NAME)

    sri_lanka_raw = sum(1 for r in normalized if r.country == "Sri Lanka")
    south_asia_raw = sum(1 for r in normalized if r.country in SOUTH_ASIA_COUNTRIES)
    southeast_asia_raw = sum(1 for r in normalized if r.country in SOUTHEAST_ASIA_COUNTRIES)
    iran_raw = sum(1 for r in normalized if r.country == IRAN_COUNTRY_NAME)

    return {
        "raw_record_count": len(normalized),
        "status_counts": dict(status_counts),
        "duplicate_group_count": len(groups),
        "merged_group_count": sum(1 for g in groups if g.merged),
        "conservative_row_count": len(conservative_rows),
        "eligible_count": eligible_count,
        "ineligible_count": len(candidate_rows) - eligible_count,
        "eligibility_reason_counts": dict(reason_counts),
        "manifest_rows": manifest_rows,
        "repeated_coordinate_stats": repeated_coord_stats,
        "date_validation_stats": date_validation_stats,
        "species_category_counts": dict(species_category_counts),
        "species_context_counts": context_counts,
        "distinct_species_raw_values": len(species_audit_rows),
        "country_count": len(countries),
        "date_range_start": dates[0] if dates else None,
        "date_range_end": dates[-1] if dates else None,
        "regional_raw_counts": {
            "sri_lanka": sri_lanka_raw,
            "south_asia": south_asia_raw,
            "southeast_asia": southeast_asia_raw,
            "iran": iran_raw,
        },
        "regional_eligible_counts": {
            "sri_lanka": sri_lanka_eligible,
            "south_asia": south_asia_eligible,
            "southeast_asia": southeast_asia_eligible,
            "iran": iran_eligible,
        },
    }


def print_summary(stats: dict) -> None:
    print(f"raw FMD normalized records: {stats['raw_record_count']}")
    print(f"diagnosis status counts: {stats['status_counts']}")
    print(f"duplicate groups: {stats['duplicate_group_count']} (merged: {stats['merged_group_count']})")
    print(f"conservative rows (resolved units, all statuses): {stats['conservative_row_count']}")
    print(f"modelling eligible: {stats['eligible_count']}  ineligible: {stats['ineligible_count']}")
    print(f"ineligibility reasons: {stats['eligibility_reason_counts']}")
    print(f"event date (onset_date) validation: {stats['date_validation_stats']}")


def main(raw_fmd_dir: str, processed_fmd_dir: str) -> None:
    stats = run(raw_fmd_dir, processed_fmd_dir)
    print_summary(stats)


if __name__ == "__main__":
    args = sys.argv[1:]
    raw_fmd_dir = args[0] if len(args) > 0 else "../local_data/pistes_raw/fmd"
    processed_fmd_dir = args[1] if len(args) > 1 else "../local_data/processed/fmd"
    main(raw_fmd_dir, processed_fmd_dir)

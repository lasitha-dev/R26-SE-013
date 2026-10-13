"""Checkpoint 2.5: conservative deduplication policy + model-candidate flags.

Checkpoint 2's `canonical_outbreaks.csv` auto-merges both HIGH and MEDIUM
confidence duplicate groups. For the scientific/model dataset that is too
permissive — MEDIUM is real but ambiguous evidence, and an ambiguous
duplicate decision must not be silently treated as resolved just because
it's convenient for row count.

This module builds a SEPARATE, more conservative view on top of the SAME
underlying duplicate groups (`dedup.build_duplicate_groups`). It does not
change Checkpoint 2's original grouping/matching logic, its `merged` field
semantics, or its `canonical_outbreaks.csv` / `deduplication_report.csv`
outputs — those remain available unchanged for audit/reproducibility
(`build_canonical.py` still writes them as before).

Conservative merge policy:
    HIGH   -> auto-merged.       dedup_status=AUTO_MERGED_HIGH, model_candidate=True
    MEDIUM -> NOT merged.        dedup_status=REVIEW_MEDIUM,     model_candidate=False
    LOW    -> NOT merged.        dedup_status=REVIEW_LOW,        model_candidate=False
    (no candidate group)         dedup_status=SINGLETON,         model_candidate=True
    (no group, but a date-conflict — see below) dedup_status=REVIEW_LOW, model_candidate=False

Date-conflict side channel (`dedup.find_date_conflicts`): a record that
agrees with another on country + strict locality + species + tight
coordinate distance, but whose date disagrees by MORE than the matching
tolerance, is a genuine near-miss — not an ordinary, unremarkable
singleton. It gets downgraded to REVIEW_LOW / model_candidate=False too,
but ONLY when it has no other resolved group membership: a record already
merged into a clean HIGH group is never downgraded just because some other
outlier record happens to conflict with it on date. This is what keeps
Sri Lanka's Chavakachcheri case correct — the well-matched CSV row + WAHIS
outbreak stay AUTO_MERGED_HIGH, while only the actual 8-day-outlier CSV row
gets flagged.

`model_candidate` is derived ONLY from `dedup_status`. The composite DQS
(`quality.py`) is never consulted here, and must not be — see
DATA_PROVENANCE.md "DQS never overrides dedup status".
"""

from __future__ import annotations

from ..schemas import DedupConfidence, DedupStatus, NormalizedOutbreakRecord
from .dedup import DuplicateGroupResult, find_date_conflicts

REASON_REVIEW_MEDIUM = "unresolved MEDIUM-confidence duplicate candidate — requires manual review before model use"
REASON_REVIEW_LOW = "unresolved LOW-confidence duplicate candidate — requires manual review before model use"
REASON_DATE_CONFLICT_PREFIX = "date conflict with an otherwise-strong candidate match — requires manual adjudication: "

CONSERVATIVE_EXTRA_COLUMNS = [
    "duplicate_group_id",
    "member_record_ids",
    "member_count",
    "dedup_confidence",
    "dedup_status",
    "dedup_resolved",
    "review_required",
    "model_candidate",
    "model_exclusion_reason",
    "date_conflict_ids",
]


def build_conservative_rows(
    normalized: list[NormalizedOutbreakRecord],
    groups: list[DuplicateGroupResult],
) -> list[dict]:
    by_id = {r.source_record_id: r for r in normalized}
    date_conflicts = find_date_conflicts(normalized)

    id_to_group: dict[str, DuplicateGroupResult] = {}
    for g in groups:
        for mid in g.member_record_ids:
            id_to_group[mid] = g

    rows: list[dict] = []
    emitted_groups: set[str] = set()

    for r in normalized:
        group = id_to_group.get(r.source_record_id)

        if group is not None and group.dedup_confidence == DedupConfidence.HIGH.value:
            if group.duplicate_group_id in emitted_groups:
                continue
            emitted_groups.add(group.duplicate_group_id)
            canonical_record = by_id[group.canonical_record_id]
            row = canonical_record.as_dict()
            row.update(
                duplicate_group_id=group.duplicate_group_id,
                member_record_ids=";".join(group.member_record_ids),
                member_count=len(group.member_record_ids),
                dedup_confidence=group.dedup_confidence,
                dedup_status=DedupStatus.AUTO_MERGED_HIGH.value,
                dedup_resolved=True,
                review_required=False,
                model_candidate=True,
                model_exclusion_reason="",
                date_conflict_ids="",
            )
            rows.append(row)
            continue

        if group is not None:
            # MEDIUM or LOW — never auto-resolved for the model dataset,
            # regardless of Checkpoint 2's original `merged` policy. Each
            # member is kept as its OWN row (member_record_ids/member_count
            # describe only this row's own raw record, matching Checkpoint
            # 2's original convention for unmerged rows) — the full
            # candidate group is still traceable via `duplicate_group_id`
            # against deduplication_report.csv, so nothing is hidden, but
            # summing member_count across the conservative dataset must
            # still equal the total raw record count exactly once each.
            status = (
                DedupStatus.REVIEW_MEDIUM.value
                if group.dedup_confidence == DedupConfidence.MEDIUM.value
                else DedupStatus.REVIEW_LOW.value
            )
            reason = REASON_REVIEW_MEDIUM if status == DedupStatus.REVIEW_MEDIUM.value else REASON_REVIEW_LOW
            row = r.as_dict()
            row.update(
                duplicate_group_id=group.duplicate_group_id,
                member_record_ids=r.source_record_id,
                member_count=1,
                dedup_confidence=group.dedup_confidence,
                dedup_status=status,
                dedup_resolved=False,
                review_required=True,
                model_candidate=False,
                model_exclusion_reason=reason,
                date_conflict_ids="",
            )
            rows.append(row)
            continue

        # No duplicate-group candidate at all. Still check the separate
        # date-conflict side channel before calling it a clean singleton.
        conflicts = date_conflicts.get(r.source_record_id, [])
        row = r.as_dict()
        if conflicts:
            conflict_ids = ";".join(c.b_id for c in conflicts)
            reason = REASON_DATE_CONFLICT_PREFIX + "; ".join(c.reason for c in conflicts)
            row.update(
                duplicate_group_id="",
                member_record_ids=r.source_record_id,
                member_count=1,
                dedup_confidence="",
                dedup_status=DedupStatus.REVIEW_LOW.value,
                dedup_resolved=False,
                review_required=True,
                model_candidate=False,
                model_exclusion_reason=reason,
                date_conflict_ids=conflict_ids,
            )
        else:
            row.update(
                duplicate_group_id="",
                member_record_ids=r.source_record_id,
                member_count=1,
                dedup_confidence="",
                dedup_status=DedupStatus.SINGLETON.value,
                dedup_resolved=True,
                review_required=False,
                model_candidate=True,
                model_exclusion_reason="",
                date_conflict_ids="",
            )
        rows.append(row)

    return rows


def build_model_candidate_report(conservative_rows: list[dict]) -> list[dict]:
    """A focused per-record projection of the conservative view, for
    quickly auditing exactly what is/isn't eligible for model use and
    why — 'do not hide exclusions'."""
    return [
        {
            "source_record_id": row["source_record_id"],
            "country": row["country"],
            "source_system": row["source_system"],
            "duplicate_group_id": row["duplicate_group_id"],
            "member_record_ids": row["member_record_ids"],
            "dedup_confidence": row["dedup_confidence"],
            "dedup_status": row["dedup_status"],
            "dedup_resolved": row["dedup_resolved"],
            "review_required": row["review_required"],
            "model_candidate": row["model_candidate"],
            "model_exclusion_reason": row["model_exclusion_reason"],
            "date_conflict_ids": row["date_conflict_ids"],
        }
        for row in conservative_rows
    ]


def build_sri_lanka_adjudication(
    normalized: list[NormalizedOutbreakRecord],
    groups: list[DuplicateGroupResult],
    conservative_rows: list[dict],
) -> list[dict]:
    """One row per raw Sri Lanka source record (not per merged group), so
    every CSV row and every WAHIS outbreak is individually visible with
    its match decision — required for the explicit Sri Lanka audit table.

    Looks up the candidate WAHIS outbreak from `groups` directly (not from
    a conservative row's `member_record_ids`) so that an unresolved
    MEDIUM/LOW candidate still shows what it *would* match, not just an
    empty field — "do not hide exclusions" applies to what a record was
    considered a candidate for, not only to what it was actually merged
    into.
    """
    by_id = {r.source_record_id: r for r in normalized}
    id_to_group: dict[str, DuplicateGroupResult] = {}
    for g in groups:
        for mid in g.member_record_ids:
            id_to_group[mid] = g

    crow_for_record: dict[str, dict] = {}
    for crow in conservative_rows:
        for mid in crow["member_record_ids"].split(";"):
            crow_for_record[mid] = crow

    rows: list[dict] = []
    for rec in normalized:
        if rec.country != "Sri Lanka":
            continue
        crow = crow_for_record[rec.source_record_id]
        group = id_to_group.get(rec.source_record_id)

        matched_wahis_outbreak_id = ""
        if rec.source_system == "WAHIS_PDF":
            matched_wahis_outbreak_id = rec.outbreak_id or ""
        elif group is not None:
            wahis_members = [by_id[m] for m in group.member_record_ids if by_id[m].source_system == "WAHIS_PDF"]
            if wahis_members:
                matched_wahis_outbreak_id = wahis_members[0].outbreak_id or ""

        date_value = rec.outbreak_start_date or rec.onset_date or rec.event_start_date

        if crow["dedup_status"] == DedupStatus.AUTO_MERGED_HIGH.value:
            reason = (
                f"matched WAHIS outbreak {matched_wahis_outbreak_id} — HIGH confidence "
                f"(locality + date + coordinates + species all agree)"
            )
        elif matched_wahis_outbreak_id and group is not None:
            reason = (
                f"candidate match to WAHIS outbreak {matched_wahis_outbreak_id} "
                f"({group.dedup_confidence} confidence, group {group.duplicate_group_id}) — "
                f"{crow['model_exclusion_reason']}"
            )
        else:
            reason = crow["model_exclusion_reason"] or "no WAHIS match found"

        rows.append(
            {
                "source_record_id": rec.source_record_id,
                "source_system": rec.source_system,
                "locality": rec.locality,
                "date": date_value,
                "latitude": rec.latitude,
                "longitude": rec.longitude,
                "species": rec.species,
                "matched_wahis_outbreak_id": matched_wahis_outbreak_id,
                "is_canonical_choice": rec.source_record_id == crow.get("source_record_id"),
                "match_status": crow["dedup_status"],
                "reason": reason,
                "model_candidate": crow["model_candidate"],
            }
        )

    rows.sort(key=lambda r: (r["locality"] or "", r["source_record_id"]))
    return rows

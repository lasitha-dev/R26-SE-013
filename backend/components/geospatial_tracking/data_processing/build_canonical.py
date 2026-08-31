"""Checkpoint 2 orchestrator: raw parsers -> normalized -> dedup -> quality
-> canonical dataset + manifests.

Run locally (never in CI — local_data/ is gitignored and not present in the
repo):

    cd backend
    python -m components.geospatial_tracking.data_processing.build_canonical \
        ../local_data/pistes_raw ../local_data/processed ../local_data/manifests

Writes, reproducibly from raw data only:
    <processed_dir>/canonical_outbreaks.csv
    <processed_dir>/canonical_outbreaks.parquet   (only if pyarrow is installed)
    <processed_dir>/canonical_outbreaks_conservative.csv  (Checkpoint 2.5 — see model_candidate.py)
    <processed_dir>/canonical_outbreaks_conservative.parquet  (only if pyarrow is installed)
    <manifest_dir>/source_manifest.csv
    <manifest_dir>/deduplication_report.csv
    <manifest_dir>/data_quality_report.csv
    <manifest_dir>/model_candidate_report.csv       (Checkpoint 2.5)
    <manifest_dir>/sri_lanka_adjudication.csv        (Checkpoint 2.5)

`canonical_outbreaks.csv` keeps Checkpoint 2's original HIGH+MEDIUM
auto-merge policy, unchanged, for audit/reproducibility.
`canonical_outbreaks_conservative.csv` is the Checkpoint 2.5 scientific/
model view: only HIGH auto-merges; MEDIUM and LOW stay unresolved
(`dedup_status` / `model_candidate` columns — see model_candidate.py).

Never mutates or writes anything into local_data/pistes_raw itself.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from .csv_parser import parse_csv_file
from .dedup import build_duplicate_groups
from .manifest import build_source_manifest, included_paths
from .model_candidate import (
    CONSERVATIVE_EXTRA_COLUMNS,
    build_conservative_rows,
    build_model_candidate_report,
    build_sri_lanka_adjudication,
)
from .normalize import assign_spatial_independence, normalize_raw_records
from .quality import compute_quality
from .wahis_parser import parse_wahis_pdf
from ..schemas import DedupStatus, NORMALIZED_FIELD_NAMES

CANONICAL_EXTRA_COLUMNS = [
    "duplicate_group_id",
    "member_record_ids",
    "member_count",
    "dedup_confidence",
    "review_required",
]


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_normalized_records(raw_dir: str | Path) -> list:
    csv_paths, pdf_paths = included_paths(raw_dir)
    raw_records = []
    for p in csv_paths:
        raw_records.extend(parse_csv_file(p))
    for p in pdf_paths:
        _, records = parse_wahis_pdf(p)
        raw_records.extend(records)

    normalized = normalize_raw_records(raw_records)
    assign_spatial_independence(normalized)
    return normalized


def build_canonical_rows(normalized: list) -> tuple[list[dict], list]:
    """Returns (canonical_outbreaks rows, duplicate_group results)."""
    by_id = {r.source_record_id: r for r in normalized}
    groups = build_duplicate_groups(normalized)

    id_to_group = {}
    for g in groups:
        for mid in g.member_record_ids:
            id_to_group[mid] = g

    canonical_rows: list[dict] = []
    emitted_groups: set[str] = set()

    for r in normalized:
        group = id_to_group.get(r.source_record_id)

        if group is not None and group.merged:
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
                review_required=group.review_required,
            )
            canonical_rows.append(row)
        else:
            # true singleton, OR a LOW-confidence candidate kept separate
            row = r.as_dict()
            row.update(
                duplicate_group_id=group.duplicate_group_id if group else "",
                member_record_ids=r.source_record_id,
                member_count=1,
                dedup_confidence=group.dedup_confidence if group else "",
                review_required=group.review_required if group else False,
            )
            canonical_rows.append(row)

    return canonical_rows, groups


def build_dedup_report_rows(groups: list) -> list[dict]:
    return [
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


def build_quality_report_rows(normalized: list) -> list[dict]:
    return [compute_quality(r).as_dict() for r in normalized]


def run(raw_dir: str, processed_dir: str, manifest_dir: str) -> dict:
    raw_path = Path(raw_dir)
    processed_path = Path(processed_dir)
    manifest_path = Path(manifest_dir)

    manifest_rows = build_source_manifest(raw_path)
    normalized = load_normalized_records(raw_path)
    canonical_rows, groups = build_canonical_rows(normalized)
    dedup_rows = build_dedup_report_rows(groups)
    quality_rows = build_quality_report_rows(normalized)
    conservative_rows = build_conservative_rows(normalized, groups)
    model_candidate_rows = build_model_candidate_report(conservative_rows)
    sri_lanka_rows = build_sri_lanka_adjudication(normalized, groups, conservative_rows)

    canonical_fieldnames = NORMALIZED_FIELD_NAMES + CANONICAL_EXTRA_COLUMNS
    _write_csv(processed_path / "canonical_outbreaks.csv", canonical_rows, canonical_fieldnames)

    conservative_fieldnames = NORMALIZED_FIELD_NAMES + CONSERVATIVE_EXTRA_COLUMNS
    _write_csv(
        processed_path / "canonical_outbreaks_conservative.csv", conservative_rows, conservative_fieldnames
    )

    manifest_fieldnames = [
        "source_file",
        "source_system",
        "file_hash",
        "country_coverage_count",
        "country_coverage",
        "date_coverage_start",
        "date_coverage_end",
        "raw_record_count",
        "parser_version",
        "included_in_canonical",
        "notes",
    ]
    _write_csv(manifest_path / "source_manifest.csv", manifest_rows, manifest_fieldnames)

    dedup_fieldnames = [
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
    _write_csv(manifest_path / "deduplication_report.csv", dedup_rows, dedup_fieldnames)

    quality_fieldnames = [
        "source_record_id",
        "gps_quality",
        "date_quality",
        "diagnostic_quality",
        "identifier_quality",
        "completeness_quality",
        "availability_quality",
        "dqs",
    ]
    _write_csv(manifest_path / "data_quality_report.csv", quality_rows, quality_fieldnames)

    model_candidate_fieldnames = [
        "source_record_id",
        "country",
        "source_system",
        "duplicate_group_id",
        "member_record_ids",
        "dedup_confidence",
        "dedup_status",
        "dedup_resolved",
        "review_required",
        "model_candidate",
        "model_exclusion_reason",
        "date_conflict_ids",
    ]
    _write_csv(manifest_path / "model_candidate_report.csv", model_candidate_rows, model_candidate_fieldnames)

    sri_lanka_fieldnames = [
        "source_record_id",
        "source_system",
        "locality",
        "date",
        "latitude",
        "longitude",
        "species",
        "matched_wahis_outbreak_id",
        "is_canonical_choice",
        "match_status",
        "reason",
        "model_candidate",
    ]
    _write_csv(manifest_path / "sri_lanka_adjudication.csv", sri_lanka_rows, sri_lanka_fieldnames)

    parquet_written = False
    try:
        import pandas as pd

        pd.DataFrame(canonical_rows).to_parquet(processed_path / "canonical_outbreaks.parquet")
        pd.DataFrame(conservative_rows).to_parquet(processed_path / "canonical_outbreaks_conservative.parquet")
        parquet_written = True
    except ImportError:
        pass

    dedup_status_counts = dict(Counter(row["dedup_status"] for row in conservative_rows))
    model_candidate_count = sum(1 for row in conservative_rows if row["model_candidate"])

    return {
        "raw_record_count": len(normalized),
        "canonical_count": len(canonical_rows),
        "duplicate_group_count": len(groups),
        "merged_group_count": sum(1 for g in groups if g.merged),
        "unmerged_low_confidence_group_count": sum(1 for g in groups if not g.merged),
        "confidence_counts": dict(Counter(g.dedup_confidence for g in groups)),
        "review_required_group_count": sum(1 for g in groups if g.review_required),
        "parquet_written": parquet_written,
        "manifest_rows": manifest_rows,
        "conservative_count": len(conservative_rows),
        "model_candidate_count": model_candidate_count,
        "dedup_status_counts": dedup_status_counts,
        "review_medium_record_count": dedup_status_counts.get(DedupStatus.REVIEW_MEDIUM.value, 0),
        "review_low_record_count": dedup_status_counts.get(DedupStatus.REVIEW_LOW.value, 0),
    }


def print_summary(stats: dict) -> None:
    print(f"raw normalized records: {stats['raw_record_count']}")
    print(f"canonical rows (Checkpoint 2, HIGH+MEDIUM merged): {stats['canonical_count']}")
    print(f"duplicate groups: {stats['duplicate_group_count']} {stats['confidence_counts']}")
    print(f"  merged (HIGH/MEDIUM): {stats['merged_group_count']}")
    print(f"  unmerged LOW (kept separate, flagged): {stats['unmerged_low_confidence_group_count']}")
    print(f"  review_required groups: {stats['review_required_group_count']}")
    print(f"conservative rows (Checkpoint 2.5, HIGH only merged): {stats['conservative_count']}")
    print(f"  dedup_status counts: {stats['dedup_status_counts']}")
    print(f"  model_candidate count: {stats['model_candidate_count']}")
    print(f"  unresolved MEDIUM records: {stats['review_medium_record_count']}")
    print(f"  unresolved LOW records: {stats['review_low_record_count']}")
    print(f"parquet written: {stats['parquet_written']}")


def main(raw_dir: str, processed_dir: str, manifest_dir: str) -> None:
    stats = run(raw_dir, processed_dir, manifest_dir)
    print_summary(stats)


if __name__ == "__main__":
    args = sys.argv[1:]
    raw_dir = args[0] if len(args) > 0 else "../local_data/pistes_raw"
    processed_dir = args[1] if len(args) > 1 else "../local_data/processed"
    manifest_dir = args[2] if len(args) > 2 else "../local_data/manifests"
    main(raw_dir, processed_dir, manifest_dir)

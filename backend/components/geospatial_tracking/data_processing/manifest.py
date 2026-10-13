"""Reproducible source manifest for the raw PISTES files.

Documents exactly which raw files feed canonical generation, and — per
Checkpoint 2 — explicitly identifies the two byte-identical
"Latest Reported Events" CSV files and excludes the second copy rather
than silently double-counting one CSV source as two.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .csv_parser import parse_csv_file
from .dedup import best_match_date, parse_date
from .wahis_parser import parse_wahis_pdf

PARSER_VERSION = "checkpoint2-2026-08-18"
"""Bumped whenever csv_parser.py / wahis_parser.py / normalize.py field
mapping changes in a way that would affect manifest counts or coverage."""


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _date_span(dates: list) -> tuple[str | None, str | None]:
    parsed = sorted(d for d in dates if d is not None)
    if not parsed:
        return None, None
    return parsed[0].isoformat(), parsed[-1].isoformat()


def build_source_manifest(raw_dir: str | Path) -> list[dict]:
    raw_path = Path(raw_dir)
    csv_paths = sorted(raw_path.glob("*.csv"))
    pdf_paths = sorted(raw_path.glob("*.pdf"))

    hash_to_files: dict[str, list[Path]] = defaultdict(list)
    for p in csv_paths + pdf_paths:
        hash_to_files[_file_hash(p)].append(p)

    # deterministic dedup: within an identical-hash group, keep the
    # lexicographically-first filename, exclude the rest.
    included: dict[Path, bool] = {}
    excluded_because_of: dict[Path, Path] = {}
    for file_hash, paths in hash_to_files.items():
        ordered = sorted(paths, key=lambda p: p.name)
        included[ordered[0]] = True
        for dup in ordered[1:]:
            included[dup] = False
            excluded_because_of[dup] = ordered[0]

    rows: list[dict] = []

    for path in csv_paths:
        records = parse_csv_file(path)
        countries = sorted({r.country for r in records if r.country})
        onset_dates = [parse_date(r.onset_date) for r in records]
        report_dates = [parse_date(r.report_date) for r in records]
        date_start, date_end = _date_span(onset_dates or report_dates)
        is_included = included[path]
        notes = (
            f"byte-identical duplicate of {excluded_because_of[path].name}; "
            "excluded from canonical generation (see DATA_AUDIT.md sec. 1)"
            if not is_included
            else ""
        )
        rows.append(
            {
                "source_file": path.name,
                "source_system": "FAO_EMPRESI_CSV",
                "file_hash": _file_hash(path),
                "country_coverage_count": len(countries),
                "country_coverage": ";".join(countries),
                "date_coverage_start": date_start,
                "date_coverage_end": date_end,
                "raw_record_count": len(records),
                "parser_version": PARSER_VERSION,
                "included_in_canonical": is_included,
                "notes": notes,
            }
        )

    for path in pdf_paths:
        event_ctx, records = parse_wahis_pdf(path)
        countries = sorted({r.country for r in records if r.country})
        dates = []
        for r in records:
            best = best_match_date(r)
            if best:
                dates.append(best[0])
        date_start, date_end = _date_span(dates)
        is_included = included[path]
        notes = (
            f"byte-identical duplicate of {excluded_because_of[path].name}; "
            "excluded from canonical generation"
            if not is_included
            else f"event_id={event_ctx.get('event_id')}"
        )
        rows.append(
            {
                "source_file": path.name,
                "source_system": "WAHIS_PDF",
                "file_hash": _file_hash(path),
                "country_coverage_count": len(countries),
                "country_coverage": ";".join(countries),
                "date_coverage_start": date_start,
                "date_coverage_end": date_end,
                "raw_record_count": len(records),
                "parser_version": PARSER_VERSION,
                "included_in_canonical": is_included,
                "notes": notes,
            }
        )

    return rows


def included_paths(raw_dir: str | Path) -> tuple[list[Path], list[Path]]:
    """Returns (csv_paths_to_parse, pdf_paths_to_parse) after excluding
    byte-identical duplicate files."""
    raw_path = Path(raw_dir)
    csv_paths = sorted(raw_path.glob("*.csv"))
    pdf_paths = sorted(raw_path.glob("*.pdf"))

    hash_to_files: dict[str, list[Path]] = defaultdict(list)
    for p in csv_paths + pdf_paths:
        hash_to_files[_file_hash(p)].append(p)

    keep: set[Path] = set()
    for paths in hash_to_files.values():
        ordered = sorted(paths, key=lambda p: p.name)
        keep.add(ordered[0])

    return (
        [p for p in csv_paths if p in keep],
        [p for p in pdf_paths if p in keep],
    )

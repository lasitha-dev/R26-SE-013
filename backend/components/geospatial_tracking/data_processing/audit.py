"""Raw-data inventory audit for PISTES source files.

Run locally (never in CI, since local_data/ is gitignored and not present
in the repo):

    cd backend
    python -m components.geospatial_tracking.data_processing.audit \
        ../local_data/pistes_raw

Produces a plain-text summary of the CSV and WAHIS PDF sources found in the
given directory: row/record counts, country distribution, date ranges,
missing-value rates, and known duplication signals. This is a raw-source
INVENTORY only — it does not deduplicate or build the canonical dataset
(that is Phase C, not implemented yet).
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .csv_parser import parse_csv_file
from .wahis_parser import parse_wahis_pdf


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def audit_csv_files(paths: list[Path]) -> str:
    lines = ["## CSV sources", ""]
    hashes: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        hashes[_file_hash(path)].append(path.name)

    for h, names in hashes.items():
        if len(names) > 1:
            lines.append(f"- BYTE-IDENTICAL duplicate files (md5 {h[:8]}...): {', '.join(names)}")
    lines.append("")

    for path in paths:
        records = parse_csv_file(path)
        n = len(records)
        countries = Counter(r.country for r in records)
        missing_obs_date = sum(1 for r in records if r.onset_date is None)
        missing_gps = sum(1 for r in records if r.latitude is None or r.longitude is None)
        dupe_event_ids = n - len(set(r.event_id for r in records))
        onset_dates = sorted(r.onset_date for r in records if r.onset_date)
        report_dates = sorted(r.report_date for r in records if r.report_date)

        # near-duplicate signal: rows sharing (country, locality, onset_date)
        groups: dict[tuple, list[str]] = defaultdict(list)
        for r in records:
            groups[(r.country, (r.locality or "").strip(), r.onset_date)].append(r.event_id)
        dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
        rows_in_dupe_groups = sum(len(v) for v in dupe_groups.values())

        lines.append(f"### {path.name}")
        lines.append(f"- rows: {n}")
        lines.append(f"- distinct countries: {len(countries)}")
        lines.append(f"- top countries: {countries.most_common(10)}")
        lines.append(f"- Sri Lanka rows: {countries.get('Sri Lanka', 0)}")
        lines.append(f"- Thailand rows: {countries.get('Thailand', 0)}")
        lines.append(f"- missing onset/observation date: {missing_obs_date} ({missing_obs_date/n:.1%})")
        lines.append(f"- missing GPS: {missing_gps}")
        lines.append(f"- duplicate Event ID values within file: {dupe_event_ids}")
        lines.append(
            f"- rows sharing (country, locality, onset_date) with another row "
            f"(near-duplicate signal, different Event ID): {rows_in_dupe_groups} in {len(dupe_groups)} groups"
        )
        if onset_dates:
            lines.append(f"- onset/observation date range: {onset_dates[0]} to {onset_dates[-1]}")
        if report_dates:
            lines.append(f"- report date range: {report_dates[0]} to {report_dates[-1]}")
        lines.append("")

    return "\n".join(lines)


def audit_pdf_files(paths: list[Path]) -> str:
    lines = ["## WAHIS PDF sources", ""]
    for path in paths:
        event_ctx, records = parse_wahis_pdf(path)
        n = len(records)
        missing_id = sum(1 for r in records if r.outbreak_id is None)
        missing_gps = sum(1 for r in records if r.latitude is None)
        missing_species = sum(1 for r in records if r.species is None)
        approx = sum(1 for r in records if r.approximate_location)
        dupe_ids = n - len(set(r.outbreak_id for r in records if r.outbreak_id))

        lines.append(f"### {path.name}")
        lines.append(f"- event_id: {event_ctx.get('event_id')}  country: {event_ctx.get('country')}")
        lines.append(
            f"- event dates: start {event_ctx.get('event_start_date')}  "
            f"end {event_ctx.get('event_end_date')}  confirmation {event_ctx.get('confirmation_date')}"
        )
        lines.append(f"- event_status: {event_ctx.get('event_status')}  report_date: {event_ctx.get('report_date')}")
        lines.append(f"- outbreak blocks extracted: {n}")
        lines.append(f"- missing outbreak_id (parse gap): {missing_id}")
        lines.append(f"- missing GPS (parse gap or malformed source row): {missing_gps} ({missing_gps/n:.1%} of {n})" if n else "- (no outbreak blocks)")
        lines.append(f"- missing species: {missing_species}")
        lines.append(f"- approximate_location flagged: {approx}")
        lines.append(f"- duplicate outbreak_id within file: {dupe_ids}")
        lines.append("")
    return "\n".join(lines)


def main(raw_dir: str) -> None:
    raw_path = Path(raw_dir)
    csv_paths = sorted(raw_path.glob("*.csv"))
    pdf_paths = sorted(raw_path.glob("*.pdf"))

    print(f"# Raw data audit: {raw_path}\n")
    print(f"Files found: {len(csv_paths)} CSV, {len(pdf_paths)} PDF\n")
    print(audit_csv_files(csv_paths))
    print(audit_pdf_files(pdf_paths))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../local_data/pistes_raw")

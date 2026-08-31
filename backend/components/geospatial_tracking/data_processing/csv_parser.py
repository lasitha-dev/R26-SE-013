"""Parser for the FAO EMPRES-i "Latest Reported Events" CSV export.

Observed columns (2026-04 export):
    Event ID, Disease, Serotype, latitude, longitude, Locality, Country,
    Region, observation date, report date, Species, Diagnosis Source,
    Humans Affected, Human Deaths, Diagnosis Status

Important, non-obvious facts about this source (see DATA_AUDIT.md):
  - "Event ID" values (e.g. "UNFAO-LEG-286458") live in a different
    namespace than WAHIS numeric event IDs / OB_ outbreak IDs used in the
    PDF reports. They must never be assumed to match across sources.
  - "Region" is a continent-level grouping (Europe, Asia, Africa, ...),
    NOT an administrative subdivision. It must not be mapped to admin1.
  - This source carries no animal-level quantitative fields (no
    susceptible/cases/deaths/vaccinated columns). "Humans Affected" and
    "Human Deaths" describe human zoonotic impact, not animal counts, and
    are additionally 100% empty in the 2026-04 export.
  - This source does not mark GPS precision explicitly, so gps_quality is
    UNKNOWN (not EXACT) for every row from this source.
  - This source gives no distinct "system operationally knew about this"
    timestamp, so `operational_availability_date` is always None /
    `operational_availability_quality` is always UNKNOWN — it is never
    inferred from "report date" (see schemas.py module docstring, category
    B vs C). "observation date" is used only as the explicitly-labeled
    RETROSPECTIVE_PROXY-mode substitute (`proxy_availability_date` /
    OBSERVATION_DATE_PROXY), never as real availability.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..schemas import AvailabilityQuality, GpsQuality, RawOutbreakRecord, SourceSystem

_EXPECTED_COLUMNS = [
    "Event ID",
    "Disease",
    "Serotype",
    "latitude",
    "longitude",
    "Locality",
    "Country",
    "Region",
    "observation date",
    "report date",
    "Species",
    "Diagnosis Source",
    "Humans Affected",
    "Human Deaths",
    "Diagnosis Status",
]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_float(value: str | None) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    return float(value)


def parse_csv_row(row: dict, source_file: str) -> RawOutbreakRecord:
    onset_date = _clean(row.get("observation date"))
    return RawOutbreakRecord(
        source_file=source_file,
        source_system=SourceSystem.FAO_EMPRESI_CSV.value,
        country=_clean(row.get("Country")),
        disease=_clean(row.get("Disease")),
        event_id=_clean(row.get("Event ID")),
        onset_date=onset_date,
        report_date=_clean(row.get("report date")),
        # true operational availability is unknown for this source (see
        # module docstring) — never inferred from report date.
        operational_availability_date=None,
        operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
        # RETROSPECTIVE_PROXY-mode-only substitute, explicitly labeled.
        proxy_availability_date=onset_date,
        proxy_availability_quality=(
            AvailabilityQuality.OBSERVATION_DATE_PROXY.value
            if onset_date
            else AvailabilityQuality.UNKNOWN.value
        ),
        locality=_clean(row.get("Locality")),
        latitude=_to_float(row.get("latitude")),
        longitude=_to_float(row.get("longitude")),
        gps_quality=GpsQuality.UNKNOWN.value,
        approximate_location=False,
        species=_clean(row.get("Species")),
        diagnostic_result=_clean(row.get("Diagnosis Status")),
        extra={
            "region_continent": _clean(row.get("Region")),
            "serotype": _clean(row.get("Serotype")),
            "reporting_source_institution": _clean(row.get("Diagnosis Source")),
            "humans_affected": _clean(row.get("Humans Affected")),
            "human_deaths": _clean(row.get("Human Deaths")),
        },
    )


def parse_csv_file(path: str | Path) -> list[RawOutbreakRecord]:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name}: missing expected columns {missing}")
        return [parse_csv_row(row, source_file=path.name) for row in reader]

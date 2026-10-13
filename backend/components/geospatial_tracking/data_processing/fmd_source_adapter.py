"""FMD-03: parser for the FAO EMPRES-i public BigQuery-backed CSV export.

This is a DIFFERENT export of the same underlying FAO EMPRES-i system that
`csv_parser.py` already handles — that module was written against the
EMPRES-i website's "Latest Reported Events" UI export (Title Case columns,
includes a `Serotype` column). This adapter is for the export served by
`https://api.data.apps.fao.org/api/v2/bigquery` (the API literally behind
data.apps.fao.org's public "Major diseases (by date) - EMPRES-i" catalog
resource — see FMD_DATA_PROVENANCE.md), which has a structurally different,
lowercase/snake_case column layout and no Serotype column at all:

    global_id, lat, lon, locality, region, location, observation_date,
    report_date, display_date, species_overview_list, humans_affected,
    humans_deaths, diagnosis_source, diagnosis_status, animal_type_list,
    disease, country

Column-for-column mapping to `csv_parser.py`'s existing "Latest Reported
Events" columns (documented so the two adapters can be reasoned about
side by side):

    global_id              -> Event ID
    lat / lon               -> latitude / longitude
    locality                -> Locality
    region                  -> Region (continent-level, NOT admin1 — same
                               caveat as csv_parser.py)
    observation_date        -> observation date
    report_date             -> report date
    species_overview_list   -> Species
    diagnosis_source        -> Diagnosis Source
    humans_affected         -> Humans Affected
    humans_deaths           -> Human Deaths
    diagnosis_status        -> Diagnosis Status
    disease, country        -> Disease, Country
    (no equivalent)         <- Serotype (this export has none)
    location, display_date, animal_type_list -> no equivalent in the old
        schema; retained verbatim in `extra` so no information is lost.

Same non-obvious facts as csv_parser.py apply here (see that module's
docstring): no animal-level quantitative fields (susceptible/cases/
deaths/vaccinated), no explicit GPS-precision marker (gps_quality is
always UNKNOWN), and no true operational-availability evidence
(operational_availability_date/quality are always None/UNKNOWN;
`observation_date` is only ever used as the explicitly-labeled
RETROSPECTIVE_PROXY substitute, never as real availability).
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..schemas import AvailabilityQuality, GpsQuality, RawOutbreakRecord, SourceSystem

_EXPECTED_COLUMNS = [
    "global_id",
    "lat",
    "lon",
    "locality",
    "region",
    "location",
    "observation_date",
    "report_date",
    "display_date",
    "species_overview_list",
    "humans_affected",
    "humans_deaths",
    "diagnosis_source",
    "diagnosis_status",
    "animal_type_list",
    "disease",
    "country",
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


def parse_fmd_bigquery_row(row: dict, source_file: str) -> RawOutbreakRecord:
    onset_date = _clean(row.get("observation_date"))
    return RawOutbreakRecord(
        source_file=source_file,
        source_system=SourceSystem.FAO_EMPRESI_BIGQUERY_CSV.value,
        country=_clean(row.get("country")),
        disease=_clean(row.get("disease")),
        event_id=_clean(row.get("global_id")),
        onset_date=onset_date,
        report_date=_clean(row.get("report_date")),
        # true operational availability is unknown for this source — never
        # inferred from report_date (see module docstring).
        operational_availability_date=None,
        operational_availability_quality=AvailabilityQuality.UNKNOWN.value,
        proxy_availability_date=onset_date,
        proxy_availability_quality=(
            AvailabilityQuality.OBSERVATION_DATE_PROXY.value
            if onset_date
            else AvailabilityQuality.UNKNOWN.value
        ),
        locality=_clean(row.get("locality")),
        latitude=_to_float(row.get("lat")),
        longitude=_to_float(row.get("lon")),
        gps_quality=GpsQuality.UNKNOWN.value,
        approximate_location=False,
        species=_clean(row.get("species_overview_list")),
        diagnostic_result=_clean(row.get("diagnosis_status")),
        extra={
            "region_continent": _clean(row.get("region")),
            "location_label": _clean(row.get("location")),
            "display_date": _clean(row.get("display_date")),
            "animal_type_list": _clean(row.get("animal_type_list")),
            "reporting_source_institution": _clean(row.get("diagnosis_source")),
            "humans_affected": _clean(row.get("humans_affected")),
            "human_deaths": _clean(row.get("humans_deaths")),
        },
    )


def parse_fmd_bigquery_csv(path: str | Path) -> list[RawOutbreakRecord]:
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _EXPECTED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name}: missing expected columns {missing}")
        return [parse_fmd_bigquery_row(row, source_file=path.name) for row in reader]

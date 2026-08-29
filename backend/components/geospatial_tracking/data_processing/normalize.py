"""Pre-dedup normalization: RawOutbreakRecord -> NormalizedOutbreakRecord.

Pure reshaping/annotation over Checkpoint 1's raw parser output. Never
merges records, never invents a value for a missing field — every added
column (`source_record_id`, `spatial_independence`,
`proxy_availability_source_field`, `species_normalized`) is either a
deterministic function of existing fields or an honest None when it can't
be determined.
"""

from __future__ import annotations

from collections import Counter

from ..schemas import AvailabilityQuality, NormalizedOutbreakRecord, RawOutbreakRecord
from .species import normalize_species


def make_source_record_id(source_system: str, source_file: str, index: int) -> str:
    """Deterministic id: stable across runs given the same input files, the
    same parser version, and the same (stable) parse order."""
    return f"{source_system}:{source_file}:{index:06d}"


def _infer_proxy_source_field(raw: RawOutbreakRecord) -> str | None:
    """Return the literal field name `proxy_availability_date` was copied
    from, verified by value equality — never just trusted from the quality
    label alone, so a parser bug can't silently mislabel provenance."""
    if raw.proxy_availability_date is None:
        return None
    if (
        raw.proxy_availability_quality == AvailabilityQuality.EVENT_DATE_PROXY.value
        and raw.proxy_availability_date == raw.outbreak_start_date
    ):
        return "outbreak_start_date"
    if (
        raw.proxy_availability_quality == AvailabilityQuality.OBSERVATION_DATE_PROXY.value
        and raw.proxy_availability_date == raw.onset_date
    ):
        return "observation_date"
    return None


def normalize_raw_records(
    raw_records: list[RawOutbreakRecord], *, id_prefix: str = ""
) -> list[NormalizedOutbreakRecord]:
    """Convert one source's raw records into normalized records.

    `id_prefix` distinguishes multiple parse batches of the same
    source_file (unused today — each raw file is parsed exactly once — but
    keeps `source_record_id` collision-proof if that ever changes).
    """
    out: list[NormalizedOutbreakRecord] = []
    for index, raw in enumerate(raw_records):
        out.append(
            NormalizedOutbreakRecord(
                source_record_id=make_source_record_id(
                    raw.source_system, f"{id_prefix}{raw.source_file}", index
                ),
                source_file=raw.source_file,
                source_system=raw.source_system,
                country=raw.country,
                disease=raw.disease,
                event_id=raw.event_id,
                outbreak_id=raw.outbreak_id,
                outbreak_reference=raw.outbreak_reference,
                event_start_date=raw.event_start_date,
                outbreak_start_date=raw.outbreak_start_date,
                onset_date=raw.onset_date,
                confirmation_date=raw.confirmation_date,
                report_date=raw.report_date,
                operational_availability_date=raw.operational_availability_date,
                operational_availability_quality=raw.operational_availability_quality,
                proxy_availability_date=raw.proxy_availability_date,
                proxy_availability_quality=raw.proxy_availability_quality,
                proxy_availability_source_field=_infer_proxy_source_field(raw),
                admin1=raw.admin1,
                admin2=raw.admin2,
                admin3=raw.admin3,
                locality=raw.locality,
                latitude=raw.latitude,
                longitude=raw.longitude,
                gps_quality=raw.gps_quality,
                approximate_location=raw.approximate_location,
                spatial_independence=None,  # filled in by assign_spatial_independence
                species=raw.species,
                species_normalized=normalize_species(raw.species),
                susceptible=raw.susceptible,
                cases=raw.cases,
                deaths=raw.deaths,
                killed_disposed=raw.killed_disposed,
                vaccinated=raw.vaccinated,
                diagnostic_method=raw.diagnostic_method,
                diagnostic_result=raw.diagnostic_result,
                event_status=raw.event_status,
                source_notes=raw.source_notes,
            )
        )
    return out


def assign_spatial_independence(records: list[NormalizedOutbreakRecord]) -> None:
    """Mutates `spatial_independence` in place across the WHOLE corpus.

    True: this record's rounded (lat, lon) is unique across every record
    passed in — its coordinates can be treated as its own independent
    point. False: >=2 records (from any source) share the exact rounded
    coordinate — e.g. WAHIS's documented case of three distinct outbreak
    IDs all reporting one shared approximate village-level coordinate; such
    points must not be treated as independent for spatial modeling later.
    None: coordinates are missing, so independence can't be assessed.

    This never decides duplication (see dedup.py) — a shared coordinate is
    a *spatial* independence signal only, not by itself proof of a
    duplicate outbreak.
    """
    coord_counts: Counter[tuple[float, float]] = Counter()
    for r in records:
        if r.latitude is not None and r.longitude is not None:
            coord_counts[(round(r.latitude, 6), round(r.longitude, 6))] += 1

    for r in records:
        if r.latitude is None or r.longitude is None:
            r.spatial_independence = None
        else:
            key = (round(r.latitude, 6), round(r.longitude, 6))
            r.spatial_independence = coord_counts[key] == 1

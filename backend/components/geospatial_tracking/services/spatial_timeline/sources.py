"""Unified, traceable source inputs for the spatial timeline.

Two record domains, never merged into one anonymous list:

- HISTORICAL: public WAHIS/EMPRES records from the scientific repository
  (MongoDB in the running application), selected by the SAME frozen
  eligibility rule the 10A runtime uses (`source_selector.get_eligible_sources`,
  RETROSPECTIVE_PROXY availability, HISTORICAL_ONLY domain).
- OPERATIONAL: veterinarian-VERIFIED ADRS diagnostic cases, nationwide.
  The scientific source pool is NOT limited to the requesting vet's own
  farms or district -- the spread of a disease does not follow the vet's
  assignment (see `collect_national_operational_sources`). A case's
  position is its farm's validated GPS coordinate -- never guessed, never a
  district centroid. A vet-verified diagnosis stays a vet-verified
  diagnosis (`PROVENANCE_OPERATIONAL`); it is never promoted to an official
  outbreak.

Privacy: only farms the vet is already authorised to see (assigned or
registered-district surveillance farms, i.e. exactly what
`/operational-context` already returns to that vet) keep their `farm_id`
and raw case ids. Every other source carries only what `/national-cases`
already exposes to any vet: farm GPS, the verification date and one-way
`record_key`s -- never a farm id, raw case id, name or clinical note.

Operational cases on the same farm for the same disease collapse into ONE
source (an infected premises), so repeat cases on one farm cannot inflate the
equal-weight C0 kernel sum. Every dropped record is counted by reason.

Dates: a case's verification instant is converted to its Asia/Colombo
calendar date (`services/sri_lanka_time.py`) before it is compared with the
Sri Lanka `as_of` date and window.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Iterable, Protocol

from shapely.geometry import Point
from shapely.prepared import prep

from ...domain.enums import RecordDomainScope
from ...domain.operational_models import OperationalGeospatialContext
from ...repositories.provider import create_outbreak_repository
from ...schemas import ValidationMode
from ..operational.disease_normalization import resolve_operational_disease
from ..operational.farm_normalization import _has_valid_coordinates
from ..operational.national_cases import record_key
from ..source_selector import EligibleSource, get_eligible_sources
from ..sri_lanka_time import sri_lanka_date
from .districts import sri_lanka_land

RECORD_DOMAIN_HISTORICAL = "HISTORICAL"
RECORD_DOMAIN_OPERATIONAL = "OPERATIONAL"

PROVENANCE_HISTORICAL = "SCIENTIFIC_REPOSITORY_HISTORICAL_RECORD"
PROVENANCE_OPERATIONAL = "ADRS_VET_VERIFIED_DIAGNOSTIC_CASE_AT_VALIDATED_FARM_GPS"

EXCLUDED_WRONG_DISEASE = "WRONG_DISEASE"
EXCLUDED_MISSING_VERIFICATION_DATE = "MISSING_OR_UNPARSEABLE_VERIFICATION_DATE"
EXCLUDED_AFTER_AS_OF = "VERIFIED_AFTER_AS_OF_DATE"
EXCLUDED_OUTSIDE_WINDOW = "OUTSIDE_ACTIVE_SOURCE_WINDOW"
EXCLUDED_INVALID_COORDINATES = "MISSING_OR_INVALID_COORDINATES"
EXCLUDED_OUTSIDE_STUDY_AREA = "FARM_COORDINATES_OUTSIDE_SRI_LANKA"

# Coastal tolerance around the ADM2 land boundary (~5.5 km), so farms on the
# shoreline or on small islands are kept.
STUDY_AREA_TOLERANCE_DEG = 0.05
EXCLUDED_DUPLICATE_SAME_FARM = "MERGED_DUPLICATE_SAME_FARM_SAME_DISEASE"
EXCLUDED_NOT_VERIFIED = "NOT_VET_VERIFIED"
EXCLUDED_DUPLICATE_CASE_RECORD = "DUPLICATE_CASE_RECORD"

DETAIL_AUTHORISED_FARM = "AUTHORISED_FARM"
DETAIL_PRIVACY_REDUCED = "PRIVACY_REDUCED_EXTERNAL_FARM"

OPERATIONAL_POOL_NATIONAL = "ALL_VET_VERIFIED_ADRS_CASES_NATIONWIDE"
OPERATIONAL_POOL_AUTHORISED_ONLY = "AUTHORISED_FARMS_ONLY_NATIONAL_CASE_READER_UNAVAILABLE"


def operational_farm_key(farm_id: str) -> str:
    """One-way, stable farm key used in operational source ids, so a source
    id never reveals the farm's database id."""
    return "F" + hashlib.sha256(f"adrs-geo-farm::{farm_id}".encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class TimelineSource:
    # Common model input for two evidence domains. Preserve domain, provenance
    # and member records so each point can be traced back to its own source.
    source_id: str
    record_domain: str
    disease: str  # canonical display name, e.g. "Lumpy skin disease"
    latitude: float
    longitude: float
    observation_date: str  # ISO date: historical availability date / latest verification date
    provenance: str
    member_record_ids: tuple = ()
    gps_quality: str | None = None
    farm_id: str | None = None
    detail_access: str | None = None  # operational only: DETAIL_AUTHORISED_FARM | DETAIL_PRIVACY_REDUCED
    # Operational, authorised farms only: the host case numbers the vet
    # already sees (latest verification first). Empty for every other source.
    case_refs: tuple = ()

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id, "record_domain": self.record_domain, "disease": self.disease,
            "latitude": self.latitude, "longitude": self.longitude, "observation_date": self.observation_date,
            "provenance": self.provenance, "member_record_ids": list(self.member_record_ids),
            "member_count": len(self.member_record_ids), "gps_quality": self.gps_quality, "farm_id": self.farm_id,
            "detail_access": self.detail_access, "case_refs": list(self.case_refs),
        }


@dataclass(frozen=True)
class OperationalCaseRecord:
    """The minimal, disease-resolved view of one host case the source
    collector needs. `disease` is the operational code ("LSD"/"FMD") or
    `None` for an unsupported diagnosis; `verification_time` is the host
    adapter's explicit-UTC text."""

    case_id: str
    farm_id: str | None
    disease: str | None
    verified: bool
    verification_time: str | None
    case_number: str | None = None


@dataclass(frozen=True)
class OperationalFarmLocation:
    farm_id: str
    latitude: float | None
    longitude: float | None
    location_valid: bool


@dataclass
class SourceCollection:
    sources: list[TimelineSource] = field(default_factory=list)
    exclusions: Counter = field(default_factory=Counter)
    historical_status: str = "NOT_REQUESTED"
    operational_status: str = "NOT_REQUESTED"

    def exclusions_dict(self) -> dict:
        return dict(sorted(self.exclusions.items()))


def active_window(as_of: date, window_days: int) -> tuple[date, date]:
    return as_of - timedelta(days=window_days), as_of


def _valid_lat_lon(lat, lon) -> bool:
    return (
        isinstance(lat, (int, float)) and isinstance(lon, (int, float))
        and math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    )


@lru_cache(maxsize=1)
def _study_area():
    return prep(sri_lanka_land().buffer(STUDY_AREA_TOLERANCE_DEG))


def _inside_study_area(lat: float, lon: float) -> bool:
    return _study_area().contains(Point(float(lon), float(lat)))


def authorised_farm_ids(context: OperationalGeospatialContext) -> frozenset[str]:
    """Farms whose id and case ids this vet may already see: assigned farms
    plus registered-district surveillance farms (`/operational-context`)."""
    return frozenset(farm.farm_id for farm in [*context.farms, *context.surveillance_farms] if farm.farm_id)


def collect_eligible_operational_sources(
    cases: Iterable[OperationalCaseRecord], farms_by_id: dict[str, OperationalFarmLocation], *,
    disease_code: str, disease_display: str, as_of: date, window_days: int, authorised_farms: frozenset[str],
) -> tuple[list[TimelineSource], Counter]:
    """The single operational eligibility rule: vet-verified, same disease,
    Asia/Colombo verification date inside [as_of - window_days, as_of], farm
    GPS valid and on the island; then one source per farm."""
    exclusions: Counter = Counter()
    seen_case_ids: set[str] = set()
    window_start, window_end = active_window(as_of, window_days)
    by_farm: dict[str, list[tuple[date, str]]] = {}
    case_numbers: dict[str, str] = {}

    for case in cases:
        if case.case_id in seen_case_ids:
            exclusions[EXCLUDED_DUPLICATE_CASE_RECORD] += 1
            continue
        seen_case_ids.add(case.case_id)
        if not case.verified:
            exclusions[EXCLUDED_NOT_VERIFIED] += 1
            continue
        if case.disease != disease_code:
            exclusions[EXCLUDED_WRONG_DISEASE] += 1
            continue
        verified_on = sri_lanka_date(case.verification_time)
        if verified_on is None:
            exclusions[EXCLUDED_MISSING_VERIFICATION_DATE] += 1
            continue
        if verified_on > window_end:
            exclusions[EXCLUDED_AFTER_AS_OF] += 1
            continue
        if verified_on < window_start:
            exclusions[EXCLUDED_OUTSIDE_WINDOW] += 1
            continue
        farm = farms_by_id.get(case.farm_id) if case.farm_id else None
        if farm is None or not farm.location_valid or not _valid_lat_lon(farm.latitude, farm.longitude):
            exclusions[EXCLUDED_INVALID_COORDINATES] += 1
            continue
        if not _inside_study_area(farm.latitude, farm.longitude):
            # A stored coordinate off the island (0,0 default, swapped lat/lon,
            # foreign point) is a data-entry error, never a Sri Lanka source.
            exclusions[EXCLUDED_OUTSIDE_STUDY_AREA] += 1
            continue
        by_farm.setdefault(case.farm_id, []).append((verified_on, case.case_id))
        if case.case_number:
            case_numbers[case.case_id] = case.case_number

    sources = []
    for farm_id, members in sorted(by_farm.items()):
        farm = farms_by_id[farm_id]
        if len(members) > 1:
            exclusions[EXCLUDED_DUPLICATE_SAME_FARM] += len(members) - 1
        authorised = farm_id in authorised_farms
        case_ids = sorted(case_id for _, case_id in members)
        sources.append(TimelineSource(
            source_id=f"OP:{disease_code}:{operational_farm_key(farm_id)}",
            record_domain=RECORD_DOMAIN_OPERATIONAL,
            disease=disease_display,
            latitude=float(farm.latitude),
            longitude=float(farm.longitude),
            observation_date=max(d for d, _ in members).isoformat(),
            provenance=PROVENANCE_OPERATIONAL,
            # Authorised: the raw case ids the vet already sees. Otherwise the
            # same one-way record keys `/national-cases` returns.
            member_record_ids=tuple(case_ids) if authorised else tuple(sorted(record_key(c) for c in case_ids)),
            gps_quality="FARM_GPS",
            farm_id=farm_id if authorised else None,
            detail_access=DETAIL_AUTHORISED_FARM if authorised else DETAIL_PRIVACY_REDUCED,
            case_refs=tuple(case_numbers[c] for _, c in sorted(members, reverse=True) if c in case_numbers) if authorised else (),
        ))
    return sources, exclusions


def collect_national_operational_sources(
    case_documents: Iterable[dict[str, Any]], farm_documents_by_id: dict[str, dict[str, Any]], *,
    disease_code: str, disease_display: str, as_of: date, window_days: int, authorised_farms: frozenset[str],
) -> tuple[list[TimelineSource], Counter]:
    """Nationwide pool from the host's read-only projection
    (`MongoOperationalDataPort.get_national_case_documents`)."""
    from ...repositories.host_operational_adapter import host_timestamp_text

    cases = []
    for doc in case_documents:
        if doc.get("_id") is None:
            continue
        disease = resolve_operational_disease(doc.get("disease_name"))
        cases.append(OperationalCaseRecord(
            case_id=str(doc["_id"]),
            farm_id=str(doc["farm_id"]) if doc.get("farm_id") else None,
            disease=disease.value if disease else None,
            verified=doc.get("verified") is True,
            verification_time=host_timestamp_text(doc.get("verified_at")),
            case_number=str(doc["case_number"]).strip() or None if doc.get("case_number") else None,
        ))
    farms = {
        str(farm_id): OperationalFarmLocation(
            farm_id=str(farm_id), latitude=doc.get("latitude"), longitude=doc.get("longitude"),
            location_valid=_has_valid_coordinates(doc.get("latitude"), doc.get("longitude")),
        )
        for farm_id, doc in farm_documents_by_id.items()
    }
    return collect_eligible_operational_sources(
        cases, farms, disease_code=disease_code, disease_display=disease_display, as_of=as_of,
        window_days=window_days, authorised_farms=authorised_farms,
    )


def collect_operational_sources(
    context: OperationalGeospatialContext, *, disease_code: str, disease_display: str, as_of: date, window_days: int,
) -> tuple[list[TimelineSource], Counter]:
    """Fallback pool when the port has no national case reader: only the
    vet-authorised verified clinical contexts (assigned + registered-district
    surveillance). The service reports this explicitly, never silently."""
    farms = {
        farm.farm_id: OperationalFarmLocation(
            farm_id=farm.farm_id, latitude=farm.latitude, longitude=farm.longitude,
            location_valid=farm.location_status == "VALID",
        )
        for farm in [*context.farms, *context.surveillance_farms]
    }
    seen: set[str] = set()
    cases = []
    for case in [*context.clinical_contexts, *context.surveillance_contexts]:
        if case.case_id in seen:  # the same case is listed in both scopes
            continue
        seen.add(case.case_id)
        cases.append(OperationalCaseRecord(case_id=case.case_id, farm_id=case.farm_id, disease=case.disease,
                                           verified=True, verification_time=case.verification_time))
    return collect_eligible_operational_sources(
        cases, farms, disease_code=disease_code, disease_display=disease_display, as_of=as_of,
        window_days=window_days, authorised_farms=authorised_farm_ids(context),
    )


class HistoricalSourceReader(Protocol):
    def eligible_sources(self, *, disease: str, as_of: str, window_days: int, country: str) -> list[EligibleSource]: ...


class RepositoryHistoricalSourceReader:
    """Reads the scientific repository through the shared provider (MongoDB in
    the running app) with the frozen 10A eligibility parameters. Read-only."""

    def eligible_sources(self, *, disease: str, as_of: str, window_days: int, country: str) -> list[EligibleSource]:
        repo = create_outbreak_repository()
        try:
            return get_eligible_sources(
                repo, disease=disease, t0=as_of, active_window_days=window_days,
                temporal_mode=ValidationMode.RETROSPECTIVE_PROXY, country_scope=country,
                domain_scope=RecordDomainScope.HISTORICAL_ONLY,
            ).sources
        finally:
            repo.close()


def historical_to_timeline_sources(eligible: list[EligibleSource]) -> tuple[list[TimelineSource], Counter]:
    exclusions: Counter = Counter()
    by_id: dict[str, TimelineSource] = {}
    for source in eligible:
        if not _valid_lat_lon(source.latitude, source.longitude):
            exclusions[EXCLUDED_INVALID_COORDINATES] += 1
            continue
        if source.source_id in by_id:
            exclusions[EXCLUDED_DUPLICATE_SAME_FARM] += 1
            continue
        by_id[source.source_id] = TimelineSource(
            source_id=f"HIST:{source.source_id}",
            record_domain=RECORD_DOMAIN_HISTORICAL,
            disease=source.disease or "",
            latitude=float(source.latitude),
            longitude=float(source.longitude),
            observation_date=str(source.effective_availability_date)[:10],
            provenance=PROVENANCE_HISTORICAL,
            member_record_ids=(source.source_id,),
            gps_quality=source.gps_quality,
        )
    return [by_id[k] for k in sorted(by_id)], exclusions

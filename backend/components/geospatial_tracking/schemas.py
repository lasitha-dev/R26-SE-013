"""Canonical data structures for PISTES raw outbreak records.

These represent a single source record (one CSV row, or one WAHIS PDF
outbreak block) BEFORE cross-source deduplication. Deduplication produces a
separate canonical dataset (Phase C) — records here are never merged or
mutated to "fill in" missing values from another source.

DATE SEMANTICS — three chronologies, never collapsed into one another:

  A. biological/event chronology — when the disease event actually happened:
     `outbreak_start_date`, `outbreak_end_date`, `event_start_date`,
     `event_end_date`, `onset_date`.
  B. source-document chronology — when a document about the event was filed:
     `confirmation_date`, `report_date`, `notification_date`. For WAHIS
     follow-up reports in particular, `report_date` is the filing date of
     the (possibly Nth, possibly final) report, which can trail the actual
     outbreak by months or years (Event_3473: report_date is ~3 years after
     confirmation_date; Event_3644: one 341-page final follow-up report
     covers 670 outbreak blocks spanning 2021-03 to 2024-01). It must never
     be read as "when the outbreak happened" or "when it became available".
  C. model operational availability — when a real-time surveillance system
     would have actually known about the outbreak. None of PISTES's current
     raw sources (WAHIS PDF, FAO EMPRES-i CSV) record this directly, so it
     is `operational_availability_date = None` /
     `operational_availability_quality = UNKNOWN` for every raw record
     produced today. It must never be silently inferred from (A) or (B) —
     in particular, never from a follow-up report's `report_date`, since
     that would make a 2021 outbreak reported in a 2024 final follow-up
     report look like a "2024 outbreak" to any date-ordered model input.

See `proxy_availability_date` / `proxy_availability_quality` below for the
separate, explicitly-labeled RETROSPECTIVE_PROXY-mode substitute, and
`ValidationMode` for how the two later validation modes consume these
fields differently.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum


class GpsQuality(str, Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    COARSE = "COARSE"
    UNKNOWN = "UNKNOWN"


class AvailabilityQuality(str, Enum):
    """Quality/provenance label for an availability-date field.

    ACTUAL means the date is defensible real operational availability
    (system-known-by evidence) — it must never be assigned without that
    evidence. The *_PROXY values mark research-only substitutes and must
    never be presented as ACTUAL. UNKNOWN means no defensible date exists
    for that field on this record.
    """

    ACTUAL = "ACTUAL"
    CONFIRMATION_PROXY = "CONFIRMATION_PROXY"
    REPORT_PROXY = "REPORT_PROXY"
    EVENT_DATE_PROXY = "EVENT_DATE_PROXY"
    OBSERVATION_DATE_PROXY = "OBSERVATION_DATE_PROXY"
    UNKNOWN = "UNKNOWN"


class ValidationMode(str, Enum):
    """Two future validation modes this schema must support (not yet
    implemented — no historical episodes are built from these today).

    STRICT_OPERATIONAL: only records with a defensible
    `operational_availability_date` (`operational_availability_quality`
    other than UNKNOWN) may participate as "known by date X". Records
    without one are excluded rather than backfilled with a guess.

    RETROSPECTIVE_PROXY: research/sensitivity-analysis only. May use
    `proxy_availability_date` / `proxy_availability_quality` (e.g.
    EVENT_DATE_PROXY, OBSERVATION_DATE_PROXY) as a documented stand-in for
    availability. Must never be reported or labeled as real-time
    operational availability.
    """

    STRICT_OPERATIONAL = "STRICT_OPERATIONAL"
    RETROSPECTIVE_PROXY = "RETROSPECTIVE_PROXY"


class SourceSystem(str, Enum):
    WAHIS_PDF = "WAHIS_PDF"
    FAO_EMPRESI_CSV = "FAO_EMPRESI_CSV"
    # FMD-03: FAO EMPRES-i's public BigQuery-backed export (the API behind
    # data.apps.fao.org's "Major diseases (by date)" CSV download). Same
    # underlying EMPRES-i system as FAO_EMPRESI_CSV but a materially
    # different column layout (see data_processing/fmd_source_adapter.py),
    # so it gets its own source_system value rather than being silently
    # conflated with the "Latest Reported Events" UI export.
    FAO_EMPRESI_BIGQUERY_CSV = "FAO_EMPRESI_BIGQUERY_CSV"


@dataclass
class RawOutbreakRecord:
    """One source-level outbreak/event observation.

    Every field is Optional in practice (default None) because raw sources
    are incomplete. Never fabricate a value to fill a gap — leave it None
    and let the relevant `*_quality` / status field say why.
    """

    # provenance — never inferred, always literal to the source
    source_file: str
    source_system: str  # SourceSystem value

    country: str | None = None
    disease: str | None = None

    event_id: str | None = None
    outbreak_id: str | None = None
    outbreak_reference: str | None = None

    # date semantics — preserved separately, never collapsed (see DATE SEMANTICS rule)
    event_start_date: str | None = None
    event_end_date: str | None = None
    outbreak_start_date: str | None = None
    outbreak_end_date: str | None = None
    onset_date: str | None = None
    confirmation_date: str | None = None
    notification_date: str | None = None
    report_date: str | None = None

    # (C) model operational availability — see module docstring. Populated
    # only from real "system knew by" evidence; never inferred from A or B.
    operational_availability_date: str | None = None
    operational_availability_quality: str = AvailabilityQuality.UNKNOWN.value

    # RETROSPECTIVE_PROXY-mode-only substitute for (C), explicitly labeled
    # via *_quality so it can never be mistaken for real availability.
    proxy_availability_date: str | None = None
    proxy_availability_quality: str = AvailabilityQuality.UNKNOWN.value

    admin1: str | None = None
    admin2: str | None = None
    admin3: str | None = None
    locality: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    gps_quality: str = GpsQuality.UNKNOWN.value
    approximate_location: bool = False

    species: str | None = None

    susceptible: int | None = None
    cases: int | None = None
    deaths: int | None = None
    killed_disposed: int | None = None
    vaccinated: int | None = None

    diagnostic_method: str | None = None
    diagnostic_result: str | None = None

    event_status: str | None = None
    source_notes: str | None = None

    # free-form, source-specific fields that don't map cleanly to the
    # canonical schema but are worth retaining for audit/debugging
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            self.operational_availability_quality == AvailabilityQuality.ACTUAL.value
            and self.operational_availability_date is None
        ):
            raise ValueError(
                "operational_availability_quality=ACTUAL requires a non-None "
                "operational_availability_date as evidence"
            )
        if self.proxy_availability_quality == AvailabilityQuality.ACTUAL.value:
            raise ValueError(
                "proxy_availability_quality must never be ACTUAL — proxy fields "
                "are RETROSPECTIVE_PROXY-mode substitutes, never real operational "
                "availability"
            )

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


CANONICAL_FIELD_NAMES: list[str] = [f.name for f in fields(RawOutbreakRecord)]


class DedupConfidence(str, Enum):
    """Transparent, non-numeric confidence categories for a duplicate group.

    These are deliberately categorical, not a score — see Checkpoint 2 rule
    "do not convert arbitrary scores into scientific confidence". Each tier
    corresponds to a documented evidence combination in `dedup.py`.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DedupStatus(str, Enum):
    """Per-record deduplication resolution state for the Checkpoint 2.5
    conservative/model-candidate view. See `data_processing/model_candidate.py`.

    SINGLETON: no duplicate candidate at all — stands alone.
    AUTO_MERGED_HIGH: collapsed into one canonical record because every
        member of its group met the documented HIGH-confidence criteria.
    REVIEW_MEDIUM / REVIEW_LOW: an unresolved duplicate candidate — kept
        as its own record, never silently merged or silently treated as a
        clean singleton, pending human review.
    MANUALLY_ACCEPTED / MANUALLY_REJECTED: reserved for a future manual
        adjudication step (not produced automatically by this pipeline
        today) — a human confirmed the candidate match should merge
        (ACCEPTED) or confirmed the records are NOT duplicates of each
        other (REJECTED, record reverts to standing alone).
    """

    SINGLETON = "SINGLETON"
    AUTO_MERGED_HIGH = "AUTO_MERGED_HIGH"
    REVIEW_MEDIUM = "REVIEW_MEDIUM"
    REVIEW_LOW = "REVIEW_LOW"
    MANUALLY_ACCEPTED = "MANUALLY_ACCEPTED"
    MANUALLY_REJECTED = "MANUALLY_REJECTED"


DEDUP_RESOLVED_STATUSES: frozenset[str] = frozenset(
    {DedupStatus.SINGLETON.value, DedupStatus.AUTO_MERGED_HIGH.value, DedupStatus.MANUALLY_ACCEPTED.value}
)
"""The single shared definition of "dedup resolved" used everywhere a
historical record's eligibility depends on it (services/source_selector.py,
services/target_quality.py, services/forecast_target.py) — REVIEW_MEDIUM
and REVIEW_LOW are excluded, MANUALLY_REJECTED is excluded (a rejected
match still needs a human decision about what the record becomes), only
these three statuses count as resolved."""


@dataclass
class NormalizedOutbreakRecord:
    """Pre-dedup, common-schema view of one raw source record.

    One row per raw CSV row / WAHIS outbreak block, produced by
    `data_processing/normalize.py`. Never merges or fabricates values —
    it is a reshaping/annotation step over `RawOutbreakRecord`, adding:

    - `source_record_id`: a deterministic id derived from
      (source_system, source_file, position-in-file), stable across runs
      given the same input files and parser version.
    - `spatial_independence`: whether this record's coordinates can be
      treated as this outbreak's own independent point (see
      `normalize.py` for the exact rule) — None when coordinates are
      missing, since independence cannot be assessed without them.
    - `proxy_availability_source_field`: the literal name of the field
      `proxy_availability_date` was copied from (e.g. "outbreak_start_date",
      "observation_date"), so the RETROSPECTIVE_PROXY substitution is
      always auditable back to its source field, never opaque.
    """

    source_record_id: str
    source_file: str
    source_system: str
    country: str | None = None
    disease: str | None = None

    event_id: str | None = None
    outbreak_id: str | None = None
    outbreak_reference: str | None = None

    event_start_date: str | None = None
    outbreak_start_date: str | None = None
    onset_date: str | None = None
    confirmation_date: str | None = None
    report_date: str | None = None

    operational_availability_date: str | None = None
    operational_availability_quality: str = AvailabilityQuality.UNKNOWN.value
    proxy_availability_date: str | None = None
    proxy_availability_quality: str = AvailabilityQuality.UNKNOWN.value
    proxy_availability_source_field: str | None = None

    admin1: str | None = None
    admin2: str | None = None
    admin3: str | None = None
    locality: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    gps_quality: str = GpsQuality.UNKNOWN.value
    approximate_location: bool = False
    spatial_independence: bool | None = None

    species: str | None = None
    species_normalized: str | None = None

    susceptible: int | None = None
    cases: int | None = None
    deaths: int | None = None
    killed_disposed: int | None = None
    vaccinated: int | None = None

    diagnostic_method: str | None = None
    diagnostic_result: str | None = None

    event_status: str | None = None
    source_notes: str | None = None

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


NORMALIZED_FIELD_NAMES: list[str] = [f.name for f in fields(NormalizedOutbreakRecord)]

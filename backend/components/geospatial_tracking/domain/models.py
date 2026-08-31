"""Checkpoint 3 domain objects.

Four record types, deliberately kept small:

- `AnimalReport` — one live submission (LIVE_OPERATIONAL_RECORD domain).
  The raw unit of input; never itself the unit PISTES reasons about.
- `OutbreakEpisode` — the live domain's aggregated unit PISTES actually
  consumes, built from one or more `AnimalReport`s by
  `services/aggregation.py`. Never every button press.
- `HistoricalOutbreakRecord` — one row from the Checkpoint 2.5 conservative
  canonical dataset (HISTORICAL_RESEARCH_RECORD domain), imported for
  retrospective research use by `services/historical_import.py`.
- `PredictionRun` — an audit record of one forecast invocation (t0,
  temporal mode, which sources were used). No prediction/risk logic exists
  yet this checkpoint; this is storage-only scaffolding for later use.

Nothing here invents a value: every field defaults to `None`/a documented
neutral value, and no service is allowed to fabricate one to fill a gap.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

from ..schemas import AvailabilityQuality, DedupStatus, GpsQuality, ValidationMode
from .enums import RecordDomain, ReportStatus


@dataclass
class AnimalReport:
    """One live submission — LIVE_OPERATIONAL_RECORD domain only.

    Date fields are kept deliberately separate and never collapsed:
    `onset_date` is the BIOLOGICAL symptom/onset date (what the farmer/vet
    observed); `submitted_at`, `notification_date`, `confirmation_date`,
    `accepted_at` are OPERATIONAL/workflow timestamps (when the system's
    process reached that stage); `created_at` is a pure STORAGE timestamp
    (row insertion time) and must never be read as either of the above —
    see DATE-01 in test_source_selector.py and REPOSITORY_DESIGN.md.
    """

    report_id: str
    disease: str
    farm_id: str | None = None
    animal_id: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    onset_date: str | None = None  # biological: symptom/onset date
    submitted_at: str | None = None  # operational: when the report reached the system
    notification_date: str | None = None
    confirmation_date: str | None = None
    accepted_at: str | None = None  # operational: when the system formally accepted it

    status: str = ReportStatus.SUBMITTED.value
    source: str | None = None
    created_at: str | None = None  # storage-only — never biological or operational

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class OutbreakEpisode:
    """The live domain's aggregated unit — see `services/aggregation.py`
    for how a set of `AnimalReport`s becomes one of these. Repeated
    submissions of the same animal, or unrelated reports that merely share
    a GPS coordinate, must never inflate `affected_animals` or split into
    spurious episodes — the aggregation service documents and tests this.

    Checkpoint 3.5 separates FOUR previously-conflated concepts, each with
    its own field(s) — never collapse one into another:

    1. `onset_date` — REAL biological symptom/onset date only (from
       `AnimalReport.onset_date`). `None` when no report in the episode
       has a documented onset date. NEVER populated from `submitted_at`,
       `notification_date`, `confirmation_date`, `accepted_at`, or
       `created_at` — see `services/aggregation.py`'s CRITICAL BUG fix.
    2. `episode_grouping_date` / `episode_grouping_date_quality` — the
       date value actually used to decide which reports cluster into this
       episode. Prefers a biological onset date
       (`GroupingDateQuality.BIOLOGICAL_DATE`); falls back to an
       operational workflow timestamp ONLY for clustering purposes
       (`GroupingDateQuality.OPERATIONAL_PROXY` — never presented as
       biological time); `GroupingDateQuality.UNKNOWN` /
       `episode_grouping_date = None` when no defensible date exists at
       all (see `aggregation_review_required` below).
    3. `operational_availability_date` / `_quality` — when the LIVE system
       could actually use this episode. May legitimately reach `ACTUAL`
       (unlike the historical domain), but ONLY from a real
       accepted/confirmed workflow timestamp — see
       `services/aggregation.py`'s documented hierarchy. Never inferred
       from `onset_date`, `episode_grouping_date`, or `created_at`.
    4. `affected_animals` / `affected_animals_quality` /
       `unidentified_report_count` — an uncertainty-aware animal count,
       never a silently-assumed exact figure. See
       `domain.enums.AnimalCountQuality` and
       `services/aggregation.py`'s CASE A/B/C.

    `aggregation_review_required` is set when reports at the same
    (farm_id, disease) could not be confidently clustered by date or by a
    shared known `animal_id` — see `services/aggregation.py` §"reports
    with no reliable grouping date".
    """

    outbreak_id: str
    disease: str
    farm_id: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    affected_animals: int | None = None
    affected_animals_quality: str = "UNKNOWN"  # AnimalCountQuality value
    unidentified_report_count: int = 0

    onset_date: str | None = None  # REAL biological onset only — see class docstring point 1

    episode_grouping_date: str | None = None
    episode_grouping_date_quality: str = "UNKNOWN"  # GroupingDateQuality value
    aggregation_review_required: bool = False

    operational_availability_date: str | None = None
    operational_availability_quality: str = AvailabilityQuality.UNKNOWN.value

    status: str = ReportStatus.SUBMITTED.value
    gps_quality: str = GpsQuality.UNKNOWN.value
    date_quality: str = "UNKNOWN"

    source_report_ids: list[str] = field(default_factory=list)
    record_domain: str = RecordDomain.LIVE_OPERATIONAL_RECORD.value
    created_at: str | None = None

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class HistoricalOutbreakRecord:
    """One row imported from Checkpoint 2.5's
    `canonical_outbreaks_conservative.csv` — HISTORICAL_RESEARCH_RECORD
    domain only. Preserves full provenance (dedup status, both
    availability-date pairs, GPS quality) so the scientific eligibility
    gate can be enforced at query time (`services/source_selector.py`)
    without needing to re-derive anything from source files.

    `operational_availability_quality` is `UNKNOWN` for every record in
    the current corpus (see `DATA_AUDIT.md`) — this class does not change
    that, it only carries it through faithfully.
    """

    source_record_id: str
    country: str | None = None
    disease: str | None = None

    event_id: str | None = None
    outbreak_id: str | None = None

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

    latitude: float | None = None
    longitude: float | None = None
    gps_quality: str = GpsQuality.UNKNOWN.value

    species: str | None = None

    dedup_status: str = DedupStatus.SINGLETON.value
    dedup_confidence: str | None = None
    model_candidate: bool = False
    duplicate_group_id: str | None = None
    member_record_ids: str | None = None

    record_domain: str = RecordDomain.HISTORICAL_RESEARCH_RECORD.value
    imported_at: str | None = None

    def __post_init__(self) -> None:
        # Same guard as RawOutbreakRecord (schemas.py) — defense in depth
        # at the domain/repository layer too, not just at parse time.
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

    def effective_availability(self, mode: ValidationMode) -> tuple[str | None, str]:
        """Returns (date, quality) for the requested temporal mode.

        STRICT_OPERATIONAL: only returns a date when
        `operational_availability_quality == ACTUAL` — i.e. real evidence.
        For every record in the current corpus this returns (None,
        UNKNOWN), by design (see DATA_AUDIT.md / DATA_PROVENANCE.md).

        RETROSPECTIVE_PROXY: returns the documented proxy date/quality
        pair, but ONLY when its quality is not UNKNOWN (a genuinely
        undocumented proxy is not usable evidence either). Never upgrades
        a proxy to ACTUAL — see `RawOutbreakRecord.__post_init__`, which
        already makes that impossible to construct.
        """
        if mode == ValidationMode.STRICT_OPERATIONAL:
            if self.operational_availability_quality == AvailabilityQuality.ACTUAL.value and self.operational_availability_date:
                return self.operational_availability_date, self.operational_availability_quality
            return None, AvailabilityQuality.UNKNOWN.value
        if mode == ValidationMode.RETROSPECTIVE_PROXY:
            if self.proxy_availability_date and self.proxy_availability_quality != AvailabilityQuality.UNKNOWN.value:
                return self.proxy_availability_date, self.proxy_availability_quality
            return None, AvailabilityQuality.UNKNOWN.value
        raise ValueError(f"unknown temporal mode: {mode!r}")

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class PredictionRun:
    """Audit record of one forecast invocation. Storage-only scaffolding —
    no prediction/risk logic exists yet. `model_version`/`config_hash` are
    nullable on purpose: they must not be fabricated before a model is
    actually frozen (master-prompt §15)."""

    prediction_id: str
    forecast_origin_t0: str
    temporal_mode: str
    primary_source_id: str | None = None
    active_source_ids: list[str] = field(default_factory=list)
    model_version: str | None = None
    config_hash: str | None = None
    created_at: str | None = None

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

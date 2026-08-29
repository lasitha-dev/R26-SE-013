"""Checkpoint 4.5 Part 7: explicit historical trigger-candidate enumeration.

Replaces Checkpoint 4's far-future-t0 / huge-window discovery hack in
`services/forecast_origin.py`. That trick worked, but was unnecessary
indirection through `get_eligible_sources`'s T0/window machinery purely to
defeat its own window check — and it already caused one real bug (an
insufficiently large "huge window" constant that silently undercounted
until caught before the Checkpoint 4 real-data run). This module
enumerates eligible historical triggers directly, with no synthetic date
and no window trick at all.

Mirrors (does not import, to keep this genuinely independent of the T0
machinery it replaces) the same non-temporal eligibility gates
`source_selector._historical_eligible` applies: HISTORICAL domain only (by
construction — this module never reads `outbreak_episodes`),
`model_candidate = True`, dedup resolved
(`schemas.DEDUP_RESOLVED_STATUSES`), disease match (normalized), and valid
coordinates. The one gate this module does NOT apply is the t0/window
check — a trigger candidate is not evaluated "as of" any particular date;
it simply reports its own real effective RETROSPECTIVE_PROXY availability
date. `HistoricalOutbreakRecord.effective_availability` already makes it
structurally impossible for this to ever report `ACTUAL` under
RETROSPECTIVE_PROXY mode — the proxy is never upgraded.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..repositories.base import OutbreakRepository
from ..schemas import DEDUP_RESOLVED_STATUSES, ValidationMode
from .dates import parse_flexible_date
from .disease import normalize_disease


@dataclass
class HistoricalTriggerCandidate:
    source_id: str
    country: str | None
    disease: str | None
    effective_availability_date: str
    availability_quality: str

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "country": self.country,
            "disease": self.disease,
            "effective_availability_date": self.effective_availability_date,
            "availability_quality": self.availability_quality,
        }


def list_historical_trigger_candidates(
    repo: OutbreakRepository,
    *,
    disease: str,
    country_scope: str | None = None,
    temporal_mode: ValidationMode = ValidationMode.RETROSPECTIVE_PROXY,
) -> list[HistoricalTriggerCandidate]:
    """Deterministic: sorted by `source_id`, so repeated calls against
    unchanged data always return the same list in the same order (see
    DISCOVERY-04 / ORIGIN-01)."""
    target_disease = normalize_disease(disease)
    candidates: list[HistoricalTriggerCandidate] = []

    for record in repo.list_historical_records(country=country_scope):
        if not record.model_candidate:
            continue
        if record.dedup_status not in DEDUP_RESOLVED_STATUSES:
            continue
        if normalize_disease(record.disease) != target_disease:
            continue
        if record.latitude is None or record.longitude is None:
            continue

        avail_date_str, avail_quality = record.effective_availability(temporal_mode)
        if avail_date_str is None:
            continue
        avail_date = parse_flexible_date(avail_date_str)
        if avail_date is None:
            continue

        candidates.append(
            HistoricalTriggerCandidate(
                source_id=record.source_record_id,
                country=record.country,
                disease=record.disease,
                effective_availability_date=avail_date.isoformat(),
                availability_quality=avail_quality,
            )
        )

    candidates.sort(key=lambda c: c.source_id)
    return candidates

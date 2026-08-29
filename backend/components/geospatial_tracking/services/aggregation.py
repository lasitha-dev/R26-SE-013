"""Report -> outbreak episode aggregation (LIVE_OPERATIONAL_RECORD domain).

PISTES must consume outbreak episodes, not every individual animal report
(master-prompt Checkpoint 3 §3). This is a deliberately conservative,
fully documented aggregation rule — not a claimed epidemiological model.

CHECKPOINT 3.5 CORRECTIONS (read this before touching this file):

Checkpoint 3's `_best_report_date` mixed a report's biological onset date
with its operational workflow timestamps (`submitted_at`,
`notification_date`, `confirmation_date`, `accepted_at`) into one generic
"best date", which then flowed straight into `OutbreakEpisode.onset_date`.
That is a real bug: a system/operational timestamp silently became a
claimed biological onset date. This file now keeps FOUR concepts
completely separate, at every step:

1. BIOLOGICAL ONSET (`OutbreakEpisode.onset_date`) — only ever populated
   from `AnimalReport.onset_date`. `None` when no report in the episode
   has one. Never derived from any operational or storage timestamp.

2. EPISODE GROUPING DATE (`episode_grouping_date` /
   `episode_grouping_date_quality`) — the date value actually used to
   decide which reports cluster together. Fallback hierarchy, applied
   per report:
       a. `onset_date` (biological)                  -> BIOLOGICAL_DATE
       b. `submitted_at`                              -> OPERATIONAL_PROXY
       c. `notification_date`                         -> OPERATIONAL_PROXY
       d. `confirmation_date`                          -> OPERATIONAL_PROXY
       e. `accepted_at`                                -> OPERATIONAL_PROXY
       f. (none of the above)                          -> UNKNOWN, date=None
   An OPERATIONAL_PROXY grouping date is used ONLY to decide clustering —
   it is never copied into `onset_date` and never described as biological
   event time.

3. REPORTS WITH NO GROUPING DATE — same (farm_id, disease) reports that
   have no defensible date (case f above) are NEVER silently merged into
   whatever episode happens to be temporally adjacent. They are attached
   to an existing dated cluster ONLY when they share a known `animal_id`
   with a report already in that cluster (strong identity evidence, no
   date needed). Anything left over is grouped only by shared `animal_id`
   among itself, or stands alone. EVERY episode assembled this way sets
   `aggregation_review_required = True` — its placement in the farm's
   outbreak timeline is unconfirmed and needs a human's eyes
   (master-prompt §4, option B; see `_cluster_group`).

4. OPERATIONAL AVAILABILITY (`operational_availability_date` / `_quality`)
   — derived ONLY from a genuine accepted/confirmed workflow timestamp,
   with a documented, conservative priority:
       a. earliest `accepted_at` among ACCEPTED/CONFIRMED reports -> ACTUAL
       b. earliest `confirmation_date` among CONFIRMED reports, only if
          (a) found nothing                                      -> ACTUAL
       c. neither exists                                          -> UNKNOWN
   NEVER `onset_date`, `created_at`, or a bare `submitted_at`.

Animal-count uncertainty (`affected_animals` / `affected_animals_quality`
/ `unidentified_report_count`) — see `_affected_animal_count`:

    CASE A — every report has animal_id:
        affected_animals = distinct animal_id count, quality = EXACT.
    CASE B — some reports have animal_id, some don't:
        affected_animals = distinct KNOWN animal_id count (a lower
        bound — two unidentified reports might be the same animal),
        quality = LOWER_BOUND, unidentified_report_count = the rest.
    CASE C — no report has animal_id:
        affected_animals = None, quality = UNKNOWN,
        unidentified_report_count = all of them.

Repeated ingestion of the same `report_id` is deduplicated (keeping the
first occurrence) before any grouping/counting happens — see
`_dedupe_by_report_id` — so re-submitting the same report can never
inflate an animal count or contribute twice to an episode.
"""

from __future__ import annotations

from datetime import date

from ..domain.enums import AnimalCountQuality, GroupingDateQuality, RecordDomain, ReportStatus
from ..domain.models import AnimalReport, OutbreakEpisode
from ..schemas import AvailabilityQuality, GpsQuality
from .dates import parse_flexible_date
from .disease import normalize_disease

_STATUS_PRIORITY = {
    ReportStatus.REJECTED.value: 0,
    ReportStatus.SUBMITTED.value: 1,
    ReportStatus.ACCEPTED.value: 2,
    ReportStatus.CONFIRMED.value: 3,
}

# priority order for the EPISODE GROUPING DATE fallback, checked only
# after AnimalReport.onset_date (biological) has already failed to parse.
_OPERATIONAL_PROXY_FIELDS = ("submitted_at", "notification_date", "confirmation_date", "accepted_at")


def _dedupe_by_report_id(reports: list[AnimalReport]) -> list[AnimalReport]:
    """Same report_id submitted more than once = one report. Keeps the
    first occurrence; does not attempt to merge/reconcile differing field
    values across duplicates (they are expected to be identical resends,
    not conflicting versions)."""
    seen: dict[str, AnimalReport] = {}
    for r in reports:
        if r.report_id not in seen:
            seen[r.report_id] = r
    return list(seen.values())


def _grouping_date_for_report(r: AnimalReport) -> tuple[date | None, str]:
    bio = parse_flexible_date(r.onset_date)
    if bio is not None:
        return bio, GroupingDateQuality.BIOLOGICAL_DATE.value
    for field_name in _OPERATIONAL_PROXY_FIELDS:
        parsed = parse_flexible_date(getattr(r, field_name))
        if parsed is not None:
            return parsed, GroupingDateQuality.OPERATIONAL_PROXY.value
    return None, GroupingDateQuality.UNKNOWN.value


def _affected_animal_count(reports: list[AnimalReport]) -> tuple[int | None, str, int]:
    """Returns (affected_animals, affected_animals_quality, unidentified_report_count)."""
    identified = {r.animal_id for r in reports if r.animal_id}
    unidentified_count = sum(1 for r in reports if not r.animal_id)
    if unidentified_count == 0:
        return len(identified), AnimalCountQuality.EXACT.value, 0
    if identified:
        return len(identified), AnimalCountQuality.LOWER_BOUND.value, unidentified_count
    return None, AnimalCountQuality.UNKNOWN.value, unidentified_count


def _episode_status(reports: list[AnimalReport]) -> str:
    return max(
        (r.status for r in reports),
        key=lambda s: _STATUS_PRIORITY.get(s, _STATUS_PRIORITY[ReportStatus.SUBMITTED.value]),
    )


def _operational_availability(reports: list[AnimalReport]) -> tuple[str | None, str]:
    accepted = [
        parsed
        for r in reports
        if r.status in (ReportStatus.ACCEPTED.value, ReportStatus.CONFIRMED.value)
        for parsed in [parse_flexible_date(r.accepted_at)]
        if parsed is not None
    ]
    if accepted:
        return min(accepted).isoformat(), AvailabilityQuality.ACTUAL.value

    confirmed = [
        parsed
        for r in reports
        if r.status == ReportStatus.CONFIRMED.value
        for parsed in [parse_flexible_date(r.confirmation_date)]
        if parsed is not None
    ]
    if confirmed:
        return min(confirmed).isoformat(), AvailabilityQuality.ACTUAL.value

    return None, AvailabilityQuality.UNKNOWN.value


def _episode_grouping_summary(reports: list[AnimalReport]) -> tuple[str | None, str]:
    """The stored (episode_grouping_date, episode_grouping_date_quality)
    for an already-assembled episode: the earliest BIOLOGICAL_DATE among
    its reports if any exist, else the earliest OPERATIONAL_PROXY, else
    (None, UNKNOWN)."""
    candidates = [_grouping_date_for_report(r) for r in reports]
    dated = [(d, q) for d, q in candidates if d is not None]
    if not dated:
        return None, GroupingDateQuality.UNKNOWN.value
    biological = [(d, q) for d, q in dated if q == GroupingDateQuality.BIOLOGICAL_DATE.value]
    chosen = min(biological, key=lambda t: t[0]) if biological else min(dated, key=lambda t: t[0])
    return chosen[0].isoformat(), chosen[1]


def _build_episode(
    outbreak_id: str,
    farm_id: str | None,
    disease: str,
    reports: list[AnimalReport],
    *,
    aggregation_review_required: bool,
) -> OutbreakEpisode:
    bio_dates = [d for d in (parse_flexible_date(r.onset_date) for r in reports) if d is not None]
    onset_date = min(bio_dates).isoformat() if bio_dates else None

    episode_grouping_date, episode_grouping_date_quality = _episode_grouping_summary(reports)

    operational_availability_date, operational_availability_quality = _operational_availability(reports)

    affected_animals, affected_animals_quality, unidentified_report_count = _affected_animal_count(reports)

    country = next((r.country for r in reports if r.country), None)
    lat = next((r.latitude for r in reports if r.latitude is not None), None)
    lon = next((r.longitude for r in reports if r.longitude is not None), None)
    # "EXACT" here means only "a real coordinate was submitted with this
    # live report" — not a WAHIS-style approximate/exact source flag.
    gps_quality = GpsQuality.EXACT.value if (lat is not None and lon is not None) else GpsQuality.UNKNOWN.value
    date_quality = "HIGH" if onset_date else "UNKNOWN"

    return OutbreakEpisode(
        outbreak_id=outbreak_id,
        disease=disease,
        farm_id=farm_id,
        country=country,
        latitude=lat,
        longitude=lon,
        affected_animals=affected_animals,
        affected_animals_quality=affected_animals_quality,
        unidentified_report_count=unidentified_report_count,
        onset_date=onset_date,
        episode_grouping_date=episode_grouping_date,
        episode_grouping_date_quality=episode_grouping_date_quality,
        aggregation_review_required=aggregation_review_required,
        operational_availability_date=operational_availability_date,
        operational_availability_quality=operational_availability_quality,
        status=_episode_status(reports),
        gps_quality=gps_quality,
        date_quality=date_quality,
        source_report_ids=sorted(r.report_id for r in reports),
        record_domain=RecordDomain.LIVE_OPERATIONAL_RECORD.value,
    )


def _cluster_group(
    group_reports: list[AnimalReport], *, episode_gap_days: int
) -> list[tuple[list[AnimalReport], bool]]:
    """One (farm_id, disease) group -> list of (cluster_reports,
    aggregation_review_required). See module docstring point 3."""
    dated: list[tuple[AnimalReport, date, str]] = []
    undated: list[AnimalReport] = []
    for r in group_reports:
        d, quality = _grouping_date_for_report(r)
        if d is not None:
            dated.append((r, d, quality))
        else:
            undated.append(r)

    dated.sort(key=lambda t: (t[1], t[0].report_id))
    clusters: list[list[tuple[AnimalReport, date, str]]] = []
    current: list[tuple[AnimalReport, date, str]] = []
    last_date: date | None = None
    for item in dated:
        _, d, _ = item
        if current and last_date is not None and (d - last_date).days > episode_gap_days:
            clusters.append(current)
            current = []
        current.append(item)
        last_date = d
    if current:
        clusters.append(current)

    result: list[tuple[list[AnimalReport], bool]] = []
    remaining_undated: list[AnimalReport] = list(undated)

    # Attach undated reports to a dated cluster ONLY via a shared known
    # animal_id already present in that cluster — strong identity
    # evidence overriding a missing date, never temporal-proximity
    # guesswork we don't actually have.
    for cluster in clusters:
        cluster_reports = [item[0] for item in cluster]
        cluster_animal_ids = {r.animal_id for r in cluster_reports if r.animal_id}
        attached = [r for r in remaining_undated if r.animal_id and r.animal_id in cluster_animal_ids]
        for r in attached:
            remaining_undated.remove(r)
        result.append((cluster_reports + attached, False))

    # Whatever is left has no defensible date AND no identity link to a
    # dated cluster — group only by shared animal_id among the leftovers
    # (still identity evidence, no date needed); anything with no
    # animal_id stands alone. Every episode built this way is flagged for
    # review (master-prompt §4, option B) — its temporal placement is
    # unconfirmed.
    while remaining_undated:
        r = remaining_undated.pop(0)
        group = [r]
        if r.animal_id:
            matches = [x for x in remaining_undated if x.animal_id == r.animal_id]
            for x in matches:
                remaining_undated.remove(x)
            group.extend(matches)
        result.append((group, True))

    return result


def aggregate_reports_into_episodes(
    reports: list[AnimalReport],
    *,
    episode_gap_days: int,
    id_prefix: str = "EP",
) -> list[OutbreakEpisode]:
    """`episode_gap_days` has NO default — callers must pass it
    explicitly (see config.py). Must be >= 0; 0 means reports must share
    the exact same grouping date to cluster together (deterministic: any
    gap of 1+ days starts a new episode)."""
    if episode_gap_days < 0:
        raise ValueError(f"episode_gap_days must be >= 0, got {episode_gap_days}")

    reports = _dedupe_by_report_id(reports)

    # Checkpoint 4 Part 0A: group by NORMALIZED disease, not the raw
    # string — "LSD" / "Lumpy skin disease" / "Lumpy skin disease virus
    # (Inf. with)" must aggregate as one disease identity, while genuinely
    # different diseases (e.g. LSD vs FMD) never collide (see
    # services/disease.py). The raw string a report actually carries is
    # still preserved for provenance/display — see `_build_episode`'s
    # `disease` argument below, which uses one cluster's own reports, not
    # the normalized grouping key.
    grouped: dict[tuple[str, str], list[AnimalReport]] = {}
    singletons: list[AnimalReport] = []
    for r in reports:
        if r.farm_id:
            disease_key = normalize_disease(r.disease) or r.disease.strip().lower()
            grouped.setdefault((r.farm_id, disease_key), []).append(r)
        else:
            singletons.append(r)

    episodes: list[OutbreakEpisode] = []
    episode_index = 0

    for (farm_id, _disease_key), group_reports in sorted(grouped.items()):
        for cluster_reports, review_required in _cluster_group(group_reports, episode_gap_days=episode_gap_days):
            episode_index += 1
            # representative RAW disease text for this specific cluster —
            # never the normalized key, which is an internal grouping
            # detail only.
            raw_disease = cluster_reports[0].disease
            episodes.append(
                _build_episode(
                    f"{id_prefix}-{episode_index:06d}",
                    farm_id,
                    raw_disease,
                    cluster_reports,
                    aggregation_review_required=review_required,
                )
            )

    for r in singletons:
        episode_index += 1
        # No farm_id at all — a distinct, already-documented policy from
        # Checkpoint 3 (never group without a farm/herd identifier), not
        # the "missing grouping date" case this file's §3 addresses.
        episodes.append(
            _build_episode(
                f"{id_prefix}-{episode_index:06d}", r.farm_id, r.disease, [r], aggregation_review_required=False
            )
        )

    return episodes

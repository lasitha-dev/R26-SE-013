"""Deterministic, explainable cross-source (and within-source) deduplication.

Hierarchical evidence matching per the Checkpoint 2 master-prompt rules:

  Level 0 — a known, differing `disease` value is an absolute gate (FMD-03):
  two records are never matched if both sides have a resolved disease and
  those diseases differ (e.g. FMD vs LSD) — see `disease.py`.

  Level 1 — same trusted outbreak/reference identifier, only when the two
  records share a source_system (WAHIS OB_ ids and FAO EMPRES-i Event IDs
  live in different namespaces and are NEVER treated as comparable).

  Level 2/3 — country + normalized locality + date-within-tolerance +
  coordinate-within-tolerance + species, combined into three transparent,
  documented confidence tiers (HIGH / MEDIUM / LOW). Coordinates alone
  NEVER establish a match: country agreement and date-within-tolerance are
  both hard gates before any spatial evidence is even considered, which is
  what keeps WAHIS's documented case of three distinct outbreak IDs sharing
  one approximate coordinate from being merged (see
  `test_approximate_coordinate_protection`).

Only HIGH and MEDIUM confidence groups are auto-merged into one canonical
record in the output dataset. LOW confidence candidates are reported (for
manual review) but never merged — "never merge solely because coordinates
are equal" is enforced structurally, not just by convention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from datetime import date, datetime

from ..schemas import DedupConfidence, GpsQuality, NormalizedOutbreakRecord
from .disease import normalize_disease
from .geo import haversine_km
from .species import species_matches

# ---- documented, fixed tolerances (never tuned against model performance) ----

DATE_TOLERANCE_DAYS = 3
"""Cross-source reporting lag tolerance for "same real-world outbreak
date". Chosen as a small, human-explainable buffer for admin-level
rounding/timezone/weekend-filing effects between two independently-typed
sources — not fit to any downstream metric."""

COORD_TOLERANCE_KM_TIGHT = 2.0
"""Distance below which two points are considered the same reported
location outright (village/farm-cluster scale)."""

COORD_TOLERANCE_KM_LOOSE = 5.0
"""Distance below which two points are still considered plausibly the same
locality (accounts for CSV vs. WAHIS geocoding to different reference
points within one administrative locality) but require corroborating
evidence (locality name or species) to count as a match at all."""

LOCALITY_MAX_EDIT_DISTANCE = 2
"""Tolerates small transliteration/typo differences (e.g. WAHIS "Vavuniya"
vs. CSV "Vavuniy") without accepting arbitrary fuzzy matches — gated by a
minimum normalized length so short names can't cheaply satisfy it."""

LOCALITY_MIN_LENGTH_FOR_FUZZY = 4

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")

_DATE_FORMATS = ("%Y/%m/%d", "%Y-%m-%d")

# preference order for "the" date used in matching — see best_match_date()
_DATE_FIELD_PRIORITY = ("outbreak_start_date", "onset_date", "event_start_date", "confirmation_date")


def normalize_locality(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = _NON_ALNUM.sub(" ", raw.lower())
    text = _WHITESPACE.sub(" ", text).strip()
    return text or None


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def locality_matches_strict(a: str | None, b: str | None) -> bool:
    """Exact match after normalization only — no fuzzy tolerance. Used
    specifically where a false-positive locality match would defeat the
    approximate-coordinate protection (see `match_pair`): two distinct
    real place names ("Village A" vs "Village B", "Ban Pa" vs "Ban Pha")
    can be within the general fuzzy-match edit distance by coincidence,
    and must not be allowed to justify merging outbreaks that only share
    an explicitly-approximate/snapped coordinate."""
    na, nb = normalize_locality(a), normalize_locality(b)
    if na is None or nb is None:
        return False
    return na == nb


def locality_matches(a: str | None, b: str | None) -> bool:
    """True on exact match after normalization, or a small edit distance
    when both normalized names are long enough for that to be meaningful
    (tolerates e.g. WAHIS "Vavuniya" vs CSV "Vavuniy"). Two missing
    localities never count as a match. NOT used for the
    approximate-coordinate protection gate — see `locality_matches_strict`."""
    na, nb = normalize_locality(a), normalize_locality(b)
    if na is None or nb is None:
        return False
    if na == nb:
        return True
    if len(na) < LOCALITY_MIN_LENGTH_FOR_FUZZY or len(nb) < LOCALITY_MIN_LENGTH_FOR_FUZZY:
        return False
    return _levenshtein(na, nb) <= LOCALITY_MAX_EDIT_DISTANCE


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def best_match_date(r: NormalizedOutbreakRecord) -> tuple[date, str] | None:
    """The single date field used for temporal matching, in priority
    order: the record's own outbreak/observation date first, falling back
    to broader event-level dates only when nothing more specific exists.
    Never `report_date` or `proxy_availability_date`/`confirmation_date`
    used as a stand-in for when the outbreak happened (see schemas.py DATE
    SEMANTICS) — confirmation_date is included only as a last resort, and
    report_date is deliberately excluded entirely."""
    for field_name in _DATE_FIELD_PRIORITY:
        raw_value = getattr(r, field_name)
        parsed = parse_date(raw_value)
        if parsed is not None:
            return parsed, field_name
    return None


@dataclass
class PairMatch:
    a_id: str
    b_id: str
    tier: str  # DedupConfidence value
    match_rule: str
    country_match: bool
    date_diff_days: int | None
    distance_km: float | None
    locality_match: bool
    species_match: bool


def match_pair(a: NormalizedOutbreakRecord, b: NormalizedOutbreakRecord) -> PairMatch | None:
    if a.source_record_id == b.source_record_id:
        return None

    # FMD-03 hard gate: never match two records with a KNOWN, DIFFERENT
    # disease (e.g. FMD vs LSD) — checked before Level 1 so even a trusted
    # identifier match can't override it. Two records with an unknown
    # disease on either side are neither blocked nor confirmed here; every
    # real source this pipeline parses always populates `disease`, so this
    # is a no-op for the existing single-disease LSD corpus (see
    # disease.py) and only becomes active once a second disease's data is
    # actually present.
    disease_a = normalize_disease(a.disease)
    disease_b = normalize_disease(b.disease)
    if disease_a is not None and disease_b is not None and disease_a != disease_b:
        return None

    # Level 1: trusted identifier, only comparable within the same source
    # system (cross-source ID namespaces never overlap in this dataset).
    if (
        a.source_system == b.source_system
        and a.outbreak_id
        and b.outbreak_id
        and a.outbreak_id == b.outbreak_id
        and a.source_file != b.source_file
    ):
        return PairMatch(
            a_id=a.source_record_id,
            b_id=b.source_record_id,
            tier=DedupConfidence.HIGH.value,
            match_rule="LEVEL_1_TRUSTED_IDENTIFIER",
            country_match=(a.country or "").strip().lower() == (b.country or "").strip().lower(),
            date_diff_days=None,
            distance_km=None,
            locality_match=locality_matches(a.locality, b.locality),
            species_match=species_matches(a.species, b.species),
        )

    # Hard gate: country. Never merge across different countries.
    country_a = (a.country or "").strip().lower()
    country_b = (b.country or "").strip().lower()
    if not country_a or not country_b or country_a != country_b:
        return None

    # Hard gate: date-within-tolerance. Coordinates alone never establish
    # a match — both records must have a usable date, and it must agree.
    date_a = best_match_date(a)
    date_b = best_match_date(b)
    if date_a is None or date_b is None:
        return None
    date_diff_days = abs((date_a[0] - date_b[0]).days)
    if date_diff_days > DATE_TOLERANCE_DAYS:
        return None

    distance_km = None
    if a.latitude is not None and a.longitude is not None and b.latitude is not None and b.longitude is not None:
        distance_km = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)

    locality_match = locality_matches(a.locality, b.locality)
    species_match = species_matches(a.species, b.species)

    tight_spatial = distance_km is not None and distance_km <= COORD_TOLERANCE_KM_TIGHT
    loose_spatial = distance_km is not None and distance_km <= COORD_TOLERANCE_KM_LOOSE
    spatial_evidence = tight_spatial or loose_spatial or locality_match

    if not spatial_evidence:
        # country + date agree but there is no spatial link at all —
        # not enough evidence to even flag as a candidate duplicate.
        return None

    either_approximate_gps = a.gps_quality in (GpsQuality.APPROXIMATE.value, GpsQuality.COARSE.value) or (
        b.gps_quality in (GpsQuality.APPROXIMATE.value, GpsQuality.COARSE.value)
    )
    coordinate_only_evidence = (tight_spatial or loose_spatial) and not locality_matches_strict(
        a.locality, b.locality
    )

    # Approximate-coordinate protection is checked FIRST and takes priority
    # over the HIGH branch below: an explicitly-flagged imprecise/snapped
    # coordinate matching by distance alone (no *strict* locality-name
    # match — a fuzzy locality match is not enough here) is NEVER
    # auto-merge evidence, even when species also happens to agree. This is
    # exactly WAHIS's documented case of multiple distinct outbreak IDs
    # sharing one approximate village-level coordinate. Capped at LOW so it
    # is reported for manual review but never silently merged.
    if either_approximate_gps and coordinate_only_evidence:
        tier = DedupConfidence.LOW.value
        match_rule = "LEVEL_3_APPROXIMATE_COORDINATE_ONLY"
    elif tight_spatial and locality_match and species_match:
        tier = DedupConfidence.HIGH.value
        match_rule = "LEVEL_2_FULL_EVIDENCE"
    elif species_match:
        tier = DedupConfidence.MEDIUM.value
        match_rule = "LEVEL_2_PARTIAL_EVIDENCE"
    else:
        tier = DedupConfidence.LOW.value
        match_rule = "LEVEL_3_SPATIOTEMPORAL_ONLY"

    return PairMatch(
        a_id=a.source_record_id,
        b_id=b.source_record_id,
        tier=tier,
        match_rule=match_rule,
        country_match=True,
        date_diff_days=date_diff_days,
        distance_km=distance_km,
        locality_match=locality_match,
        species_match=species_match,
    )


class _UnionFind:
    def __init__(self, ids: list[str]):
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic: smaller id string becomes the root
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra


_TIER_RANK = {DedupConfidence.LOW.value: 0, DedupConfidence.MEDIUM.value: 1, DedupConfidence.HIGH.value: 2}


def _by_country_buckets(
    records: list[NormalizedOutbreakRecord],
) -> "list[list[NormalizedOutbreakRecord]]":
    by_country: dict[str, list[NormalizedOutbreakRecord]] = {}
    for r in records:
        key = (r.country or "").strip().lower()
        by_country.setdefault(key, []).append(r)
    return list(by_country.values())


def _candidate_pairs(records: list[NormalizedOutbreakRecord]) -> list[PairMatch]:
    """All pairwise matches, restricted to same-country buckets (a
    correctness-preserving performance optimization — country agreement is
    a hard gate for every match rule above, so records in different
    country buckets could never match anyway)."""
    pairs: list[PairMatch] = []
    for bucket in _by_country_buckets(records):
        n = len(bucket)
        for i in range(n):
            for j in range(i + 1, n):
                m = match_pair(bucket[i], bucket[j])
                if m is not None:
                    pairs.append(m)
    return pairs


@dataclass
class DateConflict:
    a_id: str
    b_id: str
    date_diff_days: int
    reason: str


def _check_date_conflict(a: NormalizedOutbreakRecord, b: NormalizedOutbreakRecord) -> DateConflict | None:
    """A pair that agrees on everything `match_pair` requires for a HIGH
    match — country, STRICT locality name, species, and a tight coordinate
    distance — except that their dates disagree by MORE than
    `DATE_TOLERANCE_DAYS`. `match_pair` returns None for such a pair (no
    usable date agreement = no candidate at all), which would let it look
    like an ordinary, unremarkable singleton in the conservative/
    model-candidate view. That is exactly wrong for a record this close on
    every other axis — it is a genuine near-miss that needs a human's eyes,
    not a silent pass-through. This is a deliberately separate, narrow
    side-channel (NOT folded into `build_duplicate_groups`'s union-find):
    flagging it must never drag an otherwise-clean HIGH group down through
    graph transitivity (see `model_candidate.py` for how the flag is
    applied only to records with no other resolved group membership)."""
    disease_a = normalize_disease(a.disease)
    disease_b = normalize_disease(b.disease)
    if disease_a is not None and disease_b is not None and disease_a != disease_b:
        return None
    country_a = (a.country or "").strip().lower()
    country_b = (b.country or "").strip().lower()
    if not country_a or not country_b or country_a != country_b:
        return None
    if not locality_matches_strict(a.locality, b.locality):
        return None
    if not species_matches(a.species, b.species):
        return None
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return None
    distance_km = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
    if distance_km > COORD_TOLERANCE_KM_TIGHT:
        return None

    date_a = best_match_date(a)
    date_b = best_match_date(b)
    if date_a is None or date_b is None:
        return None
    date_diff_days = abs((date_a[0] - date_b[0]).days)
    if date_diff_days <= DATE_TOLERANCE_DAYS:
        return None  # within tolerance — handled as a normal match, not a conflict

    return DateConflict(
        a_id=a.source_record_id,
        b_id=b.source_record_id,
        date_diff_days=date_diff_days,
        reason=(
            f"locality/species/coordinates agree with {b.source_record_id} but dates differ by "
            f"{date_diff_days} days (tolerance is {DATE_TOLERANCE_DAYS}) — "
            f"{date_a[1]}={date_a[0].isoformat()} vs {date_b[1]}={date_b[0].isoformat()}"
        ),
    )


def find_date_conflicts(records: list[NormalizedOutbreakRecord]) -> dict[str, list[DateConflict]]:
    """Per-record map of `source_record_id` -> the date-conflict edges it
    participates in (see `_check_date_conflict`). Restricted to
    same-country buckets for the same reason as `_candidate_pairs`."""
    conflicts: dict[str, list[DateConflict]] = {}
    for bucket in _by_country_buckets(records):
        n = len(bucket)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = bucket[i], bucket[j]
                c = _check_date_conflict(a, b)
                if c is None:
                    continue
                conflicts.setdefault(a.source_record_id, []).append(c)
                conflicts.setdefault(b.source_record_id, []).append(
                    DateConflict(
                        a_id=b.source_record_id,
                        b_id=a.source_record_id,
                        date_diff_days=c.date_diff_days,
                        reason=(
                            f"locality/species/coordinates agree with {a.source_record_id} but dates "
                            f"differ by {c.date_diff_days} days (tolerance is {DATE_TOLERANCE_DAYS})"
                        ),
                    )
                )
    return conflicts


def _completeness_score(r: NormalizedOutbreakRecord) -> int:
    return sum(
        1
        for f in fields(r)
        if f.name not in ("source_record_id", "source_file", "source_system")
        and getattr(r, f.name) not in (None, "")
    )


_SOURCE_SYSTEM_RICHNESS_RANK = {"WAHIS_PDF": 1, "FAO_EMPRESI_CSV": 0}


def select_canonical(group: list[NormalizedOutbreakRecord]) -> str:
    """Deterministic choice of which group member becomes the canonical
    record: most complete first, then WAHIS_PDF over FAO_EMPRESI_CSV
    (WAHIS carries species/case-count fields the CSV never has), then
    lexicographically smallest source_record_id as a final, fully
    reproducible tie-break."""
    ranked = sorted(
        group,
        key=lambda r: (
            -_completeness_score(r),
            -_SOURCE_SYSTEM_RICHNESS_RANK.get(r.source_system, 0),
            r.source_record_id,
        ),
    )
    return ranked[0].source_record_id


@dataclass
class DuplicateGroupResult:
    duplicate_group_id: str
    canonical_record_id: str
    member_record_ids: list[str]
    match_rule: str
    match_features: str
    dedup_confidence: str
    review_required: bool
    notes: str
    merged: bool  # whether this group collapses to one canonical record


def build_duplicate_groups(records: list[NormalizedOutbreakRecord]) -> list[DuplicateGroupResult]:
    by_id = {r.source_record_id: r for r in records}
    pairs = _candidate_pairs(records)

    uf = _UnionFind(list(by_id.keys()))
    edges_by_root: dict[str, list[PairMatch]] = {}
    for m in pairs:
        uf.union(m.a_id, m.b_id)
    for m in pairs:
        root = uf.find(m.a_id)
        edges_by_root.setdefault(root, []).append(m)

    groups: list[DuplicateGroupResult] = []
    group_index = 0
    for root, edges in sorted(edges_by_root.items()):
        member_ids = sorted({m.a_id for m in edges} | {m.b_id for m in edges})
        if len(member_ids) < 2:
            continue
        # group confidence = the WEAKEST pairwise edge tying the group
        # together — a chain is only as trustworthy as its weakest link.
        weakest = min(edges, key=lambda m: _TIER_RANK[m.tier])
        confidence = weakest.tier
        merged = confidence in (DedupConfidence.HIGH.value, DedupConfidence.MEDIUM.value)
        review_required = confidence != DedupConfidence.HIGH.value

        group_index += 1
        duplicate_group_id = f"DUPGRP:{group_index:05d}"
        canonical_id = select_canonical([by_id[i] for i in member_ids]) if merged else None

        feature_strs = []
        for m in edges:
            feature_strs.append(
                f"{m.a_id}~{m.b_id}: rule={m.match_rule} date_diff_days={m.date_diff_days} "
                f"distance_km={None if m.distance_km is None else round(m.distance_km, 3)} "
                f"locality_match={m.locality_match} species_match={m.species_match}"
            )

        notes = (
            "auto-merged into one canonical record"
            if merged
            else "NOT merged — LOW confidence candidate kept as separate canonical records pending manual review"
        )

        groups.append(
            DuplicateGroupResult(
                duplicate_group_id=duplicate_group_id,
                canonical_record_id=canonical_id or "",
                member_record_ids=member_ids,
                match_rule="; ".join(sorted({m.match_rule for m in edges})),
                match_features=" | ".join(feature_strs),
                dedup_confidence=confidence,
                review_required=review_required,
                notes=notes,
                merged=merged,
            )
        )
    return groups

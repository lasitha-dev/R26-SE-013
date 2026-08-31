"""FMD-03: species-category normalization for the FAO EMPRES-i FMD export's
`species_overview_list` field (surfaced on `RawOutbreakRecord.species`).

This is a DIFFERENT normalization from `species.py`'s `normalize_species` —
that module strips filler words and sorts tokens ONLY to decide whether two
records' species plausibly match for dedup (never written back, never a
fixed target vocabulary). This module instead produces a documented,
deterministic mapping onto a small set of host-density-relevant categories
(cattle / swine / sheep / goat / buffalo / small_ruminant / mixed / unknown,
plus additional literal wildlife-taxon tokens the real data actually
contains — see below), suitable for FMD-04 host-density feature work. The
original `species` field is never overwritten.

Multi-species records (`"Domestic - Cattle | Domestic - Sheep"` etc.) are
NOT collapsed by picking the first token. Every "|"-delimited token is
parsed and mapped independently; the record's `species_normalized_category`
is then a deterministic function of the full set of mapped tokens (see
`normalize_species_category`):

  - one distinct mapped category                       -> that category
  - only sheep/goat/small_ruminant tokens (>1 distinct) -> "small_ruminant"
    (the source itself uses "Domestic - Small Ruminant" as a first-order
    single-token label for exactly this aggregate — this rule follows that
    existing source precedent rather than inventing a new taxonomy)
  - more than one distinct category, spanning beyond
    the sheep/goat/small_ruminant aggregate                -> "mixed"
  - every token maps to "unknown"                       -> "unknown"

Host-rearing context (Domestic / Wild / Captive) is preserved separately
(`domestic_context_present` / `wild_context_present` / `captive_context_present`)
rather than folded into the species category — a wild buffalo and a
domestic buffalo are the same base taxon for this mapping (both "buffalo")
but very different host populations for a later density model, and that
distinction must not be silently lost.

Uncommon wildlife host names not covered by the fixed 8-category vocabulary
(e.g. "Sable Antelope (Hippotragus niger)", "Goitered gazelle (Gazella
subgutturosa)") are NOT collapsed into "unknown" — a specific reported taxon
is real information "unknown" would discard. Each gets its own literal,
deterministic normalized token instead (parenthetical/colon-suffixed
scientific-name qualifiers stripped, snake_cased) — see
`_fallback_normalize_token`. This keeps the fixed vocabulary honest (limited
to the categories actually documented above) while never fabricating or
discarding a distinct reported host identity.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

CATTLE = "cattle"
SWINE = "swine"
SHEEP = "sheep"
GOAT = "goat"
BUFFALO = "buffalo"
SMALL_RUMINANT = "small_ruminant"
MIXED = "mixed"
UNKNOWN = "unknown"

_SMALL_RUMINANT_FAMILY = {SHEEP, GOAT, SMALL_RUMINANT}

_CONTEXT_PREFIX = re.compile(r"^\s*(domestic|wild|captive)\s*-\s*", re.IGNORECASE)
_TRAILING_QUALIFIER = re.compile(r"\s*[:(].*$")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Known single-token base-taxon synonyms actually observed in the real
# 2002-2026 export (case-insensitive, matched after context-prefix removal
# and lowercasing). Deliberately covers only strings seen in the data plus
# the small set of obvious spelling variants documented here, not a general
# species gazetteer.
_KNOWN_TOKEN_MAP = {
    "cattle": CATTLE,
    "swine": SWINE,
    "sheep": SHEEP,
    "goats": GOAT,
    "goat": GOAT,
    "goat/sheep": SMALL_RUMINANT,  # ambiguous combined single token
    "small ruminant": SMALL_RUMINANT,
    "buffaloes": BUFFALO,
    "buffaloe": BUFFALO,  # source spelling
    "water buffalo": BUFFALO,
    "african buffalo": BUFFALO,
    "unspecified mammal": UNKNOWN,
    "unspecified bird": UNKNOWN,
}


def _clean_token_text(text: str) -> str:
    m = _CONTEXT_PREFIX.match(text)
    context = m.group(1).lower() if m else None
    remainder = text[m.end():] if m else text
    return context, remainder.strip()


def _fallback_normalize_token(remainder: str) -> str:
    """Deterministic literal token for a species name not in
    `_KNOWN_TOKEN_MAP` — strips a trailing parenthetical/colon-introduced
    scientific-name qualifier, then snake_cases what remains. Never
    corrects apparent source typos (e.g. "Impata" is kept as "impata", not
    silently rewritten to "impala") — the audit CSV is the record of what
    the source actually said."""
    base = _TRAILING_QUALIFIER.sub("", remainder).strip().lower()
    if not base:
        base = remainder.strip().lower()
    token = _NON_ALNUM.sub("_", base).strip("_")
    return token or UNKNOWN


@dataclass(frozen=True)
class ParsedSpeciesToken:
    raw_token: str
    context: str | None  # "domestic" / "wild" / "captive" / None
    base_category: str


def _parse_token(raw_token: str) -> ParsedSpeciesToken:
    context, remainder = _clean_token_text(raw_token)
    key = remainder.lower().strip()
    base_category = _KNOWN_TOKEN_MAP.get(key)
    if base_category is None:
        # Recognize known wild-boar spellings without a context prefix match
        # quirk (e.g. "Wild boar:Sus scrofa(Suidae)" has "Wild boar" fused
        # to the qualifier, not a clean "Wild - " prefix in every case).
        stripped = _TRAILING_QUALIFIER.sub("", key).strip()
        if stripped in ("wild boar", "boar"):
            base_category = "wild_boar"
        else:
            base_category = _fallback_normalize_token(remainder)
    return ParsedSpeciesToken(raw_token=raw_token.strip(), context=context, base_category=base_category)


@dataclass(frozen=True)
class SpeciesNormalizationResult:
    raw_value: str | None
    tokens: tuple[ParsedSpeciesToken, ...]
    species_normalized_category: str
    species_tokens_normalized: str  # "+"-joined, sorted, deduped base categories
    domestic_context_present: bool
    wild_context_present: bool
    captive_context_present: bool


_EMPTY_RESULT_CATEGORY = UNKNOWN


def normalize_species_category(raw_value: str | None) -> SpeciesNormalizationResult:
    if raw_value is None or not raw_value.strip():
        return SpeciesNormalizationResult(
            raw_value=raw_value,
            tokens=(),
            species_normalized_category=UNKNOWN,
            species_tokens_normalized="",
            domestic_context_present=False,
            wild_context_present=False,
            captive_context_present=False,
        )

    raw_tokens = [t for t in (part.strip() for part in raw_value.split("|")) if t]
    parsed = tuple(_parse_token(t) for t in raw_tokens)

    distinct_categories = sorted({p.base_category for p in parsed})
    if len(distinct_categories) == 0:
        category = UNKNOWN
    elif len(distinct_categories) == 1:
        category = distinct_categories[0]
    elif set(distinct_categories) <= _SMALL_RUMINANT_FAMILY:
        category = SMALL_RUMINANT
    elif set(distinct_categories) == {UNKNOWN}:
        category = UNKNOWN
    else:
        category = MIXED

    return SpeciesNormalizationResult(
        raw_value=raw_value,
        tokens=parsed,
        species_normalized_category=category,
        species_tokens_normalized="+".join(distinct_categories),
        domestic_context_present=any(p.context == "domestic" for p in parsed),
        wild_context_present=any(p.context == "wild" for p in parsed),
        captive_context_present=any(p.context == "captive" for p in parsed),
    )


def build_species_normalization_audit(raw_species_values: list[str | None]) -> list[dict]:
    """One row per DISTINCT raw `species_overview_list` string actually
    present in the input, with its normalized category and how many rows
    carried that exact raw string — the mapping audit required before any
    FMD-04 host-density work consumes this normalization."""
    counts = Counter(raw_species_values)
    rows: list[dict] = []
    for raw_value, count in counts.items():
        result = normalize_species_category(raw_value)
        rows.append(
            {
                "raw_species_value": raw_value if raw_value is not None else "",
                "normalized_species_category": result.species_normalized_category,
                "species_tokens_normalized": result.species_tokens_normalized,
                "domestic_context_present": result.domestic_context_present,
                "wild_context_present": result.wild_context_present,
                "captive_context_present": result.captive_context_present,
                "row_count": count,
            }
        )
    rows.sort(key=lambda r: (-r["row_count"], r["raw_species_value"]))
    return rows

"""Disease-name normalization — FMD-03 addition.

Before FMD-03 every raw source in this pipeline described exactly one
disease (Lumpy skin disease), so `dedup.py`'s `match_pair` never compared
the `disease` field at all: country + locality + date + coordinates +
species were sufficient because disease was implicitly constant across
the whole corpus. Introducing a second disease (FMD) into the same
disease-agnostic pipeline exposes that gap — two records from different
diseases could otherwise satisfy every other matching rule (same country,
close dates, shared/approximate coordinates, same host species) and be
flagged as duplicates of each other, which would be wrong.

`normalize_disease` / `disease_matches` mirror `species.py`'s pattern:
normalization is used only to decide whether two records plausibly
describe the same disease for dedup matching — never written back over
the original `disease` field.
"""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")

# Known short-form/alternate spellings this pipeline's real sources use.
# Not an exhaustive disease gazetteer — only covers the two diseases this
# pipeline actually ingests (LSD, FMD) plus FMD's common abbreviation.
_ALIASES = {
    "foot and mouth disease": "foot and mouth disease",
    "foot-and-mouth disease": "foot and mouth disease",
    "fmd": "foot and mouth disease",
    "lumpy skin disease": "lumpy skin disease",
    "lsd": "lumpy skin disease",
}


def normalize_disease(raw: str | None) -> str | None:
    """Return a canonical lowercase disease token, or None if `raw` is
    missing/empty. Unrecognized disease strings still normalize (lowercased,
    punctuation-collapsed) rather than returning None, so an unmapped
    disease name can still be compared for equality against itself."""
    if raw is None:
        return None
    text = _NON_ALNUM.sub(" ", raw.lower())
    text = _WHITESPACE.sub(" ", text).strip()
    if not text:
        return None
    return _ALIASES.get(text, text)


def disease_matches(a: str | None, b: str | None) -> bool:
    """True only when both sides normalize to the same non-empty token.
    Two missing disease values never count as a match OR a mismatch — see
    `dedup.match_pair`, which treats "either side unknown" as "no evidence
    either way" rather than blocking on it."""
    na, nb = normalize_disease(a), normalize_disease(b)
    if na is None or nb is None:
        return False
    return na == nb

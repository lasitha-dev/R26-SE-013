"""Species-name normalization for cross-source dedup matching only.

The two raw sources describe the same animal differently:
  - FAO EMPRES-i CSV: "Domestic - Cattle"
  - WAHIS PDF:         "cattle (domestic)"

Normalization here is used ONLY to decide whether two records plausibly
describe the same species for dedup matching — it is never written back
over the original `species` field (that raw value is preserved verbatim).
"""

from __future__ import annotations

import re

# filler tokens that describe rearing/provenance context, not the species
# itself — stripped before comparison so "Domestic - Cattle" and
# "cattle (domestic)" both normalize to "cattle".
_FILLER_WORDS = {"domestic", "wildlife", "captive", "wild", "unspecified", "animal"}

_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize_species(raw: str | None) -> str | None:
    """Return a lowercase, filler-stripped, word-order-independent token.

    Returns None if `raw` is None/empty or normalizes to nothing (so an
    empty species is never silently treated as matching another empty one).
    """
    if raw is None:
        return None
    text = raw.lower()
    text = _NON_ALNUM.sub(" ", text)
    words = [w for w in _WHITESPACE.split(text.strip()) if w and w not in _FILLER_WORDS]
    if not words:
        return None
    return " ".join(sorted(words))


def species_matches(a: str | None, b: str | None) -> bool:
    """True only when both sides normalize to the same non-empty token.

    Two missing/unnormalizable species values never count as a match —
    absence of evidence is not evidence of agreement.
    """
    na, nb = normalize_species(a), normalize_species(b)
    if na is None or nb is None:
        return False
    return na == nb

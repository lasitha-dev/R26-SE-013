"""Disease-name normalization, used both by the eligible-source selector
(historical disease matching) and by the live-domain aggregation service
(Checkpoint 4 Part 0A — the report-grouping KEY, not just query matching).

Sources/callers spell the same disease differently — FAO EMPRES-i CSV:
"Lumpy skin disease"; WAHIS PDF event titles: "Lumpy skin disease virus
(Inf. with)"; a live submission might use the bare abbreviation "LSD" —
same disease, different naming convention. This mirrors
`data_processing/species.py`'s approach exactly: normalize only for
matching/grouping, never overwrite the literal source field (an
`OutbreakEpisode`'s `disease` field always stores a real submitted
string, never the normalized key — see `services/aggregation.py`).

Genuinely different diseases (e.g. LSD vs. FMD) must never normalize to
the same value — `_ABBREVIATION_EXPANSIONS` only expands a handful of
known, unambiguous abbreviations; anything else is word-normalized as-is,
so two different disease names will not accidentally collide.
"""

from __future__ import annotations

import re

_FILLER_WORDS = {"virus", "inf", "with"}
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")

# Known, unambiguous abbreviation -> full name, checked only against the
# WHOLE normalized string (not substrings) so this can't accidentally
# expand part of an unrelated longer name.
_ABBREVIATION_EXPANSIONS = {
    "lsd": "lumpy skin disease",
    "fmd": "foot and mouth disease",
}


def normalize_disease(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = _WHITESPACE.sub(" ", _NON_ALNUM.sub(" ", raw.lower())).strip()
    text = _ABBREVIATION_EXPANSIONS.get(text, text)
    words = [w for w in text.split(" ") if w and w not in _FILLER_WORDS]
    if not words:
        return None
    return " ".join(sorted(words))


def disease_matches(a: str | None, b: str | None) -> bool:
    na, nb = normalize_disease(a), normalize_disease(b)
    if na is None or nb is None:
        return False
    return na == nb


# ---------------------------------------------------------------------------
# FMD-02: canonical disease-selection registry.
#
# This is the ONE place a runtime caller's disease *identifier* is resolved
# to a canonical display string -- it says nothing about whether frozen
# SCIENTIFIC parameters (Checkpoint 7B-9C kernel scale/family, apparent
# spread rate) exist for that disease. That separate question is answered
# by `services.application.frozen_geospatial_analysis_10a.DISEASE_MODEL_READINESS_10A`
# -- being resolvable here (an accepted disease IDENTIFIER) must never be
# read as implying model readiness (a SCIENTIFIC availability fact).
# ---------------------------------------------------------------------------

DEFAULT_DISEASE = "Lumpy skin disease"
"""The pre-FMD-02 implicit disease, preserved as the explicit backward-
compatible default: every existing caller/route that omits a disease
selection must resolve to exactly this string, unchanged from Checkpoint
1-10B.1a behavior."""

SUPPORTED_DISEASES: dict[str, str] = {
    "lsd": "Lumpy skin disease",
    "fmd": "Foot and mouth disease",
}
"""Canonical abbreviation -> canonical display-string registry of disease
identifiers this runtime API/pipeline accepts as an explicit selection.
Deliberately the single place this list is declared -- callers must never
hardcode a second copy of a disease name to check against."""


class UnsupportedDiseaseError(ValueError):
    """Raised by `resolve_disease_selection` for any input that does not
    normalize to a `SUPPORTED_DISEASES` entry. Callers at an external
    boundary (HTTP query param, WebSocket message) are expected to catch
    this and produce a clear 4xx response -- never a fabricated analysis."""

    def __init__(self, requested: str):
        self.requested = requested
        super().__init__(
            f"unsupported disease: {requested!r} -- supported diseases: "
            f"{sorted(set(SUPPORTED_DISEASES.values()))}"
        )


def resolve_disease_selection(disease: str | None) -> str:
    """Normalizes an optional caller-supplied disease identifier
    (a `SUPPORTED_DISEASES` abbreviation, a canonical display string, or an
    equivalent raw spelling `normalize_disease` already recognizes as the
    same disease) into exactly one canonical display string.

    `disease=None` -> `DEFAULT_DISEASE` -- the ONLY implicit fallback in
    this function, reserved for the external request boundary so that
    omitting a disease selection reproduces pre-FMD-02 LSD-only behavior
    exactly. Anything else that does not normalize to a known supported
    disease raises `UnsupportedDiseaseError` rather than silently falling
    back to the default or to a fabricated value.
    """
    if disease is None:
        return DEFAULT_DISEASE
    normalized = normalize_disease(disease)
    if normalized is not None:
        for canonical in SUPPORTED_DISEASES.values():
            if normalize_disease(canonical) == normalized:
                return canonical
    raise UnsupportedDiseaseError(disease)

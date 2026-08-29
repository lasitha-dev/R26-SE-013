"""GEO-INT-01 Section 10: operational disease-name normalization for
verified clinical cases arriving from the host application boundary.

Reuses the existing Checkpoint 4 disease registry
(`services/disease.py::normalize_disease`,
`services/disease.py::SUPPORTED_DISEASES`) rather than declaring a second
alias table (Section 3 architecture-reuse rule). That module's
`resolve_disease_selection` is deliberately NOT called from here: it
defaults an omitted disease (`None`) to `DEFAULT_DISEASE` (Lumpy skin
disease) for a different use case — an HTTP query param picking which
disease to run the map analysis for. Classifying an actual clinical
case's `disease_name` must never silently default that way (Section 10 —
"Unknown disease -> UNSUPPORTED", "Never: unknown disease -> LSD/FMD"), so
this module calls the lower-level `normalize_disease`/`disease_matches`
directly against the same `SUPPORTED_DISEASES` registry, with its own
explicit UNSUPPORTED fallback for anything that doesn't match.

Two verified alias forms per disease are recognized:

  1. Any spelling `services/disease.py::disease_matches` already treats as
     equivalent to a `SUPPORTED_DISEASES` canonical display string
     ("Lumpy skin disease", "Foot and mouth disease") — covers what a
     verified case's `disease_name` actually contains in practice, since
     `smart_diagnostics`'s classifier response field is populated from
     `CLASS_DISPLAY_NAMES` ("Lumpy Skin Disease", "Foot and Mouth
     Disease") — verified read-only via
     `git show origin/main:backend/components/smart_diagnostics/
     implementations/vit_classifier.py` (the `"name": top_display` line).
  2. The classifier's raw internal class key, verified read-only via
     `git show origin/main:backend/components/smart_diagnostics/config.py`
     -- `CLASS_NAMES = ["cattle", "foot_and_mouth", "lumpy_skin",
     "mastitis"]` (NOT imported here — Section 5 forbids importing
     `components.smart_diagnostics`; these two literal strings are
     transcribed, not derived, from that read-only inspection). Only
     "foot_and_mouth" and "lumpy_skin" are aliased; "cattle" (healthy) and
     "mastitis" are genuinely different classes and must never resolve to
     LSD or FMD.
"""

from __future__ import annotations

from ...domain.operational_enums import OperationalDisease
from ..disease import SUPPORTED_DISEASES, disease_matches

UNSUPPORTED_DISEASE = "UNSUPPORTED"

_OPERATIONAL_DISEASE_BY_ABBREVIATION: dict[str, OperationalDisease] = {
    "lsd": OperationalDisease.LSD,
    "fmd": OperationalDisease.FMD,
}

_VERIFIED_RAW_CLASSIFIER_KEY_ALIASES: dict[str, OperationalDisease] = {
    "foot_and_mouth": OperationalDisease.FMD,
    "lumpy_skin": OperationalDisease.LSD,
}


def resolve_operational_disease(raw_disease_name: str | None) -> OperationalDisease | None:
    """Returns the `OperationalDisease` this raw case disease-name string
    represents, or `None` (meaning `UNSUPPORTED_DISEASE`) if it is
    missing, unrecognized, or a genuinely different class (e.g.
    "Mastitis", "Cattle (Healthy)"). Never defaults a missing/unmatched
    name to LSD or FMD — Section 10/26 tests 15-17.
    """
    if not raw_disease_name or not raw_disease_name.strip():
        return None

    raw_key = raw_disease_name.strip().lower()
    if raw_key in _VERIFIED_RAW_CLASSIFIER_KEY_ALIASES:
        return _VERIFIED_RAW_CLASSIFIER_KEY_ALIASES[raw_key]

    for abbreviation, canonical_display in SUPPORTED_DISEASES.items():
        if disease_matches(raw_disease_name, canonical_display):
            return _OPERATIONAL_DISEASE_BY_ABBREVIATION[abbreviation]

    return None

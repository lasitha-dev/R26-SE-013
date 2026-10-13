"""
District reference data for the v2 forecasting pipeline.

Provenance (verified 2026-10-13 against the curated training datasets):
- `pcode`, `lat`, `lon`: the PCODEs and point coordinates used when the training
  data was built. NASA POWER monthly T2M/RH2M/WS2M at these points reproduce the
  training weather columns exactly (2,400/2,400 rows).
- ADJACENCY: `geometry.touches` on HDX COD-AB `lka_admin2` boundaries (the same
  source used by scripts/phase2_spatial_lags.py). Reproduces all neighbour
  outbreak features of both FMD and LSD datasets (100% of rows, within rounding).
"""

DISTRICTS = {
    "Ampara": {"pcode": "LK52", "lat": 7.2913, "lon": 81.6722},
    "Anuradhapura": {"pcode": "LK71", "lat": 8.3114, "lon": 80.4037},
    "Badulla": {"pcode": "LK81", "lat": 6.9934, "lon": 81.055},
    "Batticaloa": {"pcode": "LK51", "lat": 7.717, "lon": 81.7},
    "Colombo": {"pcode": "LK11", "lat": 6.9271, "lon": 79.8612},
    "Galle": {"pcode": "LK31", "lat": 6.0535, "lon": 80.221},
    "Gampaha": {"pcode": "LK12", "lat": 7.0873, "lon": 80.0144},
    "Hambantota": {"pcode": "LK33", "lat": 6.1429, "lon": 81.1212},
    "Jaffna": {"pcode": "LK41", "lat": 9.6615, "lon": 80.0255},
    "Kalutara": {"pcode": "LK13", "lat": 6.5854, "lon": 80.1794},
    "Kandy": {"pcode": "LK21", "lat": 7.2906, "lon": 80.6337},
    "Kegalle": {"pcode": "LK92", "lat": 7.2513, "lon": 80.3464},
    "Kilinochchi": {"pcode": "LK42", "lat": 9.3803, "lon": 80.377},
    "Kurunegala": {"pcode": "LK61", "lat": 7.4863, "lon": 80.3647},
    "Mannar": {"pcode": "LK43", "lat": 8.981, "lon": 79.9044},
    "Matale": {"pcode": "LK22", "lat": 7.4675, "lon": 80.6234},
    "Matara": {"pcode": "LK32", "lat": 5.9549, "lon": 80.555},
    "Monaragala": {"pcode": "LK82", "lat": 6.8728, "lon": 81.3507},
    "Mullaitivu": {"pcode": "LK45", "lat": 9.2671, "lon": 80.8128},
    "Nuwara Eliya": {"pcode": "LK23", "lat": 6.9497, "lon": 80.7891},
    "Polonnaruwa": {"pcode": "LK72", "lat": 7.9403, "lon": 81.0188},
    "Puttalam": {"pcode": "LK62", "lat": 8.0362, "lon": 79.8283},
    "Ratnapura": {"pcode": "LK91", "lat": 6.6828, "lon": 80.3992},
    "Trincomalee": {"pcode": "LK53", "lat": 8.5874, "lon": 81.2152},
    "Vavuniya": {"pcode": "LK44", "lat": 8.7514, "lon": 80.4971},
}

ADJACENCY = {
    "Ampara": ["Badulla", "Batticaloa", "Hambantota", "Matale", "Monaragala", "Polonnaruwa"],
    "Anuradhapura": ["Kurunegala", "Mannar", "Matale", "Mullaitivu", "Polonnaruwa", "Puttalam", "Trincomalee", "Vavuniya"],
    "Badulla": ["Ampara", "Kandy", "Matale", "Monaragala", "Nuwara Eliya", "Ratnapura"],
    "Batticaloa": ["Ampara", "Polonnaruwa", "Trincomalee"],
    "Colombo": ["Gampaha", "Kalutara", "Kegalle", "Ratnapura"],
    "Galle": ["Kalutara", "Matara", "Ratnapura"],
    "Gampaha": ["Colombo", "Kegalle", "Kurunegala", "Puttalam"],
    "Hambantota": ["Ampara", "Matara", "Monaragala", "Ratnapura"],
    "Jaffna": ["Kilinochchi", "Mullaitivu"],
    "Kalutara": ["Colombo", "Galle", "Ratnapura"],
    "Kandy": ["Badulla", "Kegalle", "Kurunegala", "Matale", "Nuwara Eliya"],
    "Kegalle": ["Colombo", "Gampaha", "Kandy", "Kurunegala", "Nuwara Eliya", "Ratnapura"],
    "Kilinochchi": ["Jaffna", "Mannar", "Mullaitivu"],
    "Kurunegala": ["Anuradhapura", "Gampaha", "Kandy", "Kegalle", "Matale", "Puttalam"],
    "Mannar": ["Anuradhapura", "Kilinochchi", "Mullaitivu", "Puttalam", "Vavuniya"],
    "Matale": ["Ampara", "Anuradhapura", "Badulla", "Kandy", "Kurunegala", "Polonnaruwa"],
    "Matara": ["Galle", "Hambantota", "Ratnapura"],
    "Monaragala": ["Ampara", "Badulla", "Hambantota", "Ratnapura"],
    "Mullaitivu": ["Anuradhapura", "Jaffna", "Kilinochchi", "Mannar", "Trincomalee", "Vavuniya"],
    "Nuwara Eliya": ["Badulla", "Kandy", "Kegalle", "Ratnapura"],
    "Polonnaruwa": ["Ampara", "Anuradhapura", "Batticaloa", "Matale", "Trincomalee"],
    "Puttalam": ["Anuradhapura", "Gampaha", "Kurunegala", "Mannar"],
    "Ratnapura": ["Badulla", "Colombo", "Galle", "Hambantota", "Kalutara", "Kegalle", "Matara", "Monaragala", "Nuwara Eliya"],
    "Trincomalee": ["Anuradhapura", "Batticaloa", "Mullaitivu", "Polonnaruwa"],
    "Vavuniya": ["Anuradhapura", "Mannar", "Mullaitivu"],
}

DISTRICT_NAMES = sorted(DISTRICTS)

_ALIASES = {"moneragala": "Monaragala", "nuwaraeliya": "Nuwara Eliya"}


def normalize_district(value):
    """Map free-text district values (e.g. 'Anuradhapura District',
    '8.41, 80.02 (Anuradhapura District)') to a canonical district name, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().lower()
    compact = text.replace(" ", "")
    for alias, canonical in _ALIASES.items():
        if alias in compact:
            return canonical
    matches = [name for name in DISTRICT_NAMES if name.lower() in text]
    if len(matches) == 1:
        return matches[0]
    return None

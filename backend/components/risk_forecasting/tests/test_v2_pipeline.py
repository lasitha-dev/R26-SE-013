"""Unit tests for the v2 forecasting pipeline (pure functions; no network or database)."""

import json

import pytest

from components.risk_forecasting.pipeline import sources as src
from components.risk_forecasting.pipeline.features import (
    ALL_FEATURES, FeatureSources, build_features, monsoon_flags, nino_anomalies, shift,
)
from components.risk_forecasting.pipeline.geography import ADJACENCY, DISTRICTS, normalize_district


# ─── geography ─────────────────────────────────────────────────────────────

def test_adjacency_is_symmetric_and_covers_all_districts():
    assert set(ADJACENCY) == set(DISTRICTS)
    for district, neighbours in ADJACENCY.items():
        for n in neighbours:
            assert district in ADJACENCY[n]


@pytest.mark.parametrize("raw,expected", [
    ("Anuradhapura", "Anuradhapura"),
    ("Anuradhapura District", "Anuradhapura"),
    ("8.4162, 80.0261 (Anuradhapura District)", "Anuradhapura"),
    ("  nuwara eliya ", "Nuwara Eliya"),
    ("NuwaraEliya", "Nuwara Eliya"),
    ("Moneragala", "Monaragala"),
    ("Sri Lanka Central Jurisdiction", None),
    ("", None),
    (None, None),
])
def test_normalize_district(raw, expected):
    assert normalize_district(raw) == expected


# ─── sources ───────────────────────────────────────────────────────────────

CHIRPS_CSV = """date,adm_level,adm_id,PCODE,n_pixels,rfh,rfh_avg,r1h,r1h_avg,r3h,r3h_avg,rfq,r1q,r3q,version
2024-01-01,2,1,LK71,10,10.0,0,,,300.0,0,90.0,,,final
2024-01-11,2,1,LK71,10,20.0,0,,,330.0,0,100.0,,,final
2024-01-21,2,1,LK71,10,30.0,0,,,360.0,0,110.0,,,prelim
2024-02-01,2,1,LK71,10,5.0,0,,,200.0,0,50.0,,,prelim
2024-01-01,1,9,LK7,10,99.0,0,,,999.0,0,99.0,,,final
"""


def test_chirps_monthly_applies_verified_rules_and_drops_incomplete_months():
    monthly = src.chirps_monthly(CHIRPS_CSV)
    assert len(monthly) == 1  # February has one dekad only; adm1 row ignored
    row = monthly.iloc[0]
    assert row.pcode == "LK71" and row.year == 2024 and row.month == 1
    assert row.rainfall_mm == pytest.approx(60.0)   # sum of rfh
    assert row.r3h == pytest.approx(330.0)          # mean of r3h
    assert row.rfq == pytest.approx(100.0)          # mean of rfq
    assert bool(row.preliminary) is True


def _daily_payload(days, value=1.0, missing_day=None):
    params = {p: {} for p in src.NASA_PARAMETERS}
    for day in range(1, days + 1):
        key = f"202402{day:02d}"
        for p in src.NASA_PARAMETERS:
            params[p][key] = src.NASA_FILL_VALUE if day == missing_day else value + day
    return {"properties": {"parameter": params}}


def test_nasa_daily_aggregation_keeps_complete_months_only():
    complete = src.nasa_power_monthly_from_daily_payload(_daily_payload(29))  # 2024 is a leap year
    assert len(complete) == 1
    assert complete.iloc[0]["T2M"] == pytest.approx(round(sum(1 + d for d in range(1, 30)) / 29, 2))
    assert src.nasa_power_monthly_from_daily_payload(_daily_payload(29, missing_day=10)).empty
    assert src.nasa_power_monthly_from_daily_payload(_daily_payload(20)).empty


def test_nasa_monthly_payload_skips_annual_row_and_fill_values():
    payload = {"properties": {"parameter": {
        "T2M": {"202401": 25.0, "202402": -999.0, "202413": 26.0},
        "RH2M": {"202401": 80.0, "202402": 81.0, "202413": 80.5},
        "WS2M": {"202401": 2.0, "202402": 2.1, "202413": 2.05},
    }}}
    frame = src.nasa_power_monthly_from_payload(payload)
    assert frame[["year", "month"]].values.tolist() == [[2024, 1]]


def test_parse_psl_series_ignores_missing_markers():
    text = " 2025 2026\n2025  0.1  0.2  0.3  0.4  0.5  0.6  0.7  0.8  0.9  1.0  1.1  1.2\n" \
           "2026  0.5 -99.99 -9999.000 0 0 0 0 0 0 0 0 0\n  NINA34\n"
    series = src.parse_psl_series(text)
    assert series[(2025, 12)] == pytest.approx(1.2)
    assert (2026, 2) not in series and (2026, 3) not in series
    assert series[(2026, 1)] == pytest.approx(0.5)


# ─── features ──────────────────────────────────────────────────────────────

def test_shift_and_monsoon_flags():
    assert shift((2025, 1), -1) == (2024, 12)
    assert shift((2025, 1), -3) == (2024, 10)
    assert monsoon_flags(1) == {"monsoon_first_inter": 0, "monsoon_sw": 0, "monsoon_second_inter": 0, "monsoon_ne": 1}
    assert sum(monsoon_flags(m)[k] for m in range(1, 13) for k in monsoon_flags(m)) == 12


def test_nino_anomalies_use_1991_2020_climatology():
    series = {(y, 1): 26.0 + (y - 1991) * 0.0 for y in range(1991, 2021)}
    series[(2025, 1)] = 27.5
    assert nino_anomalies(series)[(2025, 1)] == pytest.approx(1.5)


def _sources(statuses):
    pcode = DISTRICTS["Jaffna"]["pcode"]
    return FeatureSources(
        rain={(pcode, 2024, 12): {"rainfall_mm": 100.0, "r3h": 400.0, "rfq": 95.0},
              (pcode, 2024, 11): {"rainfall_mm": 200.0, "r3h": 350.0, "rfq": 120.0}},
        weather={("Jaffna", 2024, 12): {"T2M": 26.0, "RH2M": 80.0, "WS2M": 3.0}},
        nino_anomaly={(2024, 11): 0.4, (2024, 10): 0.3},
        density={"Jaffna": [(2023, 1.0, 5.0), (2024, 1.5, 6.0)]},
        surveillance=lambda d, y, m: statuses.get((d, y, m)),
    )


def test_build_features_uses_only_lagged_inputs_and_complete_surveillance():
    statuses = {("Jaffna", 2024, 12): 1, ("Jaffna", 2024, 11): 0,
                ("Kilinochchi", 2024, 12): 1, ("Mullaitivu", 2024, 12): 0,
                ("Kilinochchi", 2024, 11): 0, ("Mullaitivu", 2024, 11): 0}
    feats, missing = build_features("Jaffna", 2025, 1, _sources(statuses))
    assert set(feats) == set(ALL_FEATURES)
    assert missing == []
    assert feats["rain_t1"] == 100.0 and feats["rain_t2"] == 200.0
    assert feats["nino34_anom_t2"] == 0.4 and feats["nino34_anom_t3"] == 0.3
    assert feats["own_t1"] == 1.0 and feats["own_t2"] == 0.0
    assert feats["neighbour_count_t1"] == 1 and feats["neighbour_fraction_t1"] == pytest.approx(0.5)
    assert feats["buffalo_density"] == 1.5


def test_build_features_never_turns_unknown_into_zero():
    statuses = {("Jaffna", 2024, 12): 0, ("Kilinochchi", 2024, 12): 1}  # Mullaitivu unknown
    feats, missing = build_features("Jaffna", 2025, 1, _sources(statuses))
    assert feats["own_t1"] == 0.0
    assert feats["own_t2"] is None
    assert feats["neighbour_fraction_t1"] is None and feats["neighbour_count_t1"] is None
    assert {"own_t2", "neighbour_fraction_t1", "neighbour_count_t1", "neighbour_fraction_t2"} <= set(missing)
    assert json.dumps(feats)  # serialisable for the feature snapshot

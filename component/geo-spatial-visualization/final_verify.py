"""
PISTES Final Verification — 5-test suite.
Run: python final_verify.py
"""
import sys
import math
sys.path.insert(0, '.')

from web_demo import app, physics_evf_predict
from src.predict import PISTESPredictor

print("=" * 55)
print("PISTES FINAL VERIFICATION")
print("=" * 55)

predictor = PISTESPredictor()
failures = []


# ──────────────────────────────────────────────
# TEST 1: EVF Wind Sensitivity
# Each scenario must produce a unique direction
# ──────────────────────────────────────────────
print("\n--- TEST 1: EVF Wind Sensitivity ---")

scenarios = [
    (2.0,   0, "N",  "wind 2 m/s N  (0°)"),
    (4.0, 135, "SE", "wind 4 m/s SE (135°)"),
    (6.0, 180, "S",  "wind 6 m/s S  (180°)"),
    (8.0, 270, "W",  "wind 8 m/s W  (270°)"),
]

t1_directions = []
t1_ok = True
for spd, drn, expected_dir, label in scenarios:
    r = physics_evf_predict(8.28, 80.47, spd, drn, 72.0)
    got = r['direction']
    ok = got == expected_dir
    if not ok:
        t1_ok = False
        failures.append(
            f"TEST 1 FAIL — {label}: expected {expected_dir}, got {got}")
    t1_directions.append(got)
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} -> {got} "
          f"({r['movement_km']:.1f} km)")

unique_dirs = len(set(t1_directions))
if unique_dirs < 4:
    t1_ok = False
    failures.append(
        f"TEST 1 FAIL — only {unique_dirs}/4 unique directions")
print(f"  Unique directions: {unique_dirs}/4"
      f" — {'PASS' if unique_dirs == 4 else 'FAIL'}")


# ──────────────────────────────────────────────
# TEST 2: EVF Biological Range
# distance 3–100 km, coords within 2° of Sri Lanka
# ──────────────────────────────────────────────
print("\n--- TEST 2: EVF Biological Range ---")

t2_ok = True
SRI_LANKA_LAT = 8.28
SRI_LANKA_LON = 80.47

for spd, drn, _, label in scenarios:
    r = physics_evf_predict(SRI_LANKA_LAT, SRI_LANKA_LON, spd, drn, 72.0)
    d = r['movement_km']
    lat_ok = abs(r['future_lat'] - SRI_LANKA_LAT) <= 2.0
    lon_ok = abs(r['future_lon'] - SRI_LANKA_LON) <= 2.0
    range_ok = 3 < d < 100
    ok = range_ok and lat_ok and lon_ok
    if not ok:
        t2_ok = False
        reason = []
        if not range_ok:
            reason.append(f"distance {d:.1f} km out of 3–100 km range")
        if not lat_ok:
            reason.append(f"future_lat {r['future_lat']} > 2° from SL")
        if not lon_ok:
            reason.append(f"future_lon {r['future_lon']} > 2° from SL")
        failures.append(f"TEST 2 FAIL — {label}: {', '.join(reason)}")
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} -> {d:.1f} km "
          f"({r['future_lat']:.4f}, {r['future_lon']:.4f})")


# ──────────────────────────────────────────────
# TEST 3: Direction Sign Check
# SE wind: dlat<0 (south), dlon>0 (east)
# NW wind: dlat>0 (north), dlon<0 (west)
# ──────────────────────────────────────────────
print("\n--- TEST 3: Direction Sign Check ---")

t3_ok = True
se = physics_evf_predict(8.28, 80.47, 4.0, 135.0, 72.0)
nw = physics_evf_predict(8.28, 80.47, 4.0, 315.0, 72.0)

checks = [
    ("SE dlat_km < 0 (going south)", se['dlat_km'] < 0,
     f"dlat_km={se['dlat_km']}"),
    ("SE dlon_km > 0 (going east)",  se['dlon_km'] > 0,
     f"dlon_km={se['dlon_km']}"),
    ("NW dlat_km > 0 (going north)", nw['dlat_km'] > 0,
     f"dlat_km={nw['dlat_km']}"),
    ("NW dlon_km < 0 (going west)",  nw['dlon_km'] < 0,
     f"dlon_km={nw['dlon_km']}"),
]

for desc, passed, detail in checks:
    if not passed:
        t3_ok = False
        failures.append(f"TEST 3 FAIL — {desc}: {detail}")
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {desc} ({detail})")


# ──────────────────────────────────────────────
# TEST 4: Wind Fetch (skip if no internet)
# ──────────────────────────────────────────────
print("\n--- TEST 4: Wind Fetch ---")

t4_ok = True
try:
    wind = predictor.fetch_live_wind(8.28, 80.47)
    if wind is None:
        raise RuntimeError("fetch_live_wind returned None")
    ws_ok  = wind['wind_speed'] > 0
    wd_ok  = 0 <= wind['wind_direction'] <= 360
    hum_ok = 0 <= wind['humidity'] <= 100
    t4_ok  = ws_ok and wd_ok and hum_ok
    if not ws_ok:
        failures.append(
            f"TEST 4 FAIL — wind_speed={wind['wind_speed']} must be > 0")
    if not wd_ok:
        failures.append(
            f"TEST 4 FAIL — wind_direction={wind['wind_direction']} "
            "not in 0–360")
    if not hum_ok:
        failures.append(
            f"TEST 4 FAIL — humidity={wind['humidity']} not in 0–100")
    status = "PASS" if t4_ok else "FAIL"
    print(f"  [{status}] wind_speed={wind['wind_speed']:.1f} m/s, "
          f"direction={wind['wind_direction']:.0f}°, "
          f"humidity={wind['humidity']:.0f}%")
except Exception as e:
    print(f"  [SKIP] Wind fetch failed (no internet?): {e}")


# ──────────────────────────────────────────────
# TEST 5: Full Pipeline via Flask test client
# ──────────────────────────────────────────────
print("\n--- TEST 5: Full Pipeline ---")

t5_ok = True
VALID_DIRS = {'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'}

try:
    client = app.test_client()
    resp = client.post(
        '/predict',
        json={'lat': 8.28, 'lng': 80.47},
        content_type='application/json'
    )
    body = resp.get_json()

    checks5 = [
        ("status == 'ok'",
         body.get('status') == 'ok',
         f"status={body.get('status')}"),
        ("physics.direction valid compass",
         body.get('physics', {}).get('direction') in VALID_DIRS,
         f"direction={body.get('physics', {}).get('direction')}"),
        ("physics.movement_km > 0",
         body.get('physics', {}).get('movement_km', 0) > 0,
         f"movement_km={body.get('physics', {}).get('movement_km')}"),
        ("ml.available == True",
         body.get('ml', {}).get('available') is True,
         f"ml.available={body.get('ml', {}).get('available')}"),
        ("wind.humidity > 0",
         body.get('wind', {}).get('humidity', 0) > 0,
         f"humidity={body.get('wind', {}).get('humidity')}"),
    ]

    for desc, passed, detail in checks5:
        if not passed:
            t5_ok = False
            failures.append(f"TEST 5 FAIL — {desc}: {detail}")
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {desc} ({detail})")

except Exception as e:
    t5_ok = False
    failures.append(f"TEST 5 FAIL — exception: {e}")
    print(f"  [FAIL] Pipeline exception: {e}")


# ──────────────────────────────────────────────
# Final result
# ──────────────────────────────────────────────
all_ok = t1_ok and t2_ok and t3_ok and t4_ok and t5_ok

print("\n" + "=" * 55)
if all_ok:
    print("ALL TESTS PASSED")
    print("SYSTEM READY FOR PRESENTATION")
else:
    print("FAILURES FOUND - fix before demo")
    for f in failures:
        print(f"  {f}")
print("=" * 55)

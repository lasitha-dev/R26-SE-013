"""
PISTES Web Demo — Pre-flight verification
Run before presentation: python verify.py
"""
import sys
import os
import math
import socket
import warnings
warnings.filterwarnings('ignore')

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = []

def check(label, ok, detail=""):
    tag = PASS if ok else FAIL
    line = f"  {tag}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    results.append(ok)

print()
print("=" * 55)
print("  PISTES — Pre-flight Verification")
print("=" * 55)

# ── 1. Model files exist ──────────────────────────────────
print("\n[1] Model files")
for fname in ["models/model_lat.pkl",
              "models/model_lon.pkl",
              "models/scaler.pkl"]:
    check(fname, os.path.isfile(fname))

# ── 2. Models load ────────────────────────────────────────
print("\n[2] Model loading")
try:
    import joblib
    model_lat = joblib.load("models/model_lat.pkl")
    model_lon = joblib.load("models/model_lon.pkl")
    scaler    = joblib.load("models/scaler.pkl")
    check("joblib load (all 3 models)", True)
except Exception as e:
    check("joblib load", False, str(e))
    print("\n  Cannot continue without models. Exiting.")
    sys.exit(1)

# ── 3. Test prediction ────────────────────────────────────
print("\n[3] Test prediction  (lat=7.47, lng=80.37, ws=4.2, wd=45, hum=75)")
try:
    import numpy as np
    lat, lng = 7.47, 80.37
    ws, wd, hum = 4.2, 45.0, 75.0

    wu = ws * math.cos(math.radians(wd))
    wv = ws * math.sin(math.radians(wd))

    X  = np.array([[wu, wv, ws, wd, hum]])
    Xs = scaler.transform(X)

    d_lat = float(model_lat.predict(Xs)[0])
    d_lon = float(model_lon.predict(Xs)[0])

    fut_lat = lat + d_lat
    fut_lon = lng + d_lon

    dlat_km = d_lat * 111.0
    dlon_km = d_lon * 111.0 * math.cos(math.radians(lat))
    dist    = math.sqrt(dlat_km**2 + dlon_km**2)
    bearing = math.degrees(math.atan2(dlon_km, dlat_km)) % 360
    dirs    = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    direction = dirs[int((bearing + 22.5) / 45) % 8]

    check("Prediction runs without error", True)
    check(f"Future lat in range  ({fut_lat:.4f}°)",
          5.0 <= fut_lat <= 12.0,
          "expected 5–12° for Sri Lanka")
    check(f"Future lon in range  ({fut_lon:.4f}°)",
          78.0 <= fut_lon <= 83.0,
          "expected 78–83° for Sri Lanka")
    check(f"Movement distance    ({dist:.2f} km)",
          dist < 100,
          "WARN if > 100 km" if dist >= 100 else "OK")
    if dist >= 100:
        print(f"  {WARN}  Movement {dist:.1f} km exceeds typical LSD spread. "
              f"Review training data.")
    check(f"Direction returned   ({direction})", direction in dirs)

    print(f"\n       Day+7 location : {fut_lat:.4f}°, {fut_lon:.4f}°")
    print(f"       Movement       : {dist:.2f} km  {direction}  ({bearing:.1f}°)")

except Exception as e:
    check("Prediction", False, str(e))

# ── 4. Open-Meteo API reachable ───────────────────────────
print("\n[4] Open-Meteo API connectivity")
try:
    import requests
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=7.47&longitude=80.37"
        "&hourly=wind_speed_10m&forecast_days=1",
        timeout=8
    )
    ok = r.status_code == 200
    if ok:
        ws_live = r.json()['hourly']['wind_speed_10m'][12]
        check("API reachable", True, f"wind at noon = {ws_live} m/s")
    else:
        check("API reachable", False, f"HTTP {r.status_code}")
except Exception as e:
    check("API reachable", False, str(e))
    print(f"  {WARN}  Fallback defaults (4.0 m/s, 90°, 75% hum) will be used.")

# ── 5. Flask import ───────────────────────────────────────
print("\n[5] Flask")
try:
    from flask import Flask
    check("flask importable", True)
except ImportError as e:
    check("flask importable", False, str(e))

# ── 6. Port 5000 free ─────────────────────────────────────
print("\n[6] Port 5000")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    result = s.connect_ex(('127.0.0.1', 5000))
    s.close()
    if result == 0:
        check("Port 5000 free", False,
              "something already listening — stop it before running web_demo.py")
    else:
        check("Port 5000 free", True)
except Exception as e:
    check("Port 5000 free", False, str(e))

# ── 7. Template file exists ───────────────────────────────
print("\n[7] Template")
check("templates/index.html exists",
      os.path.isfile("templates/index.html"))

# ── Summary ───────────────────────────────────────────────
total  = len(results)
passed = sum(results)
failed = total - passed

print()
print("=" * 55)
if failed == 0:
    print(f"  ALL {total} CHECKS PASSED — ready to demo")
    print()
    print("  Run:  python web_demo.py")
    print("  Open: http://localhost:5000")
else:
    print(f"  {passed}/{total} PASSED  |  {failed} FAILED")
    print()
    print("  Fix the FAILED items above before presenting.")
print("=" * 55)
print()

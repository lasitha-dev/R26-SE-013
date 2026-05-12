"""
STEP 7 - DEMO TEST
Test the PISTES prediction model
"""
import sys
import math
import joblib
import numpy as np

print("="*50)
print("STEP 7: DEMO TEST")
print("="*50)

# Load models
print("\nLoading models...")
model_lat = joblib.load('models/model_lat.pkl')
model_lon = joblib.load('models/model_lon.pkl')
scaler = joblib.load('models/feature_scaler.pkl')

# Test parameters
latitude = 7.47
longitude = 80.37
wind_speed = 4.2
wind_direction = 45

# Convert wind to u/v
wd_rad = math.radians(wind_direction)
wind_u = wind_speed * math.cos(wd_rad)
wind_v = wind_speed * math.sin(wd_rad)

# Prepare features
features = np.array([[wind_u, wind_v, wind_speed, wind_direction]])
feat_scaled = scaler.transform(features)

# Predict
delta_lat = model_lat.predict(feat_scaled)[0]
delta_lon = model_lon.predict(feat_scaled)[0]

# Calculate results
future_lat = latitude + delta_lat
future_lon = longitude + delta_lon

dist_lat_km = delta_lat * 111.0
dist_lon_km = delta_lon * 111.0 * math.cos(math.radians(latitude))
dist_km = math.sqrt(dist_lat_km**2 + dist_lon_km**2)

bearing = math.degrees(math.atan2(delta_lon, delta_lat)) % 360
dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
dir_idx = int((bearing + 22.5) / 45) % 8
direction = dirs[dir_idx]

# Confidence
if dist_km < 10:
    confidence = "HIGH"
elif dist_km < 25:
    confidence = "MEDIUM"
else:
    confidence = "LOW"

# Warning
warning = ""
if dist_km > 30:
    warning = "⚠️  Exceeds LSD biological spread range (30km)."

# Display results
print("\n" + "="*50)
print("  PISTES — LSD TRAJECTORY PREDICTION")
print("="*50)
print(f"  Input location  : {latitude}, {longitude}")
print(f"  Wind            : {wind_speed} m/s @ {wind_direction}°")
print("-"*50)
print(f"  Day+7 location  : {future_lat:.4f}, {future_lon:.4f}")
print(f"  Movement        : {dist_km:.2f} km")
print(f"  Direction       : {direction}")
print(f"  Bearing         : {bearing:.1f}°")
print(f"  Confidence      : {confidence}")
print("-"*50)
print(f"  wind_u          : {wind_u:.3f} m/s")
print(f"  wind_v          : {wind_v:.3f} m/s")
if warning:
    print(f"  WARNING         : {warning}")
print("="*50)

print("\nExpected results:")
print("  ✓ Movement: 2-25 km (within biological range)")
print("  ✓ Direction: NorthEast (wind=45°)")
print("  ✓ Confidence: MEDIUM")
print("  ✓ No movement > 30km = BUG")

success = (2 <= dist_km <= 25) and direction in ["N", "NE", "NW"] and confidence in ["HIGH", "MEDIUM"]

if success:
    print(f"\n✅ Demo test PASSED!")
else:
    print(f"\n❌ Demo test FAILED!")
    sys.exit(1)

print(f"\nStep 7 complete.")

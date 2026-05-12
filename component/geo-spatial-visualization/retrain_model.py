"""
PHASE 2: RETRAIN MODEL WITH REAL WIND DATA
Uses Ridge Regression with real meteorological data from Open-Meteo
Includes wind sensitivity testing to verify model responsiveness
"""

from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
import numpy as np
import joblib
import pandas as pd
import math

print("="*70)
print("PHASE 2: RETRAIN MODEL WITH REAL WIND DATA")
print("="*70)

# Load real wind data
pairs = pd.read_csv('data/processed/lsd_with_wind_real.csv')
n = len(pairs)

print(f"\nLoading training data...")
print(f"  Pairs with real wind: {n}")
print(f"  Source: Open-Meteo Archive API")

# Prepare features and targets
FEATURES = ['wind_u', 'wind_v', 'wind_speed', 'wind_direction', 'humidity']

X = pairs[FEATURES].values
y_lat = pairs['delta_lat'].values
y_lon = pairs['delta_lon'].values

print(f"\nFeatures used:")
for feat in FEATURES:
    print(f"  • {feat}")

# Normalize features
print(f"\nScaling features with MinMaxScaler...")
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, 'models/scaler.pkl')
print(f"  ✓ Scaler saved")

# Train latitude model
print(f"\nTraining Latitude Model (Ridge CV)...")
model_lat = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100],
    cv=5,
    scoring='neg_mean_absolute_error'
)
model_lat.fit(X_scaled, y_lat)
print(f"  ✓ Optimal alpha: {model_lat.alpha_}")

# Train longitude model
print(f"\nTraining Longitude Model (Ridge CV)...")
model_lon = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100],
    cv=5,
    scoring='neg_mean_absolute_error'
)
model_lon.fit(X_scaled, y_lon)
print(f"  ✓ Optimal alpha: {model_lon.alpha_}")

# Save models
joblib.dump(model_lat, 'models/model_lat.pkl')
joblib.dump(model_lon, 'models/model_lon.pkl')
print(f"\n✓ Models saved to models/")

# Evaluate performance
print(f"\n" + "="*70)
print("MODEL EVALUATION (on training data)")
print("="*70)

pred_lat = model_lat.predict(X_scaled)
pred_lon = model_lon.predict(X_scaled)

mae_lat = mean_absolute_error(y_lat, pred_lat)
mae_lon = mean_absolute_error(y_lon, pred_lon)
rmse_lat = np.sqrt(mean_squared_error(y_lat, pred_lat))
rmse_lon = np.sqrt(mean_squared_error(y_lon, pred_lon))
r2_lat = r2_score(y_lat, pred_lat)
r2_lon = r2_score(y_lon, pred_lon)

# Convert to km
mae_lat_km = mae_lat * 111.0
mae_lon_km = mae_lon * 111.0
rmse_lat_km = rmse_lat * 111.0
rmse_lon_km = rmse_lon * 111.0

print(f"\nDELTA_LATITUDE Model:")
print(f"  MAE         : {mae_lat_km:.2f} km")
print(f"  RMSE        : {rmse_lat_km:.2f} km")
print(f"  R² Score    : {r2_lat:.6f}")
print(f"  Alpha       : {model_lat.alpha_}")

print(f"\nDELTA_LONGITUDE Model:")
print(f"  MAE         : {mae_lon_km:.2f} km")
print(f"  RMSE        : {rmse_lon_km:.2f} km")
print(f"  R² Score    : {r2_lon:.6f}")
print(f"  Alpha       : {model_lon.alpha_}")

avg_mae_km = (mae_lat_km + mae_lon_km) / 2
print(f"\nAverage MAE: {avg_mae_km:.2f} km")
print(f"Training Pairs: {n}")

# Wind sensitivity test - CRITICAL
print(f"\n" + "="*70)
print("WIND SENSITIVITY TEST (CRITICAL)")
print("="*70)
print("\nTesting: Do different winds produce different predictions?")
print("If yes → Model is working! ✅")
print("If no  → Model learned nothing ❌")

test_winds = [
    (2.0, 0,   "Slow North Wind   (2 m/s @ 0°)   "),
    (8.0, 0,   "Fast North Wind   (8 m/s @ 0°)   "),
    (2.0, 90,  "Slow East Wind    (2 m/s @ 90°)  "),
    (8.0, 90,  "Fast East Wind    (8 m/s @ 90°)  "),
    (5.0, 180, "Medium South Wind (5 m/s @ 180°) "),
    (5.0, 270, "Medium West Wind  (5 m/s @ 270°) "),
]

predictions = []
for spd, drn, label in test_winds:
    wu = spd * math.cos(math.radians(drn))
    wv = spd * math.sin(math.radians(drn))
    
    X_test = np.array([[wu, wv, spd, drn, 75]])
    X_ts = scaler.transform(X_test)
    
    d_lat = float(model_lat.predict(X_ts)[0])
    d_lon = float(model_lon.predict(X_ts)[0])
    
    d_lat_km = d_lat * 111.0
    d_lon_km = d_lon * 111.0 * math.cos(math.radians(7.5))  # Sri Lanka lat
    
    d_km = math.sqrt(d_lat_km**2 + d_lon_km**2)
    
    predictions.append(d_km)
    bearing = math.degrees(math.atan2(d_lon_km, d_lat_km)) % 360
    
    dirs_map = {0:'N', 45:'NE', 90:'E', 135:'SE', 180:'S', 225:'SW', 270:'W', 315:'NW'}
    direction = dirs_map.get(min(dirs_map.keys(), key=lambda x: abs(x - bearing)), 'N')
    
    print(f"  {label} → {d_km:6.2f} km {direction}")

# Check if predictions vary
unique_preds = len(set([round(p, 1) for p in predictions]))
print(f"\nUnique predictions (rounded): {unique_preds}/6")

if unique_preds >= 4:
    print(f"✅ WIND SENSITIVITY: EXCELLENT")
    print(f"   Model responds to wind variations!")
elif unique_preds >= 2:
    print(f"⚠️  WIND SENSITIVITY: MODERATE")
    print(f"   Model shows some wind response")
else:
    print(f"❌ WIND SENSITIVITY: FAILED")
    print(f"   Model not responding to wind changes")

# Save metrics
metrics_df = pd.DataFrame([
    {
        'model': 'model_lat',
        'mae_km': round(mae_lat_km, 2),
        'rmse_km': round(rmse_lat_km, 2),
        'r2': round(r2_lat, 6),
        'training_pairs': n,
        'wind_source': 'real_api',
        'alpha': model_lat.alpha_
    },
    {
        'model': 'model_lon',
        'mae_km': round(mae_lon_km, 2),
        'rmse_km': round(rmse_lon_km, 2),
        'r2': round(r2_lon, 6),
        'training_pairs': n,
        'wind_source': 'real_api',
        'alpha': model_lon.alpha_
    }
])

metrics_df.to_csv('data/output/model_metrics_real.csv', index=False)

print(f"\n" + "="*70)
print(f"PHASE 2 COMPLETE")
print("="*70)
print(f"\n✓ Models trained with {n} real-wind pairs")
print(f"✓ Average MAE: {avg_mae_km:.2f} km")
print(f"✓ Wind sensitivity: {['FAILED','MODERATE','EXCELLENT'][min(unique_preds//3, 2)]}")
print(f"✓ Metrics saved: data/output/model_metrics_real.csv")
print(f"\nReady for PHASE 3: Interactive Demo")
print("="*70)

# Show sample predictions
print(f"\nSample predictions on real data:")
sample_indices = np.random.choice(len(pairs), min(5, len(pairs)), replace=False)
print(pairs.iloc[sample_indices][['country', 'movement_km', 'wind_speed', 
                                   'wind_direction', 'humidity']].to_string())

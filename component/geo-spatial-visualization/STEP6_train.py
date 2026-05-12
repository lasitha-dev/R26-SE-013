"""
STEP 6: TRAIN RIDGE REGRESSION MODELS
Train two separate models: delta_lat and delta_lon
"""
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import joblib
import pandas as pd

print("="*70)
print("STEP 6: TRAIN RIDGE REGRESSION MODELS")
print("="*70)

pairs = pd.read_csv('data/processed/lsd_with_wind.csv')
n = len(pairs)
print(f"\nTraining on {n} pairs")

if n == 0:
    print("ERROR: No training data!")
    exit()

# Feature selection
FEATURES = [
    'wind_u', 'wind_v',
    'wind_speed', 'wind_direction',
    'humidity'
]

X     = pairs[FEATURES].values
y_lat = pairs['delta_lat'].values
y_lon = pairs['delta_lon'].values

print(f"\nFeatures: {FEATURES}")
print(f"Training samples: {n}")

print(f"\nFeature statistics:")
for i, feat in enumerate(FEATURES):
    print(f"  {feat:20s}: min={X[:,i].min():8.3f}, max={X[:,i].max():8.3f}, mean={X[:,i].mean():8.3f}")

print(f"\nTarget statistics:")
print(f"  delta_lat: min={y_lat.min():.6f}, max={y_lat.max():.6f}, mean={y_lat.mean():.6f}")
print(f"  delta_lon: min={y_lon.min():.6f}, max={y_lon.max():.6f}, mean={y_lon.mean():.6f}")

# Normalization with MinMaxScaler
scaler   = MinMaxScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, 'models/scaler.pkl')

print(f"\n✅ Feature scaling applied (MinMaxScaler)")

# Train models with cross-validation
cv_folds = min(5, max(2, n // 100))  # Adaptive CV folds
print(f"\nCross-validation folds: {cv_folds}")

print(f"\nTraining delta_latitude model...")
model_lat = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100, 1000],
    cv=cv_folds,
    scoring='neg_mean_absolute_error'
)
model_lat.fit(X_scaled, y_lat)

print(f"Training delta_longitude model...")
model_lon = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100, 1000],
    cv=cv_folds,
    scoring='neg_mean_absolute_error'
)
model_lon.fit(X_scaled, y_lon)

# Save models
joblib.dump(model_lat, 'models/model_lat.pkl')
joblib.dump(model_lon, 'models/model_lon.pkl')

print(f"\n✅ Models saved")

# Evaluate on training data
y_lat_pred = model_lat.predict(X_scaled)
y_lon_pred = model_lon.predict(X_scaled)

mae_lat = mean_absolute_error(y_lat, y_lat_pred)
mae_lon = mean_absolute_error(y_lon, y_lon_pred)
rmse_lat = np.sqrt(mean_squared_error(y_lat, y_lat_pred))
rmse_lon = np.sqrt(mean_squared_error(y_lon, y_lon_pred))
r2_lat = r2_score(y_lat, y_lat_pred)
r2_lon = r2_score(y_lon, y_lon_pred)

mae_lat_km = mae_lat * 111.0
mae_lon_km = mae_lon * 111.0
rmse_lat_km = rmse_lat * 111.0
rmse_lon_km = rmse_lon * 111.0

print(f"\n{'='*70}")
print(f"MODEL PERFORMANCE (Training Set)")
print(f"{'='*70}")

print(f"\nModel 1: DELTA_LATITUDE")
print(f"  Alpha: {model_lat.alpha_:.6f}")
print(f"  MAE: {mae_lat:.6f}° ({mae_lat_km:.2f} km)")
print(f"  RMSE: {rmse_lat:.6f}° ({rmse_lat_km:.2f} km)")
print(f"  R² Score: {r2_lat:.6f}")

print(f"\nModel 2: DELTA_LONGITUDE")
print(f"  Alpha: {model_lon.alpha_:.6f}")
print(f"  MAE: {mae_lon:.6f}° ({mae_lon_km:.2f} km)")
print(f"  RMSE: {rmse_lon:.6f}° ({rmse_lon_km:.2f} km)")
print(f"  R² Score: {r2_lon:.6f}")

print(f"\nAverage MAE: {(mae_lat_km + mae_lon_km)/2:.2f} km")

# Biological validation on training predictions
pred_lat_km = y_lat_pred * 111.0
pred_lon_km = y_lon_pred * 111.0
pred_dist = np.sqrt(pred_lat_km**2 + pred_lon_km**2)

print(f"\n{'='*70}")
print(f"PREDICTED MOVEMENT RANGE (Training Data)")
print(f"{'='*70}")
print(f"  Min: {pred_dist.min():.2f} km")
print(f"  Max: {pred_dist.max():.2f} km")
print(f"  Mean: {pred_dist.mean():.2f} km")
print(f"  Median: {np.median(pred_dist):.2f} km")

# Reliability assessment
if n < 100:
    reliability = "LOW (proof-of-concept only, need 500+ pairs)"
elif n < 500:
    reliability = "MEDIUM (limited validation, use with caution)"
elif n < 1000:
    reliability = "GOOD (reasonable confidence)"
else:
    reliability = "EXCELLENT (production-ready)"

print(f"\nReliability: {reliability}")

# Check for unrealistic predictions
outliers = (pred_dist > 100).sum()
if outliers > 0:
    print(f"\n⚠️  WARNING: {outliers} predictions > 100km")
    print(f"  This suggests training data may include multi-day outbreak progressions")
else:
    print(f"\n✅ Biological validation: PASS")
    print(f"   All predictions within realistic range (< 50km typical)")

# Save metrics
metrics = pd.DataFrame([{
    'model': 'delta_lat',
    'alpha': model_lat.alpha_,
    'mae_deg': mae_lat,
    'mae_km': mae_lat_km,
    'rmse_deg': rmse_lat,
    'rmse_km': rmse_lat_km,
    'r2_score': r2_lat,
    'training_samples': n,
    'reliability': reliability
},{
    'model': 'delta_lon',
    'alpha': model_lon.alpha_,
    'mae_deg': mae_lon,
    'mae_km': mae_lon_km,
    'rmse_deg': rmse_lon,
    'rmse_km': rmse_lon_km,
    'r2_score': r2_lon,
    'training_samples': n,
    'reliability': reliability
}])

metrics.to_csv('data/output/model_metrics.csv', index=False)

print(f"\n{'='*70}")
print(f"✅ Step 6 Complete")
print(f"   Models saved: models/model_lat.pkl, models/model_lon.pkl")
print(f"   Scaler saved: models/scaler.pkl")
print(f"   Metrics saved: data/output/model_metrics.csv")
print(f"   Training pairs: {n}")
print(f"{'='*70}")

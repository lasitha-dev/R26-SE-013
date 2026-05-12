"""
STEP 5 - TRAIN MODEL
Train Ridge regression models for latitude and longitude deltas
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
import joblib

print("="*50)
print("STEP 5: TRAIN MODEL")
print("="*50)

pairs = pd.read_csv('data/processed/lsd_training_pairs.csv')
print(f"Training on {len(pairs)} pairs")

FEATURES = ['wind_u', 'wind_v', 'wind_speed', 'wind_direction']

X = pairs[FEATURES].values
y_lat = pairs['delta_lat'].values
y_lon = pairs['delta_lon'].values

# Normalize features
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, 'models/feature_scaler.pkl')

# Determine cross-validation size
n = len(X)
cv_val = min(5, n) if n >= 3 else 2

# Train latitude model
print(f"\nTraining latitude model with CV={cv_val}...")
model_lat = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100, 1000],
    cv=cv_val
)
model_lat.fit(X_scaled, y_lat)

# Train longitude model
print(f"Training longitude model with CV={cv_val}...")
model_lon = RidgeCV(
    alphas=[0.001, 0.01, 0.1, 1, 10, 100, 1000],
    cv=cv_val
)
model_lon.fit(X_scaled, y_lon)

joblib.dump(model_lat, 'models/model_lat.pkl')
joblib.dump(model_lon, 'models/model_lon.pkl')

# Evaluate
pred_lat = model_lat.predict(X_scaled)
pred_lon = model_lon.predict(X_scaled)

mae_lat = mean_absolute_error(y_lat, pred_lat)
mae_lon = mean_absolute_error(y_lon, pred_lon)

# Convert MAE to km (1 degree ≈ 111 km)
mae_lat_km = mae_lat * 111.0
mae_lon_km = mae_lon * 111.0

print("\n" + "="*50)
print("TRAINING RESULTS")
print("="*50)
print(f"Pairs used      : {n}")
print(f"MAE delta_lat   : {mae_lat:.6f}° = {mae_lat_km:.2f} km")
print(f"MAE delta_lon   : {mae_lon:.6f}° = {mae_lon_km:.2f} km")
print(f"Alpha lat       : {model_lat.alpha_}")
print(f"Alpha lon       : {model_lon.alpha_}")

# Biological check
avg_mae_km = (mae_lat_km + mae_lon_km) / 2
if avg_mae_km < 30:
    print(f"Biological check: ✅ PASS ({avg_mae_km:.1f} km < 30 km)")
else:
    print(f"Biological check: ⚠️  WARNING ({avg_mae_km:.1f} km > 30 km)")
    print("Model may have limited training data.")

# Save metrics
metrics = pd.DataFrame([{
    'model': 'model_lat',
    'mae_degrees': round(mae_lat, 6),
    'mae_km': round(mae_lat_km, 2),
    'training_pairs': n
}, {
    'model': 'model_lon',
    'mae_degrees': round(mae_lon, 6),
    'mae_km': round(mae_lon_km, 2),
    'training_pairs': n
}])
metrics.to_csv('data/output/model_metrics.csv', index=False)

print(f"\nStep 5 complete.")

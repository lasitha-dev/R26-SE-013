import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import RidgeCV
from sklearn.metrics import (
    mean_absolute_error, r2_score
)
from sklearn.model_selection import (
    cross_val_score, KFold
)
import joblib
import math

df = pd.read_csv(
    'data/processed/lsd_real_wind_final.csv'
)

print(f"Training pairs: {len(df)}")
print(f"Real wind: "
      f"{(df['source']=='real_archive').sum()}")

# === FEATURE ENGINEERING ===
# Add month (seasonal signal)
df['report_date_dt'] = pd.to_datetime(
    df['date_d']
)
df['month'] = df['report_date_dt'].dt.month
df['month_sin'] = np.sin(
    2 * np.pi * df['month'] / 12
)
df['month_cos'] = np.cos(
    2 * np.pi * df['month'] / 12
)

# Wind magnitude
df['wind_magnitude'] = np.sqrt(
    df['wind_u']**2 + df['wind_v']**2
)

# Days gap (longer gap = more spread)
df['days_gap_norm'] = df['days_gap'] / 21.0

FEATURES = [
    'wind_u',
    'wind_v',
    'wind_speed',
    'wind_magnitude',
    'wind_direction',
    'humidity',
    'temperature',
    'days_gap_norm',
    'month_sin',
    'month_cos'
]

# Use only available columns
FEATURES = [
    f for f in FEATURES
    if f in df.columns
]

print(f"Features used: {FEATURES}")

X     = df[FEATURES].fillna(0).values
y_lat = df['delta_lat'].values
y_lon = df['delta_lon'].values

# Target stats
print(f"\nTarget statistics:")
print(f"  delta_lat: "
      f"{y_lat.min():.4f} to "
      f"{y_lat.max():.4f}°")
print(f"  delta_lon: "
      f"{y_lon.min():.4f} to "
      f"{y_lon.max():.4f}°")
print(f"  delta_lat km: "
      f"{(y_lat*111).min():.1f} to "
      f"{(y_lat*111).max():.1f} km")

# Scale features
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, 'models/scaler.pkl')

n = len(X)
cv = KFold(
    n_splits=min(5, n//10),
    shuffle=True,
    random_state=42
)

# Train latitude model
alphas = [
    0.001, 0.01, 0.1, 1, 10, 100, 1000
]
model_lat = RidgeCV(
    alphas=alphas,
    cv=cv,
    scoring='neg_mean_absolute_error'
)
model_lat.fit(X_scaled, y_lat)

# Train longitude model
model_lon = RidgeCV(
    alphas=alphas,
    cv=cv,
    scoring='neg_mean_absolute_error'
)
model_lon.fit(X_scaled, y_lon)

# Save models
joblib.dump(model_lat, 'models/model_lat.pkl')
joblib.dump(model_lon, 'models/model_lon.pkl')

# Evaluate
pred_lat = model_lat.predict(X_scaled)
pred_lon = model_lon.predict(X_scaled)

mae_lat_km = mean_absolute_error(
    y_lat, pred_lat
) * 111.0
mae_lon_km = mean_absolute_error(
    y_lon, pred_lon
) * 111.0
r2_lat = r2_score(y_lat, pred_lat)
r2_lon = r2_score(y_lon, pred_lon)

print("\n" + "="*50)
print("TRAINING RESULTS")
print("="*50)
print(f"Pairs     : {n}")
print(f"Features  : {len(FEATURES)}")
print(f"Alpha lat : {model_lat.alpha_}")
print(f"Alpha lon : {model_lon.alpha_}")
print(f"MAE lat   : {mae_lat_km:.2f} km")
print(f"MAE lon   : {mae_lon_km:.2f} km")
print(f"Avg MAE   : "
      f"{(mae_lat_km+mae_lon_km)/2:.2f} km")
print(f"R² lat    : {r2_lat:.4f}")
print(f"R² lon    : {r2_lon:.4f}")

# Feature importance
print(f"\nTop features (lat model):")
importances = list(zip(
    FEATURES, model_lat.coef_
))
importances.sort(
    key=lambda x: abs(x[1]), reverse=True
)
for feat, coef in importances[:5]:
    print(f"  {feat}: {coef:.6f}")

# === WIND SENSITIVITY TEST ===
print("\n" + "="*50)
print("WIND SENSITIVITY TEST")
print("="*50)
print("Same location, different winds:")
print("Expected: all values DIFFERENT")

test_scenarios = [
    (2.0,   0, 75, 28, "Light wind North"),
    (8.0,   0, 75, 28, "Strong wind North"),
    (2.0,  90, 75, 28, "Light wind East"),
    (8.0,  90, 75, 28, "Strong wind East"),
    (5.0, 180, 75, 28, "Medium wind South"),
    (5.0, 270, 75, 28, "Medium wind West"),
]

predictions = []
for ws, wd, hm, tm, label in test_scenarios:
    wu = ws * math.cos(math.radians(wd))
    wv = ws * math.sin(math.radians(wd))
    wm = math.sqrt(wu**2 + wv**2)

    feat_vals = {
        'wind_u':         wu,
        'wind_v':         wv,
        'wind_speed':     ws,
        'wind_magnitude': wm,
        'wind_direction': wd,
        'humidity':       hm,
        'temperature':    tm,
        'days_gap_norm':  0.5,
        'month_sin':      0.5,
        'month_cos':      0.5
    }

    X_test = np.array([[
        feat_vals.get(f, 0.0)
        for f in FEATURES
    ]])
    X_ts = scaler.transform(X_test)

    d_lat = float(model_lat.predict(X_ts)[0])
    d_lon = float(model_lon.predict(X_ts)[0])
    d_lat_km = d_lat * 111.0
    d_lon_km = d_lon * 111.0 * math.cos(
        math.radians(7.47)
    )
    dist = math.sqrt(d_lat_km**2 + d_lon_km**2)
    predictions.append(dist)

    print(f"  {label:<22}: {dist:.2f} km")

unique = len(set(round(p,1) for p in predictions))
print(f"\nUnique values: {unique}/6")

if unique >= 4:
    print("Wind sensitivity: EXCELLENT [PASS]")
elif unique >= 2:
    print("Wind sensitivity: PARTIAL [WARN]")
else:
    print("Wind sensitivity: FAILED [FAIL]")
    print("Model still not learning!")

# Save metrics
pd.DataFrame([{
    'model':   'model_lat',
    'mae_km':  round(mae_lat_km, 2),
    'r2':      round(r2_lat, 4),
    'alpha':   model_lat.alpha_,
    'pairs':   n,
    'features': len(FEATURES)
},{
    'model':   'model_lon',
    'mae_km':  round(mae_lon_km, 2),
    'r2':      round(r2_lon, 4),
    'alpha':   model_lon.alpha_,
    'pairs':   n,
    'features': len(FEATURES)
}]).to_csv(
    'data/output/model_metrics_final.csv',
    index=False
)
print("\nMetrics saved to model_metrics_final.csv")

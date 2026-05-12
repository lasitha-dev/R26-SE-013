import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

print('='*80)
print('STEP 5: TRAIN RIDGE REGRESSION MODELS')
print('='*80)

# Read training dataset
train_df = pd.read_csv('data/processed/lsd_model_training_dataset.csv')

print(f'Training dataset size: {len(train_df)} records')

# Features
X = train_df[['wind_speed', 'wind_direction', 'rainfall']]
y_lat = train_df['delta_lat']
y_lon = train_df['delta_lon']

print(f'\nInput Features:')
print(f'  - wind_speed: {X["wind_speed"].min():.2f} to {X["wind_speed"].max():.2f}')
print(f'  - wind_direction: {X["wind_direction"].min():.1f} to {X["wind_direction"].max():.1f}')
print(f'  - rainfall: {X["rainfall"].min():.2f} to {X["rainfall"].max():.2f}')

print(f'\nTarget Variables:')
print(f'  - delta_lat: {y_lat.min():.6f} to {y_lat.max():.6f}')
print(f'  - delta_lon: {y_lon.min():.6f} to {y_lon.max():.6f}')

# Train models with Ridge Regression (alpha=1.0)
alpha = 1.0
model_lat = Ridge(alpha=alpha)
model_lon = Ridge(alpha=alpha)

model_lat.fit(X, y_lat)
model_lon.fit(X, y_lon)

# Predictions
y_lat_pred = model_lat.predict(X)
y_lon_pred = model_lon.predict(X)

# Evaluate models
mae_lat = mean_absolute_error(y_lat, y_lat_pred)
mae_lon = mean_absolute_error(y_lon, y_lon_pred)
rmse_lat = np.sqrt(mean_squared_error(y_lat, y_lat_pred))
rmse_lon = np.sqrt(mean_squared_error(y_lon, y_lon_pred))
r2_lat = r2_score(y_lat, y_lat_pred)
r2_lon = r2_score(y_lon, y_lon_pred)

print(f'\n{"="*80}')
print(f'MODEL 1: DELTA_LAT PREDICTION')
print(f'{"="*80}')
print(f'Algorithm: Ridge Regression (alpha={alpha})')
print(f'Samples: {len(X)}')
print(f'\nMetrics:')
print(f'  Mean Absolute Error (MAE):    {mae_lat:.6f}')
print(f'  Root Mean Squared Error (RMSE): {rmse_lat:.6f}')
print(f'  R² Score:                      {r2_lat:.6f}')

print(f'\nModel Coefficients:')
for feat, coef in zip(X.columns, model_lat.coef_):
    print(f'  {feat:20s}: {coef:12.8f}')
print(f'  Intercept:          {model_lat.intercept_:12.8f}')

print(f'\n{"="*80}')
print(f'MODEL 2: DELTA_LON PREDICTION')
print(f'{"="*80}')
print(f'Algorithm: Ridge Regression (alpha={alpha})')
print(f'Samples: {len(X)}')
print(f'\nMetrics:')
print(f'  Mean Absolute Error (MAE):    {mae_lon:.6f}')
print(f'  Root Mean Squared Error (RMSE): {rmse_lon:.6f}')
print(f'  R² Score:                      {r2_lon:.6f}')

print(f'\nModel Coefficients:')
for feat, coef in zip(X.columns, model_lon.coef_):
    print(f'  {feat:20s}: {coef:12.8f}')
print(f'  Intercept:          {model_lon.intercept_:12.8f}')

# Save models
model_lat_path = 'models/lsd_delta_lat_model.pkl'
model_lon_path = 'models/lsd_delta_lon_model.pkl'

joblib.dump(model_lat, model_lat_path)
joblib.dump(model_lon, model_lon_path)

print(f'\n✅ Model 1 saved: {model_lat_path}')
print(f'✅ Model 2 saved: {model_lon_path}')

# Save metrics to CSV
metrics_df = pd.DataFrame({
    'model': ['delta_lat', 'delta_lon'],
    'algorithm': ['Ridge Regression', 'Ridge Regression'],
    'alpha': [alpha, alpha],
    'training_samples': [len(X), len(X)],
    'mae': [mae_lat, mae_lon],
    'rmse': [rmse_lat, rmse_lon],
    'r2_score': [r2_lat, r2_lon]
})

metrics_path = 'data/output/model_metrics.csv'
metrics_df.to_csv(metrics_path, index=False)
print(f'✅ Metrics saved: {metrics_path}')

print(f'\nMetrics Summary:')
print(metrics_df.to_string(index=False))

print(f'\n{"="*80}')
print('STEP 5 COMPLETE - Models Trained and Saved')
print(f'{"="*80}')

print(f'\n⚠️  NOTE: Small dataset (7 samples) - models are illustrative')
print(f'    In production, use larger datasets for robust predictions')

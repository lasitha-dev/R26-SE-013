import pandas as pd
import numpy as np

print('='*80)
print('STEP 4: ADD ENVIRONMENTAL FEATURES (PLACEHOLDER VALUES)')
print('='*80)

# Read movement pairs
pairs_df = pd.read_csv('data/processed/lsd_training_pairs.csv')

print(f'Starting with {len(pairs_df)} movement pairs')

# Add realistic placeholder environmental features
# For Thailand during December-January (dry season) and May-October (rainy season)
# These are realistic values based on Thailand climate data

np.random.seed(42)  # For reproducibility

# Realistic, calibrated placeholder values for Thailand LSD outbreak context
wind_speeds = np.array([5.2, 4.8, 6.1, 5.5, 5.9, 4.6, 7.2])  # m/s - typical dry/wet season
wind_directions = np.array([45, 90, 135, 270, 180, 45, 90])   # degrees (0-360)
rainfall_mm = np.array([0.5, 0.8, 2.1, 1.2, 0.9, 3.5, 15.2]) # mm/day during dry and wet seasons

pairs_df['wind_speed'] = wind_speeds
pairs_df['wind_direction'] = wind_directions
pairs_df['rainfall'] = rainfall_mm
pairs_df['placeholder_environment'] = True

print(f'\n✅ Environmental features added:')
print(f'  - wind_speed (m/s)')
print(f'  - wind_direction (degrees 0-360)')
print(f'  - rainfall (mm/day)')
print(f'  - placeholder_environment = True')

print(f'\nEnvironmental features - Statistics:')
print(f'\nWind Speed (m/s):')
print(f'  Min: {pairs_df["wind_speed"].min():.1f}')
print(f'  Max: {pairs_df["wind_speed"].max():.1f}')
print(f'  Mean: {pairs_df["wind_speed"].mean():.2f}')

print(f'\nWind Direction (degrees):')
print(f'  Min: {pairs_df["wind_direction"].min():.1f}')
print(f'  Max: {pairs_df["wind_direction"].max():.1f}')
print(f'  Mean: {pairs_df["wind_direction"].mean():.1f}')

print(f'\nRainfall (mm/day):')
print(f'  Min: {pairs_df["rainfall"].min():.1f}')
print(f'  Max: {pairs_df["rainfall"].max():.1f}')
print(f'  Mean: {pairs_df["rainfall"].mean():.2f}')

print(f'\nFinal training dataset columns:')
print(pairs_df.columns.tolist())

print(f'\nFirst 10 records with environmental features:')
cols_to_show = ['case_id', 'date_d', 'lat_d', 'lon_d', 'delta_lat', 'delta_lon', 
                'wind_speed', 'wind_direction', 'rainfall', 'placeholder_environment']
print(pairs_df[cols_to_show].to_string())

# Save final training dataset
output_path = 'data/processed/lsd_model_training_dataset.csv'
pairs_df.to_csv(output_path, index=False)
print(f'\n✅ Final training dataset saved: {output_path}')

print(f'\nDataset shape: {pairs_df.shape[0]} rows × {pairs_df.shape[1]} columns')

print('\n' + '='*80)
print('STEP 4 COMPLETE - Environmental Features Added')
print('='*80)
print('\n⚠️  NOTE: All environmental values are REALISTIC PLACEHOLDERS')
print('    In production, these should be fetched from weather API')

import pandas as pd
import numpy as np
from datetime import timedelta

print('='*80)
print('STEP 3: CREATE MOVEMENT PAIRS (D → D+7)')
print('='*80)

# Read cleaned data
cleaned = pd.read_csv('data/processed/cleaned_lsd_cases.csv')
cleaned['report_date'] = pd.to_datetime(cleaned['report_date'])

print(f'Starting records: {len(cleaned)}')

# Sort by date
cleaned = cleaned.sort_values('report_date').reset_index(drop=True)

# Create movement pairs
movement_pairs = []

for idx, current_row in cleaned.iterrows():
    current_date = current_row['report_date']
    current_lat = current_row['latitude']
    current_lon = current_row['longitude']
    current_id = current_row['case_id']
    
    # Look for future records within 5-10 days
    min_days = 5
    max_days = 10
    
    future_records = cleaned[
        (cleaned['report_date'] > current_date) &
        (cleaned['report_date'] <= current_date + timedelta(days=max_days)) &
        (cleaned['report_date'] >= current_date + timedelta(days=min_days))
    ]
    
    if len(future_records) > 0:
        # Use the closest future record
        closest_idx = (future_records['report_date'] - current_date).abs().idxmin()
        future_row = cleaned.loc[closest_idx]
        
        future_date = future_row['report_date']
        future_lat = future_row['latitude']
        future_lon = future_row['longitude']
        future_id = future_row['case_id']
        
        # Calculate deltas
        delta_lat = future_lat - current_lat
        delta_lon = future_lon - current_lon
        days_diff = (future_date - current_date).days
        
        movement_pairs.append({
            'case_id': current_id,
            'country': current_row['country'],
            'disease_type': current_row['disease_type'],
            'date_d': current_row['report_date'].strftime('%Y-%m-%d'),
            'lat_d': current_lat,
            'lon_d': current_lon,
            'future_date': future_date.strftime('%Y-%m-%d'),
            'future_lat': future_lat,
            'future_lon': future_lon,
            'delta_lat': delta_lat,
            'delta_lon': delta_lon,
            'days_diff': days_diff,
            'future_case_id': future_id
        })

pairs_df = pd.DataFrame(movement_pairs)

print(f'\n✅ Movement pairs created: {len(pairs_df)}')

if len(pairs_df) > 0:
    print(f'\nDay differences - Statistics:')
    print(f'  Min: {pairs_df["days_diff"].min()} days')
    print(f'  Max: {pairs_df["days_diff"].max()} days')
    print(f'  Mean: {pairs_df["days_diff"].mean():.2f} days')
    
    print(f'\nDelta latitude - Statistics:')
    print(f'  Min: {pairs_df["delta_lat"].min():.6f}')
    print(f'  Max: {pairs_df["delta_lat"].max():.6f}')
    print(f'  Mean: {pairs_df["delta_lat"].mean():.6f}')
    print(f'  Std: {pairs_df["delta_lat"].std():.6f}')
    
    print(f'\nDelta longitude - Statistics:')
    print(f'  Min: {pairs_df["delta_lon"].min():.6f}')
    print(f'  Max: {pairs_df["delta_lon"].max():.6f}')
    print(f'  Mean: {pairs_df["delta_lon"].mean():.6f}')
    print(f'  Std: {pairs_df["delta_lon"].std():.6f}')
    
    print(f'\nSample movement pairs:')
    print(pairs_df[['case_id', 'date_d', 'lat_d', 'lon_d', 'delta_lat', 'delta_lon', 'days_diff']].head(15).to_string())
    
    # Save to CSV
    output_path = 'data/processed/lsd_training_pairs.csv'
    pairs_df.to_csv(output_path, index=False)
    print(f'\n✅ Movement pairs saved: {output_path}')
else:
    print('⚠️ No movement pairs could be created - need more records with temporal proximity.')

print('\n' + '='*80)
print('STEP 3 COMPLETE')
print('='*80)

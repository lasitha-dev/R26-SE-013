"""
STEP 4 - CREATE MOVEMENT PAIRS
Create pairs from Thailand (train) and Sri Lanka (test)
"""
import pandas as pd
import math
from geopy.distance import geodesic

print("="*50)
print("STEP 4: CREATE MOVEMENT PAIRS")
print("="*50)

df = pd.read_csv('data/processed/lsd_with_wind.csv')
df['report_date'] = pd.to_datetime(df['report_date'])
df = df.sort_values('report_date').reset_index(drop=True)

# Separate Thailand (train) and Sri Lanka (test)
thailand_df = df[
    df['country'].str.lower() == 'thailand'
].copy()
srilanka_df = df[
    df['country'].str.lower() == 'sri lanka'
].copy()

print(f"Thailand records: {len(thailand_df)}")
print(f"Sri Lanka records: {len(srilanka_df)}")

# Pair creation parameters
MAX_DIST_KM = 30
MIN_DAYS = 3
MAX_DAYS = 14
MAX_DELTA = 0.30  # degrees

def create_pairs(source_df, label=""):
    """Create movement pairs from source data"""
    pairs = []
    source_df = source_df.sort_values('report_date').reset_index(drop=True)
    
    for i in range(len(source_df)):
        row_a = source_df.iloc[i]
        
        for j in range(i+1, len(source_df)):
            row_b = source_df.iloc[j]
            
            days_diff = (row_b['report_date'] - row_a['report_date']).days
            
            if days_diff < MIN_DAYS:
                continue
            if days_diff > MAX_DAYS:
                break
            
            dist_km = geodesic(
                (row_a['latitude'], row_a['longitude']),
                (row_b['latitude'], row_b['longitude'])
            ).kilometers
            
            if dist_km > MAX_DIST_KM:
                continue
            
            # Targets in degrees
            delta_lat = row_b['latitude'] - row_a['latitude']
            delta_lon = row_b['longitude'] - row_a['longitude']
            
            # Skip biologically impossible movements
            if abs(delta_lat) > MAX_DELTA or abs(delta_lon) > MAX_DELTA:
                continue
            
            pairs.append({
                'case_id': i,
                'country': row_a['country'],
                'date_d': str(row_a['report_date'].date()),
                'lat_d': row_a['latitude'],
                'lon_d': row_a['longitude'],
                'future_date': str(row_b['report_date'].date()),
                'future_lat': row_b['latitude'],
                'future_lon': row_b['longitude'],
                'delta_lat': round(delta_lat, 6),
                'delta_lon': round(delta_lon, 6),
                'days_gap': days_diff,
                'dist_km': round(dist_km, 2),
                'wind_speed': row_a['wind_speed'],
                'wind_direction': row_a['wind_direction'],
                'wind_u': row_a['wind_u'],
                'wind_v': row_a['wind_v'],
                'env_source': row_a['env_source']
            })
    
    return pd.DataFrame(pairs)

print("\nCreating training pairs from Thailand...")
train_pairs = create_pairs(thailand_df, "Thailand")
print(f"Training pairs (Thailand): {len(train_pairs)}")

if len(train_pairs) > 0:
    print(f"  delta_lat range: {train_pairs['delta_lat'].min():.4f} to {train_pairs['delta_lat'].max():.4f}")
    print(f"  delta_lon range: {train_pairs['delta_lon'].min():.4f} to {train_pairs['delta_lon'].max():.4f}")
    print(f"  distance range: {train_pairs['dist_km'].min():.1f} to {train_pairs['dist_km'].max():.1f} km")

if len(train_pairs) < 10:
    print(f"\n⚠️  WARNING: Only {len(train_pairs)} pairs! Expanding search window to 21 days...")
    old_max_days = MAX_DAYS
    MAX_DAYS = 21
    train_pairs = create_pairs(thailand_df, "Thailand-expanded")
    print(f"Pairs after expansion: {len(train_pairs)}")
    MAX_DAYS = old_max_days

train_pairs.to_csv('data/processed/lsd_training_pairs.csv', index=False)

# Create test pairs from Sri Lanka
print(f"\nCreating test pairs from Sri Lanka...")
if len(srilanka_df) >= 2:
    test_pairs = create_pairs(srilanka_df, "SriLanka")
    test_pairs.to_csv('data/processed/lsd_test_pairs.csv', index=False)
    print(f"Test pairs (Sri Lanka): {len(test_pairs)}")
else:
    test_pairs = pd.DataFrame()
    print(f"Test pairs (Sri Lanka): 0 (insufficient data)")

print(f"\nStep 4 complete. Pairs: {len(train_pairs)}")

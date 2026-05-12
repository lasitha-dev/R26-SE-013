"""
PHASE 1: REBUILD TRAINING DATA WITH REAL WIND
Fetch real wind data from Open-Meteo Archive API for each training pair
This replaces the fake wind data with actual meteorological records
"""

import pandas as pd
import requests
import time
import math
from datetime import datetime

pairs = pd.read_csv('data/processed/lsd_training_pairs.csv')

print("="*70)
print("PHASE 1: REBUILD WIND DATA WITH REAL API")
print("="*70)
print(f"\nFetching REAL wind for {len(pairs)} pairs...")
print("Source: Open-Meteo Historical Weather API")
print("This may take 15-30 minutes (rate-limited to avoid overload)")
print("\nReal data = Much better model! ✅")
print("-"*70)

def fetch_real_wind(lat, lng, date_str):
    """
    Fetch real wind data from Open-Meteo Archive API
    Returns: (wind_speed, wind_direction, humidity, source)
    """
    try:
        url = (
            "https://archive-api.open-meteo.com/v1/archive"
            f"?latitude={round(lat, 2)}"
            f"&longitude={round(lng, 2)}"
            f"&start_date={date_str}"
            f"&end_date={date_str}"
            "&hourly=wind_speed_10m,wind_direction_10m,relative_humidity_2m"
            "&wind_speed_unit=ms"
        )
        
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if 'hourly' in data:
                h = data['hourly']
                # Use noon data (hour 12) for stability
                spd = h['wind_speed_10m'][12]
                drn = h['wind_direction_10m'][12]
                hum = h['relative_humidity_2m'][12]
                
                if None not in (spd, drn, hum):
                    return (float(spd), float(drn), float(hum), "real_api")
    except Exception as e:
        pass
    
    return None, None, None, None

# Process in batches with progress reporting
speeds = []
directions = []
humidities = []
sources = []
failed_indices = []

print(f"\nProcessing {len(pairs)} records...")
print("(Every 100 records: progress report)")

for i, row in pairs.iterrows():
    spd, drn, hum, src = fetch_real_wind(
        row['lat_d'],
        row['lon_d'],
        row['date_d']
    )
    
    if spd is None:
        failed_indices.append(i)
        speeds.append(None)
        directions.append(None)
        humidities.append(None)
        sources.append("failed")
    else:
        speeds.append(round(spd, 2))
        directions.append(round(drn, 1))
        humidities.append(round(hum, 1))
        sources.append(src)
    
    # Rate limiting: 0.15s per request
    time.sleep(0.15)
    
    if (i+1) % 100 == 0:
        success = (i+1) - len(failed_indices)
        pct = 100 * success / (i+1)
        print(f"  ✓ {i+1:5d}/{len(pairs)} | "
              f"Success: {success:4d} ({pct:5.1f}%) | "
              f"Failed: {len(failed_indices):4d}")

# Add wind columns to dataframe
pairs['wind_speed'] = speeds
pairs['wind_direction'] = directions
pairs['humidity'] = humidities
pairs['env_source'] = sources

print(f"\n" + "-"*70)
print(f"API Fetch Complete")
print(f"  Total rows        : {len(pairs)}")
print(f"  Successfully got  : {len(pairs) - len(failed_indices)}")
print(f"  Failed/No data    : {len(failed_indices)}")

# Remove failed rows
before_count = len(pairs)
pairs = pairs.dropna(subset=['wind_speed'])
removed_count = before_count - len(pairs)

print(f"\nCleaning up...")
print(f"  Removed {removed_count} rows with missing wind data")
print(f"  Final training pairs: {len(pairs)}")

# Calculate wind vector components
print(f"\nCalculating wind vectors...")
pairs['wind_u'] = pairs.apply(
    lambda r: round(
        r['wind_speed'] * math.cos(math.radians(r['wind_direction'])),
        4
    ),
    axis=1
)
pairs['wind_v'] = pairs.apply(
    lambda r: round(
        r['wind_speed'] * math.sin(math.radians(r['wind_direction'])),
        4
    ),
    axis=1
)

# Wind statistics
print(f"\n" + "="*70)
print("WIND DATA STATISTICS (Real API)")
print("="*70)
print(f"\nWind Speed (m/s):")
print(f"  Min    : {pairs['wind_speed'].min():.2f}")
print(f"  Max    : {pairs['wind_speed'].max():.2f}")
print(f"  Mean   : {pairs['wind_speed'].mean():.2f}")
print(f"  Median : {pairs['wind_speed'].median():.2f}")
print(f"  Std    : {pairs['wind_speed'].std():.2f}")

print(f"\nWind Direction (degrees):")
print(f"  Min    : {pairs['wind_direction'].min():.0f}°")
print(f"  Max    : {pairs['wind_direction'].max():.0f}°")
print(f"  Mean   : {pairs['wind_direction'].mean():.0f}°")

print(f"\nRelative Humidity (%):")
print(f"  Min    : {pairs['humidity'].min():.0f}%")
print(f"  Max    : {pairs['humidity'].max():.0f}%")
print(f"  Mean   : {pairs['humidity'].mean():.1f}%")

print(f"\nWind Components (u = East, v = North):")
print(f"  wind_u range: {pairs['wind_u'].min():.2f} to {pairs['wind_u'].max():.2f}")
print(f"  wind_v range: {pairs['wind_v'].min():.2f} to {pairs['wind_v'].max():.2f}")

print(f"\nData Source:")
print(f"  Real API: {(pairs['env_source'] == 'real_api').sum()}")
print(f"  Failed  : {(pairs['env_source'] == 'failed').sum()}")

print(f"\n✅ Source: REAL OPEN-METEO ARCHIVE API")

# Save to file
output_path = 'data/processed/lsd_with_wind_real.csv'
pairs.to_csv(output_path, index=False)

print(f"\n" + "="*70)
print(f"✅ SAVED: {output_path}")
print(f"   Ready for PHASE 2 (model retraining)")
print("="*70)

# Show sample
print(f"\nSample rows:")
print(pairs[['country', 'date_d', 'movement_km', 'wind_speed', 
             'wind_direction', 'humidity', 'env_source']].head(10).to_string())

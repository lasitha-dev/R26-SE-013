"""
STEP 5: ADD WIND FEATURES FROM WEATHER API
Fetch realistic wind data for training pairs
"""
import requests, time, math
import pandas as pd
import numpy as np

print("="*70)
print("STEP 5: ADD WIND FEATURES")
print("="*70)

pairs = pd.read_csv('data/processed/lsd_training_pairs.csv')

if len(pairs) == 0:
    print("ERROR: No training pairs!")
    print("Fix Step 4 first.")
    exit()

print(f"\nProcessing {len(pairs)} pairs...")

# Wind data will be fetched from Open-Meteo API (free, no key needed)
def fetch_wind(lat, lon, date_str):
    """
    Fetch wind data from Open-Meteo historical weather API
    Returns (speed_ms, direction_deg, humidity_percent, source)
    """
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={round(lat, 2)}"
        f"&longitude={round(lon, 2)}"
        f"&start_date={date_str}"
        f"&end_date={date_str}"
        "&hourly=wind_speed_10m,"
        "wind_direction_10m,"
        "relative_humidity_2m"
        "&wind_speed_unit=ms"
        "&timezone=auto"
    )
    
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if 'hourly' in data and data['hourly']['wind_speed_10m']:
                    # Use noon (12:00) values
                    spd = data['hourly']['wind_speed_10m'][12]
                    drn = data['hourly']['wind_direction_10m'][12]
                    hum = data['hourly']['relative_humidity_2m'][12]
                    
                    if spd is not None and drn is not None and hum is not None:
                        return (float(spd), float(drn), float(hum), "api")
        except Exception as e:
            pass
        
        time.sleep(0.5)
    
    return None, None, None, None

# Fetch wind data for all pairs
speeds, dirs, hums, sources = [], [], [], []

api_success = 0
api_failed = 0

for idx, row in pairs.iterrows():
    spd, drn, hum, src = fetch_wind(
        row['lat_d'],
        row['lon_d'],
        row['date_d']
    )
    
    if spd is None:
        # Use realistic SE Asia/regional placeholders
        # Seed based on date+location for consistency
        seed = (hash(f"{row['date_d']}{row['country']}") % 1000) / 1000.0
        
        # Regional wind patterns
        if 'Thailand' in str(row['country']) or 'Malaysia' in str(row['country']):
            spd = 2.0 + seed * 6.0  # SE Asia: 2-8 m/s
        elif 'France' in str(row['country']) or 'Italy' in str(row['country']):
            spd = 1.5 + seed * 5.0  # Europe: 1.5-6.5 m/s
        elif 'Korea' in str(row['country']) or 'Japan' in str(row['country']):
            spd = 2.0 + seed * 7.0  # East Asia: 2-9 m/s
        else:
            spd = 2.5 + seed * 5.5  # Default: 2.5-8 m/s
        
        drn = (seed * 360) % 360
        hum = 50 + (seed * 30)
        src = "placeholder"
        api_failed += 1
    else:
        api_success += 1
    
    speeds.append(round(spd, 2))
    dirs.append(round(drn, 1))
    hums.append(round(hum, 1))
    sources.append(src)
    
    if (idx+1) % 500 == 0:
        print(f"  {idx+1}/{len(pairs)} done (API: {api_success} success, {api_failed} placeholder)")

pairs['wind_speed']     = speeds
pairs['wind_direction'] = dirs
pairs['humidity']       = hums
pairs['env_source']     = sources

# Calculate wind vector components
pairs['wind_u'] = pairs.apply(
    lambda r: round(
        r['wind_speed'] * math.cos(math.radians(r['wind_direction'])),
        4),
    axis=1
)
pairs['wind_v'] = pairs.apply(
    lambda r: round(
        r['wind_speed'] * math.sin(math.radians(r['wind_direction'])),
        4),
    axis=1
)

print(f"\n{'='*70}")
print(f"Wind data summary:")
print(f"  API successful: {api_success}")
print(f"  Placeholder used: {api_failed}")
print(f"  Total: {len(pairs)}")

print(f"\nWind speed statistics:")
print(f"  Min: {pairs['wind_speed'].min():.2f} m/s")
print(f"  Max: {pairs['wind_speed'].max():.2f} m/s")
print(f"  Mean: {pairs['wind_speed'].mean():.2f} m/s")

print(f"\nWind direction distribution:")
print(f"  Min: {pairs['wind_direction'].min():.1f}°")
print(f"  Max: {pairs['wind_direction'].max():.1f}°")
print(f"  Mean: {pairs['wind_direction'].mean():.1f}°")

print(f"\nHumidity statistics:")
print(f"  Min: {pairs['humidity'].min():.1f}%")
print(f"  Max: {pairs['humidity'].max():.1f}%")
print(f"  Mean: {pairs['humidity'].mean():.1f}%")

# Save
pairs.to_csv('data/processed/lsd_with_wind.csv', index=False)

print(f"\n{'='*70}")
print(f"✅ Step 5 Complete")
print(f"   Saved: data/processed/lsd_with_wind.csv")
print(f"   Records: {len(pairs)}")
print(f"{'='*70}")

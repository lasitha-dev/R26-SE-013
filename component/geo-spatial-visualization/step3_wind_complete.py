"""
STEP 3 - ADD WIND FEATURES
Fetch wind data from Open-Meteo API with placeholder fallback
"""
import pandas as pd
import numpy as np
import math
import requests
import time

print("="*50)
print("STEP 3: ADD WIND FEATURES")
print("="*50)

df = pd.read_csv('data/processed/cleaned_lsd_cases.csv')
print(f"Starting with {len(df)} records")

def get_wind_openmeteo(lat, lng, date_str):
    """Fetch wind from Open-Meteo archive API"""
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={round(lat,2)}"
        f"&longitude={round(lng,2)}"
        f"&start_date={date_str}"
        f"&end_date={date_str}"
        "&hourly=wind_speed_10m,wind_direction_10m"
        "&wind_speed_unit=ms"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            spd = data['hourly']['wind_speed_10m'][12]  # noon
            drn = data['hourly']['wind_direction_10m'][12]
            return float(spd), float(drn), "api"
    except Exception as e:
        pass
    return None, None, None

wind_speeds = []
wind_dirs = []
sources = []

print(f"\nFetching wind for {len(df)} records...")

for i, row in df.iterrows():
    spd, drn, src = get_wind_openmeteo(
        row['latitude'],
        row['longitude'],
        row['report_date']
    )
    
    if spd is None:
        # Placeholder: realistic SE Asia wind
        spd = round(3.0 + (i % 5) * 0.8, 1)
        drn = round(45 + (i % 8) * 22.5, 1)
        src = "placeholder"
    
    wind_speeds.append(spd)
    wind_dirs.append(drn)
    sources.append(src)
    
    if i % 200 == 0:
        print(f"  Progress: {i}/{len(df)}")
    
    time.sleep(0.05)  # rate limit

df['wind_speed'] = wind_speeds
df['wind_direction'] = wind_dirs
df['env_source'] = sources

# Convert to u/v components
df['wind_u'] = df.apply(
    lambda r: r['wind_speed'] * 
    math.cos(math.radians(r['wind_direction'])),
    axis=1
)
df['wind_v'] = df.apply(
    lambda r: r['wind_speed'] * 
    math.sin(math.radians(r['wind_direction'])),
    axis=1
)

api_count = (df['env_source'] == 'api').sum()
placeholder_count = (df['env_source'] == 'placeholder').sum()

print(f"\nWind data summary:")
print(f"  From API: {api_count}")
print(f"  Placeholder: {placeholder_count}")
print(f"  Total: {len(df)}")

df.to_csv('data/processed/lsd_with_wind.csv', index=False)

print(f"\nStep 3 complete. Records: {len(df)}")

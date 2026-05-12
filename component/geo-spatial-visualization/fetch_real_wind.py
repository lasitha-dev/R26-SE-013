import pandas as pd
import requests
import time
import math
import os

pairs = pd.read_csv(
    'data/processed/lsd_training_pairs.csv'
)

print(f"Total pairs: {len(pairs)}")
print("Fetching REAL historical wind...")
print("This takes 20-40 minutes.")
print("Progress shown every 50 records.")

def get_archive_wind(lat, lon, date_str):
    """
    Fetch real historical wind from
    Open-Meteo Archive (ERA5 reanalysis).
    Data available from 1940 to present.
    """
    url = (
        "https://archive-api.open-meteo.com"
        "/v1/archive"
        f"?latitude={round(lat, 3)}"
        f"&longitude={round(lon, 3)}"
        f"&start_date={date_str}"
        f"&end_date={date_str}"
        "&hourly=wind_speed_10m,"
        "wind_direction_10m,"
        "relative_humidity_2m,"
        "temperature_2m"
        "&wind_speed_unit=ms"
        "&timezone=auto"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                h = data.get('hourly', {})
                ws = h.get('wind_speed_10m', [])
                wd = h.get('wind_direction_10m', [])
                hm = h.get('relative_humidity_2m', [])
                tm = h.get('temperature_2m', [])

                # Use midday value (index 12)
                if len(ws) > 12:
                    return {
                        'wind_speed':     float(ws[12] or 3.0),
                        'wind_direction': float(wd[12] or 90.0),
                        'humidity':       float(hm[12] or 75.0),
                        'temperature':    float(tm[12] or 28.0),
                        'source':         'real_archive'
                    }
        except Exception as e:
            time.sleep(1)
    return None

# Process all pairs
results = []
failed_count = 0

for i, row in pairs.iterrows():
    wind = get_archive_wind(
        row['lat_d'],
        row['lon_d'],
        str(row['date_d'])[:10]
    )

    if wind is None:
        failed_count += 1
        wind = {
            'wind_speed':     3.5,
            'wind_direction': 90.0,
            'humidity':       75.0,
            'temperature':    28.0,
            'source':         'fallback'
        }

    row_dict = row.to_dict()
    row_dict.update(wind)
    results.append(row_dict)

    time.sleep(0.15)

    if (i + 1) % 50 == 0:
        real = sum(
            1 for r in results
            if r.get('source') == 'real_archive'
        )
        print(f"  {i+1}/{len(pairs)} | "
              f"Real: {real} | "
              f"Fallback: {failed_count}")

df_out = pd.DataFrame(results)

# Add wind vector components
df_out['wind_u'] = df_out.apply(
    lambda r: round(
        r['wind_speed'] *
        math.cos(math.radians(r['wind_direction'])),
        4),
    axis=1
)
df_out['wind_v'] = df_out.apply(
    lambda r: round(
        r['wind_speed'] *
        math.sin(math.radians(r['wind_direction'])),
        4),
    axis=1
)

# Statistics
real_count = (
    df_out['source'] == 'real_archive'
).sum()
print(f"\nWind fetch complete:")
print(f"  Real API data: {real_count}")
print(f"  Fallback:      {failed_count}")
print(f"  Total:         {len(df_out)}")
print(f"\nWind statistics:")
print(f"  Speed: "
      f"{df_out['wind_speed'].min():.1f} - "
      f"{df_out['wind_speed'].max():.1f} m/s")
print(f"  Direction: "
      f"{df_out['wind_direction'].min():.0f}° - "
      f"{df_out['wind_direction'].max():.0f}°")

df_out.to_csv(
    'data/processed/lsd_real_wind_final.csv',
    index=False
)
print("\nSaved: lsd_real_wind_final.csv")

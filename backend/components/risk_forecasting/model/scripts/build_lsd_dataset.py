"""
Step 1: Build LSD Feature-Engineered Dataset (Dual-File Integrated Pipeline)
=============================================================================
Integrates:
  1. LSD_SriLanka_2020_2024.csv (1,500 district-month grid for Stage 1 Binary Outbreak)
  2. LSD_District_Year_Cases_Deaths.csv (56 event records for Stage 2 Outbreak Severity)
Merges with CHIRPS rainfall, ERA5 climate, spatial neighbor lags, and NOAA teleconnections.
"""

import os
import pandas as pd
import numpy as np
import geopandas as gpd
import warnings
warnings.filterwarnings('ignore')

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID_PATH      = os.path.join(BASE_DIR, 'data', 'raw', 'daph', 'LSD_SriLanka_2020_2024.csv')
SEV_PATH       = os.path.join(BASE_DIR, 'data', 'raw', 'daph', 'LSD_District_Year_Cases_Deaths.csv')
CLIMATE_PATH   = os.path.join(BASE_DIR, 'data', 'processed', 'FMD_dataset_with_spatial_and_climate_indices.csv')
SHAPEFILE_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'lka_admin_boundaries', 'lka_admin2.shp')
OUTPUT_PATH    = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_dataset_with_spatial_and_climate_indices.csv')
SEV_OUT_PATH   = os.path.join(BASE_DIR, 'data', 'processed', 'LSD_severity_labels.csv')

print("=== STEP 1: BUILDING LSD FEATURE DATASET (DUAL-FILE PIPELINE) ===")

# 1. Load Raw Grid & Severity Files
df_grid = pd.read_csv(GRID_PATH)
df_sev  = pd.read_csv(SEV_PATH)

print(f"Loaded Stage 1 Grid: {df_grid.shape[0]} rows x {df_grid.shape[1]} columns")
print(f"Loaded Stage 2 Severity Events: {df_sev.shape[0]} rows x {df_sev.shape[1]} columns")

# Standardize district names
district_map = {
    'Moneragala': 'Monaragala',
    'NuwaraEliya': 'Nuwara Eliya'
}
df_grid['district'] = df_grid['district'].replace(district_map)
df_sev['District']  = df_sev['District'].replace(district_map)
df_sev.rename(columns={'District': 'district', 'Year': 'year'}, inplace=True)

# Parse month_num
month_map = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}
if 'month' in df_grid.columns:
    df_grid['month_num'] = df_grid['month'].astype(str).str.strip().str.lower().map(month_map)
df_grid['month_num'] = pd.to_numeric(df_grid['month_num'], errors='coerce').astype(int)
df_grid['year'] = pd.to_numeric(df_grid['year'], errors='coerce').astype(int)

# 2. Add Cyclical Month Features
df_grid['sin_month'] = np.sin(2 * np.pi * df_grid['month_num'] / 12)
df_grid['cos_month'] = np.cos(2 * np.pi * df_grid['month_num'] / 12)

# 3. Add Monsoon Phase One-Hot Encodings
df_grid['monsoon_phase_First_Inter_Monsoon'] = df_grid['month_num'].isin([3, 4]).astype(int)
df_grid['monsoon_phase_SW_Monsoon']          = df_grid['month_num'].isin([5, 6, 7, 8, 9]).astype(int)
df_grid['monsoon_phase_Second_Inter_Monsoon'] = df_grid['month_num'].isin([10, 11]).astype(int)
df_grid['monsoon_phase_NE_Monsoon']          = df_grid['month_num'].isin([12, 1, 2]).astype(int)

# 4. Merge Climate & Teleconnection Features
df_climate = pd.read_csv(CLIMATE_PATH)
climate_cols = [
    'year', 'month_num', 'district', 'PCODE', 'rainfall_mm', 'r3h', 'rfq',
    'rain_lag1', 'rain_lag2', 'rfq_lag1', 'lat', 'lon', 'humidity', 'wind_speed',
    'temp_lag1', 'humidity_lag1', 'wind_lag1', 'buffalo_density', 'livestock_density',
    'nino34', 'nino34_lag3', 'iod_dmi', 'iod_dmi_lag2'
]
climate_subset = df_climate[climate_cols].drop_duplicates(subset=['year', 'month_num', 'district'])

df_merged = pd.merge(df_grid, climate_subset, on=['year', 'month_num', 'district'], how='left', suffixes=('', '_climate'))
if 'PCODE_climate' in df_merged.columns:
    df_merged['PCODE'] = df_merged['PCODE'].fillna(df_merged['PCODE_climate'])
    df_merged.drop(columns=['PCODE_climate'], inplace=True)

# 5. Compute LSD Spatial Neighbor Adjacency Lags
gdf = gpd.read_file(SHAPEFILE_PATH)
adjacency = {}
for _, row in gdf.iterrows():
    district_name = row['adm2_name']
    neighbors = gdf[gdf.geometry.touches(row.geometry)]['adm2_name'].tolist()
    adjacency[district_name] = neighbors

outbreak_lookup = df_merged.set_index(['district', 'year', 'month_num'])['Outbreak status'].to_dict()

def get_lagged_year_month(year, month, lag):
    m = month - lag
    y = year
    while m <= 0:
        m += 12
        y -= 1
    return y, m

spatial_lag1_mean  = []
spatial_lag1_count = []
spatial_lag1_frac  = []
spatial_lag2_mean  = []

for idx, row in df_merged.iterrows():
    district  = row['district']
    year      = row['year']
    month     = row['month_num']
    neighbors = adjacency.get(district, [])
    
    # Lag 1
    y1, m1 = get_lagged_year_month(year, month, 1)
    n_statuses_lag1 = [outbreak_lookup.get((n, y1, m1), 0) for n in neighbors]
    if len(n_statuses_lag1) > 0:
        s_mean1  = np.mean(n_statuses_lag1)
        s_count1 = np.sum(n_statuses_lag1)
        s_frac1  = s_count1 / len(neighbors)
    else:
        s_mean1, s_count1, s_frac1 = 0.0, 0, 0.0

    # Lag 2
    y2, m2 = get_lagged_year_month(year, month, 2)
    n_statuses_lag2 = [outbreak_lookup.get((n, y2, m2), 0) for n in neighbors]
    s_mean2 = np.mean(n_statuses_lag2) if len(n_statuses_lag2) > 0 else 0.0

    spatial_lag1_mean.append(round(s_mean1, 4))
    spatial_lag1_count.append(int(s_count1))
    spatial_lag1_frac.append(round(s_frac1, 4))
    spatial_lag2_mean.append(round(s_mean2, 4))

df_merged['neighbor_outbreak_lag1']         = spatial_lag1_mean
df_merged['neighbor_outbreak_count_lag1']   = spatial_lag1_count
df_merged['neighbor_outbreak_fraction_lag1'] = spatial_lag1_frac
df_merged['neighbor_outbreak_lag2']         = spatial_lag2_mean

# 6. Process Stage 2 Severity Event Dataset & Merge
duration_map = df_merged.groupby(['district', 'year'])['Outbreak status'].sum().to_dict()
df_sev['Outbreak_Months'] = df_sev.apply(lambda r: duration_map.get((r['district'], r['year']), 1), axis=1)
df_sev['severity_score'] = df_sev['Cases'] + (10 * df_sev['Deaths']) + (5 * df_sev['Outbreak_Months'])

q33 = df_sev['severity_score'].quantile(0.333)
q66 = df_sev['severity_score'].quantile(0.666)

def get_3class(score):
    if score <= q33:
        return 'LOW'
    elif score <= q66:
        return 'MEDIUM'
    else:
        return 'HIGH'

df_sev['severity_class'] = df_sev['severity_score'].apply(get_3class)

# Save Stage 2 severity event labels
df_sev.to_csv(SEV_OUT_PATH, index=False)
print(f"[OK] LSD Severity event dataset saved: {SEV_OUT_PATH}")

# Merge Severity Scores to Grid
df_merged = pd.merge(df_merged, df_sev[['district', 'year', 'Cases', 'Deaths', 'severity_score', 'severity_class']], 
                     on=['district', 'year'], how='left')

df_merged['Cases'] = df_merged['Cases'].fillna(0).astype(int)
df_merged['Deaths'] = df_merged['Deaths'].fillna(0).astype(int)
df_merged['severity_score'] = df_merged['severity_score'].fillna(0.0)
df_merged['severity_class'] = df_merged['severity_class'].fillna('NONE')

# Sort dataset cleanly
df_merged.sort_values(by=['year', 'month_num', 'district'], inplace=True)
df_merged.reset_index(drop=True, inplace=True)

# Save output
df_merged.to_csv(OUTPUT_PATH, index=False)
print(f"[SUCCESS] Step 1 Complete! LSD dataset saved to: {OUTPUT_PATH}")
print(f"Final Dataset Shape: {df_merged.shape[0]} rows x {df_merged.shape[1]} columns")
print(f"Outbreak Target Balance: {df_merged['Outbreak status'].value_counts().to_dict()}")

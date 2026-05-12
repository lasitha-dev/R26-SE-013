import pandas as pd
import numpy as np

print('='*80)
print('STEP 2: DATA CLEANING - REFINED VERSION')
print('='*80)

# Read raw CSV
df = pd.read_csv('data/raw/Latest Reported Events (3).csv')

# Filter for LSD
lsd_df = df[df['Disease'].str.lower() == 'lumpy skin disease'].copy()

# Filter for Thailand and Sri Lanka
countries_df = lsd_df[lsd_df['Country'].isin(['Thailand', 'Sri Lanka'])].copy()

# Filter for cattle or buffaloes (not wild animals)
def filter_species(species_str):
    s = str(species_str).lower()
    return ('cattle' in s or 'buffalo' in s) and 'wild' not in s

species_df = countries_df[countries_df['Species'].apply(filter_species)].copy()

# Filter for confirmed diagnosis
confirmed_df = species_df[species_df['Diagnosis Status'].str.lower() == 'confirmed'].copy()

print(f'Starting with confirmed LSD cases (cattle/buffaloes): {len(confirmed_df)}')

# Standardize columns
cleaned = pd.DataFrame()
cleaned['case_id'] = confirmed_df['Event ID'].values
cleaned['country'] = confirmed_df['Country'].values
cleaned['disease_type'] = 'LSD'
cleaned['report_date'] = pd.to_datetime(confirmed_df['observation date']).dt.strftime('%Y-%m-%d')
cleaned['latitude'] = confirmed_df['latitude'].astype(float)
cleaned['longitude'] = confirmed_df['longitude'].astype(float)
cleaned['locality'] = confirmed_df['Locality'].values
cleaned['species'] = confirmed_df['Species'].values

# Remove records with missing lat/lon/date
invalid_before = len(cleaned)
cleaned = cleaned.dropna(subset=['latitude', 'longitude', 'report_date'])
invalid_removed = invalid_before - len(cleaned)
print(f'Records with missing coordinates or dates removed: {invalid_removed}')

# Remove duplicates based on country, lat, lon, and date
duplicates_before = len(cleaned)
cleaned = cleaned.drop_duplicates(subset=['country', 'latitude', 'longitude', 'report_date'], keep='first')
duplicates_removed = duplicates_before - len(cleaned)
print(f'Exact duplicate records removed: {duplicates_removed}')

# Validate lat/lon ranges
valid_coords = (
    (cleaned['latitude'] >= -90) & (cleaned['latitude'] <= 90) &
    (cleaned['longitude'] >= -180) & (cleaned['longitude'] <= 180)
).sum()
print(f'Records with valid coordinates: {valid_coords}/{len(cleaned)}')

print(f'\n✅ Final cleaned records: {len(cleaned)}')
print(f'Date range: {cleaned["report_date"].min()} to {cleaned["report_date"].max()}')

# Sort by date
cleaned = cleaned.sort_values('report_date').reset_index(drop=True)

# Save cleaned data
output_path = 'data/processed/cleaned_lsd_cases.csv'
cleaned.to_csv(output_path, index=False)
print(f'✅ Saved to: {output_path}')

print(f'\nRecords by country:')
print(cleaned['country'].value_counts())

print(f'\nRecords by species:')
print(cleaned['species'].value_counts())

print(f'\nSample records:')
print(cleaned[['case_id', 'country', 'report_date', 'latitude', 'longitude', 'species']].head(15).to_string())

print('\n' + '='*80)
print('STEP 2 COMPLETE')
print('='*80)

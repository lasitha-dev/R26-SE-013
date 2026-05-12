import pandas as pd
import numpy as np

# Read CSV file (using first one as they seem identical)
df = pd.read_csv('data/raw/Latest Reported Events (3).csv')

print('='*80)
print('STEP 1: DATA INSPECTION - DETAILED ANALYSIS')
print('='*80)

print(f'\nTotal records in dataset: {len(df)}')
print(f'\nDisease types:')
print(df['Disease'].value_counts())

print('\n' + '='*80)
print('FILTERING FOR LSD + THAILAND + SRI LANKA')
print('='*80)

# LSD records
lsd_df = df[df['Disease'].str.lower() == 'lumpy skin disease'].copy()
print(f'\nTotal LSD records: {len(lsd_df)}')

# Thailand records
thailand_lsd = lsd_df[lsd_df['Country'] == 'Thailand'].copy()
print(f'LSD records in Thailand: {len(thailand_lsd)}')

# Sri Lanka records
srilanka_lsd = lsd_df[lsd_df['Country'] == 'Sri Lanka'].copy()
print(f'LSD records in Sri Lanka: {len(srilanka_lsd)}')

print('\n' + '='*80)
print('THAILAND LSD DATA')
print('='*80)
print(f'\nThailand LSD records by Species:')
print(thailand_lsd['Species'].value_counts())
print(f'\nThailand LSD records by Diagnosis Status:')
print(thailand_lsd['Diagnosis Status'].value_counts())
print(f'\nDate range: {thailand_lsd["observation date"].min()} to {thailand_lsd["observation date"].max()}')
print(f'\nThailand sample records:')
print(thailand_lsd[['Event ID', 'observation date', 'latitude', 'longitude', 'Species', 'Diagnosis Status']].head(10).to_string())

print('\n' + '='*80)
print('SRI LANKA LSD DATA')
print('='*80)
print(f'\nSri Lanka LSD records by Species:')
print(srilanka_lsd['Species'].value_counts())
print(f'\nSri Lanka LSD records by Diagnosis Status:')
print(srilanka_lsd['Diagnosis Status'].value_counts())
print(f'\nDate range: {srilanka_lsd["observation date"].min()} to {srilanka_lsd["observation date"].max()}')
print(f'\nSri Lanka sample records:')
print(srilanka_lsd[['Event ID', 'observation date', 'latitude', 'longitude', 'Species', 'Diagnosis Status']].head(10).to_string())

print('\n' + '='*80)
print('FILTERING FOR CATTLE + BUFFALOES ONLY')
print('='*80)

# Filter for cattle or buffaloes (either as single or in combination)
def filter_species(species_str):
    s = str(species_str).lower()
    return ('cattle' in s or 'buffalo' in s) and 'wild' not in s

# Thailand - cattle and buffaloes, confirmed only
thailand_clean = thailand_lsd[
    thailand_lsd['Species'].apply(filter_species) &
    (thailand_lsd['Diagnosis Status'].str.lower() == 'confirmed')
].copy()

# Sri Lanka - cattle and buffaloes, confirmed only
srilanka_clean = srilanka_lsd[
    srilanka_lsd['Species'].apply(filter_species) &
    (srilanka_lsd['Diagnosis Status'].str.lower() == 'confirmed')
].copy()

print(f'\nThailand: Cattle/Buffaloes + Confirmed: {len(thailand_clean)} records')
print(f'Sri Lanka: Cattle/Buffaloes + Confirmed: {len(srilanka_clean)} records')

print(f'\nThailand usable records:')
print(thailand_clean[['Event ID', 'observation date', 'latitude', 'longitude', 'Species']].head(10).to_string())

print(f'\nSri Lanka usable records:')
print(srilanka_clean[['Event ID', 'observation date', 'latitude', 'longitude', 'Species']].head(10).to_string())

print('\n' + '='*80)
print('DATA QUALITY CHECK')
print('='*80)

combined = pd.concat([thailand_clean, srilanka_clean])
print(f'\nCombined usable LSD records: {len(combined)}')
print(f'Records with valid lat/lon: {(combined["latitude"].notna() & combined["longitude"].notna()).sum()}')
print(f'Records with valid dates: {(combined["observation date"].notna()).sum()}')
print(f'Missing values:')
print(combined[['latitude', 'longitude', 'observation date']].isnull().sum())


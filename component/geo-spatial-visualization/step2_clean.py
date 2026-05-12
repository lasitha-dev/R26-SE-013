import pandas as pd
import os

print("\n" + "="*60)
print("STEP 2 — CLEAN DATA")
print("="*60)

# Load all CSV files and concatenate
raw_dir = 'data/raw'
csv_files = [f for f in os.listdir(raw_dir) if f.endswith('.csv')]
dfs = []

for csv_file in csv_files:
    filepath = os.path.join(raw_dir, csv_file)
    df = pd.read_csv(filepath)
    dfs.append(df)
    print(f"\nLoaded {csv_file}: {len(df)} rows")

all_data = pd.concat(dfs, ignore_index=True)
print(f"\nConcatenated all files: {len(all_data)} rows")

# Remove duplicates
all_data = all_data.drop_duplicates().reset_index(drop=True)
print(f"After deduplication: {len(all_data)} rows")

# Apply cleaning criteria
print("\nApplying cleaning criteria:")

# a) Disease contains "lumpy" OR "lsd" (case insensitive)
before_disease = len(all_data)
all_data = all_data[
    all_data['Disease'].astype(str).str.lower().str.contains('lumpy|lsd', na=False)
]
print(f"  a) After disease filter (lumpy/LSD): {len(all_data)} rows "
      f"(removed {before_disease - len(all_data)})")

# b) Species contains "cattle" OR "buffalo" (case insensitive)
before_species = len(all_data)
all_data = all_data[
    all_data['Species'].astype(str).str.lower().str.contains('cattle|buffalo', na=False)
]
print(f"  b) After species filter (cattle/buffalo): {len(all_data)} rows "
      f"(removed {before_species - len(all_data)})")

# c) Latitude numeric and between -90 and 90
before_lat = len(all_data)
all_data['latitude'] = pd.to_numeric(all_data['latitude'], errors='coerce')
all_data = all_data[
    (all_data['latitude'].notna()) & 
    (all_data['latitude'] >= -90) & 
    (all_data['latitude'] <= 90)
]
print(f"  c) After latitude validation: {len(all_data)} rows "
      f"(removed {before_lat - len(all_data)})")

# d) Longitude numeric and between -180 and 180
before_lon = len(all_data)
all_data['longitude'] = pd.to_numeric(all_data['longitude'], errors='coerce')
all_data = all_data[
    (all_data['longitude'].notna()) & 
    (all_data['longitude'] >= -180) & 
    (all_data['longitude'] <= 180)
]
print(f"  d) After longitude validation: {len(all_data)} rows "
      f"(removed {before_lon - len(all_data)})")

# e) Date column is parseable
before_date = len(all_data)
all_data['report date'] = pd.to_datetime(all_data['report date'], errors='coerce')
all_data = all_data[all_data['report date'].notna()]
print(f"  e) After date parsing: {len(all_data)} rows "
      f"(removed {before_date - len(all_data)})")

# Standardize columns
all_data = all_data.reset_index(drop=True)
cleaned_df = pd.DataFrame({
    'case_id': range(1, len(all_data) + 1),
    'country': all_data['Country'],
    'disease_type': 'LSD',
    'report_date': all_data['report date'].dt.strftime('%Y-%m-%d'),
    'latitude': all_data['latitude'],
    'longitude': all_data['longitude'],
    'species': all_data['Species']
})

print(f"\nFinal cleaned data: {len(cleaned_df)} rows")

# Summary statistics
print(f"\n{'='*60}")
print(f"CLEANED DATA SUMMARY")
print(f"{'='*60}")
print(f"Total rows: {len(cleaned_df)}")
print(f"\nRows by country:")
country_counts = cleaned_df['country'].value_counts()
for country, count in country_counts.items():
    print(f"  {country}: {count}")

print(f"\nDate range: {cleaned_df['report_date'].min()} to {cleaned_df['report_date'].max()}")

# Save cleaned data
cleaned_df.to_csv('data/processed/cleaned_lsd_cases.csv', index=False)
print(f"\n✓ Saved to data/processed/cleaned_lsd_cases.csv")
print(f"Step 2 complete. Records: {len(cleaned_df)}")

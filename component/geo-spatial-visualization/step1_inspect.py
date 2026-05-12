import pandas as pd
import os

raw_dir = 'data/raw'
csv_files = [f for f in os.listdir(raw_dir) if f.endswith('.csv')]

print("\n" + "="*60)
print("STEP 1 — INSPECT ALL FILES")
print("="*60)

for csv_file in csv_files:
    filepath = os.path.join(raw_dir, csv_file)
    print(f"\n📄 File: {csv_file}")
    
    df = pd.read_csv(filepath)
    print(f"   Shape: {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"   Columns: {list(df.columns)}")
    
    # Check for disease column
    disease_cols = [c for c in df.columns if 'disease' in c.lower()]
    species_cols = [c for c in df.columns if 'species' in c.lower() or 'animal' in c.lower() or 'host' in c.lower()]
    
    print(f"\n   Disease-related columns: {disease_cols}")
    if disease_cols:
        for col in disease_cols:
            unique_vals = df[col].unique()
            print(f"      {col}: {list(unique_vals)}")
            lsd_rows = df[df[col].astype(str).str.lower().str.contains('lumpy|lsd', na=False)]
            print(f"      → Rows with 'lumpy'/'LSD': {len(lsd_rows)}")
    
    print(f"\n   Species-related columns: {species_cols}")
    if species_cols:
        for col in species_cols:
            unique_vals = df[col].unique()
            print(f"      {col}: {list(unique_vals)}")
            cattle_rows = df[df[col].astype(str).str.lower().str.contains('cattle|buffalo', na=False)]
            print(f"      → Rows with 'cattle'/'buffalo': {len(cattle_rows)}")
    
    # Check geographic columns
    geo_cols = [c for c in df.columns if any(x in c.lower() for x in ['lat', 'lon', 'x', 'y'])]
    print(f"\n   Geographic columns: {geo_cols}")
    if geo_cols:
        for col in geo_cols:
            try:
                numeric_val = pd.to_numeric(df[col], errors='coerce').notna().sum()
                print(f"      {col}: {numeric_val} numeric values")
            except:
                print(f"      {col}: conversion failed")
    
    # Check date columns
    date_cols = [c for c in df.columns if any(x in c.lower() for x in ['date', 'time', 'report', 'occurred'])]
    print(f"\n   Date columns: {date_cols}")
    
    print(f"\n   First 3 rows:")
    print(df.head(3).to_string())

print("\n" + "="*60)
print(f"Step 1 complete. Total files inspected: {len(csv_files)}")
print("="*60)

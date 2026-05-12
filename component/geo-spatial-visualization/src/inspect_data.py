import pandas as pd
import os

# Read CSV files
csv_files = sorted([f for f in os.listdir('data/raw') if f.endswith('.csv')])
print('='*80)
print('CSV FILES IN data/raw:')
print('='*80)

for csv_file in csv_files:
    filepath = f'data/raw/{csv_file}'
    print(f'\n--- FILE: {csv_file} ---')
    df = pd.read_csv(filepath)
    print(f'Shape: {df.shape[0]} rows, {df.shape[1]} columns')
    print(f'Columns: {list(df.columns)}')
    print(f'\nFirst 2 rows:')
    print(df.head(2).to_string())
    print(f'\nData types:')
    print(df.dtypes)
    print(f'\nUnique values in key columns:')
    if 'Disease Type' in df.columns:
        print(f"  Disease Type: {df['Disease Type'].unique()}")
    if 'Species' in df.columns:
        print(f"  Species: {df['Species'].unique()[:10]}")  # First 10
    if 'Country' in df.columns:
        print(f"  Country: {df['Country'].unique()}")
    print()

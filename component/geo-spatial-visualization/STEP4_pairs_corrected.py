"""
STEP 4: CREATE VALID MOVEMENT PAIRS (WITHIN-CLUSTER ONLY)
CRITICAL: Only pair cases within the SAME cluster
This prevents 800km unbiological pairs
"""
import pandas as pd
import math
from geopy.distance import geodesic

print("="*70)
print("STEP 4: CREATE VALID MOVEMENT PAIRS (WITHIN-CLUSTER ONLY)")
print("="*70)

# Read clustered data
df = pd.read_csv('data/processed/lsd_clustered.csv')
df['report_date'] = pd.to_datetime(df['report_date'])

print(f"\nStarting with {len(df)} records")
print(f"Clusters: {df['cluster_id'].nunique()}")

# Pairing parameters (biologically strict)
MAX_DIST_KM = 50      # Within cluster max distance
MIN_DAYS = 1          # At least 1 day apart
MAX_DAYS = 21         # Max 3 weeks apart

pairs = []

# Process each cluster separately
for cluster_id in sorted(df['cluster_id'].unique()):
    cluster = df[df['cluster_id'] == cluster_id].sort_values('report_date').reset_index(drop=True)
    
    if len(cluster) < 2:
        continue  # Skip single-case clusters
    
    # Create pairs within cluster
    for i in range(len(cluster)):
        case_a = cluster.iloc[i]
        
        for j in range(i+1, len(cluster)):
            case_b = cluster.iloc[j]
            
            # Time constraint
            days = (case_b['report_date'] - case_a['report_date']).days
            
            if days < MIN_DAYS or days > MAX_DAYS:
                continue
            
            # Distance validation (geodesic)
            dist_km = geodesic(
                (case_a['latitude'], case_a['longitude']),
                (case_b['latitude'], case_b['longitude'])
            ).kilometers
            
            # HARD REJECT: Must be < 50km (already in same cluster, but double-check)
            if dist_km > MAX_DIST_KM:
                continue
            
            # Calculate deltas
            d_lat = case_b['latitude'] - case_a['latitude']
            d_lon = case_b['longitude'] - case_a['longitude']
            
            # Convert deltas to km for validation
            d_lat_km = d_lat * 111.0
            d_lon_km = d_lon * 111.0 * math.cos(math.radians(case_a['latitude']))
            
            # Calculate movement distance
            movement_km = math.sqrt(d_lat_km**2 + d_lon_km**2)
            
            # STRICT BIOLOGICAL CHECK: No movement > 50km within-cluster
            if movement_km > 50:
                continue
            
            # Valid pair!
            pairs.append({
                'cluster_id': cluster_id,
                'country': case_a['country'],
                'date_d': str(case_a['report_date'].date()),
                'lat_d': round(case_a['latitude'], 4),
                'lon_d': round(case_a['longitude'], 4),
                'future_date': str(case_b['report_date'].date()),
                'future_lat': round(case_b['latitude'], 4),
                'future_lon': round(case_b['longitude'], 4),
                'delta_lat': round(d_lat, 6),
                'delta_lon': round(d_lon, 6),
                'delta_lat_km': round(d_lat_km, 2),
                'delta_lon_km': round(d_lon_km, 2),
                'movement_km': round(movement_km, 2),
                'days_gap': days,
            })

pairs_df = pd.DataFrame(pairs)

print(f"\n{'='*70}")
print(f"MOVEMENT PAIRS CREATED: {len(pairs_df)}")
print(f"{'='*70}")

if len(pairs_df) == 0:
    print("\n⚠️  ZERO PAIRS! Debugging info:")
    print(f"\n  Total records: {len(df)}")
    print(f"  Total clusters: {df['cluster_id'].nunique()}")
    
    cluster_sizes = df.groupby('cluster_id').size()
    multi_case = (cluster_sizes >= 2).sum()
    print(f"  Multi-case clusters (2+): {multi_case}")
    
    print(f"\n  FIX: Increase MAX_CLUSTER_KM or MAX_DAYS")
    
else:
    print(f"\nMovement statistics:")
    print(f"  Min distance: {pairs_df['movement_km'].min():.1f} km")
    print(f"  Max distance: {pairs_df['movement_km'].max():.1f} km")
    print(f"  Mean distance: {pairs_df['movement_km'].mean():.1f} km")
    print(f"  Median distance: {pairs_df['movement_km'].median():.1f} km")
    print(f"  Std dev: {pairs_df['movement_km'].std():.1f} km")
    
    print(f"\nTop countries by pair count:")
    print(pairs_df['country'].value_counts().head(10).to_string())
    
    print(f"\nPairs by days gap:")
    print(pairs_df['days_gap'].value_counts().sort_index().to_string())
    
    # Biological validation
    invalid_pairs = pairs_df[pairs_df['movement_km'] > 100]
    
    if len(invalid_pairs) > 0:
        print(f"\n⚠️  WARNING: {len(invalid_pairs)} pairs > 100km!")
        print("These SHOULD NOT EXIST. Check clustering.")
        pairs_df = pairs_df[pairs_df['movement_km'] <= 100]
        print(f"After removal: {len(pairs_df)} valid pairs")
    else:
        print(f"\n✅ BIOLOGICAL CHECK: PASS")
        print(f"   All {len(pairs_df)} pairs biologically valid (< 50km)")
    
    print(f"\nSample pairs (first 10):")
    if len(pairs_df) > 0:
        print(pairs_df[['country', 'date_d', 'movement_km', 'days_gap']].head(10).to_string())

# Save
pairs_df.to_csv('data/processed/lsd_training_pairs.csv', index=False)

print(f"\n{'='*70}")
print(f"✅ Step 4 Complete")
print(f"   Saved: data/processed/lsd_training_pairs.csv")
print(f"   Valid pairs: {len(pairs_df)}")
print(f"{'='*70}")

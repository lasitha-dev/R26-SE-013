"""
STEP 3: GEOGRAPHIC CLUSTERING (CRITICAL FIX FOR 800KM PROBLEM)
Cases within 50km radius = same outbreak cluster
Cases > 50km apart = different clusters
"""
import pandas as pd
import numpy as np
from geopy.distance import geodesic

print("="*70)
print("STEP 3: GEOGRAPHIC CLUSTERING (FIXING 800KM ISSUE)")
print("="*70)

# Read cleaned data
df = pd.read_csv('data/processed/cleaned_lsd_cases.csv')
df['report_date'] = pd.to_datetime(df['report_date'])

print(f"\nStarting with {len(df)} records")

# Sort by date for clustering
df = df.copy().sort_values('report_date').reset_index(drop=True)

MAX_CLUSTER_KM = 50
BUFFER_KM = 5  # Include nearby records within 55km

# Geographic clustering: DBSCAN-like approach
def assign_clusters(df, max_km=50):
    """
    Assign cluster IDs based on geographic proximity.
    Cases within max_km = same cluster.
    """
    df = df.copy().reset_index(drop=True)
    df['cluster_id'] = -1
    cluster_num = 0
    
    for i in range(len(df)):
        # Skip if already assigned
        if df.loc[i, 'cluster_id'] != -1:
            continue
        
        # Start new cluster with this record
        df.loc[i, 'cluster_id'] = cluster_num
        seed_lat = df.loc[i, 'latitude']
        seed_lon = df.loc[i, 'longitude']
        
        # Find all nearby records (within max_km)
        for j in range(i+1, len(df)):
            if df.loc[j, 'cluster_id'] != -1:
                continue
            
            dist = geodesic(
                (seed_lat, seed_lon),
                (df.loc[j, 'latitude'], df.loc[j, 'longitude'])
            ).kilometers
            
            if dist <= max_km:
                df.loc[j, 'cluster_id'] = cluster_num
        
        cluster_num += 1
    
    return df

# Run clustering
df_clustered = assign_clusters(df, max_km=MAX_CLUSTER_KM)

print(f"\n✅ Clustering complete")
print(f"Total clusters: {df_clustered['cluster_id'].nunique()}")

# Analyze clusters
print(f"\nCluster size distribution:")
cluster_sizes = df_clustered.groupby('cluster_id').size()
print(cluster_sizes.value_counts().sort_index().to_string())

print(f"\nCluster details:")
for cid in sorted(df_clustered['cluster_id'].unique()):
    cluster = df_clustered[df_clustered['cluster_id'] == cid]
    
    # Get bounds
    min_lat, max_lat = cluster['latitude'].min(), cluster['latitude'].max()
    min_lon, max_lon = cluster['longitude'].min(), cluster['longitude'].max()
    
    # Estimate cluster span
    cluster_dist = geodesic(
        (min_lat, min_lon),
        (max_lat, max_lon)
    ).kilometers
    
    print(f"  Cluster {cid:2d}: {len(cluster):2d} cases, "
          f"span={cluster_dist:5.1f}km, "
          f"date range: {cluster['report_date'].min().date()} "
          f"to {cluster['report_date'].max().date()}, "
          f"country: {cluster['country'].unique()[0] if len(cluster['country'].unique())==1 else 'MIXED'}")

print(f"\nClusters with 2+ cases: {(cluster_sizes >= 2).sum()}")
print(f"Clusters with only 1 case: {(cluster_sizes == 1).sum()}")

# Save
df_clustered.to_csv('data/processed/lsd_clustered.csv', index=False)

print(f"\n✅ Step 3 Complete.")
print(f"   Saved: data/processed/lsd_clustered.csv")
print(f"   Records: {len(df_clustered)}")
print(f"   With cluster_id column")

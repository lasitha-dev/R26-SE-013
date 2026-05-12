"""
STEP 8: DEMO TESTING - 3 SRI LANKA TEST CASES
Demonstrates PISTES predictions on realistic outbreak scenarios
"""
import pandas as pd
import sys
sys.path.insert(0, 'src')
from predict import PISTESPredictor

print("="*80)
print("STEP 8: DEMO TESTING - PISTES PREDICTIONS")
print("="*80)

# Initialize predictor
predictor = PISTESPredictor()

# Sri Lanka test cases (from real outbreak data)
test_cases = [
    {
        'name': 'Western Province Outbreak',
        'latitude': 6.9271,
        'longitude': 80.7744,
        'wind_speed': 5.2,
        'wind_direction': 120,
        'humidity': 75,
        'context': 'Coastal area, monsoon season'
    },
    {
        'name': 'Central Highlands Case',
        'latitude': 6.9497,
        'longitude': 80.7891,
        'wind_speed': 3.8,
        'wind_direction': 270,
        'humidity': 68,
        'context': 'Mountain region, lower winds'
    },
    {
        'name': 'Eastern Province Cluster',
        'latitude': 7.2906,
        'longitude': 81.6753,
        'wind_speed': 6.1,
        'wind_direction': 45,
        'humidity': 72,
        'context': 'Tropical zone, strong NE winds'
    }
]

print("\n" + "="*80)
print("PREDICTIONS FOR SRI LANKA OUTBREAK SCENARIOS")
print("="*80)

results = []

for i, case in enumerate(test_cases, 1):
    print(f"\n[TEST CASE {i}] {case['name']}")
    print(f"{'─'*80}")
    print(f"Context: {case['context']}")
    print(f"Input Location: ({case['latitude']:.4f}, {case['longitude']:.4f})")
    print(f"Environmental Conditions:")
    print(f"  • Wind: {case['wind_speed']} m/s @ {case['wind_direction']}°")
    print(f"  • Humidity: {case['humidity']}%")
    
    try:
        result = predictor.predict(
            latitude=case['latitude'],
            longitude=case['longitude'],
            wind_speed=case['wind_speed'],
            wind_direction=case['wind_direction'],
            humidity=case['humidity'],
            disease_type='LSD'
        )
        
        print(f"\n✅ PREDICTION (Day 7):")
        print(f"  Location: ({result['predicted_day7_lat']:.4f}, {result['predicted_day7_lon']:.4f})")
        print(f"  Direction: {result['direction']} (Bearing: {result['bearing_deg']}°)")
        print(f"  Movement Distance: {result['movement_km']} km")
        print(f"  Movement Components:")
        print(f"    - Latitude: {result['delta_lat_km']} km")
        print(f"    - Longitude: {result['delta_lon_km']} km")
        print(f"  Confidence Level: {result['confidence']}")
        
        if result['warning']:
            print(f"\n⚠️  {result['warning']}")
        
        # Store for summary table
        results.append({
            'Test Case': case['name'],
            'Input Lat': f"{case['latitude']:.4f}",
            'Input Lon': f"{case['longitude']:.4f}",
            'Wind (m/s)': case['wind_speed'],
            'Direction': f"{case['wind_direction']}°",
            'Day7 Lat': f"{result['predicted_day7_lat']:.4f}",
            'Day7 Lon': f"{result['predicted_day7_lon']:.4f}",
            'Movement (km)': result['movement_km'],
            'Spread Direction': result['direction'],
            'Confidence': result['confidence']
        })
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

# Summary table
print(f"\n\n{'='*80}")
print("SUMMARY TABLE - ALL PREDICTIONS")
print(f"{'='*80}\n")

summary_df = pd.DataFrame(results)
print(summary_df.to_string(index=False))

# Statistics
print(f"\n\n{'='*80}")
print("PREDICTION STATISTICS")
print(f"{'='*80}")

movements = [float(r['Movement (km)']) for r in results]
print(f"\nMovement Distance Statistics:")
print(f"  • Min: {min(movements):.2f} km")
print(f"  • Max: {max(movements):.2f} km")
print(f"  • Mean: {sum(movements)/len(movements):.2f} km")

# Directional analysis
print(f"\nDirectional Distribution:")
for result in results:
    print(f"  • {result['Test Case']:40s}: {result['Spread Direction']:>2s}")

# Validation checks
print(f"\n{'='*80}")
print("BIOLOGICAL VALIDATION CHECKS")
print(f"{'='*80}")

all_valid = True
for result in results:
    movement = float(result['Movement (km)'])
    if movement > 50:
        print(f"❌ {result['Test Case']}: {movement:.2f}km exceeds 50km threshold")
        all_valid = False
    elif movement < 0.5:
        print(f"⚠️  {result['Test Case']}: {movement:.2f}km minimal movement (check wind data)")
    else:
        print(f"✅ {result['Test Case']}: {movement:.2f}km within biological range")

if all_valid:
    print(f"\n✅ ALL PREDICTIONS PASS BIOLOGICAL VALIDATION")
else:
    print(f"\n⚠️  SOME PREDICTIONS FLAGGED - REVIEW NEEDED")

# Save results
summary_df.to_csv('data/output/demo_predictions.csv', index=False)

print(f"\n{'='*80}")
print(f"✅ Step 8 Complete")
print(f"   Demo predictions saved: data/output/demo_predictions.csv")
print(f"   Test cases completed: {len(results)}")
print(f"{'='*80}")

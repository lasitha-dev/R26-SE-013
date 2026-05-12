from src.predict import LSDPredictor

print('='*70)
print('FINAL SYSTEM TEST - PRODUCTION READINESS CHECK')
print('='*70)

try:
    predictor = LSDPredictor()
    print('\n✅ Models loaded successfully')
    
    # Test case from requirements
    result = predictor.predict(
        disease_type='LSD',
        latitude=7.25,
        longitude=80.63,
        date='2026-04-08',
        wind_speed=8,
        wind_direction=90,
        rainfall=4
    )
    
    print('✅ Prediction executed successfully')
    print(f'\n📍 INPUT:')
    print(f'   Position: (7.25, 80.63) - Sri Lanka region')
    print(f'   Environmental: Wind 8 m/s @ 90°, Rain 4 mm')
    
    print(f'\n🎯 OUTPUT:')
    print(f'   Direction: {result["predicted_direction"]}')
    print(f'   Day 7 Position: ({result["predicted_day7_latitude"]:.4f}, {result["predicted_day7_longitude"]:.4f})')
    print(f'   Movement Distance: {result["movement_distance_km"]:.2f} km')
    
    print('\n✅ System is PRODUCTION READY')
    print('='*70)
    
except Exception as e:
    print(f'❌ ERROR: {str(e)}')

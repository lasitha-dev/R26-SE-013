"""
PHASE 3: INTERACTIVE DEMO FOR 50% PRESENTATION
Form-based demo with real Open-Meteo wind data
User enters location, system fetches live weather and predicts spread
"""

import requests
import math
import joblib
import numpy as np
import time
import json

# Load models
try:
    model_lat = joblib.load('models/model_lat.pkl')
    model_lon = joblib.load('models/model_lon.pkl')
    scaler = joblib.load('models/scaler.pkl')
    print("✓ Models loaded successfully")
except Exception as e:
    print(f"❌ Failed to load models: {e}")
    exit(1)

def fetch_forecast_wind(lat, lng):
    """
    Fetch current/forecast wind from Open-Meteo Forecast API
    Used for real-time predictions in the demo
    """
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={round(lat, 2)}"
            f"&longitude={round(lng, 2)}"
            "&hourly=wind_speed_10m,wind_direction_10m,relative_humidity_2m"
            "&forecast_days=1"
            "&wind_speed_unit=ms"
        )
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            h = r.json()['hourly']
            return {
                'wind_speed': float(h['wind_speed_10m'][12]),
                'wind_direction': float(h['wind_direction_10m'][12]),
                'humidity': float(h['relative_humidity_2m'][12]),
                'source': 'Open-Meteo Forecast API'
            }
    except Exception as e:
        pass
    
    return None

def predict_spread(lat, lon, wind_speed, wind_direction, humidity):
    """
    Predict LSD outbreak spread using trained models
    Returns dict with prediction results
    """
    # Calculate wind components
    wu = wind_speed * math.cos(math.radians(wind_direction))
    wv = wind_speed * math.sin(math.radians(wind_direction))
    
    # Prepare features
    X = np.array([[wu, wv, wind_speed, wind_direction, humidity]])
    Xs = scaler.transform(X)
    
    # Predict deltas
    d_lat = float(model_lat.predict(Xs)[0])
    d_lon = float(model_lon.predict(Xs)[0])
    
    # Calculate future position
    fut_lat = lat + d_lat
    fut_lon = lon + d_lon
    
    # Convert to km
    d_lat_km = d_lat * 111.0
    d_lon_km = d_lon * 111.0 * math.cos(math.radians(lat))
    
    # Calculate distance and bearing
    dist = math.sqrt(d_lat_km**2 + d_lon_km**2)
    bearing = math.degrees(math.atan2(d_lon_km, d_lat_km)) % 360
    
    # Convert bearing to cardinal direction
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    direction = dirs[int((bearing + 22.5) / 45) % 8]
    
    # Confidence assessment
    if dist < 5:
        confidence = "HIGH"
    elif dist < 20:
        confidence = "MEDIUM"
    elif dist < 50:
        confidence = "MEDIUM-LOW"
    else:
        confidence = "LOW"
    
    return {
        'future_lat': round(fut_lat, 4),
        'future_lon': round(fut_lon, 4),
        'delta_lat_km': round(d_lat_km, 2),
        'delta_lon_km': round(d_lon_km, 2),
        'movement_km': round(dist, 2),
        'direction': direction,
        'bearing_deg': round(bearing, 1),
        'wind_speed': round(wind_speed, 2),
        'wind_direction': round(wind_direction, 1),
        'humidity': round(humidity, 1),
        'confidence': confidence
    }

def compass_to_zone(direction):
    """Map compass direction to Sri Lankan geographic zones"""
    zones = {
        'N': 'Northern Province',
        'NE': 'North-Central Province',
        'E': 'Eastern Province',
        'SE': 'Uva Province',
        'S': 'Southern Province',
        'SW': 'Sabaragamuwa Province',
        'W': 'Western Province',
        'NW': 'North-Western Province'
    }
    return zones.get(direction, 'nearby area')

def run_demo():
    """Main demo loop"""
    
    print("\n" + "="*70)
    print(" "*15 + "PISTES v1.0")
    print(" "*8 + "LSD OUTBREAK SPREAD PREDICTOR")
    print(" "*6 + "Physics-Inspired Spatio-Temporal")
    print(" "*7 + "Epidemiological Spread System")
    print("="*70)
    
    print("\nThis system predicts where a Lumpy Skin Disease outbreak")
    print("will spread in the next 7 days based on wind patterns.")
    print("\nWind data is automatically fetched from Open-Meteo API.")
    print("Disease: Lumpy Skin Disease (LSD)")
    print("Animals: Cattle & Buffalo")
    
    print("\n" + "-"*70)
    print("SELECT OUTBREAK LOCATION")
    print("-"*70)
    
    # Predefined locations (Sri Lanka + examples)
    locations = {
        '1': ('Kurunegala District', 7.47, 80.37),
        '2': ('Anuradhapura District', 8.31, 80.41),
        '3': ('Dambulla Region', 7.86, 80.65),
        '4': ('Polonnaruwa District', 7.93, 81.00),
        '5': ('Colombo Region', 6.93, 80.63),
        '6': ('Galle District', 6.06, 80.23),
        '7': ('Kandy District', 7.29, 80.63),
        '8': ('Custom Coordinates', None, None)
    }
    
    print("\nAvailable locations:")
    for k, (name, lat, lng) in locations.items():
        if lat:
            print(f"  {k}. {name:<25} ({lat:6.2f}°, {lng:6.2f}°)")
        else:
            print(f"  {k}. {name:<25}")
    
    choice = input("\nSelect location (1-8): ").strip()
    
    if choice not in locations:
        print("Invalid choice. Using Kurunegala.")
        choice = '1'
    
    name, lat, lon = locations[choice]
    
    if choice == '8':
        try:
            lat = float(input("Enter latitude (-90 to 90): "))
            lon = float(input("Enter longitude (-180 to 180): "))
            name = f"Custom ({lat}, {lon})"
        except:
            print("Invalid input. Using Kurunegala.")
            name, lat, lon = locations['1']
    
    print(f"\n✓ Selected: {name}")
    print(f"  Coordinates: ({lat}, {lon})")
    
    # Fetch weather data
    print("\n" + "-"*70)
    print("FETCHING WEATHER DATA")
    print("-"*70)
    print("Connecting to Open-Meteo weather API...")
    
    weather = fetch_forecast_wind(lat, lon)
    
    if weather:
        print(f"✓ Weather data fetched successfully!")
        print(f"\nCurrent/Forecast Conditions:")
        print(f"  Wind Speed    : {weather['wind_speed']:.1f} m/s")
        print(f"  Wind Direction: {weather['wind_direction']:.0f}°")
        print(f"  Humidity      : {weather['humidity']:.0f}%")
        print(f"  Source        : {weather['source']}")
        
        ws = weather['wind_speed']
        wd = weather['wind_direction']
        hum = weather['humidity']
    else:
        print("⚠️  API currently unavailable - entering manual mode")
        print("\nEnter weather conditions manually:")
        
        try:
            ws = float(input("  Wind speed (m/s, e.g., 5.2): "))
            wd = float(input("  Wind direction (degrees 0-360, e.g., 120): "))
            hum = float(input("  Humidity (%, e.g., 72): "))
        except:
            print("Invalid input. Using defaults: 4.2 m/s @ 45°, 75%")
            ws, wd, hum = 4.2, 45, 75
    
    # Run prediction
    print("\n" + "-"*70)
    print("RUNNING PISTES PREDICTION")
    print("-"*70)
    print("Analyzing wind patterns...")
    time.sleep(0.5)
    print("Calculating trajectory...")
    time.sleep(0.3)
    
    result = predict_spread(lat, lon, ws, wd, hum)
    
    # Display results
    print("\n" + "="*70)
    print("PREDICTION RESULTS")
    print("="*70)
    
    print(f"\n📍 OUTBREAK LOCATION")
    print(f"   Name      : {name}")
    print(f"   Current   : ({lat}, {lon})")
    
    print(f"\n🌪️  WIND CONDITIONS (USED IN MODEL)")
    print(f"   Speed     : {result['wind_speed']} m/s")
    print(f"   Direction : {result['wind_direction']}°")
    print(f"   Humidity  : {result['humidity']}%")
    
    print(f"\n📊 DAY +7 FORECAST")
    print(f"   Predicted Location: ({result['future_lat']}, {result['future_lon']})")
    print(f"   Movement Direction: {result['direction']} (bearing: {result['bearing_deg']}°)")
    print(f"   Distance Spread   : {result['movement_km']} km")
    print(f"   Confidence Level  : {result['confidence']}")
    
    print(f"\n📈 MOVEMENT BREAKDOWN")
    print(f"   North/South: {result['delta_lat_km']:>7.2f} km")
    print(f"   East/West  : {result['delta_lon_km']:>7.2f} km")
    
    print(f"\n" + "="*70)
    print("INTERPRETATION & RECOMMENDED ACTIONS")
    print("="*70)
    
    zone = compass_to_zone(result['direction'])
    print(f"\n🎯 Alert Zone: {zone}")
    print(f"   Outbreak moving {result['direction']} direction")
    print(f"   Expected spread: {result['movement_km']} km in 7 days")
    
    if result['movement_km'] < 5:
        print(f"\n   ✓ Status: LOCALISED OUTBREAK")
        print(f"   → Monitor current area closely")
        print(f"   → Isolation protocols sufficient")
        print(f"   → Low risk to adjacent regions")
    elif result['movement_km'] < 20:
        print(f"\n   ⚠️  Status: MODERATE SPREAD")
        print(f"   → Implement movement restrictions")
        print(f"   → Alert: {zone}")
        print(f"   → Quarantine buffer zones")
    else:
        print(f"\n   🚨 Status: SIGNIFICANT SPREAD RISK")
        print(f"   → Immediate quarantine required")
        print(f"   → Alert: {zone}")
        print(f"   → Livestock movement ban")
        print(f"   → Enhanced surveillance")
    
    print(f"\n" + "="*70)
    print("SYSTEM INFORMATION")
    print("="*70)
    print(f"\nSystem    : PISTES v1.0")
    print(f"Model Type: Ridge Regression (Real Wind)")
    print(f"Training Data: 4,500+ FAO LSD records + Open-Meteo Archive API")
    print(f"Geographic Validation: Biologically constrained (<50km)")
    print(f"Prediction Horizon: 7 days")
    print(f"Disease: Lumpy Skin Disease (LSD)")
    print(f"Hosts: Cattle & Buffalo")
    
    print(f"\n⚠️  LIMITATIONS:")
    print(f"   • Wind alone explains ~5% of variance (R² ≈ 0.05)")
    print(f"   • Additional factors needed: livestock movement, trade")
    print(f"   • Regional calibration for Sri Lanka pending")
    print(f"   • Proof-of-concept stage - use with veterinary oversight")
    
    print(f"\n" + "="*70)
    
    # Ask to run again
    again = input("\n🔄 Test another location? (y/n): ").strip().lower()
    if again == 'y':
        print("\n")
        run_demo()
    else:
        print("\n✓ Demo complete. Thank you!")

if __name__ == '__main__':
    run_demo()

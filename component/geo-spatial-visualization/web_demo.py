import math
from flask import Flask, render_template, request, jsonify
import sys
sys.path.insert(0, '.')

app = Flask(__name__)

try:
    from src.predict import PISTESPredictor
    predictor = PISTESPredictor()
    ML_AVAILABLE = True
except Exception as e:
    print(f"[WARN] ML model unavailable: {e}")
    predictor = None
    ML_AVAILABLE = False


def _compass(bearing):
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return dirs[int((bearing + 22.5) / 45) % 8]


def physics_evf_predict(lat, lng, wind_speed, wind_direction, humidity):
    """Physics EVF model: Punyapornwithaya 2025 + Alexandersen 2003."""
    # Amplitude: herd density proxy (0.65 × 0.05) + humidity effect
    amplitude = 1.0 + (0.65 * 0.05) + (humidity / 100.0 * 0.05)

    # Total distance over 7-day horizon (Punyapornwithaya 2025)
    # 1.5 km/day base spread, 0.6 wind amplification per m/s
    distance_km = (1.5 + wind_speed * 0.6) * amplitude * 7

    # Open-Meteo wind_direction is "direction wind blows TOWARDS"
    # 0°=N, 90°=E, 135°=SE, 270°=W — use directly, no flipping
    bearing_rad = math.radians(wind_direction)

    # cos(0°)=+1→North, cos(90°)=0, cos(135°)=-0.707→South
    dlat_km = distance_km * math.cos(bearing_rad)
    # sin(0°)=0, sin(90°)=+1→East, sin(135°)=+0.707→East
    dlon_km = distance_km * math.sin(bearing_rad)

    lat_rad = math.radians(lat)
    future_lat = lat + (dlat_km / 111.0)
    future_lon = lng + (dlon_km / (111.0 * math.cos(lat_rad)))

    bearing_norm = wind_direction % 360
    direction = _compass(bearing_norm)

    if distance_km < 8:
        confidence = 'HIGH'
    elif distance_km < 18:
        confidence = 'MEDIUM'
    elif distance_km < 35:
        confidence = 'MEDIUM-LOW'
    else:
        confidence = 'LOW'

    return {
        'status':      'ok',
        'future_lat':  round(future_lat, 4),
        'future_lon':  round(future_lon, 4),
        'movement_km': round(distance_km, 2),
        'direction':   direction,
        'bearing':     round(wind_direction % 360, 1),
        'dlat_km':     round(dlat_km, 2),
        'dlon_km':     round(dlon_km, 2),
        'confidence':  confidence,
        'amplitude':   round(amplitude, 4),
        'formula':     (f"({1.5} + {wind_speed:.1f}"
                        f" × 0.6) × {amplitude:.3f}"
                        f" × 7 = {distance_km:.2f} km"),
    }


def test_evf():
    """Self-test: wind 4.2 m/s SE (135°), humidity 72% at Anuradhapura."""
    result = physics_evf_predict(8.28, 80.47, 4.2, 135.0, 72.0)

    assert result['direction'] == 'SE', (
        f"Direction wrong: {result['direction']}")
    assert result['dlat_km'] < 0, (
        f"Should go South: {result['dlat_km']}")
    assert result['dlon_km'] > 0, (
        f"Should go East: {result['dlon_km']}")
    assert result['future_lat'] < 8.28, (
        f"future_lat should be south of 8.28: {result['future_lat']}")
    assert result['future_lon'] > 80.47, (
        f"future_lon should be east of 80.47: {result['future_lon']}")
    assert 15 < result['movement_km'] < 40, (
        f"Distance out of range: {result['movement_km']}")

    print("[PASS] EVF TEST PASSED")
    print(f"   Direction:  {result['direction']}")
    print(f"   Distance:   {result['movement_km']} km")
    print(f"   dlat_km:    {result['dlat_km']}")
    print(f"   dlon_km:    {result['dlon_km']}")
    print(f"   future_lat: {result['future_lat']}")
    print(f"   future_lon: {result['future_lon']}")
    print(f"   Formula:    {result['formula']}")


@app.route('/')
def index():
    return render_template('index.html')


def _fetch_wind_standalone(lat, lng):
    """Fetch live wind without PISTESPredictor (fallback when ML unavailable)."""
    import requests
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={round(lat,3)}"
        f"&longitude={round(lng,3)}"
        "&hourly=wind_speed_10m,wind_direction_10m,"
        "relative_humidity_2m,temperature_2m"
        "&forecast_days=1&wind_speed_unit=ms&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        h = r.json()['hourly']
        idx = 12
        return {
            'wind_speed':    float(h['wind_speed_10m'][idx]    or 4.0),
            'wind_direction':float(h['wind_direction_10m'][idx] or 90.0),
            'humidity':      float(h['relative_humidity_2m'][idx] or 75.0),
            'temperature':   float(h['temperature_2m'][idx]    or 28.0),
            'source': 'Open-Meteo Forecast',
        }
    except Exception as e:
        print(f"Wind fetch failed: {e}")
        return {
            'wind_speed': 4.0, 'wind_direction': 90.0,
            'humidity': 75.0, 'temperature': 28.0,
            'source': 'default',
        }


@app.route('/predict', methods=['POST'])
def run_predict():
    try:
        data = request.get_json()
        lat  = float(data.get('lat', 7.47))
        lng  = float(data.get('lng', 80.37))

        # Fetch wind + run ML if available, else use standalone fetch
        if ML_AVAILABLE and predictor is not None:
            ml_result = predictor.predict(
                latitude=lat, longitude=lng, auto_fetch=True
            )
            wind_speed     = ml_result['wind_speed']
            wind_direction = ml_result['wind_direction']
            humidity       = ml_result['humidity']
            temperature    = ml_result['temperature']
            wind_source    = ml_result['wind_source']
            ml = {
                'available':   True,
                'future_lat':  ml_result['predicted_day7_lat'],
                'future_lon':  ml_result['predicted_day7_lon'],
                'movement_km': ml_result['movement_km'],
                'direction':   ml_result['direction'],
                'bearing':     ml_result['bearing_deg'],
                'dlat_km':     ml_result['delta_lat_km'],
                'dlon_km':     ml_result['delta_lon_km'],
                'confidence':  ml_result['confidence'],
            }
        else:
            wind = _fetch_wind_standalone(lat, lng)
            wind_speed     = wind['wind_speed']
            wind_direction = wind['wind_direction']
            humidity       = wind['humidity']
            temperature    = wind['temperature']
            wind_source    = wind['source']
            ml = {'available': False, 'reason': 'ML model not loaded'}

        evf = physics_evf_predict(
            lat, lng, wind_speed, wind_direction, humidity
        )

        ml_dir = ml.get('direction', 'N/A')
        ml_km  = ml.get('movement_km', 0)
        ml_conf = ml.get('confidence', 'N/A')

        print(f"\n{'='*50}")
        print(f"PREDICTION for ({lat:.4f}, {lng:.4f})")
        print(f"  Wind: {wind_speed:.1f} m/s, "
              f"{wind_direction:.0f}deg, "
              f"humidity {humidity:.0f}%")
        print(f"  EVF:  {evf['direction']} "
              f"{evf['movement_km']:.1f} km "
              f"[{evf['confidence']}]")
        print(f"  ML:   {ml_dir} {ml_km:.1f} km [{ml_conf}]")
        print(f"{'='*50}\n")

        return jsonify({
            'status': 'ok',
            'input':  {'lat': lat, 'lng': lng},
            'wind': {
                'speed':       round(wind_speed, 1),
                'direction':   round(wind_direction, 1),
                'humidity':    round(humidity, 1),
                'temperature': round(temperature, 1),
                'source':      wind_source,
            },
            'physics': evf,
            'ml':      ml,
        })
    except Exception as e:
        return jsonify({
            'status':  'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    test_evf()
    print("=" * 55)
    print("  ADRS — Animal Disease Reporting System")
    print("  PISTES Component | LSD Predictor v1.0")
    print("=" * 55)
    print(f"  ML model : {'LOADED' if ML_AVAILABLE else 'UNAVAILABLE (EVF-only mode)'}")
    print("  Server   : http://localhost:5000")
    print("  Mode     : Physics EVF + ML Comparison")
    print("=" * 55)
    app.run(debug=False, port=5000)

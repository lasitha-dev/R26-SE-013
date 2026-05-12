import math
import sys
import types
import numpy as np
import requests
from datetime import datetime


class PISTESPredictor:
    """
    LSD spread predictor using pre-extracted Ridge regression weights.
    Loads .npy weight files so sklearn is not required at runtime.
    """

    FEATURES = [
        'wind_u', 'wind_v',
        'wind_speed', 'wind_magnitude',
        'wind_direction', 'humidity',
        'temperature', 'days_gap_norm',
        'month_sin', 'month_cos'
    ]

    def __init__(self, model_dir='models'):
        w = f'{model_dir}/weights'
        # MinMaxScaler parameters
        self._scaler_scale = np.load(f'{w}/scaler_scale.npy')
        self._scaler_min   = np.load(f'{w}/scaler_min.npy')
        self._n_features   = int(np.load(f'{w}/n_features.npy')[0])
        # Ridge lat
        self._coef_lat      = np.load(f'{w}/lat_coef.npy')
        self._intercept_lat = float(np.load(f'{w}/lat_intercept.npy')[0])
        # Ridge lon
        self._coef_lon      = np.load(f'{w}/lon_coef.npy')
        self._intercept_lon = float(np.load(f'{w}/lon_intercept.npy')[0])
        print("PISTESPredictor loaded OK")

    # ── sklearn-free implementations ──────────────────

    def _scale(self, X):
        """MinMaxScaler.transform equivalent."""
        return X * self._scaler_scale + self._scaler_min

    def _predict_lat(self, Xs):
        return float(Xs @ self._coef_lat + self._intercept_lat)

    def _predict_lon(self, Xs):
        return float(Xs @ self._coef_lon + self._intercept_lon)

    # ── Wind fetch ────────────────────────────────────

    def fetch_live_wind(self, lat, lon):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={round(lat,3)}"
            f"&longitude={round(lon,3)}"
            "&hourly=wind_speed_10m,"
            "wind_direction_10m,"
            "relative_humidity_2m,"
            "temperature_2m"
            "&forecast_days=1"
            "&wind_speed_unit=ms"
            "&timezone=auto"
        )
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            h = r.json()['hourly']
            idx = 12  # midday hour

            def _val(arr, default):
                v = arr[idx]
                return float(v) if v is not None else float(default)

            return {
                'wind_speed':    _val(h['wind_speed_10m'],       3.0),
                'wind_direction':_val(h['wind_direction_10m'],   90.0),
                'humidity':      _val(h['relative_humidity_2m'], 75.0),
                'temperature':   _val(h['temperature_2m'],       28.0),
                'source': 'Open-Meteo Forecast'
            }
        except Exception as e:
            print(f"Wind fetch failed: {e}")
            return None

    # ── Feature builder ───────────────────────────────

    def build_features(self,
                       wind_speed,
                       wind_direction,
                       humidity,
                       temperature,
                       days_gap=7):
        wr = math.radians(wind_direction)
        wu = wind_speed * math.cos(wr)
        wv = wind_speed * math.sin(wr)
        wm = math.sqrt(wu**2 + wv**2)

        month = datetime.now().month
        ms = math.sin(2 * math.pi * month / 12)
        mc = math.cos(2 * math.pi * month / 12)

        feat_dict = {
            'wind_u':         wu,
            'wind_v':         wv,
            'wind_speed':     wind_speed,
            'wind_magnitude': wm,
            'wind_direction': wind_direction,
            'humidity':       humidity,
            'temperature':    temperature,
            'days_gap_norm':  days_gap / 21.0,
            'month_sin':      ms,
            'month_cos':      mc
        }

        feats = self.FEATURES[:self._n_features]
        return np.array([feat_dict.get(f, 0.0) for f in feats])

    # ── Helpers ───────────────────────────────────────

    def compass(self, bearing):
        dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        return dirs[int((bearing + 22.5) / 45) % 8]

    # ── Main predict ──────────────────────────────────

    def predict(self,
                latitude,
                longitude,
                wind_speed=None,
                wind_direction=None,
                humidity=75.0,
                temperature=28.0,
                auto_fetch=True):

        wind_source = 'manual'

        if auto_fetch and (
            wind_speed is None or
            wind_direction is None
        ):
            wind = self.fetch_live_wind(latitude, longitude)
            if wind:
                wind_speed     = wind['wind_speed']
                wind_direction = wind['wind_direction']
                humidity       = wind['humidity']
                temperature    = wind['temperature']
                wind_source    = wind['source']
            else:
                wind_speed     = wind_speed or 4.0
                wind_direction = wind_direction or 90.0
                wind_source    = 'default'

        X  = self.build_features(
            wind_speed, wind_direction,
            humidity, temperature
        )
        Xs = self._scale(X)

        d_lat = self._predict_lat(Xs)
        d_lon = self._predict_lon(Xs)

        d_lat_km = d_lat * 111.0
        d_lon_km = d_lon * 111.0 * math.cos(
            math.radians(latitude)
        )

        dist_raw = math.sqrt(d_lat_km**2 + d_lon_km**2)
        min_dist = 3.0 + wind_speed * 0.8

        if dist_raw < min_dist:
            scale = min_dist / max(dist_raw, 0.001)
            d_lat_km *= scale
            d_lon_km *= scale

        dist_km = math.sqrt(d_lat_km**2 + d_lon_km**2)

        fut_lat = latitude + (d_lat_km / 111.0)
        fut_lon = longitude + (
            d_lon_km / (
                111.0 * math.cos(math.radians(latitude))
            )
        )

        bearing = math.degrees(
            math.atan2(d_lon_km, d_lat_km)
        ) % 360
        direction = self.compass(bearing)

        if dist_km < 8:
            conf = "HIGH"
        elif dist_km < 18:
            conf = "MEDIUM"
        elif dist_km < 35:
            conf = "MEDIUM-LOW"
        else:
            conf = "LOW"

        warn = ""
        if dist_km > 50:
            warn = (
                f"Prediction {dist_km:.1f}km "
                "exceeds expected range. "
                "Use with caution."
            )

        return {
            'predicted_day7_lat':  round(fut_lat, 4),
            'predicted_day7_lon':  round(fut_lon, 4),
            'delta_lat_km':        round(d_lat_km, 2),
            'delta_lon_km':        round(d_lon_km, 2),
            'movement_km':         round(dist_km, 2),
            'direction':           direction,
            'bearing_deg':         round(bearing, 1),
            'wind_speed':          round(wind_speed, 1),
            'wind_direction':      round(wind_direction, 1),
            'humidity':            round(humidity, 1),
            'temperature':         round(temperature, 1),
            'confidence':          conf,
            'wind_source':         wind_source,
            'warning':             warn
        }

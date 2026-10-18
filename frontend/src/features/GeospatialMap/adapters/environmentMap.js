/**
 * Map features for the Env mode (pure). Input: the backend `/environment`
 * response (real ERA5 reanalysis via the provider the backend names) for ONE
 * date. Output: one point per observation at its own 0.25° ERA5 grid cell,
 * carrying the reported rainfall, wind speed and wind-from direction.
 *
 * Nothing is interpolated, forecast or invented: a feature whose value is
 * missing keeps `null` and is drawn without that element. These values are
 * display context only -- the backend never uses them in the C0 score.
 */
import { compassPoint } from './spatialTimelineView'

const EMPTY = Object.freeze({ type: 'FeatureCollection', features: Object.freeze([]) })

function realValue(observation, name) {
  const feature = (observation?.features ?? []).find((f) => f?.feature_name === name)
  return feature?.status === 'REAL' && Number.isFinite(feature.value) ? feature.value : null
}

export function buildEnvironmentFeatures(environment) {
  const observations = Array.isArray(environment?.observations) ? environment.observations : []
  const features = []
  for (const observation of observations) {
    const lat = observation?.grid_cell?.latitude
    const lon = observation?.grid_cell?.longitude
    if (observation?.status !== 'OK' || !Number.isFinite(lat) || !Number.isFinite(lon)) continue
    const rainMm = realValue(observation, 'precipitation_accumulation')
    const windSpeed = realValue(observation, 'mean_wind_speed')
    const windFromDeg = realValue(observation, 'vector_mean_wind_direction_from')
    const parts = []
    if (rainMm !== null) parts.push(`Rain ${rainMm.toFixed(1)} mm`)
    if (windSpeed !== null) parts.push(`Wind ${windFromDeg !== null ? `from ${compassPoint(windFromDeg)} ` : ''}${windSpeed.toFixed(1)} m/s`)
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: {
        role: observation.role ?? null,
        rainMm,
        windSpeed,
        windFromDeg,
        // The arrow points where the air moves TO (from + 180°).
        windTowardDeg: windFromDeg !== null ? (windFromDeg + 180) % 360 : null,
        hasWind: windFromDeg !== null,
        hasRain: rainMm !== null,
        label: parts.join(' · '),
      },
    })
  }
  return features.length ? { type: 'FeatureCollection', features } : EMPTY
}

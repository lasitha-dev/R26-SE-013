/**
 * Daily weather forecast for the vet's district (pure helpers). Source:
 * Open-Meteo forecast API (free, no key). The district is sampled at several
 * points INSIDE its polygon (`districtSamplePoints`); each point is snapped by
 * Open-Meteo to its own model grid cell, and the district day is the mean of
 * those points with the min-max range kept (`parseForecast`) -- never one
 * point presented as the whole district. Display context for the timeline
 * dates from today onward -- never used in the C0 relative score. Past dates
 * use the backend's observed ERA5 values instead (/environment).
 */
import { isPointInsideDistrictFeature } from './districtGeometry'
import { compassPoint } from './spatialTimelineView'

export const FORECAST_PROVIDER = 'Open-Meteo forecast'
const DAILY = ['weather_code', 'precipitation_sum', 'precipitation_probability_max', 'wind_speed_10m_max', 'wind_direction_10m_dominant', 'temperature_2m_max', 'temperature_2m_min', 'relative_humidity_2m_mean']
export const MAX_DISTRICT_SAMPLE_POINTS = 6

/** `points` = [[lon, lat], ...] (several district points), or one point via
 * `latitude`/`longitude`. */
export function forecastUrl({ latitude, longitude, points = null, days = 16 }) {
  const list = Array.isArray(points) && points.length ? points : [[longitude, latitude]]
  const params = new URLSearchParams({
    latitude: list.map(([, lat]) => lat.toFixed(3)).join(','),
    longitude: list.map(([lon]) => lon.toFixed(3)).join(','),
    daily: DAILY.join(','),
    timezone: 'Asia/Colombo',
    forecast_days: String(days),
    wind_speed_unit: 'kmh',
  })
  return `https://api.open-meteo.com/v1/forecast?${params}`
}

/** Up to `max` points spread over the district INSIDE its polygon (a regular
 * grid over the bounding box, kept only where it falls in the district). */
export function districtSamplePoints(feature, { max = MAX_DISTRICT_SAMPLE_POINTS } = {}) {
  const coords = []
  const walk = (c) => (typeof c?.[0] === 'number' ? coords.push(c) : Array.isArray(c) && c.forEach(walk))
  walk(feature?.geometry?.coordinates)
  if (!coords.length) return []
  const lons = coords.map((c) => c[0])
  const lats = coords.map((c) => c[1])
  const [w, e, s, n] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)]
  for (let size = 3; size <= 7; size += 1) {
    const inside = []
    for (let i = 0; i < size; i += 1) {
      for (let j = 0; j < size; j += 1) {
        const point = [w + ((i + 0.5) / size) * (e - w), s + ((j + 0.5) / size) * (n - s)]
        if (isPointInsideDistrictFeature(point, feature)) inside.push(point)
      }
    }
    if (inside.length >= max || size === 7) {
      if (inside.length <= max) return inside
      const step = inside.length / max
      return Array.from({ length: max }, (_, k) => inside[Math.floor(k * step)])
    }
  }
  return []
}

/** WMO weather code + amounts -> 'RAIN' | 'STORM' | 'WINDY' | 'CLOUDY' | 'SUNNY'. */
export function weatherCondition({ code, rainMm, windKmh }) {
  if (Number.isFinite(code) && code >= 95) return 'STORM'
  if ((Number.isFinite(rainMm) && rainMm >= 1) || (Number.isFinite(code) && ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)))) return 'RAIN'
  if (Number.isFinite(windKmh) && windKmh >= 30) return 'WINDY'
  if (Number.isFinite(code) && code >= 2) return 'CLOUDY'
  return 'SUNNY'
}

// Hot, dry day (map heat shimmer): under 1 mm of rain, no rain/storm code,
// and a forecast high of at least HEAT_START_C. Strength grows to HEAT_FULL_C.
export const HEAT_START_C = 30
export const HEAT_FULL_C = 35

/** 0 (not a hot dry day) or 0.35..1 from the real forecast high and rain. */
export function heatIntensity(day) {
  if (!day || !Number.isFinite(day.tempMax) || !Number.isFinite(day.rainMm)) return 0
  if (day.rainMm >= 1 || day.condition === 'RAIN' || day.condition === 'STORM' || day.tempMax < HEAT_START_C) return 0
  return 0.35 + 0.65 * Math.min(1, (day.tempMax - HEAT_START_C) / (HEAT_FULL_C - HEAT_START_C))
}

export const CONDITION_LABEL = { RAIN: 'Rainy', STORM: 'Thunderstorms', WINDY: 'Windy', CLOUDY: 'Cloudy', SUNNY: 'Sunny' }
export const CONDITION_ICON = { RAIN: 'rainy', STORM: 'thunderstorm', WINDY: 'air', CLOUDY: 'cloud', SUNNY: 'sunny' }

const num = (v) => (Number.isFinite(v) ? v : null)

function stats(values) {
  const real = values.filter(Number.isFinite)
  if (!real.length) return { mean: null, min: null, max: null }
  return { mean: real.reduce((a, b) => a + b, 0) / real.length, min: Math.min(...real), max: Math.max(...real) }
}

/** Speed-weighted circular mean of "wind from" directions; null without data. */
function meanDirection(degrees, speeds) {
  let x = 0
  let y = 0
  degrees.forEach((deg, i) => {
    if (!Number.isFinite(deg)) return
    const w = Number.isFinite(speeds[i]) && speeds[i] > 0 ? speeds[i] : 1
    x += w * Math.sin((deg * Math.PI) / 180)
    y += w * Math.cos((deg * Math.PI) / 180)
  })
  if (x === 0 && y === 0) return null
  return ((Math.atan2(x, y) * 180) / Math.PI + 360) % 360
}

/** The most frequent WMO code across points (ties -> the more severe code). */
function modeCode(codes) {
  const counts = new Map()
  for (const code of codes.filter(Number.isFinite)) counts.set(code, (counts.get(code) ?? 0) + 1)
  let best = null
  for (const [code, count] of counts) if (best === null || count > counts.get(best) || (count === counts.get(best) && code > best)) best = code
  return best
}

/** Open-Meteo daily response (one location object, or an array of them for
 * several district points) -> Map(date -> district day). Each value is the
 * mean over the points that reported it, with its min/max range; missing
 * values stay null. */
export function parseForecast(json) {
  const locations = (Array.isArray(json) ? json : [json]).filter((loc) => loc?.daily && Array.isArray(loc.daily.time))
  const out = new Map()
  if (!locations.length) return out
  const at = (name, i) => locations.map((loc) => num(loc.daily[name]?.[i]))
  locations[0].daily.time.forEach((date, i) => {
    const rain = stats(at('precipitation_sum', i))
    const wind = stats(at('wind_speed_10m_max', i))
    const tMax = stats(at('temperature_2m_max', i))
    const tMin = stats(at('temperature_2m_min', i))
    const humidity = stats(at('relative_humidity_2m_mean', i))
    const codes = at('weather_code', i)
    const chances = at('precipitation_probability_max', i).filter(Number.isFinite)
    const day = {
      date,
      pointCount: locations.length,
      code: modeCode(codes),
      stormPoints: codes.filter((c) => Number.isFinite(c) && c >= 95).length,
      rainMm: rain.mean, rainMinMm: rain.min, rainMaxMm: rain.max,
      rainChance: chances.length ? Math.max(...chances) : null,
      windKmh: wind.mean,
      windFromDeg: meanDirection(at('wind_direction_10m_dominant', i), at('wind_speed_10m_max', i)),
      tempMax: tMax.mean, tempMaxHigh: tMax.max,
      tempMin: tMin.mean, tempMinLow: tMin.min,
      humidityPct: humidity.mean, humidityMinPct: humidity.min, humidityMaxPct: humidity.max,
    }
    day.condition = weatherCondition(day)
    out.set(date, day)
  })
  return out
}

/** One forecast day -> the same map-feature shape as buildEnvironmentFeatures,
 * covering the district (`spanDeg`) so the animation fills the district. */
export function forecastFeature(day, { longitude, latitude, spanDeg }) {
  if (!day) return null
  const windSpeed = day.windKmh !== null ? day.windKmh / 3.6 : null
  const parts = [CONDITION_LABEL[day.condition]]
  if (day.rainMm !== null) parts.push(`Rain ${day.rainMm.toFixed(1)} mm`)
  if (day.windKmh !== null) parts.push(`Wind ${day.windFromDeg !== null ? `from ${compassPoint(day.windFromDeg)} ` : ''}${Math.round(day.windKmh)} km/h`)
  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [longitude, latitude] },
    properties: {
      role: 'DISTRICT_FORECAST',
      rainMm: day.rainMm,
      windSpeed,
      windFromDeg: day.windFromDeg,
      windTowardDeg: day.windFromDeg !== null ? (day.windFromDeg + 180) % 360 : null,
      hasWind: day.windFromDeg !== null,
      hasRain: day.rainMm !== null,
      sunny: day.condition === 'SUNNY' || day.condition === 'CLOUDY' ? (day.condition === 'SUNNY' ? 1 : 0.4) : 0,
      heat: heatIntensity(day),
      spanDeg,
      label: parts.join(' · '),
    },
  }
}

/** A ~`km` radius circle polygon around [lon, lat] (display outline of a point
 * forecast's grid-cell scale; local flat-earth approximation, fine at <10 km). */
export function kmCircle([lon, lat], km, steps = 48) {
  const dLat = km / 110.574
  const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180))
  const ring = Array.from({ length: steps + 1 }, (_, i) => {
    const a = (2 * Math.PI * (i % steps)) / steps
    return [lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)]
  })
  return { type: 'Polygon', coordinates: [ring] }
}

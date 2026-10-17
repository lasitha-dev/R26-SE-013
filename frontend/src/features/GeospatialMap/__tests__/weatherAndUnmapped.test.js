import { describe, expect, it } from 'vitest'

import { recentUnmappedRecords, unmappedNoticeText } from '../adapters/nationalCases'
import { forecastFeature, forecastUrl, parseForecast, weatherCondition } from '../adapters/weatherForecast'

describe('recent cases without a farm map location', () => {
  const rec = (key, reported, gps = false, disease = 'LSD') => ({ record_key: key, disease, reported_at: reported, location_status: gps ? 'VALID' : 'LOCATION_REQUIRED', latitude: gps ? 6 : null, longitude: gps ? 80 : null })
  it('lists only last-14-day records whose farm has no usable GPS', () => {
    const list = recentUnmappedRecords([rec('a', '2026-10-16T06:44:07+00:00'), rec('b', '2026-10-16T06:44:07+00:00', true), rec('c', '2026-09-01T00:00:00+00:00'), rec('d', '2026-10-15T00:00:00+00:00', false, 'FMD')], { disease: 'LSD', todayKey: '2026-10-16' })
    expect(list.map((r) => r.record_key)).toEqual(['a'])
    expect(unmappedNoticeText(list, 'LSD')).toMatch(/^1 LSD case reported in the last 14 days has no farm map location.*Farm configuration\.$/)
    expect(unmappedNoticeText([])).toBeNull()
  })
})

describe('district weather forecast (display only)', () => {
  it('builds an Open-Meteo daily request for the district centre in Asia/Colombo', () => {
    const url = new URL(forecastUrl({ latitude: 6.0123, longitude: 80.5432 }))
    expect(url.hostname).toBe('api.open-meteo.com')
    expect(url.searchParams.get('latitude')).toBe('6.012')
    expect(url.searchParams.get('timezone')).toBe('Asia/Colombo')
    expect(url.searchParams.get('daily')).toContain('precipitation_sum')
  })

  it('classifies days from the reported values only', () => {
    expect(weatherCondition({ code: 95 })).toBe('STORM')
    expect(weatherCondition({ code: 3, rainMm: 4 })).toBe('RAIN')
    expect(weatherCondition({ code: 1, rainMm: 0, windKmh: 35 })).toBe('WINDY')
    expect(weatherCondition({ code: 2, rainMm: 0, windKmh: 10 })).toBe('CLOUDY')
    expect(weatherCondition({ code: 0, rainMm: 0, windKmh: 10 })).toBe('SUNNY')
  })

  it('parses the daily response and keeps missing values null', () => {
    const days = parseForecast({ daily: { time: ['2026-10-16', '2026-10-17'], weather_code: [61, 0], precipitation_sum: [12.4, null], precipitation_probability_max: [90, 5], wind_speed_10m_max: [18, 12], wind_direction_10m_dominant: [225, 90], temperature_2m_max: [29, 31] } })
    expect(days.get('2026-10-16')).toMatchObject({ condition: 'RAIN', rainMm: 12.4, windFromDeg: 225 })
    expect(days.get('2026-10-17')).toMatchObject({ condition: 'SUNNY', rainMm: null })
    const feature = forecastFeature(days.get('2026-10-16'), { longitude: 80.5, latitude: 6.1, spanDeg: 0.6 })
    expect(feature.properties).toMatchObject({ windTowardDeg: 45, spanDeg: 0.6, hasRain: true, hasWind: true })
    expect(feature.properties.windSpeed).toBeCloseTo(5, 5)
    expect(feature.properties.label).toBe('Rainy · Rain 12.4 mm · Wind from SW 18 km/h')
  })
})

describe('district weather: several points inside the district, mean with range', async () => {
  const { districtSamplePoints, forecastUrl: url, parseForecast: parse } = await import('../adapters/weatherForecast')
  const { isPointInsideDistrictFeature } = await import('../adapters/districtGeometry')
  // An L-shaped district: its bounding-box centre (80.5, 6.5) is OUTSIDE it.
  const district = { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[80, 6], [81, 6], [81, 6.4], [80.4, 6.4], [80.4, 7], [80, 7], [80, 6]]] } }

  it('samples only points inside the polygon and sends all of them in one request', () => {
    const points = districtSamplePoints(district)
    expect(points.length).toBeGreaterThan(1)
    expect(points.length).toBeLessThanOrEqual(6)
    expect(points.every((p) => isPointInsideDistrictFeature(p, district))).toBe(true)
    const params = new URL(url({ points })).searchParams
    expect(params.get('latitude').split(',')).toHaveLength(points.length)
    expect(params.get('daily')).toMatch(/relative_humidity_2m_mean/)
    expect(params.get('daily')).toMatch(/temperature_2m_min/)
  })

  it('aggregates an Open-Meteo multi-location array: mean, min-max range, circular wind mean, nulls kept', () => {
    const loc = (rain, wind, dir, tmax, tmin, rh, code) => ({ daily: { time: ['2026-10-16'], precipitation_sum: [rain], wind_speed_10m_max: [wind], wind_direction_10m_dominant: [dir], temperature_2m_max: [tmax], temperature_2m_min: [tmin], relative_humidity_2m_mean: [rh], weather_code: [code], precipitation_probability_max: [80] } })
    const day = parse([loc(11.7, 10, 350, 30, 23, 90, 95), loc(20.7, 10, 10, 29, 24, 88, 95), loc(null, 10, null, 31, 22, null, 61)]).get('2026-10-16')
    expect(day.pointCount).toBe(3)
    expect(day.rainMm).toBeCloseTo(16.2, 6) // mean of the two points that reported rain
    expect([day.rainMinMm, day.rainMaxMm]).toEqual([11.7, 20.7])
    expect(day.tempMax).toBeCloseTo(30, 6)
    expect(day.tempMin).toBeCloseTo(23, 6)
    expect(day.humidityPct).toBeCloseTo(89, 6)
    expect(Math.min(day.windFromDeg, 360 - day.windFromDeg)).toBeLessThan(0.001) // 350 and 10 -> north, not 180
    expect(day.code).toBe(95)
    expect(day.stormPoints).toBe(2)
    const empty = parse([{ daily: { time: ['2026-10-17'], precipitation_sum: [null] } }]).get('2026-10-17')
    expect(empty).toMatchObject({ rainMm: null, humidityPct: null, windFromDeg: null })
  })
})

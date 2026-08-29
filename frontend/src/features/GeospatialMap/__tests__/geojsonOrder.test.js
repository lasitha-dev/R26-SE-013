import { describe, expect, it } from 'vitest'
import { computeBounds, lonLatFromFeature, project } from '../components/mapProjection'

// Real, well-known coordinates (Bangkok, Thailand) -- |longitude| > 90,
// so a lat/lon reversal is structurally detectable: a "latitude" of
// 100.5 is out of the valid [-90, 90] range.
const BANGKOK_LON = 100.523186
const BANGKOK_LAT = 13.756331

describe('11A-GEO-01: coordinates remain [longitude, latitude]', () => {
  it('lonLatFromFeature reads coordinates[0] as longitude, coordinates[1] as latitude, never reversed', () => {
    const feature = { geometry: { type: 'Point', coordinates: [BANGKOK_LON, BANGKOK_LAT] } }
    const [lon, lat] = lonLatFromFeature(feature)
    expect(lon).toBe(BANGKOK_LON)
    expect(lat).toBe(BANGKOK_LAT)
    expect(Math.abs(lon)).toBeGreaterThan(90) // would be an invalid latitude if reversed
    expect(Math.abs(lat)).toBeLessThanOrEqual(90)
  })

  it('projection uses longitude for the x-bounds and latitude for the y-bounds', () => {
    const points = [
      [BANGKOK_LON, BANGKOK_LAT],
      [BANGKOK_LON + 1, BANGKOK_LAT + 1],
    ]
    const bounds = computeBounds(points)
    expect(bounds.minLon).toBe(BANGKOK_LON)
    expect(bounds.minLat).toBe(BANGKOK_LAT)
    const [x, y] = project(BANGKOK_LON, BANGKOK_LAT, bounds, 640, 480, 24)
    expect(x).toBeCloseTo(24, 6) // at minLon -> left padding edge
    expect(y).toBeCloseTo(480 - 24, 6) // at minLat -> bottom padding edge (y flipped for screen space)
  })
})

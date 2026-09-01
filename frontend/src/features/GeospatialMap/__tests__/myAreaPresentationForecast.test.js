import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import {
  advanceAreaForecastIndex,
  AREA_DISTRICT_RISK_LEVELS,
  AREA_FORECAST_DATES,
  AREA_FORECAST_OUTLOOK,
  areaDistanceKm,
  areaInfluenceStatus,
  buildMyAreaPresentationForecast,
  classifyAreaRiskOverlap,
  MAX_PRESENTATION_ANCHORS,
} from '../adapters/myAreaPresentationForecast'

const MATARA = {
  type: 'Feature',
  properties: { shapeName: 'Matara District' },
  geometry: { type: 'Polygon', coordinates: [[[80.4, 5.8], [80.8, 5.8], [80.8, 6.2], [80.4, 6.2], [80.4, 5.8]]] },
}

function realCase(caseId, coordinates, overrides = {}) {
  return {
    type: 'Feature',
    id: caseId,
    geometry: { type: 'Point', coordinates },
    properties: { caseId, disease: 'LSD', locationDistrict: 'Matara', ...overrides },
  }
}

const CASE_A = realCase('REAL-CASE-A', [80.53, 5.96])
const CASE_B = realCase('REAL-CASE-B', [80.58, 5.99])

describe('Page-2 Matara presentation generator', () => {
  it('defines exactly Sep 01 through Sep 14 2026 and one matching chart risk value per frame', () => {
    expect(AREA_FORECAST_DATES).toHaveLength(14)
    expect(AREA_FORECAST_DATES[0]).toBe('2026-09-01')
    expect(AREA_FORECAST_DATES[13]).toBe('2026-09-14')
    expect(AREA_FORECAST_OUTLOOK.map((frame) => frame.riskLevel)).toEqual(AREA_DISTRICT_RISK_LEVELS)
  })

  it('preserves every real confirmed anchor coordinate and creates one purple path/front per case', () => {
    const snapshot = buildMyAreaPresentationForecast([CASE_A, CASE_B], 6, MATARA)
    expect(snapshot.anchors.features.map((feature) => feature.geometry.coordinates)).toEqual([CASE_A.geometry.coordinates, CASE_B.geometry.coordinates])
    expect(snapshot.paths.features).toHaveLength(2)
    expect(snapshot.fronts.features).toHaveLength(2)
    expect(snapshot.paths.features.map((feature) => feature.properties.caseId)).toEqual(['REAL-CASE-A', 'REAL-CASE-B'])
  })

  it('stays capped at exactly two primary purple paths even when more real Matara cases are loaded', () => {
    expect(MAX_PRESENTATION_ANCHORS).toBe(2)
    const third = realCase('NEW-REAL-CASE', [80.62, 6.01])
    const snapshot = buildMyAreaPresentationForecast([CASE_A, CASE_B, third], 4, MATARA)
    expect(snapshot.anchorCount).toBe(2)
    expect(snapshot.anchors.features).toHaveLength(2)
    expect(snapshot.paths.features).toHaveLength(2)
    expect(snapshot.fronts.features).toHaveLength(2)
    // Deterministic identity-sorted selection, not the fetch/array order.
    expect(snapshot.anchors.features.map((feature) => feature.properties.caseId)).toEqual(['NEW-REAL-CASE', 'REAL-CASE-A'])
  })

  it('moves projected fronts and changes directional risk geometry with activeIndex while red anchors remain fixed', () => {
    const early = buildMyAreaPresentationForecast([CASE_A, CASE_B], 0, MATARA)
    const later = buildMyAreaPresentationForecast([CASE_A, CASE_B], 9, MATARA)
    expect(early.fronts.features[0].geometry.coordinates).not.toEqual(later.fronts.features[0].geometry.coordinates)
    expect(early.riskZones.features[0].geometry.coordinates).not.toEqual(later.riskZones.features[0].geometry.coordinates)
    expect(early.anchors.features[0].geometry.coordinates).toEqual(later.anchors.features[0].geometry.coordinates)
  })

  it('generates valid closed [lng, lat] ellipse rings with explicit qualitative riskLevel properties', () => {
    const snapshot = buildMyAreaPresentationForecast([CASE_A, CASE_B], 8, MATARA)
    const levels = new Set(snapshot.riskZones.features.map((feature) => feature.properties.riskLevel))
    expect(levels).toEqual(new Set(['green', 'yellow', 'orange', 'red']))
    for (const feature of snapshot.riskZones.features) {
      const ring = feature.geometry.coordinates[0]
      expect(ring.length).toBe(65)
      expect(ring[0]).toEqual(ring.at(-1))
      expect(ring.every(([longitude, latitude]) => Number.isFinite(longitude) && Number.isFinite(latitude) && Math.abs(longitude) <= 180 && Math.abs(latitude) <= 90)).toBe(true)
    }
  })

  it('classifies explicit overlapping influence more severely during peak frames', () => {
    expect(classifyAreaRiskOverlap({ distanceKm: 3, combinedReachKm: 10, activeIndex: 1 })).toBeNull()
    expect(classifyAreaRiskOverlap({ distanceKm: 3, combinedReachKm: 10, activeIndex: 3 })).toBe('yellow')
    expect(classifyAreaRiskOverlap({ distanceKm: 3, combinedReachKm: 10, activeIndex: 8 })).toBe('red')
    expect(classifyAreaRiskOverlap({ distanceKm: 30, combinedReachKm: 10, activeIndex: 8 })).toBeNull()
  })

  it('uses a rise-peak-stabilize district-risk story and date-aware influence states', () => {
    expect(AREA_DISTRICT_RISK_LEVELS).toEqual(['low', 'low', 'moderate', 'moderate', 'elevated', 'elevated', 'high', 'high', 'high', 'high', 'elevated', 'elevated', 'moderate', 'moderate'])
    expect(areaInfluenceStatus(0)).toBe('APPROACHING AREA')
    expect(areaInfluenceStatus(5)).toBe('PROJECTED PATH APPROACHING')
    expect(areaInfluenceStatus(9, true)).toBe('OVERLAPPING AREA INFLUENCE')
    expect(areaInfluenceStatus(13)).toBe('PROJECTED IMPACT STABILIZING')
  })

  it('stops on Sep 14 without resetting or looping', () => {
    expect(advanceAreaForecastIndex(12)).toEqual({ index: 13, complete: true })
    expect(advanceAreaForecastIndex(13)).toEqual({ index: 13, complete: true })
  })

  it('contains no backend request primitive or random generator', () => {
    const root = join(dirname(fileURLToPath(import.meta.url)), '..')
    const source = readFileSync(join(root, 'adapters', 'myAreaPresentationForecast.js'), 'utf8')
    expect(source).not.toContain('fetch(')
    expect(source).not.toContain('axios')
    expect(source).not.toContain('Math.random')
  })

  it('keeps each local risk field compact -- never spans the whole district', () => {
    const snapshot = buildMyAreaPresentationForecast([CASE_A, CASE_B], 13, MATARA)
    for (const feature of snapshot.riskZones.features) {
      const ring = feature.geometry.coordinates[0]
      const center = [
        ring.reduce((sum, [lng]) => sum + lng, 0) / ring.length,
        ring.reduce((sum, [, lat]) => sum + lat, 0) / ring.length,
      ]
      const maxRadiusKm = Math.max(...ring.map((point) => areaDistanceKm(center, point)))
      expect(maxRadiusKm).toBeLessThan(20)
    }
  })

  it("changes each case's own risk field independently across the timeline", () => {
    const early = buildMyAreaPresentationForecast([CASE_A, CASE_B], 1, MATARA)
    const late = buildMyAreaPresentationForecast([CASE_A, CASE_B], 9, MATARA)
    const nonOverlapFieldFor = (snapshot, anchorId) => snapshot.riskZones.features.filter((f) => f.properties.anchorId === anchorId && !f.properties.overlap)
    for (const anchorId of ['REAL-CASE-A', 'REAL-CASE-B']) {
      expect(nonOverlapFieldFor(early, anchorId).map((f) => f.properties.fillOpacity)).not.toEqual(nonOverlapFieldFor(late, anchorId).map((f) => f.properties.fillOpacity))
      expect(nonOverlapFieldFor(early, anchorId).map((f) => f.geometry.coordinates)).not.toEqual(nonOverlapFieldFor(late, anchorId).map((f) => f.geometry.coordinates))
    }
  })

  it('keeps an overlap patch local rather than district-wide', () => {
    const closeCaseB = realCase('REAL-CASE-B', [80.535, 5.965])
    const snapshot = buildMyAreaPresentationForecast([CASE_A, closeCaseB], 8, MATARA)
    const overlapFeatures = snapshot.riskZones.features.filter((f) => f.properties.overlap)
    expect(overlapFeatures.length).toBeGreaterThan(0)
    for (const feature of overlapFeatures) {
      const ring = feature.geometry.coordinates[0]
      const center = ring[0]
      const maxRadiusKm = Math.max(...ring.map((point) => areaDistanceKm(center, point)))
      expect(maxRadiusKm).toBeLessThan(10)
    }
  })

  it('creates exactly one purple front per anchor, never a duplicate marker', () => {
    const snapshot = buildMyAreaPresentationForecast([CASE_A, CASE_B], 12, MATARA)
    expect(snapshot.fronts.features).toHaveLength(snapshot.anchors.features.length)
    const ids = snapshot.fronts.features.map((feature) => feature.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})

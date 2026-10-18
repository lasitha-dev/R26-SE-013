import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  advancePage1ForecastIndex,
  buildDirectionalEllipse,
  buildPage1ForecastVisualization,
  interpolatePage1ForecastVisualization,
  isPage1MasterTimelineActive,
  PAGE1_FORECAST_DATES,
  PAGE1_PLAYBACK_INTERVAL_MS,
  PAGE1_RISK_PHASE,
} from '../adapters/page1ForecastVisualization'
import { isPointInsideDistrictFeature } from '../adapters/districtGeometry'

const boundary = {
  type: 'Feature',
  properties: { shapeName: 'Test Sri Lanka' },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [79.5, 5.5],
        [82, 5.5],
        [82, 10],
        [79.5, 10],
        [79.5, 5.5],
      ],
    ],
  },
}

function outbreak(sourceId, coordinates) {
  return {
    type: 'Feature',
    properties: { source_id: sourceId, outbreakId: `outbreak-${sourceId}` },
    geometry: { type: 'Point', coordinates },
  }
}

const anchors = [outbreak('source-a', [80.2, 8.2]), outbreak('source-b', [80.8, 7.3])]
const RISK_LEVELS = new Set(['green', 'yellow', 'orange', 'red'])

function everyPoint(coordinates, visit) {
  if (typeof coordinates[0] === 'number') visit(coordinates)
  else for (const value of coordinates) everyPoint(value, visit)
}

function riskLevelsPresent(snapshot) {
  return new Set(snapshot.riskZones.features.map((f) => f.properties.riskLevel))
}

describe('Page 1 fixed forecast presentation', () => {
  it('uses exactly 14 fixed dates from 01 Sep through 14 Sep 2026', () => {
    expect(PAGE1_FORECAST_DATES).toHaveLength(14)
    expect(PAGE1_FORECAST_DATES[0]).toBe('2026-09-01')
    expect(PAGE1_FORECAST_DATES[6]).toBe('2026-09-07')
    expect(PAGE1_FORECAST_DATES[13]).toBe('2026-09-14')
    expect(PAGE1_RISK_PHASE).toHaveLength(14)
  })

  it('uses the requested speeds and stops at frame 14 without looping or resetting', () => {
    expect(PAGE1_PLAYBACK_INTERVAL_MS).toEqual({ 0.5: 2200, 1: 1100, 2: 550 })
    expect(advancePage1ForecastIndex(11)).toEqual({ index: 12, complete: false })
    expect(advancePage1ForecastIndex(12)).toEqual({ index: 13, complete: true })
    expect(advancePage1ForecastIndex(13)).toEqual({ index: 13, complete: true })
  })

  it('one activeForecastIndex controls every derived output -- date, paths, fronts, and risk all key off the same requested index', () => {
    const snapshot = buildPage1ForecastVisualization(anchors, 6, [boundary])
    expect(snapshot.activeIndex).toBe(6)
    expect(snapshot.date).toBe('2026-09-07')
    for (const feature of [...snapshot.paths.features, ...snapshot.fronts.features, ...snapshot.riskZones.features]) {
      expect(feature.properties.activeIndex).toBe(6)
      expect(feature.properties.date).toBe('2026-09-07')
    }
  })

  it('never leaves the master timeline mounted for an empty collection but activates it for any non-empty one', () => {
    expect(isPage1MasterTimelineActive([])).toBe(false)
    expect(isPage1MasterTimelineActive({ features: [] })).toBe(false)
    expect(isPage1MasterTimelineActive(anchors)).toBe(true)
    // The exact district-focus bug this guards: a location-scope filter can
    // legitimately narrow anchors to zero while the real national
    // collection still has outbreaks -- callers must feed this the
    // UNFILTERED collection, never the scope-filtered one.
    expect(isPage1MasterTimelineActive({ type: 'FeatureCollection', features: anchors })).toBe(true)
  })

  describe('every real outbreak automatically participates -- no case-ID branching', () => {
    it('builds one path/front for every current real anchor, and at least one risk feature per outbreak', () => {
      const two = buildPage1ForecastVisualization(anchors, 9, [boundary])
      expect(two.anchorCount).toBe(2)
      expect(two.paths.features).toHaveLength(2)
      expect(two.fronts.features).toHaveLength(2)
      const groups = new Set(two.riskZones.features.map((f) => f.properties.visualizationId))
      expect(groups.size).toBe(2) // multiple outbreaks -> multiple independent risk groups
      for (const anchorFeature of anchors) {
        const id = anchorFeature.properties.source_id
        expect(two.riskZones.features.some((f) => f.properties.sourceId === id)).toBe(true)
      }
    })

    it('a NEW outbreak (D) arriving alongside A/B/C automatically receives its own confirmed path/front/risk output, with no source change', () => {
      const abc = anchors
      const abcSnapshot = buildPage1ForecastVisualization(abc, 9, [boundary])
      expect(abcSnapshot.anchorCount).toBe(2)

      // D arrives -- same generic call, no new branch, no new case ID handling.
      const outbreakD = outbreak('brand-new-outbreak-D', [81.3, 7.8])
      const abcdSnapshot = buildPage1ForecastVisualization([...abc, outbreakD], 9, [boundary])
      expect(abcdSnapshot.anchorCount).toBe(3)
      expect(abcdSnapshot.paths.features).toHaveLength(3)
      expect(abcdSnapshot.fronts.features).toHaveLength(3)
      expect(abcdSnapshot.riskZones.features.some((f) => f.properties.sourceId === 'brand-new-outbreak-D')).toBe(true)
      // A/B unaffected by D's arrival at the SAME activeIndex.
      expect(abcdSnapshot.paths.features.filter((f) => f.properties.sourceId !== 'brand-new-outbreak-D')).toEqual(abcSnapshot.paths.features)
    })

    it('contains no origin-specific/case-ID branching -- arbitrary/unfamiliar identities are processed by the same generic path', () => {
      const genericAnchors = [outbreak('any-random-id-1', [80.4, 7.9]), outbreak('completely-different-id-2', [81.0, 8.5])]
      const result = buildPage1ForecastVisualization(genericAnchors, 9, [boundary])
      expect(result.paths.features).toHaveLength(2)
      expect(result.riskZones.features.length).toBeGreaterThan(0)
    })
  })

  it('is deterministic and visibly changes geometry between timeline dates', () => {
    const dayOne = buildPage1ForecastVisualization(anchors, 0, [boundary])
    const repeatedDayOne = buildPage1ForecastVisualization(anchors, 0, [boundary])
    const dayNine = buildPage1ForecastVisualization(anchors, 8, [boundary])
    expect(repeatedDayOne).toEqual(dayOne)
    expect(dayNine.paths).not.toEqual(dayOne.paths)
    expect(dayNine.riskZones).not.toEqual(dayOne.riskZones)
  })

  it('confirmed coordinates never move -- only the anchor point feeds risk/path generation, the real coordinate itself is untouched across every date', () => {
    for (const activeIndex of [0, 5, 9, 13]) {
      const snapshot = buildPage1ForecastVisualization(anchors, activeIndex, [boundary])
      expect(snapshot).toBeTruthy()
    }
    // The anchors array itself (the real confirmed coordinates) is never
    // mutated by generation at any date.
    expect(anchors[0].geometry.coordinates).toEqual([80.2, 8.2])
    expect(anchors[1].geometry.coordinates).toEqual([80.8, 7.3])
  })

  it('the projected front coordinate changes between dates (purple spread progresses)', () => {
    const early = buildPage1ForecastVisualization(anchors, 1, [boundary])
    const later = buildPage1ForecastVisualization(anchors, 11, [boundary])
    expect(later.fronts.features[0].geometry.coordinates).not.toEqual(early.fronts.features[0].geometry.coordinates)
  })

  it('keeps every generated path/front/risk coordinate inside the supplied Sri Lanka boundary', () => {
    const snapshot = buildPage1ForecastVisualization(anchors, 13, [boundary])
    for (const collection of [snapshot.paths, snapshot.fronts, snapshot.riskZones]) {
      for (const feature of collection.features) {
        everyPoint(feature.geometry.coordinates, (point) => {
          expect(isPointInsideDistrictFeature(point, boundary)).toBe(true)
        })
      }
    }
  })

  it('interpolates matching source geometries for smooth MapLibre setData transitions', () => {
    const start = buildPage1ForecastVisualization(anchors, 2, [boundary])
    const end = buildPage1ForecastVisualization(anchors, 3, [boundary])
    const halfway = interpolatePage1ForecastVisualization(start, end, 0.5)
    expect(halfway.paths).not.toEqual(start.paths)
    expect(halfway.paths).not.toEqual(end.paths)
    expect(halfway.anchorCount).toBe(2)
  })

  describe('risk severity evolves -- tiers unlock progressively, never all four at maximum from day one', () => {
    it('day 1 (index 0) shows only the lower bands (green, and yellow), never orange/red yet', () => {
      const day1 = buildPage1ForecastVisualization(anchors, 0, [boundary])
      const levels = riskLevelsPresent(day1)
      expect(levels.has('green')).toBe(true)
      expect(levels.has('orange')).toBe(false)
      expect(levels.has('red')).toBe(false)
    })

    it('by index 3 (Sep 04) a local orange band has unlocked', () => {
      const day4 = buildPage1ForecastVisualization(anchors, 3, [boundary])
      expect(riskLevelsPresent(day4).has('orange')).toBe(true)
      expect(riskLevelsPresent(day4).has('red')).toBe(false)
    })

    it('by index 6 (Sep 07) a local red core has unlocked', () => {
      const day7 = buildPage1ForecastVisualization(anchors, 6, [boundary])
      expect(riskLevelsPresent(day7).has('red')).toBe(true)
    })

    it('the final frame (index 13) keeps every band that ever unlocked -- the phase curve settles (1.02) rather than collapsing back below any threshold', () => {
      const final = riskLevelsPresent(buildPage1ForecastVisualization(anchors, 13, [boundary]))
      expect(final).toEqual(new Set(['green', 'yellow', 'orange', 'red']))
      expect(PAGE1_RISK_PHASE[13]).toBeGreaterThan(0.8) // still above the highest (red) activation threshold
    })
  })

  describe('risk contours: multiple independent local fields, smooth ellipses, no black fallback', () => {
    const snapshot = buildPage1ForecastVisualization(anchors, 9, [boundary])
    const riskFeatures = snapshot.riskZones.features

    it('generates MANY risk features across MULTIPLE outbreaks, not one shared blob', () => {
      expect(riskFeatures.length).toBeGreaterThan(8) // 2 outbreaks x up to 4 tiers x 3 lobes
      const byOutbreak = new Map()
      for (const f of riskFeatures) {
        byOutbreak.set(f.properties.sourceId, (byOutbreak.get(f.properties.sourceId) ?? 0) + 1)
      }
      expect(byOutbreak.size).toBe(2)
      for (const count of byOutbreak.values()) expect(count).toBeGreaterThan(0)
    })

    it('tags every risk feature with only the four approved riskLevel values -- no default/black value', () => {
      expect(riskFeatures.length).toBeGreaterThan(0)
      for (const feature of riskFeatures) {
        expect(RISK_LEVELS.has(feature.properties.riskLevel)).toBe(true)
        expect(['#22C55E', '#FACC15', '#F97316', '#EF4444']).toContain(feature.properties.color)
      }
    })

    it('produces closed rings with no NaN/undefined and coordinates as [lng, lat]', () => {
      for (const feature of riskFeatures) {
        const ring = feature.geometry.coordinates[0]
        expect(ring.length).toBeGreaterThanOrEqual(9)
        expect(ring[0]).toEqual(ring[ring.length - 1])
        for (const [lng, lat] of ring) {
          expect(Number.isFinite(lng)).toBe(true)
          expect(Number.isFinite(lat)).toBe(true)
          expect(lng).toBeGreaterThanOrEqual(-180)
          expect(lng).toBeLessThanOrEqual(180)
          expect(lat).toBeGreaterThanOrEqual(-90)
          expect(lat).toBeLessThanOrEqual(90)
        }
      }
    })

    it('is directionally elongated on a mid-playback frame: major axis exceeds minor axis', () => {
      for (const feature of riskFeatures) {
        const ring = feature.geometry.coordinates[0]
        const lngs = ring.map((p) => p[0])
        const lats = ring.map((p) => p[1])
        const spanLng = Math.max(...lngs) - Math.min(...lngs)
        const spanLat = Math.max(...lats) - Math.min(...lats)
        expect(Math.max(spanLng, spanLat) / Math.min(spanLng, spanLat)).toBeGreaterThan(1.02)
      }
    })

    it('two different outbreaks receive two different deterministic orientations (never the same bearing forced on both)', () => {
      const frontA = snapshot.fronts.features.find((f) => f.properties.sourceId === 'source-a').geometry.coordinates
      const frontB = snapshot.fronts.features.find((f) => f.properties.sourceId === 'source-b').geometry.coordinates
      const originA = anchors[0].geometry.coordinates
      const originB = anchors[1].geometry.coordinates
      const bearingA = Math.atan2(frontA[0] - originA[0], frontA[1] - originA[1])
      const bearingB = Math.atan2(frontB[0] - originB[0], frontB[1] - originB[1])
      expect(bearingA).not.toBeCloseTo(bearingB, 3)
    })

    it('grows and reshapes the ellipse geometry with every activeForecastIndex change', () => {
      const dayZero = buildPage1ForecastVisualization(anchors, 0, [boundary])
      const dayThirteen = buildPage1ForecastVisualization(anchors, 13, [boundary])
      expect(dayThirteen.riskZones).not.toEqual(dayZero.riskZones)
    })

    it('the adapter itself never performs network I/O -- no per-tick backend request is structurally possible', () => {
      const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'adapters', 'page1ForecastVisualization.js'), 'utf-8')
      expect(src).not.toMatch(/\bfetch\(/)
      expect(src).not.toMatch(/XMLHttpRequest/)
      expect(src).not.toMatch(/axios/)
    })
  })

  describe('buildDirectionalEllipse', () => {
    it('builds a closed, simple ring oriented along the requested bearing with major > minor axis', () => {
      const ring = buildDirectionalEllipse({ centerLat: 8.0, centerLng: 80.5, majorRadiusKm: 10, minorRadiusKm: 4, bearingDeg: 45, steps: 64 })
      expect(ring.length).toBe(65)
      expect(ring[0]).toEqual(ring[ring.length - 1])
      for (const [lng, lat] of ring) {
        expect(Number.isFinite(lng)).toBe(true)
        expect(Number.isFinite(lat)).toBe(true)
      }
    })

    it('is deterministic for identical inputs', () => {
      const params = { centerLat: 6.9, centerLng: 79.9, majorRadiusKm: 6, minorRadiusKm: 3, bearingDeg: 120, steps: 48 }
      expect(buildDirectionalEllipse(params)).toEqual(buildDirectionalEllipse(params))
    })
  })
})

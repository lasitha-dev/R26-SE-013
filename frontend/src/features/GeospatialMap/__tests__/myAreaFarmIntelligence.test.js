import { describe, expect, it } from 'vitest'

import {
  buildFarmWatchlist,
  buildFollowUpItems,
  districtSnapshotSummary,
  pointInGeometry,
  tierAtPoint,
} from '../adapters/myAreaFarmIntelligence'

const square = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
const zone = (tier, label, coordinates, type = 'Polygon') => ({ type: 'Feature', properties: { tier, label }, geometry: { type, coordinates } })

// Fictional geometry only: two nested tier zones and a Day-3 reach envelope.
const TIMELINE = {
  as_of: '2026-10-14',
  risk_zones: {
    type: 'FeatureCollection',
    features: [
      zone('moderate', 'Moderate relative risk', [square(0, 0, 10, 10)]),
      zone('highest', 'Highest relative risk', [[square(4, 4, 6, 6)]], 'MultiPolygon'),
    ],
  },
  district_summaries: [{ district: 'Kandy', max_tier: 'highest', district_area_km2: 1932, scored_area_km2: 1300, n_sources_in_district: 2 }],
  frames: [
    { day: 0, reach_envelope: null },
    { day: 3, reach_envelope: { type: 'Polygon', coordinates: [square(3, 3, 7, 7)] } },
  ],
}

const farm = (farmId, lon, lat) => ({ farmId, longitude: lon, latitude: lat, locationStatus: lon == null ? 'LOCATION_REQUIRED' : 'VALID', locationDistrict: 'Kandy' })

describe('point-in-polygon on backend geometry', () => {
  it('handles Polygon, MultiPolygon, holes and Features', () => {
    expect(pointInGeometry(5, 5, { type: 'Polygon', coordinates: [square(0, 0, 10, 10)] })).toBe(true)
    expect(pointInGeometry(11, 5, { type: 'Polygon', coordinates: [square(0, 0, 10, 10)] })).toBe(false)
    expect(pointInGeometry(5, 5, { type: 'Polygon', coordinates: [square(0, 0, 10, 10), square(4, 4, 6, 6)] })).toBe(false)
    expect(pointInGeometry(5, 5, zone('x', 'x', [[square(4, 4, 6, 6)]], 'MultiPolygon'))).toBe(true)
    expect(pointInGeometry(5, 5, { type: 'Point', coordinates: [5, 5] })).toBe(false)
  })

  it('a point gets the highest backend tier containing it, or null outside every zone', () => {
    expect(tierAtPoint(TIMELINE, 5, 5)).toBe('highest')
    expect(tierAtPoint(TIMELINE, 1, 1)).toBe('moderate')
    expect(tierAtPoint(TIMELINE, 20, 20)).toBeNull()
  })
})

describe('district snapshot summary', () => {
  it('reads the backend district summary and its tier label, case-insensitively', () => {
    const s = districtSnapshotSummary(TIMELINE, 'kandy')
    expect(s.maxTier).toBe('highest')
    expect(s.maxTierLabel).toBe('Highest relative risk')
    expect(s.asOf).toBe('2026-10-14')
  })

  it('returns null for another district instead of borrowing one', () => {
    expect(districtSnapshotSummary(TIMELINE, 'Galle')).toBeNull()
  })
})

describe('farm watchlist', () => {
  const farms = [farm('F-out', 20, 20), farm('F-mod', 1, 1), farm('F-high', 5, 5), farm('F-nogps', null, null), farm('F-case', 1.5, 1.5)]
  const clinicalContexts = [{ caseId: 'C1', farmId: 'F-case', disease: 'LSD', verificationTime: '2026-10-14T04:17:46+00:00' }]
  const names = new Map([['F-case', { name: 'Case Farm' }]])

  it('orders verified cases first, then tier, and keeps no-GPS farms visible but unplaced', () => {
    const rows = buildFarmWatchlist({ farms, clinicalContexts, timeline: TIMELINE, frameIndex: 1, farmNames: names, disease: 'LSD' })
    expect(rows.map((r) => r.farmId)).toEqual(['F-case', 'F-high', 'F-mod', 'F-out', 'F-nogps'])
    expect(rows[0].name).toBe('Case Farm')
    expect(rows[0].cases).toEqual([{ caseId: 'C1', disease: 'LSD', verificationTime: '2026-10-14T04:17:46+00:00' }])
    const nogps = rows.find((r) => r.farmId === 'F-nogps')
    expect(nogps.hasGps).toBe(false)
    expect(nogps.tier).toBeNull()
  })

  it('reach membership follows only the selected frame’s envelope (none on Day 0)', () => {
    const day3 = buildFarmWatchlist({ farms, clinicalContexts, timeline: TIMELINE, frameIndex: 1, disease: 'LSD' })
    expect(day3.find((r) => r.farmId === 'F-high').withinReach).toBe(true)
    expect(day3.find((r) => r.farmId === 'F-mod').withinReach).toBe(false)
    const day0 = buildFarmWatchlist({ farms, clinicalContexts, timeline: TIMELINE, frameIndex: 0, disease: 'LSD' })
    expect(day0.some((r) => r.withinReach)).toBe(false)
  })

  it('without a renderable timeline, no tier is invented', () => {
    const rows = buildFarmWatchlist({ farms, clinicalContexts, timeline: null, disease: 'LSD' })
    expect(rows.every((r) => r.tier === null && r.withinReach === false)).toBe(true)
  })
})

describe('follow-up prompts', () => {
  it('are tied to on-screen facts and never issue control measures', () => {
    const rows = buildFarmWatchlist({
      farms: [farm('F-case', 1.5, 1.5), farm('F-high', 5, 5), farm('F-nogps', null, null)],
      clinicalContexts: [{ caseId: 'C1', farmId: 'F-case', disease: 'LSD', verificationTime: null }],
      timeline: TIMELINE,
      frameIndex: 1,
      disease: 'LSD',
    })
    const items = buildFollowUpItems({ watchlist: rows, diseaseShortLabel: 'LSD', districtLabel: 'Kandy' })
    const ids = items.map((i) => i.id)
    expect(ids).toEqual(['review-cases', 'check-nearby', 'monitor', 'gps', 'protocol'])
    const text = items.map((i) => i.text).join(' ').toLowerCase()
    for (const forbidden of ['quarantine', 'vaccinat', 'cull', 'movement ban', 'must ', 'probability']) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('with no evidence, only the procedural reminder remains', () => {
    expect(buildFollowUpItems({ watchlist: [], diseaseShortLabel: 'LSD' }).map((i) => i.id)).toEqual(['protocol'])
  })
})

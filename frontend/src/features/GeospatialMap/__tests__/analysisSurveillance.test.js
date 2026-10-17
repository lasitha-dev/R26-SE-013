// Analysis & Trends adapters over FICTIONAL case records and three FICTIONAL
// square districts. "Today" is fixed at 17 Oct 2026 (Asia/Colombo).
import { describe, expect, it } from 'vitest'

import {
  buildAffectedAreas, buildClusterRows, buildDailyActivity, distanceToDistrictKm, forecastHorizon, prepareRecords, recordDistrict,
  scopeRecords, summarizeWindow, windowKeys,
} from '../adapters/analysisSurveillance'

const NOW = Date.parse('2026-10-17T06:00:00Z')
const box = (name, w, s, size = 0.3) => ({ type: 'Feature', properties: { shapeName: `${name} District` }, geometry: { type: 'Polygon', coordinates: [[[w, s], [w + size, s], [w + size, s + size], [w, s + size], [w, s]]] } })
const TESTSHIRE = box('Testshire', 80.0, 6.0)
const OTHERLAND = box('Otherland', 80.3, 6.0) // shares Testshire's east edge
const FARLAND = box('Farland', 81.5, 7.5)
const DISTRICTS = { type: 'FeatureCollection', features: [TESTSHIRE, OTHERLAND, FARLAND] }

let n = 0
const rec = (day, { verified = true, lon = null, lat = null, district = null, disease = 'LSD' } = {}) => ({
  record_key: `R${(n += 1)}`, disease, verification_status: verified ? 'VERIFIED' : 'PENDING_VERIFICATION',
  reported_at: `2026-${day}T03:00:00+00:00`, district,
  latitude: lat, longitude: lon, location_status: lon !== null ? 'VALID' : 'LOCATION_REQUIRED',
})
const RECORDS = [
  rec('10-17', { lon: 80.1, lat: 6.1 }), rec('10-17', { lon: 80.1, lat: 6.1, verified: false }), // same farm twice
  rec('10-12', { lon: 80.2, lat: 6.2, district: 'Otherland' }), // GPS says Testshire
  rec('10-05', { district: 'Testshire' }), // no GPS: registered district
  rec('09-25', { lon: 80.15, lat: 6.15 }), // previous window
  rec('10-16', { lon: 80.35, lat: 6.1 }), rec('10-15', { lon: 80.4, lat: 6.2, verified: false }), // Otherland
  rec('10-14', { lon: 81.6, lat: 7.6 }), // Farland, far away
  rec('10-10', { lon: 80.1, lat: 6.1, disease: 'FMD' }),
]
const prepared = prepareRecords(RECORDS, 'LSD', DISTRICTS)

describe('records, districts and windows', () => {
  it('a record district is its GPS polygon, else its registered district; other diseases are left out', () => {
    expect(recordDistrict(RECORDS[2], DISTRICTS)).toBe('Testshire')
    expect(recordDistrict(RECORDS[3], DISTRICTS)).toBe('Testshire')
    expect(prepared).toHaveLength(8)
  })

  it('14-day window ending today, and the 14 days before it', () => {
    expect(windowKeys(14, NOW)).toMatchObject({ endKey: '2026-10-17', startKey: '2026-10-04', previousEndKey: '2026-10-03', previousStartKey: '2026-09-20' })
  })

  it('district scope: current records, verified/pending, farm locations, previous window', () => {
    const scoped = scopeRecords(prepared, { scope: 'district', districtName: 'Testshire' })
    expect(summarizeWindow(scoped, { windowDays: 14, nowMs: NOW, scope: 'district' })).toMatchObject({
      current: 4, verified: 3, pending: 1, previous: 1, affectedAreas: 2, withoutGps: 1, allDates: 5, latestReportKey: '2026-10-17',
    })
  })

  it('national scope: distinct districts with a current record', () => {
    expect(summarizeWindow(prepared, { windowDays: 14, nowMs: NOW, scope: 'national' })).toMatchObject({ current: 7, affectedAreas: 3 })
  })

  it('daily activity stacks verified and pending per day, zero days included', () => {
    const days = buildDailyActivity(scopeRecords(prepared, { scope: 'district', districtName: 'Testshire' }), { windowDays: 7, nowMs: NOW })
    expect(days).toHaveLength(7)
    expect(days[6]).toEqual({ date: '2026-10-17', verified: 1, pending: 1 })
    expect(days[3]).toEqual({ date: '2026-10-14', verified: 0, pending: 0 })
  })

  it('an unresolved district never falls back to national data', () => {
    expect(scopeRecords(prepared, { scope: 'district', districtName: null })).toEqual([])
  })
})

describe('most affected areas', () => {
  it('national: ranked by current records with the change vs the previous window, MY flagged', () => {
    const rows = buildAffectedAreas(prepared, { windowDays: 14, nowMs: NOW, scope: 'national', districtName: 'Testshire' })
    expect(rows.map((r) => [r.district, r.records, r.verified, r.pending, r.previous, r.delta, r.mine])).toEqual([
      ['Testshire', 4, 3, 1, 1, 3, true], ['Otherland', 2, 1, 1, 0, 2, false], ['Farland', 1, 1, 0, 0, 1, false],
    ])
    expect(rows[0].lastObserved).toBe('2026-10-17')
  })

  it('district scope: my district plus nearby districts within the model range; far ones left out', () => {
    const rows = buildAffectedAreas(prepared, { windowDays: 14, nowMs: NOW, scope: 'district', districtName: 'Testshire', districtFeature: TESTSHIRE, nearbyKm: 46.3 })
    expect(rows.map((r) => r.district)).toEqual(['Testshire', 'Otherland'])
    expect(rows[1].nearestKm).toBeGreaterThan(0)
    expect(rows[1].nearestKm).toBeLessThan(46.3)
  })

  it('the vet district is always shown, even with no current record', () => {
    const rows = buildAffectedAreas(prepared, { windowDays: 14, nowMs: NOW, scope: 'national', districtName: 'Quietshire' })
    expect(rows.find((r) => r.mine)).toMatchObject({ district: 'Quietshire', records: 0, delta: 0 })
  })

  it('distance to a district: 0 inside, km outside', () => {
    expect(distanceToDistrictKm(TESTSHIRE, 80.1, 6.1)).toBe(0)
    expect(distanceToDistrictKm(TESTSHIRE, 80.35, 6.1)).toBeCloseTo(0.05 * 111.32 * Math.cos((6.1 * Math.PI) / 180), 0)
  })
})

describe('clusters and forecast horizon', () => {
  const ST = {
    clusters: [
      { cluster_id: 'small', member_count: 2, distinct_farm_or_support_count: 2, member_locations: [{ longitude: 81.6, latitude: 7.6 }, { longitude: 81.62, latitude: 7.61 }], radius_km: 1.2, drift: { supported: false }, start_date: '2026-10-10', end_date: '2026-10-10' },
      { cluster_id: 'big', member_count: 5, distinct_farm_or_support_count: 3, member_locations: [{ longitude: 80.25, latitude: 6.1 }, { longitude: 80.35, latitude: 6.12 }], radius_km: 9.4, drift: { supported: true, km: 6.2, bearing_deg: 111 }, start_date: '2026-10-08', end_date: '2026-10-15' },
    ],
  }
  it('C1 = largest, districts from member GPS, unsupported drift has no direction', () => {
    const rows = buildClusterRows(ST, { districtCollection: DISTRICTS, districtFeature: TESTSHIRE, scope: 'national' })
    expect(rows.map((r) => [r.label, r.cases, r.districts.join('+'), r.radiusKm, r.driftKm, r.bearingDeg])).toEqual([
      ['C1', 5, 'Otherland+Testshire', 9.4, 6.2, 111], ['C2', 2, 'Farland', 1.2, null, null],
    ])
  })
  it('district scope keeps only clusters with a member in the district', () => {
    expect(buildClusterRows(ST, { districtCollection: DISTRICTS, districtFeature: TESTSHIRE, scope: 'district' }).map((r) => r.label)).toEqual(['C1'])
    expect(buildClusterRows(ST, { districtCollection: DISTRICTS, districtFeature: FARLAND, scope: 'district' }).map((r) => r.label)).toEqual(['C2'])
  })
  it('forecast horizon comes from the backend timeline frames and sources', () => {
    const timeline = { status: 'OK', frames: [{ day: 0, date: '2026-10-17' }, { day: 14, date: '2026-10-31' }], sources: [{}, {}, {}], source_selection: { district_relevance_distance_km: 46.3 } }
    expect(forecastHorizon(timeline)).toEqual({ from: '2026-10-17', to: '2026-10-31', lastDay: 14, sources: 3, relevanceKm: 46.3 })
    expect(forecastHorizon({ status: 'MODEL_NOT_READY', frames: [{}] })).toBeNull()
  })
})

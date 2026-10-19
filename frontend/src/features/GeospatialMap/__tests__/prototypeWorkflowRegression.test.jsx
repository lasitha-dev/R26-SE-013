import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { buildNationalCaseView } from '../adapters/nationalCases'
import { clustersForDistrict, recordsForDistrict } from '../adapters/currentSurveillance'
import { monitoringZoneDetails } from '../adapters/myAreaIntelligence'
import { buildMyAreaTimelineView, directionGeometryInDomain } from '../adapters/spatialTimelineView'
import MyAreaIntelligencePanel from '../components/MyAreaIntelligencePanel'
import MyAreaOutbreaksInfluencing from '../components/MyAreaOutbreaksInfluencing'
import Era5Observations from '../components/Era5Observations'

afterEach(cleanup)

const polygon = (west, east) => ({ type: 'Polygon', coordinates: [[[west, 0], [east, 0], [east, 4], [west, 4], [west, 0]]] })
const land = { type: 'Feature', properties: {}, geometry: polygon(0, 4) }
const report = (id, date, district = 'Matara', extra = {}) => ({ record_key: `CASE:${id}`, disease: 'LSD', verification_status: 'VERIFIED', reported_at: `${date}T08:00:00Z`, verified_at: `${date}T09:00:00Z`, district, location_status: 'VALID', latitude: 6, longitude: 80.5, ...extra })

describe('Observed Cases use the same real reports as their timeline', () => {
  it('replays national records, including a different district, without moving any point', () => {
    const records = [report('a', '2026-08-29', 'Galle'), report('b', '2026-08-31')]
    const view = buildNationalCaseView(records, { disease: 'LSD', observedThrough: '2026-08-29', ageReferenceDateKey: '2026-09-01' })
    expect(view.replayDates).toEqual(['2026-08-29', '2026-08-31'])
    expect(view.counts.verified).toBe(1)
    expect(view.featureCollection.features).toHaveLength(1)
    expect(view.featureCollection.features[0].geometry.coordinates).toEqual([80.5, 6])
    expect(view.featureCollection.features[0].properties.recordKey).toBe('CASE:a')
  })

  it('includes real missing-GPS and pending dates without fabricating coordinates', () => {
    const records = [report('a', '2026-08-29'), report('b', '2026-08-30', 'Matara', { verification_status: 'PENDING_VERIFICATION', verified_at: null, location_status: 'LOCATION_REQUIRED', latitude: null, longitude: null })]
    const view = buildNationalCaseView(records, { disease: 'LSD', ageReferenceDateKey: '2026-08-30' })
    expect(view.replayDates).toEqual(['2026-08-29', '2026-08-30'])
    expect(view.counts.pending).toBe(1)
    expect(view.counts.withoutGps).toBe(1)
    expect(view.featureCollection.features).toHaveLength(1)
  })
})

describe('District analysis never borrows another district', () => {
  const records = [report('m', '2026-08-29'), report('c', '2026-08-30', 'Colombo'), report('g', '2026-08-31', 'Galle')]
  it('selects the authenticated district and returns a real empty result for a no-case district', () => {
    expect(recordsForDistrict(records, 'Matara District').map((r) => r.record_key)).toEqual(['CASE:m'])
    expect(recordsForDistrict(records, 'Colombo').map((r) => r.record_key)).toEqual(['CASE:c'])
    expect(recordsForDistrict(records, 'Kegalle')).toEqual([])
  })
  it('does not silently fall back to national records when the district is unresolved', () => {
    expect(recordsForDistrict(records, null)).toEqual([])
    expect(recordsForDistrict(records, 'ALL_DISTRICTS')).toEqual([])
  })
  it('uses the API member-location objects for district cluster membership', () => {
    const clusters = [
      { cluster_id: 'inside', member_locations: [{ longitude: 2, latitude: 1 }, { longitude: 8, latitude: 1 }] },
      { cluster_id: 'outside', member_locations: [{ longitude: 8, latitude: 1 }] },
      { cluster_id: 'missing', member_locations: [{ longitude: null, latitude: null }] },
    ]
    expect(clustersForDistrict(clusters, land).map((cluster) => cluster.cluster_id)).toEqual(['inside'])
    expect(clustersForDistrict(clusters, null)).toEqual([])
  })
})

describe('Direction stays on land; the UI never redirects an invalid route', () => {
  it('keeps a backend line on land and rejects an endpoint outside the domain', () => {
    expect(directionGeometryInDomain({ type: 'LineString', coordinates: [[1, 1], [3, 3]] }, land)).toBe(true)
    expect(directionGeometryInDomain({ type: 'LineString', coordinates: [[1, 1], [8, 3]] }, land)).toBe(false)
    expect(directionGeometryInDomain({ type: 'LineString', coordinates: [[1, 1], [3, 3]] }, null)).toBe(false)
  })
  it('rejects a sea crossing even when both endpoints lie on land', () => {
    const islands = { type: 'FeatureCollection', features: [0, 3].map((west) => ({ type: 'Feature', properties: {}, geometry: polygon(west, west + 1) })) }
    expect(directionGeometryInDomain({ type: 'LineString', coordinates: [[0.5, 1], [3.5, 1]] }, islands)).toBe(false)
  })
})

it('My Area keeps the as-of surface fixed and highlights only the backend selected-day intersection', () => {
  const staticGeometry = polygon(0, 4)
  const dayGeometry = polygon(0, 2)
  const zone = (geometry) => ({ type: 'Feature', properties: { tier: 'high', area_km2: 2 }, geometry })
  const timeline = { status: 'OK', as_of: '2026-08-30', sources: [], risk_zones: { type: 'FeatureCollection', features: [zone(staticGeometry)] }, frames: [{ day: 0, date: '2026-08-30', source_corridors: [], reach_limited_risk_zones: { type: 'FeatureCollection', features: [] } }, { day: 7, date: '2026-09-06', source_corridors: [], reach_limited_risk_zones: { type: 'FeatureCollection', features: [zone(dayGeometry)] } }] }
  const first = buildMyAreaTimelineView(timeline, 0, 'Matara')
  const seventh = buildMyAreaTimelineView(timeline, 1, 'Matara')
  expect(first.contextZones.features[0].geometry).toBe(staticGeometry)
  expect(seventh.contextZones.features[0].geometry).toBe(staticGeometry)
  expect(first.riskZones.features).toHaveLength(0)
  expect(seventh.riskZones.features[0].geometry).toBe(dayGeometry)
  expect(timeline.risk_zones.features[0].geometry).toBe(staticGeometry)
})

it('a clicked monitoring zone names only its real district and returned relative tier', () => {
  const rows = monitoringZoneDetails({ tier: 'highest', day: 7, date: '2026-09-06', area_km2: 12.34 }, 'Matara District')
  expect(rows).toContain('Matara District')
  expect(rows).toContain('Highest relative spatial concern')
  expect(rows).toContain('Day 7 · 6 Sep 2026')
  expect(rows).toContain('12.3 km² in this relative tier')
  expect(rows).toContain('Scored monitoring area within nominal reach. Not a predicted infection location.')
  expect(monitoringZoneDetails({ tier: 'unknown' }, 'Matara')).toEqual([])
})

it('an outside influencing source can be focused without revealing its private farm label', () => {
  const focus = vi.fn()
  const farmNames = new Map([['private-farm', { name: 'DO NOT DISCLOSE' }]])
  render(<MyAreaIntelligencePanel authorizedDistrict="Matara" mode="FUTURE_IMPACT" diseaseShortLabel="LSD" farmNames={farmNames} sourceBreakdown={{ inside: 0, outside: 1, sources: [{ sourceId: 'OP:LSD:Fpublic', recordDomain: 'OPERATIONAL', farmId: 'private-farm', privacyReduced: true, inside: false, coordinates: [80.5, 6], observationDate: '2026-08-30', memberCount: 1, bearingDeg: null }] }} />)
  expect(screen.queryByText('DO NOT DISCLOSE')).toBeNull()
  cleanup()
  // Focusing happens on the influencing card ("View on Map"), by the source identity only.
  const card = { kind: 'APPROACHING AREA', modelData: true, series: [0, 0.1], directionText: 'direction unavailable', dayStatusText: 'reaches the district on Day 1' }
  render(<MyAreaOutbreaksInfluencing influences={[{ anchorId: 'OP:LSD:Fpublic', caseId: 'k1', sourceId: 'OP:LSD:Fpublic', recordDomain: 'OPERATIONAL', farmId: 'private-farm', privacyReduced: true, card }]} farmNames={farmNames} onViewOnMap={focus} />)
  expect(screen.queryByText('DO NOT DISCLOSE')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'View on Map →' }))
  expect(focus).toHaveBeenCalledWith(expect.objectContaining({ sourceId: 'OP:LSD:Fpublic' }))
})

describe('Weather context uses reported values with their own location and date', () => {
  const data = { model: 'Fixture reanalysis', provider: 'Fixture provider', observations: [{ role: 'DISTRICT_REFERENCE_POINT', district: 'Galle', grid_cell: { latitude: 6.25, longitude: 80.25 }, status: 'OK', window: { number_of_hourly_samples: 72, window_start: '2026-08-27T00:00:00Z', window_end: '2026-08-30T00:00:00Z' }, features: [{ feature_name: 'precipitation_accumulation', status: 'REAL', value: 12.4, units: 'mm' }, { feature_name: 'vector_mean_wind_direction_from', status: 'REAL', value: 225, units: 'deg' }, { feature_name: 'mean_temperature_2m', status: 'MISSING', value: null, units: 'degC' }] }] }
  it('shows the provided rainfall, wind-from direction and missing temperature', () => {
    render(<Era5Observations state={{ status: 'ready', data }} asOf="2026-08-30" district="Galle" />)
    expect(screen.getByText('12.4 mm')).toBeTruthy()
    expect(screen.getByText('225.0 deg · SW')).toBeTruthy()
    expect(screen.getByText('MISSING')).toBeTruthy()
    expect(screen.getByText('Galle district reference')).toBeTruthy()
    expect(screen.getByText(/not used in C0/)).toBeTruthy()
  })
  it('does not display stale observations for a selected future day', () => {
    render(<Era5Observations state={{ status: 'ready', data }} asOf="2099-01-01" district="Galle" unavailableText="No future observations available" />)
    expect(screen.getByText('No future observations available')).toBeTruthy()
    expect(screen.queryByText('12.4 mm')).toBeNull()
  })
})

import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { buildNationalActivityBuckets, buildNationalMostAffectedAreas, summarizeNationalRecords } from '../adapters/currentSurveillance'
import { buildRiskCells, unavailableReason } from '../adapters/spatialStory'
import GeospatialRouteBoundary from '../components/GeospatialRouteBoundary'
import { DISTRICT_GEOMETRY_STATUS } from '../context/useDistrictGeometry'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'
import { AREA_CONTEXT_STATE, resolveAreaContextState } from '../adapters/myAreaContextState'

const NOW = Date.parse('2026-10-16T06:00:00+05:30')

describe('My Area district context states (no successful-looking zeros while unknown)', () => {
  const base = { operationalState: OPERATIONAL_STATE.LOADING, hasOperationalData: false, district: null, districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.IDLE, hasDistrictFeature: false }

  it('separates loading, failed, unresolved, boundary failure and ready', () => {
    expect(resolveAreaContextState(base)).toBe(AREA_CONTEXT_STATE.LOADING)
    expect(resolveAreaContextState({ ...base, operationalState: OPERATIONAL_STATE.ERROR })).toBe(AREA_CONTEXT_STATE.FAILED)
    expect(resolveAreaContextState({ ...base, operationalState: OPERATIONAL_STATE.SESSION_REQUIRED })).toBe(AREA_CONTEXT_STATE.FAILED)
    expect(resolveAreaContextState({ ...base, operationalState: OPERATIONAL_STATE.CONNECTED, hasOperationalData: true })).toBe(AREA_CONTEXT_STATE.UNRESOLVED)
    const resolved = { ...base, operationalState: OPERATIONAL_STATE.CONNECTED, hasOperationalData: true, district: 'Galle' }
    expect(resolveAreaContextState({ ...resolved, districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.LOADING })).toBe(AREA_CONTEXT_STATE.LOADING)
    expect(resolveAreaContextState({ ...resolved, districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.ERROR })).toBe(AREA_CONTEXT_STATE.BOUNDARY_FAILED)
    expect(resolveAreaContextState({ ...resolved, districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.READY, hasDistrictFeature: false })).toBe(AREA_CONTEXT_STATE.BOUNDARY_FAILED)
    expect(resolveAreaContextState({ ...resolved, districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.READY, hasDistrictFeature: true })).toBe(AREA_CONTEXT_STATE.READY)
  })

  it('a refresh failure after data loaded keeps the resolved district (never falls back)', () => {
    expect(resolveAreaContextState({ operationalState: OPERATIONAL_STATE.ERROR, hasOperationalData: true, district: 'Kandy', districtGeometryStatus: DISTRICT_GEOMETRY_STATUS.READY, hasDistrictFeature: true })).toBe(AREA_CONTEXT_STATE.READY)
  })
})

describe('Analysis & Trends national population, window and empty-period explanation', () => {
  const rec = (key, status, reported, district) => ({ record_key: key, disease: 'LSD', verification_status: status, reported_at: reported, district })
  const records = [
    rec('CASE:1', 'VERIFIED', '2026-08-30T10:00:00+00:00', '5.9, 80.5 (Matara District)'),
    rec('CASE:2', 'VERIFIED', '2026-08-31T10:00:00+00:00', 'Matara'),
    rec('CASE:3', 'PENDING_VERIFICATION', '2026-08-15T10:00:00+00:00', 'Galle'),
    rec('CASE:4', 'VERIFIED', null, null),
  ]

  it('counts every record in scope and explains why the recent window is empty', () => {
    const summary = summarizeNationalRecords(records, { windowDays: 14, nowMs: NOW })
    expect(summary).toMatchObject({ total: 4, verified: 3, pending: 1, districtCount: 2, withoutDistrict: 1, inWindow: 0, beforeWindow: 3, dateUnknown: 1, latestReportDate: '2026-08-31', windowStartKey: '2026-10-03', windowEndKey: '2026-10-16' })
    const buckets = buildNationalActivityBuckets(records, 14, NOW)
    expect(buckets.points).toHaveLength(14)
    expect(buckets.points.every((p) => p.count === 0)).toBe(true)
    expect(buckets.excludedCount).toBe(1)
  })

  it('a record inside the window is a bar on its Asia/Colombo report date', () => {
    const recent = [...records, rec('CASE:5', 'VERIFIED', '2026-10-14T20:00:00+00:00', 'Kandy')] // 15 Oct 01:30 in Colombo
    const buckets = buildNationalActivityBuckets(recent, 7, NOW)
    expect(buckets.points.find((p) => p.period === '2026-10-15').count).toBe(1)
    expect(buckets.points.find((p) => p.period === '2026-10-14').count).toBe(0)
  })

  it('most affected areas are national districts with verified/pending split', () => {
    expect(buildNationalMostAffectedAreas(records)).toEqual([
      { district: 'Matara', records: 2, verified: 2, pending: 0, lastReported: '2026-08-31' },
      { district: 'Galle', records: 1, verified: 0, pending: 1, lastReported: '2026-08-15' },
    ])
  })
})

describe('Risk zones: authoritative geometry only, explicit failure reasons', () => {
  const frame = { day: 0, date: '2026-10-16', horizon_status: 'AS_OF_OBSERVED_CONTEXT', reach_envelope: null }
  const poly = { type: 'Polygon', coordinates: [[[80, 6], [80.05, 6], [80.05, 6.05], [80, 6]]] }
  const multi = { type: 'MultiPolygon', coordinates: [[[[81, 7], [81.05, 7], [81.05, 7.05], [81, 7]]]] }
  const cell = (id, geometry) => ({ cell_id: id, centroid: { longitude: 80.02, latitude: 6.02 }, score_status: 'SCORED', tier: 'high', raw_c0_score: 0.5, in_scope: true, geometry })

  it('draws the backend Polygon/MultiPolygon as sent and never invents a square for a clipped-away cell', () => {
    // Day 0: cells are drawn where a real source case sits (one per cell here).
    const timeline = { status: 'OK', frames: [frame], sources: [{ source_id: 'S1', longitude: 80.03, latitude: 6.01 }, { source_id: 'S2', longitude: 81.03, latitude: 7.01 }], cells: [cell('a', poly), cell('b', multi), cell('c', null)] }
    const fc = buildRiskCells(timeline, 0)
    expect(fc.features.map((f) => [f.properties.cellId, f.geometry.type])).toEqual([['a', 'Polygon'], ['b', 'MultiPolygon']])
    expect(fc.features[1].geometry).toBe(multi)
  })

  it('a failed request is reported as a failure with its reason, never as "no eligible sources"', () => {
    expect(unavailableReason(null, { fetchState: 'error', errorStatus: 'NETWORK_ERROR' })).toMatchObject({ title: 'Backend unreachable', failed: true })
    expect(unavailableReason(null, { fetchState: 'error', errorStatus: 'SESSION_REQUIRED' })).toMatchObject({ title: 'Sign-in required', canSwitchBasis: false })
    expect(unavailableReason(null, { fetchState: 'error', errorStatus: 'INVALID_RESPONSE' }).title).toBe('Unreadable response')
    const empty = unavailableReason({ status: 'NO_ELIGIBLE_SOURCES', time_window: { source_window_start: '2026-10-03', source_window_end: '2026-10-16' }, source_exclusions: { OUTSIDE_WINDOW: 15 } }, { diseaseShortLabel: 'LSD' })
    expect(empty.failed).toBeUndefined()
    expect(empty.body).toMatch(/15 excluded for other reasons/)
  })
})

describe('Geospatial route boundary keeps the shell when a page throws', () => {
  it('shows the error inside the page area, keeps siblings, and recovers on retry', () => {
    let shouldThrow = true
    function Page() {
      if (shouldThrow) throw new Error('boom in page')
      return <div>page ok</div>
    }
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <div>
        <nav>Geospatial tabs</nav>
        <GeospatialRouteBoundary resetKey="/vet/geospatial/my-area">
          <Page />
        </GeospatialRouteBoundary>
      </div>,
    )
    expect(screen.getByText('Geospatial tabs')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toMatch(/boom in page/)
    shouldThrow = false
    fireEvent.click(screen.getByText('Try again'))
    expect(screen.getByText('page ok')).toBeTruthy()
    spy.mockRestore()
  })
})

describe('Area Intelligence tolerates an environment response without optional fields', async () => {
  const { default: MyAreaIntelligencePanel } = await import('../components/MyAreaIntelligencePanel')
  it('renders (no "split of undefined") when provider/model are absent', () => {
    expect(() => render(<MyAreaIntelligencePanel authorizedDistrict="Kandy" diseaseShortLabel="LSD" environmentObservations={{ status: 'ready', data: { status: 'NOT_AVAILABLE', observations: [] } }} />)).not.toThrow()
  })
})

describe('Risk Zones repaint when only the day-specific reach changes', async () => {
  const { geometrySignature } = await import('../components/mapFrameTransitions')
  it('the cross-fade signature differs when a cell enters the nominal reach', () => {
    const geometry = { type: 'Polygon', coordinates: [[[80, 6], [80.05, 6], [80.05, 6.05], [80, 6]]] }
    const day0 = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry, properties: { riskLevel: 'red', inReach: false } }] }
    const day7 = { type: 'FeatureCollection', features: [{ type: 'Feature', geometry, properties: { riskLevel: 'red', inReach: true } }] }
    expect(geometrySignature(day0)).not.toBe(geometrySignature(day7))
  })
})

describe('Automatic analysis date (no cases in the last 14 days)', async () => {
  const { ANALYSIS_BASIS, automaticBasisId } = await import('../adapters/spatialStory')
  it('stays on today while a case was verified in the 14-day source window', () => {
    expect(automaticBasisId({ latestVerified: '2026-10-16', today: '2026-10-16' })).toBe(ANALYSIS_BASIS.LIVE)
    expect(automaticBasisId({ latestVerified: '2026-10-03', today: '2026-10-16' })).toBe(ANALYSIS_BASIS.LIVE)
  })
  it('moves to the latest real verified case once it falls outside that window', () => {
    expect(automaticBasisId({ latestVerified: '2026-10-02', today: '2026-10-16' })).toBe(ANALYSIS_BASIS.LATEST_VERIFIED)
    expect(automaticBasisId({ latestVerified: '2026-08-31', today: '2026-10-16' })).toBe(ANALYSIS_BASIS.LATEST_VERIFIED)
  })
  it('never invents a date when there is no verified case', () => {
    expect(automaticBasisId({ latestVerified: null, today: '2026-10-16' })).toBe(ANALYSIS_BASIS.LIVE)
  })
})

describe('Env map features use the reported ERA5 values only', async () => {
  const { buildEnvironmentFeatures } = await import('../adapters/environmentMap')
  const obs = (features, status = 'OK') => ({ role: 'DISTRICT_REFERENCE_POINT', status, grid_cell: { latitude: 6.25, longitude: 80.5 }, features })
  it('places rain and wind at the observation grid cell; wind arrow points downwind', () => {
    const fc = buildEnvironmentFeatures({ observations: [obs([
      { feature_name: 'precipitation_accumulation', value: 14.6, status: 'REAL' },
      { feature_name: 'mean_wind_speed', value: 3.4, status: 'REAL' },
      { feature_name: 'vector_mean_wind_direction_from', value: 299, status: 'REAL' },
    ])] })
    expect(fc.features[0].geometry.coordinates).toEqual([80.5, 6.25])
    expect(fc.features[0].properties).toMatchObject({ rainMm: 14.6, windSpeed: 3.4, windFromDeg: 299, windTowardDeg: 119, hasRain: true, hasWind: true })
    expect(fc.features[0].properties.label).toMatch(/Rain 14\.6 mm · Wind from (W|NW|WNW) 3\.4 m\/s/)
  })
  it('missing values are not filled and failed observations are not drawn', () => {
    const fc = buildEnvironmentFeatures({ observations: [obs([{ feature_name: 'precipitation_accumulation', value: null, status: 'MISSING' }]), obs([], 'MISSING')] })
    expect(fc.features).toHaveLength(1)
    expect(fc.features[0].properties).toMatchObject({ rainMm: null, hasRain: false, hasWind: false, label: '' })
  })
})

describe('New-case alerts come from real record changes only', async () => {
  const { diffCaseRecords, alertText } = await import('../context/useNewCaseAlerts')
  const rec = (key, status, district = 'Matara') => ({ record_key: key, disease: 'LSD', verification_status: status, district })
  it('a new key is NEW_CASE; pending -> verified is VERIFIED; unchanged records never alert', () => {
    const before = new Map([['CASE:a', 'VERIFIED'], ['CASE:b', 'PENDING_VERIFICATION']])
    const alerts = diffCaseRecords(before, [rec('CASE:a', 'VERIFIED'), rec('CASE:b', 'VERIFIED'), rec('CASE:c', 'PENDING_VERIFICATION', '6.1, 80.2 (Galle District)')])
    expect(alerts.map((a) => [a.kind, a.record.record_key])).toEqual([['VERIFIED', 'CASE:b'], ['NEW_CASE', 'CASE:c']])
    expect(alertText(alerts[1])).toBe('New LSD case (pending verification) · Galle')
  })
})

describe('Case hover text', async () => {
  const { caseHoverHtml } = await import('../adapters/caseAge')
  it('summarises one marker and escapes text; a grouped bubble invites a zoom', () => {
    const html = caseHoverHtml({ disease: 'LSD', verified: true, count: 8, district: 'Nuwara <Eliya>', reportDateKey: '2026-09-15', ageClass: 'OLDER', ageDays: 31 })
    expect(html).toContain('LSD · vet-verified')
    expect(html).toContain('8 reports here')
    expect(html).toContain('Nuwara &lt;Eliya&gt;')
    expect(html).toContain('31 days since report')
  })
})

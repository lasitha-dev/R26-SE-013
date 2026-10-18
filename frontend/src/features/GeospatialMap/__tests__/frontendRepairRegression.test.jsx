import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clipLineToDomain } from '../adapters/clipLineToDomain'
import { classifyCaseAge } from '../adapters/caseAge'
import { buildNationalCaseView } from '../adapters/nationalCases'
import { normalizeOperationalContext } from '../adapters/operationalContextAdapter'
import { buildMonitoringZones } from '../adapters/spatialTimelineView'
import { useStClusters } from '../context/useStClusters'
import { useNewCaseAlerts } from '../context/useNewCaseAlerts'
import { isFatalMapError } from '../components/mapPresentationError'

// Synthetic test geometry only; never application records or map fallbacks.
const square = (left, right) => [[[left, 0], [right, 0], [right, 2], [left, 2], [left, 0]]]
const line = (coordinates) => ({ type: 'LineString', coordinates })
const domain = { type: 'MultiPolygon', coordinates: [square(0, 2), square(4, 6)] }
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('frontend repair: age and record reconciliation', () => {
  it('rejects impossible calendar dates instead of rolling them into recent reports', () => {
    expect(classifyCaseAge('2026-02-30', '2026-03-02').ageClass).toBe('DATE_UNKNOWN')
    expect(classifyCaseAge('2026-02-30T03:00:00Z', '2026-03-02').ageClass).toBe('DATE_UNKNOWN')
    expect(classifyCaseAge('2026-03-01', '2026-02-30').ageClass).toBe('DATE_UNKNOWN')
    expect(classifyCaseAge('2024-02-29', '2024-03-01').ageDays).toBe(1)
  })

  it('reconciles returned records, exclusions, invalid GPS and grouped symbols', () => {
    const report = { disease: 'LSD', verification_status: 'VERIFIED', reported_at: '2026-09-16', verified_at: '2026-09-17', location_status: 'VALID', latitude: 6, longitude: 80 }
    const records = [
      { ...report, record_key: 'a' }, { ...report, record_key: 'b' },
      { ...report, record_key: 'c', latitude: 100 },
      { ...report, record_key: 'd', disease: 'FMD' },
    ]
    const view = buildNationalCaseView(records, { disease: 'LSD', windowDays: Infinity, ageReferenceDateKey: '2026-10-16' })
    expect(view.reconciliation).toEqual({ returned: 4, excludedByDisease: 1, excludedByWindowOrReplay: 0, included: 3, withoutGps: 1, hiddenOlderThanVisibleLimit: 0, mappable: 2, markerSymbolsBeforeZoomGrouping: 1, representedRecords: 2 })
    expect(view.featureCollection.features[0].geometry.coordinates).toEqual([80, 6])
    expect(view.featureCollection.features[0].properties).toMatchObject({ count: 2, ageClass: 'OLDER', ageDays: 30 }) // 15-30 days: muted brown, still shown
  })

  it('retains authorized unmappable reports independently of drawable clinical points', () => {
    const raw = { farms: [{ farm_id: 'f', location_status: 'LOCATION_REQUIRED', personally_assigned: true }], clinical_contexts: [{ case_id: 'c', farm_id: 'f', disease: 'LSD', semantic_class: 'VERIFIED_CLINICAL_CONTEXT', case_creation_time: '2026-09-01' }] }
    const normalized = normalizeOperationalContext(raw)
    expect(normalized.clinicalContexts).toHaveLength(0)
    expect(normalized.clinicalRecords).toHaveLength(1)
    expect(normalized.clinicalRecords[0]).toMatchObject({ caseId: 'c', reportedAt: '2026-09-01', latitude: null, longitude: null })
  })
})

describe('frontend repair: exact dated geometry', () => {
  it('shows the backend frame intersection, including MultiPolygon, without drawing future footprints at baseline', () => {
    const geometry = { type: 'MultiPolygon', coordinates: [square(0, 1), square(4, 5)] }
    const zone = { type: 'Feature', geometry, properties: { tier: 'highest', area_km2: 12.5 } }
    const timeline = { status: 'OK', as_of: '2026-10-01', frames: [
      { day: 0, date: '2026-10-01', reach_limited_risk_zones: { type: 'FeatureCollection', features: [] } },
      { day: 7, date: '2026-10-08', reach_limited_risk_zones: { type: 'FeatureCollection', features: [zone] } },
    ] }
    expect(buildMonitoringZones(timeline, 0).features).toHaveLength(0)
    const shown = buildMonitoringZones(timeline, 1).features[0]
    expect(shown.geometry).toBe(geometry)
    expect(shown.properties).toMatchObject({ areaKm2: 12.5, day: 7, date: '2026-10-08', score: null, inReach: true })
  })

  it('clips exit and re-entry into separate real line segments without an ocean connector', () => {
    expect(clipLineToDomain(line([[-1, 1], [7, 1]]), domain)).toEqual({ type: 'MultiLineString', coordinates: [[[0, 1], [2, 1]], [[4, 1], [6, 1]]] })
  })

  it('preserves holes, fully inland geometry, and separate MultiLineString parts', () => {
    const inland = line([[0.5, 1], [1.5, 1]])
    expect(clipLineToDomain(inland, domain)).toBe(inland)
    expect(clipLineToDomain(line([[-2, 3], [-1, 4]]), domain)).toBeNull()
    const withHole = { type: 'Polygon', coordinates: [...square(0, 6), ...square(2, 4).map((ring) => ring.map(([x, y]) => [x, y * 0.5 + 0.5]))] }
    expect(clipLineToDomain(line([[0, 1], [6, 1]]), withHole).coordinates).toEqual([[[0, 1], [2, 1]], [[4, 1], [6, 1]]])
    const split = { type: 'MultiLineString', coordinates: [[[0.5, 1], [1.5, 1]], [[4.5, 1], [5.5, 1]]] }
    expect(clipLineToDomain(split, domain)).toBe(split)
  })
})

it('discards a stale cluster response even when fetch ignores AbortSignal', async () => {
  const requests = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => requests.push(resolve))))
  const { result, rerender } = renderHook((props) => useStClusters(props), { initialProps: { disease: 'LSD', enabled: true, asOf: '2026-10-01' } })
  rerender({ disease: 'LSD', enabled: true, asOf: '2026-10-02' })
  const response = (label) => ({ ok: true, json: async () => ({ clusters: [], label }) })
  await act(async () => requests[1](response('new')))
  await waitFor(() => expect(result.current.data?.label).toBe('new'))
  await act(async () => requests[0](response('old')))
  expect(result.current.data.label).toBe('new')
})

it('treats a missing tile as recoverable while identifying actual renderer failures', () => {
  expect(isFatalMapError(new Error('Failed to fetch tile /tiles/8/1/1'))).toBe(false)
  expect(isFatalMapError(new Error('Failed to initialize WebGL'))).toBe(true)
  expect(isFatalMapError(new Error('WebGL context lost'))).toBe(true)
})

it('primes existing records silently, expires new-case alerts and does not relabel reappearing records as new', () => {
  const frames = []
  vi.stubGlobal('requestAnimationFrame', (cb) => { frames.push(cb); return frames.length })
  vi.stubGlobal('cancelAnimationFrame', vi.fn())
  vi.spyOn(performance, 'now').mockReturnValue(1000)
  const existing = { record_key: 'test:old', verification_status: 'VERIFIED' }
  const fresh = { record_key: 'test:new', verification_status: 'VERIFIED' }
  const { result, rerender } = renderHook((records) => useNewCaseAlerts(records), { initialProps: [existing] })
  expect(result.current.alerts).toEqual([])
  rerender([existing, fresh])
  expect(result.current.alerts.map((a) => a.record.record_key)).toEqual(['test:new'])
  act(() => frames.at(-1)(9001))
  expect(result.current.alerts).toEqual([])
  rerender([existing])
  rerender([existing, fresh])
  expect(result.current.alerts).toEqual([])
})

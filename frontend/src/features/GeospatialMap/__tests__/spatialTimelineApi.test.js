import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchSpatialTimeline, SPATIAL_TIMELINE_FETCH_STATUS } from '../api/spatialTimelineApi'

function response(status, body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

function lastUrl() {
  return new URL(String(global.fetch.mock.calls.at(-1)[0]), 'http://localhost')
}

afterEach(() => {
  vi.restoreAllMocks()
  localStorage.clear()
})

describe('fetchSpatialTimeline request', () => {
  it('sends disease, district scope, district and horizon 14 with the stored bearer token -- never as_of by default', async () => {
    localStorage.setItem('token', 'test-token')
    global.fetch = vi.fn(() => response(200, { status: 'OK', snapshot_id: 'stl_x', frames: [], cells: [] }))
    const body = await fetchSpatialTimeline({ disease: 'LSD', scope: 'district', district: 'Galle' })
    expect(body.snapshot_id).toBe('stl_x')
    const url = lastUrl()
    expect(url.pathname).toBe('/api/geospatial/spatial-timeline')
    expect(Object.fromEntries(url.searchParams)).toEqual({ disease: 'lsd', scope: 'district', district: 'Galle', horizon_days: '14' })
    expect(global.fetch.mock.calls[0][1].headers).toEqual({ Authorization: 'Bearer test-token' })
  })

  it('national scope never sends a district', async () => {
    global.fetch = vi.fn(() => response(200, { status: 'OK', frames: [] }))
    await fetchSpatialTimeline({ disease: 'fmd', scope: 'national', district: 'Galle' })
    expect(lastUrl().searchParams.has('district')).toBe(false)
    expect(lastUrl().searchParams.get('scope')).toBe('national')
  })
})

describe('fetchSpatialTimeline response shape', () => {
  it('a 200 that is not a timeline snapshot is INVALID_RESPONSE, never an empty result', async () => {
    for (const body of [{}, { status: 'OK' }, { status: 'OK', frames: [], cells: {} }, { status: 'OK', frames: [], risk_zones: { type: 'FeatureCollection' } }]) {
      global.fetch = vi.fn(() => response(200, body))
      await expect(fetchSpatialTimeline({ disease: 'lsd', scope: 'national' })).rejects.toMatchObject({ spatialTimelineStatus: SPATIAL_TIMELINE_FETCH_STATUS.INVALID_RESPONSE })
    }
    global.fetch = vi.fn(() => Promise.resolve(new Response('not json', { status: 200 })))
    await expect(fetchSpatialTimeline({ disease: 'lsd', scope: 'national' })).rejects.toMatchObject({ spatialTimelineStatus: SPATIAL_TIMELINE_FETCH_STATUS.INVALID_RESPONSE })
  })

  it('a successful empty snapshot (NO_ELIGIBLE_SOURCES) is returned as data', async () => {
    global.fetch = vi.fn(() => response(200, { status: 'NO_ELIGIBLE_SOURCES', frames: [], cells: [], risk_zones: { type: 'FeatureCollection', features: [] } }))
    expect((await fetchSpatialTimeline({ disease: 'lsd', scope: 'national' })).status).toBe('NO_ELIGIBLE_SOURCES')
  })
})

describe('fetchSpatialTimeline errors', () => {
  const cases = [
    [401, {}, SPATIAL_TIMELINE_FETCH_STATUS.SESSION_REQUIRED],
    [403, { detail: 'Veterinarian account required.' }, SPATIAL_TIMELINE_FETCH_STATUS.FORBIDDEN],
    [403, { detail: { status: 'DISTRICT_NOT_AUTHORISED' } }, SPATIAL_TIMELINE_FETCH_STATUS.DISTRICT_NOT_AUTHORISED],
    [404, { detail: { status: 'DISTRICT_NOT_FOUND' } }, SPATIAL_TIMELINE_FETCH_STATUS.DISTRICT_NOT_FOUND],
    [404, { detail: 'Not Found' }, SPATIAL_TIMELINE_FETCH_STATUS.INVALID_REQUEST],
    [409, { detail: { status: 'NO_AUTHORISED_DISTRICT' } }, SPATIAL_TIMELINE_FETCH_STATUS.NO_AUTHORISED_DISTRICT],
    [422, { detail: { status: 'DISTRICT_REQUIRED' } }, SPATIAL_TIMELINE_FETCH_STATUS.DISTRICT_REQUIRED],
    [422, { detail: { status: 'UNSUPPORTED_DISEASE' } }, SPATIAL_TIMELINE_FETCH_STATUS.UNSUPPORTED_DISEASE],
    [422, { detail: [{ msg: 'native validation' }] }, SPATIAL_TIMELINE_FETCH_STATUS.INVALID_REQUEST],
    [503, { detail: { status: 'OPERATIONAL_DATA_UNAVAILABLE' } }, SPATIAL_TIMELINE_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE],
    [500, { detail: { status: 'ANALYSIS_INTERNAL_ERROR' } }, SPATIAL_TIMELINE_FETCH_STATUS.SERVICE_UNAVAILABLE],
  ]
  it.each(cases)('HTTP %i %j -> %s', async (status, body, expected) => {
    global.fetch = vi.fn(() => response(status, body))
    await expect(fetchSpatialTimeline({ disease: 'lsd', scope: 'district' })).rejects.toMatchObject({ spatialTimelineStatus: expected })
  })

  it('a network failure is tagged NETWORK_ERROR; an abort passes through untouched', async () => {
    global.fetch = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')))
    await expect(fetchSpatialTimeline({ disease: 'lsd', scope: 'national' })).rejects.toMatchObject({ spatialTimelineStatus: 'NETWORK_ERROR' })
    const abort = new DOMException('aborted', 'AbortError')
    global.fetch = vi.fn(() => Promise.reject(abort))
    await expect(fetchSpatialTimeline({ disease: 'lsd', scope: 'national' })).rejects.toBe(abort)
  })
})

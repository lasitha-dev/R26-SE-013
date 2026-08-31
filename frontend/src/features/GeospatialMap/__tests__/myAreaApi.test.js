import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AUTH_TOKEN_STORAGE_KEY } from '../api/operationalApi'
import { MY_AREA_FETCH_STATUS, fetchMyAreaContext } from '../api/myAreaApi'

function mockResponse({ ok, status, body = {} }) {
  return { ok, status, json: () => Promise.resolve(body) }
}

function withWindowToken(token) {
  global.window = { localStorage: { getItem: vi.fn().mockReturnValue(token) } }
}

describe('GEO-AREA-02-API-01: request shape', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('uses the real bearer token convention (same AUTH_TOKEN_STORAGE_KEY as GEO-INT-03H)', async () => {
    withWindowToken('real-token-value')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer real-token-value')
    expect(global.window.localStorage.getItem).toHaveBeenCalledWith(AUTH_TOKEN_STORAGE_KEY)
  })

  it('includes farm_id in the request', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain('farm_id=F1')
  })

  it('always includes an explicit disease parameter', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'fmd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain('disease=fmd')
  })

  it('never sends vet_id, vet email, or role as request parameters', async () => {
    withWindowToken('t')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd', originId: 'O1', day: 3 })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/vet_id|vet_email|role=/)
  })

  it('never sends latitude or longitude query parameters', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/[?&]lat(itude)?=/)
    expect(url).not.toMatch(/[?&]lon(gitude)?=/)
  })

  it('omits origin_id when no origin is selected', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toContain('origin_id=')
  })

  it('sends origin_id when explicitly selected', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd', originId: 'ORIGIN:X' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain(`origin_id=${encodeURIComponent('ORIGIN:X')}`)
  })

  it('sends the day 0..7 correctly', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd', day: 5 })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain('day=5')
  })

  it('supports AbortSignal', async () => {
    const abortError = new DOMException('aborted', 'AbortError')
    withWindowToken(null)
    global.fetch = vi.fn().mockRejectedValue(abortError)
    const controller = new AbortController()
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' }, { signal: controller.signal })).rejects.toBe(abortError)
  })
})

describe('GEO-AREA-02-API-02: the critical 404 distinction (Section 7)', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => withWindowToken(null))
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('structured ASSIGNED_AREA_NOT_FOUND is distinguished from a generic 404', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404, body: { detail: { status: 'ASSIGNED_AREA_NOT_FOUND' } } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.ASSIGNED_AREA_NOT_FOUND })
  })

  it('structured ORIGIN_NOT_FOUND is distinguished from a generic 404', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404, body: { detail: { status: 'ORIGIN_NOT_FOUND' } } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd', originId: 'O1' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.ORIGIN_NOT_FOUND })
  })

  it('a generic route-not-mounted 404 (FastAPI default body, detail is a bare string) maps to HOST_COMPOSITION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404, body: { detail: 'Not Found' } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.HOST_COMPOSITION_REQUIRED })
  })

  it('a 404 with an unparseable body also maps to HOST_COMPOSITION_REQUIRED, never crashes', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, json: () => Promise.reject(new Error('not json')) })
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.HOST_COMPOSITION_REQUIRED })
  })
})

describe('GEO-AREA-02-API-03: other status mapping', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => withWindowToken(null))
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('200 is parsed and returned verbatim', async () => {
    const body = { status: 'OK', area: null }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).resolves.toEqual(body)
  })

  it('401 maps to SESSION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.SESSION_REQUIRED })
  })

  it('403 maps to FORBIDDEN', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 403 }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.FORBIDDEN })
  })

  it('structured 409 ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY mapped cleanly', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 409, body: { detail: { status: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY' } } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'fmd', originId: 'O1' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY })
  })

  it('structured 409 OPERATIONAL_DATA_UNAVAILABLE mapped cleanly', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 409, body: { detail: { status: 'OPERATIONAL_DATA_UNAVAILABLE' } } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE })
  })

  it('structured 422 UNSUPPORTED_DISEASE mapped cleanly', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body: { detail: { status: 'UNSUPPORTED_DISEASE' } } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: 'rabies' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.UNSUPPORTED_DISEASE })
  })

  it('a native FastAPI validation 422 (array detail, e.g. missing/invalid query param) maps to INVALID_REQUEST', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body: { detail: [{ type: 'missing', loc: ['query', 'disease'] }] } }))
    await expect(fetchMyAreaContext({ farmId: 'F1', disease: '' })).rejects.toMatchObject({ myAreaStatus: MY_AREA_FETCH_STATUS.INVALID_REQUEST })
  })

  it('a network failure maps to NETWORK_ERROR, never a raw stack trace message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    let caught
    try {
      await fetchMyAreaContext({ farmId: 'F1', disease: 'lsd' })
    } catch (err) {
      caught = err
    }
    expect(caught.myAreaStatus).toBe(MY_AREA_FETCH_STATUS.NETWORK_ERROR)
    expect(caught.message).not.toContain('TypeError')
  })
})

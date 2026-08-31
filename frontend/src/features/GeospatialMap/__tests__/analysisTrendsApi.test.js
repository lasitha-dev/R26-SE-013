import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AUTH_TOKEN_STORAGE_KEY } from '../api/operationalApi'
import { ANALYSIS_TRENDS_FETCH_STATUS, fetchAnalysisTrends } from '../api/analysisTrendsApi'

function mockResponse({ ok, status, body = {} }) {
  return { ok, status, json: () => Promise.resolve(body) }
}

function withWindowToken(token) {
  global.window = { localStorage: { getItem: vi.fn().mockReturnValue(token) } }
}

describe('GEO-ANALYSIS-02-API-01: request shape', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('uses the real bearer token convention (same AUTH_TOKEN_STORAGE_KEY as GEO-INT-03H)', async () => {
    withWindowToken('real-token-value')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd' })
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer real-token-value')
    expect(global.window.localStorage.getItem).toHaveBeenCalledWith(AUTH_TOKEN_STORAGE_KEY)
  })

  it('always includes an explicit disease parameter', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'fmd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain('disease=fmd')
  })

  it('never sends a country query parameter', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd', originId: 'ORIGIN:Sri Lanka:2020-09-07' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/[?&]country=/)
  })

  it('never sends vet_id, vet email, or role as request parameters', async () => {
    withWindowToken('t')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd', originId: 'O1' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/vet_id|vet_email|role=/)
  })

  it('never sends latitude or longitude query parameters', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/[?&]lat(itude)?=/)
    expect(url).not.toMatch(/[?&]lon(gitude)?=/)
  })

  it('omits origin_id when no origin is selected', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd' })
    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toContain('origin_id=')
  })

  it('sends origin_id when explicitly selected', async () => {
    withWindowToken(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    await fetchAnalysisTrends({ disease: 'lsd', originId: 'ORIGIN:Sri Lanka:2020-09-07' })
    const [url] = global.fetch.mock.calls[0]
    const params = new URLSearchParams(url.split('?')[1])
    expect(params.get('origin_id')).toBe('ORIGIN:Sri Lanka:2020-09-07')
  })

  it('supports AbortSignal', async () => {
    const abortError = new DOMException('aborted', 'AbortError')
    withWindowToken(null)
    global.fetch = vi.fn().mockRejectedValue(abortError)
    const controller = new AbortController()
    await expect(fetchAnalysisTrends({ disease: 'lsd' }, { signal: controller.signal })).rejects.toBe(abortError)
  })
})

describe('GEO-ANALYSIS-02-API-02: the critical 404/422/500 distinction', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => withWindowToken(null))
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('structured ORIGIN_NOT_FOUND is distinguished from a generic 404', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404, body: { detail: { status: 'ORIGIN_NOT_FOUND' } } }))
    await expect(fetchAnalysisTrends({ disease: 'lsd', originId: 'O1' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.ORIGIN_NOT_FOUND })
  })

  it('a generic route-not-mounted 404 (FastAPI default body, detail is a bare string) maps to HOST_COMPOSITION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404, body: { detail: 'Not Found' } }))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED })
  })

  it('a 404 with an unparseable body also maps to HOST_COMPOSITION_REQUIRED, never crashes', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, json: () => Promise.reject(new Error('not json')) })
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED })
  })

  it('structured 422 UNSUPPORTED_DISEASE mapped cleanly', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body: { detail: { status: 'UNSUPPORTED_DISEASE' } } }))
    await expect(fetchAnalysisTrends({ disease: 'rabies' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.UNSUPPORTED_DISEASE })
  })

  it('a native FastAPI validation 422 (array detail, e.g. missing disease) maps to INVALID_REQUEST', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body: { detail: [{ type: 'missing', loc: ['query', 'disease'] }] } }))
    await expect(fetchAnalysisTrends({ disease: '' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.INVALID_REQUEST })
  })

  it('structured 500 ANALYSIS_INTERNAL_ERROR mapped cleanly, without leaking a raw exception', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: { detail: { status: 'ANALYSIS_INTERNAL_ERROR' } } }))
    let caught
    try {
      await fetchAnalysisTrends({ disease: 'lsd' })
    } catch (err) {
      caught = err
    }
    expect(caught.analysisTrendsStatus).toBe(ANALYSIS_TRENDS_FETCH_STATUS.ANALYSIS_INTERNAL_ERROR)
    expect(caught.message).not.toMatch(/Traceback|Exception/i)
  })

  it('a generic/unstructured 500 maps to SERVICE_UNAVAILABLE, never crashes', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: { detail: 'Internal Server Error' } }))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.SERVICE_UNAVAILABLE })
  })
})

describe('GEO-ANALYSIS-02-API-03: other status mapping and honest bodies', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => withWindowToken(null))
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('200 OK body is parsed and returned verbatim', async () => {
    const body = { status: 'OK', disease: 'LSD', scope_country: 'Sri Lanka' }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body }))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).resolves.toEqual(body)
  })

  it('200 PARTIAL body is returned honestly, never coerced to OK', async () => {
    const body = { status: 'PARTIAL', disease: 'FMD', model_evaluation: { status: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY' } }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body }))
    await expect(fetchAnalysisTrends({ disease: 'fmd' })).resolves.toEqual(body)
  })

  it('401 maps to SESSION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 }))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.SESSION_REQUIRED })
  })

  it('403 maps to FORBIDDEN', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 403 }))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toMatchObject({ analysisTrendsStatus: ANALYSIS_TRENDS_FETCH_STATUS.FORBIDDEN })
  })

  it('a network failure maps to NETWORK_ERROR, never a raw stack trace message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    let caught
    try {
      await fetchAnalysisTrends({ disease: 'lsd' })
    } catch (err) {
      caught = err
    }
    expect(caught.analysisTrendsStatus).toBe(ANALYSIS_TRENDS_FETCH_STATUS.NETWORK_ERROR)
    expect(caught.message).not.toContain('TypeError')
  })

  it('never falls back to a runtime mock -- a rejected fetch always rejects the caller, never resolves with fabricated data', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(fetchAnalysisTrends({ disease: 'lsd' })).rejects.toBeInstanceOf(Error)
  })
})

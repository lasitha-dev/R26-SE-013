import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AUTH_TOKEN_STORAGE_KEY, OPERATIONAL_FETCH_STATUS, fetchOperationalContext, hasTokenDisappeared, readAuthToken } from '../api/operationalApi'

const FEATURE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')

function mockResponse({ ok, status, body = {} }) {
  return { ok, status, json: () => Promise.resolve(body) }
}

describe('GEO-INT-03-API-01: bearer token attachment', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window

  beforeEach(() => {
    global.window = { localStorage: { getItem: vi.fn(), setItem: vi.fn() } }
  })
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('attaches the bearer token when present', async () => {
    global.window.localStorage.getItem = vi.fn().mockReturnValue('real-token-123')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))

    await fetchOperationalContext()

    expect(global.window.localStorage.getItem).toHaveBeenCalledWith(AUTH_TOKEN_STORAGE_KEY)
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer real-token-123')
  })

  it('sends no Authorization header when no token is stored -- never a fabricated identity', async () => {
    global.window.localStorage.getItem = vi.fn().mockReturnValue(null)
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))

    await fetchOperationalContext()

    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBeUndefined()
  })

  it('never sends a vet_id, vet email, or role as a request parameter', async () => {
    global.window.localStorage.getItem = vi.fn().mockReturnValue('t')
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))

    await fetchOperationalContext()

    const [url] = global.fetch.mock.calls[0]
    expect(url).not.toMatch(/vet_id|vet_email|role=/)
  })
})

describe('GEO-INT-03H-01: reconciled against the REAL origin/main host auth contract', () => {
  const originalWindow = global.window
  afterEach(() => {
    global.window = originalWindow
  })

  it('AUTH_TOKEN_STORAGE_KEY is exactly "token" -- the real key origin/main:frontend/src/shared_components/VetLogin.jsx writes via localStorage.setItem("token", data.access_token), not an invented placeholder', () => {
    expect(AUTH_TOKEN_STORAGE_KEY).toBe('token')
  })

  it('readAuthToken reads localStorage under that exact real key, matching every origin/main authenticated screen\'s own `localStorage.getItem(\'token\')` convention', () => {
    const getItem = vi.fn().mockReturnValue('real-jwt-value')
    global.window = { localStorage: { getItem } }
    const token = readAuthToken()
    expect(getItem).toHaveBeenCalledWith('token')
    expect(token).toBe('real-jwt-value')
  })

  it('never reads role/email/full_name from localStorage -- identity/authorization is server-side only (Section 4)', () => {
    const apiSrc = readFileSync(join(FEATURE_ROOT, 'api', 'operationalApi.js'), 'utf-8')
    // Only code lines matter here -- the module's own doc comment
    // legitimately DISCUSSES role/email (explaining why they are never
    // read), so this checks for an actual `localStorage.getItem('role')`-
    // style call, not the bare word "role" appearing anywhere at all.
    expect(apiSrc).not.toMatch(/localStorage\.getItem\(\s*['"](role|email|full_name)['"]/)
  })
})

describe('GEO-INT-03H-02: token is never logged or otherwise leaked', () => {
  const originalWindow = global.window
  const originalFetch = global.fetch
  const originalConsole = { log: console.log, warn: console.warn, error: console.error }

  afterEach(() => {
    global.window = originalWindow
    global.fetch = originalFetch
    console.log = originalConsole.log
    console.warn = originalConsole.warn
    console.error = originalConsole.error
  })

  it('a successful request never logs the token value to the console', async () => {
    global.window = { localStorage: { getItem: vi.fn().mockReturnValue('super-secret-token-value') } }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: 'OK' } }))
    const logSpy = vi.fn()
    console.log = logSpy
    console.warn = logSpy
    console.error = logSpy

    await fetchOperationalContext()

    for (const call of logSpy.mock.calls) {
      expect(JSON.stringify(call)).not.toContain('super-secret-token-value')
    }
  })

  it('a failed request (e.g. 401) never includes the token value in the thrown error message', async () => {
    global.window = { localStorage: { getItem: vi.fn().mockReturnValue('super-secret-token-value') } }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 }))

    let caught
    try {
      await fetchOperationalContext()
    } catch (err) {
      caught = err
    }
    expect(caught.message).not.toContain('super-secret-token-value')
  })

  it('no operational-feature UI component (status chip / popup) source ever references a token/localStorage read -- the token never reaches a render path', () => {
    for (const relativePath of ['components/OperationalStatusChip.jsx', 'components/OperationalContextPopup.jsx']) {
      const src = readFileSync(join(FEATURE_ROOT, relativePath), 'utf-8')
      expect(src).not.toContain('localStorage')
      expect(src).not.toMatch(/\btoken\b/)
    }
  })
})

describe('GEO-INT-03-API-02: status mapping', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window
  beforeEach(() => {
    global.window = { localStorage: { getItem: vi.fn().mockReturnValue(null) } }
  })
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('200 is parsed and returned verbatim', async () => {
    const body = { status: 'OK', farms: [] }
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body }))
    await expect(fetchOperationalContext()).resolves.toEqual(body)
  })

  it('401 maps to SESSION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 }))
    await expect(fetchOperationalContext()).rejects.toMatchObject({ operationalStatus: OPERATIONAL_FETCH_STATUS.SESSION_REQUIRED })
  })

  it('403 maps to FORBIDDEN', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 403 }))
    await expect(fetchOperationalContext()).rejects.toMatchObject({ operationalStatus: OPERATIONAL_FETCH_STATUS.FORBIDDEN })
  })

  it('404 maps to HOST_COMPOSITION_REQUIRED', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 404 }))
    await expect(fetchOperationalContext()).rejects.toMatchObject({ operationalStatus: OPERATIONAL_FETCH_STATUS.HOST_COMPOSITION_REQUIRED })
  })

  it('409 maps to OPERATIONAL_UNAVAILABLE', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 409 }))
    await expect(fetchOperationalContext()).rejects.toMatchObject({ operationalStatus: OPERATIONAL_FETCH_STATUS.OPERATIONAL_UNAVAILABLE })
  })

  it('a thrown network failure maps to NETWORK_ERROR, never a raw stack trace message', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    let caught
    try {
      await fetchOperationalContext()
    } catch (err) {
      caught = err
    }
    expect(caught.operationalStatus).toBe(OPERATIONAL_FETCH_STATUS.NETWORK_ERROR)
    expect(caught.message).not.toContain('TypeError')
    expect(caught.message).not.toContain('Failed to fetch')
  })

  it('supports AbortSignal -- a deliberate abort re-throws AbortError unchanged, not remapped to NETWORK_ERROR', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    global.fetch = vi.fn().mockRejectedValue(abortError)
    const controller = new AbortController()
    await expect(fetchOperationalContext({ signal: controller.signal })).rejects.toBe(abortError)
  })

  it('an unexpected 5xx also maps to OPERATIONAL_UNAVAILABLE (transient), never thrown as an unclassified error', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500 }))
    await expect(fetchOperationalContext()).rejects.toMatchObject({ operationalStatus: OPERATIONAL_FETCH_STATUS.OPERATIONAL_UNAVAILABLE })
  })
})

describe('GEO-OWNED-FINAL-08-API-02: hasTokenDisappeared (Section 7 logout detection)', () => {
  it('reports a disappearance when a real token is now gone', () => {
    expect(hasTokenDisappeared('real-token-123', null)).toBe(true)
  })

  it('does not report a disappearance when there was never a token to begin with', () => {
    expect(hasTokenDisappeared(null, null)).toBe(false)
  })

  it('does not report a disappearance when the token is still present', () => {
    expect(hasTokenDisappeared('real-token-123', 'real-token-123')).toBe(false)
  })

  it('does not report a disappearance when a token appears where there was none (login, not logout)', () => {
    expect(hasTokenDisappeared(null, 'real-token-123')).toBe(false)
  })

  it('a token CHANGING (not disappearing) is not reported as a disappearance', () => {
    expect(hasTokenDisappeared('old-token', 'new-token')).toBe(false)
  })
})

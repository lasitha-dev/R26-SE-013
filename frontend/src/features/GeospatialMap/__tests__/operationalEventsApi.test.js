import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { OPERATIONAL_EVENTS_FETCH_STATUS, openOperationalEventStream, parseSseMessage } from '../api/operationalEventsApi'

describe('GEO-LIVE-05-EVENTS-API-01: parseSseMessage (pure)', () => {
  it('parses an event/data pair', () => {
    const parsed = parseSseMessage('event: clinical_event\ndata: {"case_id":"C1"}')
    expect(parsed).toEqual({ eventType: 'clinical_event', data: { case_id: 'C1' } })
  })

  it('defaults eventType to "message" when no event: line is present', () => {
    const parsed = parseSseMessage('data: {"x":1}')
    expect(parsed.eventType).toBe('message')
  })

  it('returns null when there is no data: line at all', () => {
    expect(parseSseMessage('event: heartbeat')).toBeNull()
  })

  it('returns null (never throws) on malformed JSON', () => {
    expect(parseSseMessage('event: clinical_event\ndata: {not json')).toBeNull()
  })

  it('joins multiple data: lines (SSE multi-line data per spec)', () => {
    const parsed = parseSseMessage('event: clinical_event\ndata: {"a":1,\ndata: "b":2}')
    expect(parsed.data).toEqual({ a: 1, b: 2 })
  })
})

function sseBody(frames) {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame))
      controller.close()
    },
  })
}

describe('GEO-LIVE-05-EVENTS-API-02: openOperationalEventStream', () => {
  const originalFetch = global.fetch
  const originalWindow = global.window

  beforeEach(() => {
    global.window = { localStorage: { getItem: vi.fn().mockReturnValue('real-token-123') } }
  })
  afterEach(() => {
    global.fetch = originalFetch
    global.window = originalWindow
  })

  it('attaches the bearer token, dispatches ready/heartbeat/clinical_event callbacks in order', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: sseBody([
        'event: ready\ndata: {"transport":"push"}\n\n',
        'event: heartbeat\ndata: {}\n\n',
        'event: clinical_event\ndata: {"case_id":"C1","event_id":"vcc:C1:x"}\n\n',
      ]),
    })

    const calls = []
    await openOperationalEventStream({
      onReady: (d) => calls.push(['ready', d]),
      onHeartbeat: () => calls.push(['heartbeat']),
      onEvent: (e) => calls.push(['event', e]),
    })

    expect(global.window.localStorage.getItem).toHaveBeenCalled()
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer real-token-123')

    expect(calls).toEqual([
      ['ready', { transport: 'push' }],
      ['heartbeat'],
      ['event', { case_id: 'C1', event_id: 'vcc:C1:x' }],
    ])
  })

  it('a 401 rejects tagged SESSION_REQUIRED, never silently succeeds', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, body: null })
    await expect(openOperationalEventStream({})).rejects.toMatchObject({
      operationalEventsStatus: OPERATIONAL_EVENTS_FETCH_STATUS.SESSION_REQUIRED,
    })
  })

  it('a 403 rejects tagged FORBIDDEN', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 403, body: null })
    await expect(openOperationalEventStream({})).rejects.toMatchObject({
      operationalEventsStatus: OPERATIONAL_EVENTS_FETCH_STATUS.FORBIDDEN,
    })
  })

  it('a 404 rejects tagged HOST_COMPOSITION_REQUIRED (route not mounted yet)', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, body: null })
    await expect(openOperationalEventStream({})).rejects.toMatchObject({
      operationalEventsStatus: OPERATIONAL_EVENTS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED,
    })
  })

  it('sends no Authorization header when no token is stored', async () => {
    global.window.localStorage.getItem = vi.fn().mockReturnValue(null)
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, body: sseBody([]) })
    await openOperationalEventStream({})
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBeUndefined()
  })
})

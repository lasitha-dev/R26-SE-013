/**
 * GEO-LIVE-05 Section 9: thin client for the Geospatial-owned operational-
 * EVENTS endpoint (`GET /api/geospatial/operational-events/stream`,
 * authenticated server-sent-event stream -- `operational_events_router_factory.py`).
 * Mirrors `operationalApi.js`'s conventions (thin wrapper, real host
 * `"token"` localStorage key, never invents a fallback value) but for a
 * long-lived streaming response instead of one JSON request/response.
 *
 * A plain `EventSource` cannot attach a custom `Authorization` header, so
 * this uses `fetch` + a manual `ReadableStream` reader and hand-rolls
 * `text/event-stream` framing (`event: ...\ndata: ...\n\n`) -- exactly
 * the same framing `operational_events_router_factory.py` emits.
 */

import { readAuthToken } from './operationalApi'
import { GEOSPATIAL_API_PREFIX } from './apiConfig'

export const OPERATIONAL_EVENTS_FETCH_STATUS = {
  SESSION_REQUIRED: 'SESSION_REQUIRED', // 401
  FORBIDDEN: 'FORBIDDEN', // 403
  HOST_COMPOSITION_REQUIRED: 'HOST_COMPOSITION_REQUIRED', // 404 -- route not mounted yet on this branch
  STREAM_UNAVAILABLE: 'STREAM_UNAVAILABLE', // any other non-2xx, or a response with no readable body
  NETWORK_ERROR: 'NETWORK_ERROR', // fetch itself failed (offline, DNS, CORS, etc.)
}

function taggedError(message, operationalEventsStatus) {
  const error = new Error(message)
  error.operationalEventsStatus = operationalEventsStatus
  return error
}

/**
 * Parses ONE complete SSE message (everything up to, but not including,
 * the blank-line terminator) into `{ eventType, data }`, or `null` if the
 * message carries no `data:` line (never thrown -- a malformed frame is
 * simply not delivered to a listener, mirroring this feature's "never
 * repair, never guess" convention). `eventType` defaults to `'message'`
 * per the SSE spec when no `event:` line is present -- this stream always
 * sends one, but a resilient parser never assumes that.
 */
export function parseSseMessage(rawMessage) {
  let eventType = 'message'
  const dataLines = []
  for (const line of rawMessage.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }
  if (dataLines.length === 0) return null
  let data
  try {
    data = JSON.parse(dataLines.join('\n'))
  } catch {
    return null
  }
  return { eventType, data }
}

/**
 * Opens the stream and calls `onReady({ transport })` once (Section 4/9 --
 * the honest push-vs-delta_refresh signal), `onEvent(verifiedClinicalEvent)`
 * for every `clinical_event` frame, and `onHeartbeat()` for every
 * `event: heartbeat` keepalive frame -- never invents any of these; a
 * frame this parser cannot recognize is silently ignored.
 *
 * Resolves normally when the server closes the stream; rejects (tagged
 * `.operationalEventsStatus`) on a connect-time failure (401/403/404/
 * network). `options.signal` aborts the underlying fetch/read loop --
 * the caller (Section 8 "abort/disconnect aware") is responsible for
 * reconnect policy; this function makes exactly one connection attempt.
 */
export async function openOperationalEventStream({ signal, onReady, onEvent, onHeartbeat } = {}) {
  const token = readAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  let response
  try {
    response = await fetch(`${GEOSPATIAL_API_PREFIX}/operational-events/stream`, { headers, signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw taggedError('Could not reach the operational events stream.', OPERATIONAL_EVENTS_FETCH_STATUS.NETWORK_ERROR)
  }

  if (response.status === 401) {
    throw taggedError('Session required.', OPERATIONAL_EVENTS_FETCH_STATUS.SESSION_REQUIRED)
  }
  if (response.status === 403) {
    throw taggedError('Veterinarian access required.', OPERATIONAL_EVENTS_FETCH_STATUS.FORBIDDEN)
  }
  if (response.status === 404) {
    throw taggedError('Operational events stream is not connected yet.', OPERATIONAL_EVENTS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED)
  }
  if (!response.ok || !response.body) {
    throw taggedError('Operational events stream request failed.', OPERATIONAL_EVENTS_FETCH_STATUS.STREAM_UNAVAILABLE)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const rawMessage = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const parsed = parseSseMessage(rawMessage)
        if (parsed) {
          if (parsed.eventType === 'ready') onReady?.(parsed.data)
          else if (parsed.eventType === 'heartbeat') onHeartbeat?.()
          else if (parsed.eventType === 'clinical_event') onEvent?.(parsed.data)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } catch (err) {
    if (err?.name === 'AbortError' || signal?.aborted) throw taggedError('Stream aborted.', OPERATIONAL_EVENTS_FETCH_STATUS.NETWORK_ERROR)
    throw taggedError('Operational events stream was interrupted.', OPERATIONAL_EVENTS_FETCH_STATUS.STREAM_UNAVAILABLE)
  } finally {
    reader.releaseLock()
  }
}

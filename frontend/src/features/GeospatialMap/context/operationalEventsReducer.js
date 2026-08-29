/**
 * GEO-LIVE-05 Section 9/11: pure, framework-free operational-EVENTS
 * connection + notification state machine -- same split this feature
 * already uses for every other stateful concern (`operationalRefreshReducer.js`
 * + `useOperationalContext.js`). `useVerifiedClinicalEvents.js` is the only
 * caller of the impure side (real `fetch`/`ReadableStream`/RAF); it
 * contains no state-transition DECISION logic of its own -- every decision
 * below is made here, independently unit-testable without any DOM/timer/
 * fetch.
 */

export const EVENT_STREAM_STATE = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  SESSION_REQUIRED: 'session_required',
  FORBIDDEN: 'forbidden',
  DISCONNECTED: 'disconnected',
}

export const TRANSPORT_MODE = {
  PUSH: 'push',
  DELTA_REFRESH: 'delta_refresh',
}

/** Section 9 "stale/fallback" required state, exposed as one derived
 * label rather than a separate connection-state enum value -- it can
 * apply to a genuinely CONNECTED stream (fallback transport, or a
 * heartbeat gap), which `EVENT_STREAM_STATE.CONNECTED` alone cannot
 * distinguish; keeping it derived (never stored) means it can never drift
 * out of sync with `state`/`transportMode`/`lastActivityAt`. */
export function deriveDisplayState(state, transportMode, isStale) {
  if (state === EVENT_STREAM_STATE.CONNECTED && (transportMode === TRANSPORT_MODE.DELTA_REFRESH || isStale)) {
    return 'stale_fallback'
  }
  return state
}

/** Section 9 "no fake LIVE wording when fallback polling is active". */
export function isLiveWordingHonest(state, transportMode) {
  return state === EVENT_STREAM_STATE.CONNECTED && transportMode === TRANSPORT_MODE.PUSH
}

const NON_RECONNECTING_STATES = new Set([EVENT_STREAM_STATE.SESSION_REQUIRED, EVENT_STREAM_STATE.FORBIDDEN])

export function shouldAttemptReconnect(state) {
  return !NON_RECONNECTING_STATES.has(state)
}

/** Section 8 "reconnectable": capped exponential backoff, deterministic
 * and pure -- `attempt` is a plain 0-based counter the caller increments
 * per failed connection. */
export function nextReconnectDelayMs(attempt, { baseMs = 1000, maxMs = 30000 } = {}) {
  const exponential = baseMs * 2 ** Math.max(0, attempt)
  return Math.min(exponential, maxMs)
}

export const initialEventStreamState = {
  state: EVENT_STREAM_STATE.CONNECTING,
  transportMode: null,
  reconnectAttempt: 0,
  lastActivityAt: null,
  notifications: [], // [{ eventId, event, receivedAt, read }], newest first
}

export function connectionReady(prev, { transportMode }, now) {
  return { ...prev, state: EVENT_STREAM_STATE.CONNECTED, transportMode, reconnectAttempt: 0, lastActivityAt: now }
}

export function heartbeatReceived(prev, now) {
  return { ...prev, lastActivityAt: now }
}

/** `reason` is one of `api/operationalEventsApi.js`'s
 * `OPERATIONAL_EVENTS_FETCH_STATUS` values, or `null` for a clean stream
 * end (server closed normally). */
export function connectionLost(prev, reason) {
  if (reason === 'SESSION_REQUIRED') {
    return { ...prev, state: EVENT_STREAM_STATE.SESSION_REQUIRED, transportMode: null }
  }
  if (reason === 'FORBIDDEN') {
    return { ...prev, state: EVENT_STREAM_STATE.FORBIDDEN, transportMode: null }
  }
  return {
    ...prev,
    state: EVENT_STREAM_STATE.RECONNECTING,
    transportMode: null,
    reconnectAttempt: prev.reconnectAttempt + 1,
  }
}

export function streamDisconnectedByCaller(prev) {
  return { ...prev, state: EVENT_STREAM_STATE.DISCONNECTED, transportMode: null }
}

/** Section 11 "deduplicated by event_id, timestamped, read/unread
 * session-local". A duplicate event_id still refreshes `lastActivityAt`
 * (proof of a live connection) but is never added twice to the list. */
export function eventReceived(prev, event, now) {
  const alreadyPresent = prev.notifications.some((n) => n.eventId === event.event_id)
  if (alreadyPresent) {
    return { ...prev, lastActivityAt: now }
  }
  const notification = { eventId: event.event_id, event, receivedAt: now, read: false }
  return { ...prev, lastActivityAt: now, notifications: [notification, ...prev.notifications] }
}

export function dismissNotification(prev, eventId) {
  return { ...prev, notifications: prev.notifications.filter((n) => n.eventId !== eventId) }
}

export function markNotificationRead(prev, eventId) {
  return {
    ...prev,
    notifications: prev.notifications.map((n) => (n.eventId === eventId ? { ...n, read: true } : n)),
  }
}

/** Section 9 staleness: no activity (event or heartbeat) within
 * `thresholdMs` of a CONNECTED stream. Pure -- `now`/`lastActivityAt` are
 * both caller-supplied monotonic milliseconds, never read from a global
 * here. */
export function isStaleNow(lastActivityAt, now, thresholdMs) {
  if (lastActivityAt == null) return false
  return now - lastActivityAt >= thresholdMs
}

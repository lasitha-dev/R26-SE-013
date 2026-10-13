import { describe, expect, it } from 'vitest'

import {
  EVENT_STREAM_STATE,
  TRANSPORT_MODE,
  connectionLost,
  connectionReady,
  deriveDisplayState,
  dismissNotification,
  eventReceived,
  heartbeatReceived,
  initialEventStreamState,
  isLiveWordingHonest,
  isStaleNow,
  markNotificationRead,
  nextReconnectDelayMs,
  shouldAttemptReconnect,
  streamDisconnectedByCaller,
} from '../context/operationalEventsReducer'

const EVENT = {
  event_id: 'vcc:C1:2026-01-02 10:00:00',
  event_type: 'VERIFIED_CLINICAL_CONTEXT_CREATED',
  case_id: 'C1',
  farm_id: 'F1',
  disease: 'LSD',
  verified_at: '2026-01-02 10:00:00',
}

describe('GEO-LIVE-05-EVENTS-01: initial state / connection lifecycle', () => {
  it('starts connecting with no notifications', () => {
    expect(initialEventStreamState.state).toBe(EVENT_STREAM_STATE.CONNECTING)
    expect(initialEventStreamState.notifications).toEqual([])
  })

  it('connectionReady moves to connected, resets reconnectAttempt, records the real transport', () => {
    const prev = { ...initialEventStreamState, reconnectAttempt: 3 }
    const next = connectionReady(prev, { transportMode: TRANSPORT_MODE.PUSH }, 1000)
    expect(next.state).toBe(EVENT_STREAM_STATE.CONNECTED)
    expect(next.transportMode).toBe(TRANSPORT_MODE.PUSH)
    expect(next.reconnectAttempt).toBe(0)
    expect(next.lastActivityAt).toBe(1000)
  })

  it('SESSION_REQUIRED and FORBIDDEN are terminal -- shouldAttemptReconnect is false', () => {
    expect(shouldAttemptReconnect(EVENT_STREAM_STATE.SESSION_REQUIRED)).toBe(false)
    expect(shouldAttemptReconnect(EVENT_STREAM_STATE.FORBIDDEN)).toBe(false)
    expect(shouldAttemptReconnect(EVENT_STREAM_STATE.RECONNECTING)).toBe(true)
  })

  it('a network failure increments reconnectAttempt and moves to reconnecting', () => {
    const prev = { ...initialEventStreamState, reconnectAttempt: 0 }
    const next = connectionLost(prev, 'NETWORK_ERROR')
    expect(next.state).toBe(EVENT_STREAM_STATE.RECONNECTING)
    expect(next.reconnectAttempt).toBe(1)
  })

  it('SESSION_REQUIRED failure stops the stream, never reconnecting', () => {
    const next = connectionLost(initialEventStreamState, 'SESSION_REQUIRED')
    expect(next.state).toBe(EVENT_STREAM_STATE.SESSION_REQUIRED)
  })

  it('streamDisconnectedByCaller (logout) is a distinct terminal state', () => {
    const next = streamDisconnectedByCaller({ ...initialEventStreamState, state: EVENT_STREAM_STATE.CONNECTED })
    expect(next.state).toBe(EVENT_STREAM_STATE.DISCONNECTED)
  })
})

describe('GEO-LIVE-05-EVENTS-02: reconnect backoff is deterministic and capped', () => {
  it('grows exponentially from the base', () => {
    expect(nextReconnectDelayMs(0, { baseMs: 1000, maxMs: 30000 })).toBe(1000)
    expect(nextReconnectDelayMs(1, { baseMs: 1000, maxMs: 30000 })).toBe(2000)
    expect(nextReconnectDelayMs(2, { baseMs: 1000, maxMs: 30000 })).toBe(4000)
  })

  it('never exceeds maxMs', () => {
    expect(nextReconnectDelayMs(20, { baseMs: 1000, maxMs: 30000 })).toBe(30000)
  })
})

describe('GEO-LIVE-05-EVENTS-03: notification dedup by event_id', () => {
  it('a new event_id is added, newest first', () => {
    const next = eventReceived(initialEventStreamState, EVENT, 1000)
    expect(next.notifications).toHaveLength(1)
    expect(next.notifications[0].eventId).toBe(EVENT.event_id)
    expect(next.notifications[0].read).toBe(false)
  })

  it('a duplicate event_id is not added twice, but activity timestamp still updates', () => {
    const once = eventReceived(initialEventStreamState, EVENT, 1000)
    const twice = eventReceived(once, EVENT, 2000)
    expect(twice.notifications).toHaveLength(1)
    expect(twice.lastActivityAt).toBe(2000)
  })

  it('dismissNotification removes exactly one notification by id', () => {
    const withEvent = eventReceived(initialEventStreamState, EVENT, 1000)
    const dismissed = dismissNotification(withEvent, EVENT.event_id)
    expect(dismissed.notifications).toEqual([])
  })

  it('markNotificationRead flips only the matching notification', () => {
    const withEvent = eventReceived(initialEventStreamState, EVENT, 1000)
    const read = markNotificationRead(withEvent, EVENT.event_id)
    expect(read.notifications[0].read).toBe(true)
  })

  it('heartbeatReceived updates activity without touching notifications', () => {
    const withEvent = eventReceived(initialEventStreamState, EVENT, 1000)
    const next = heartbeatReceived(withEvent, 5000)
    expect(next.lastActivityAt).toBe(5000)
    expect(next.notifications).toBe(withEvent.notifications)
  })
})

describe('GEO-LIVE-05-EVENTS-04: honest LIVE wording / stale-fallback display', () => {
  it('LIVE wording is honest only when connected AND transport is push', () => {
    expect(isLiveWordingHonest(EVENT_STREAM_STATE.CONNECTED, TRANSPORT_MODE.PUSH)).toBe(true)
    expect(isLiveWordingHonest(EVENT_STREAM_STATE.CONNECTED, TRANSPORT_MODE.DELTA_REFRESH)).toBe(false)
    expect(isLiveWordingHonest(EVENT_STREAM_STATE.RECONNECTING, TRANSPORT_MODE.PUSH)).toBe(false)
  })

  it('deriveDisplayState shows stale_fallback for a connected delta_refresh stream, never plain "connected"', () => {
    expect(deriveDisplayState(EVENT_STREAM_STATE.CONNECTED, TRANSPORT_MODE.DELTA_REFRESH, false)).toBe('stale_fallback')
  })

  it('deriveDisplayState shows stale_fallback for a connected-but-stale push stream', () => {
    expect(deriveDisplayState(EVENT_STREAM_STATE.CONNECTED, TRANSPORT_MODE.PUSH, true)).toBe('stale_fallback')
  })

  it('deriveDisplayState passes through a genuinely live connected push stream unchanged', () => {
    expect(deriveDisplayState(EVENT_STREAM_STATE.CONNECTED, TRANSPORT_MODE.PUSH, false)).toBe(EVENT_STREAM_STATE.CONNECTED)
  })

  it('isStaleNow is false with no prior activity, true once the threshold elapses', () => {
    expect(isStaleNow(null, 100000, 45000)).toBe(false)
    expect(isStaleNow(1000, 40000, 45000)).toBe(false)
    expect(isStaleNow(1000, 46001, 45000)).toBe(true)
  })
})

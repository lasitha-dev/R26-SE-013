import { describe, expect, it } from 'vitest'

import {
  OPERATIONAL_STATE,
  REFRESH_INTERVAL_MS,
  applyFetchResult,
  beginFetch,
  initialOperationalRefreshState,
  shouldFetchOnTick,
  shouldPoll,
} from '../context/operationalRefreshReducer'

describe('GEO-INT-03-REFRESH-01: initial fetch / loading semantics', () => {
  it('the initial state is idle with no data', () => {
    expect(initialOperationalRefreshState.state).toBe(OPERATIONAL_STATE.IDLE)
    expect(initialOperationalRefreshState.data).toBeNull()
  })

  it('beginFetch moves idle -> loading (the only visible loading transition)', () => {
    expect(beginFetch(initialOperationalRefreshState).state).toBe(OPERATIONAL_STATE.LOADING)
  })

  it('beginFetch does NOT re-enter loading once already connected -- an auto-refresh never flickers the display', () => {
    const connected = { state: OPERATIONAL_STATE.CONNECTED, data: { farms: [] }, lastRefreshedAt: 1000 }
    expect(beginFetch(connected)).toBe(connected)
  })
})

describe('GEO-INT-03-REFRESH-02: successful result renders and records last refresh', () => {
  it('a successful fetch sets CONNECTED, stores the data, and records lastRefreshedAt', () => {
    const next = applyFetchResult(initialOperationalRefreshState, { ok: true, data: { farms: ['x'] } }, 12345)
    expect(next.state).toBe(OPERATIONAL_STATE.CONNECTED)
    expect(next.data).toEqual({ farms: ['x'] })
    expect(next.lastRefreshedAt).toBe(12345)
  })
})

describe('GEO-INT-03-REFRESH-03: 401/403/404 stop polling and are terminal', () => {
  it('SESSION_REQUIRED (401) stops polling and clears data', () => {
    const prev = { state: OPERATIONAL_STATE.CONNECTED, data: { farms: ['x'] }, lastRefreshedAt: 1 }
    const next = applyFetchResult(prev, { ok: false, operationalStatus: 'SESSION_REQUIRED' }, 2)
    expect(next.state).toBe(OPERATIONAL_STATE.SESSION_REQUIRED)
    expect(next.data).toBeNull()
    expect(shouldPoll(next.state)).toBe(false)
  })

  it('FORBIDDEN (403) stops polling and clears data', () => {
    const prev = { state: OPERATIONAL_STATE.CONNECTED, data: { farms: ['x'] }, lastRefreshedAt: 1 }
    const next = applyFetchResult(prev, { ok: false, operationalStatus: 'FORBIDDEN' }, 2)
    expect(next.state).toBe(OPERATIONAL_STATE.FORBIDDEN)
    expect(next.data).toBeNull()
    expect(shouldPoll(next.state)).toBe(false)
  })

  it('HOST_COMPOSITION_REQUIRED (404) stops polling -- never re-polls a permanent 404 every interval', () => {
    const next = applyFetchResult(initialOperationalRefreshState, { ok: false, operationalStatus: 'HOST_COMPOSITION_REQUIRED' }, 2)
    expect(next.state).toBe(OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED)
    expect(shouldPoll(next.state)).toBe(false)
  })
})

describe('GEO-INT-03-REFRESH-04: transient failures retain stale previous data and keep polling', () => {
  it('OPERATIONAL_UNAVAILABLE (409/5xx) after a previous success marks STALE and keeps the old data', () => {
    const prev = { state: OPERATIONAL_STATE.CONNECTED, data: { farms: ['x'] }, lastRefreshedAt: 100 }
    const next = applyFetchResult(prev, { ok: false, operationalStatus: 'OPERATIONAL_UNAVAILABLE' }, 200)
    expect(next.state).toBe(OPERATIONAL_STATE.STALE)
    expect(next.data).toEqual({ farms: ['x'] })
    expect(next.lastRefreshedAt).toBe(100) // unchanged -- this attempt was not a success
    expect(shouldPoll(next.state)).toBe(true)
  })

  it('NETWORK_ERROR after a previous success also marks STALE, keeping data', () => {
    const prev = { state: OPERATIONAL_STATE.CONNECTED, data: { farms: ['x'] }, lastRefreshedAt: 100 }
    const next = applyFetchResult(prev, { ok: false, operationalStatus: 'NETWORK_ERROR' }, 200)
    expect(next.state).toBe(OPERATIONAL_STATE.STALE)
    expect(next.data).toEqual({ farms: ['x'] })
  })

  it('a transient failure with NO previous success is a plain ERROR, not STALE (nothing to keep)', () => {
    const next = applyFetchResult(initialOperationalRefreshState, { ok: false, operationalStatus: 'OPERATIONAL_UNAVAILABLE' }, 100)
    expect(next.state).toBe(OPERATIONAL_STATE.ERROR)
    expect(next.data).toBeNull()
    expect(shouldPoll(next.state)).toBe(true)
  })
})

describe('GEO-INT-03-REFRESH-05: 60s controlled tick, never faster than 30s', () => {
  it('REFRESH_INTERVAL_MS is 60000 (60s)', () => {
    expect(REFRESH_INTERVAL_MS).toBe(60000)
  })

  it('REFRESH_INTERVAL_MS is never shorter than 30s (Section 14 floor)', () => {
    expect(REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(30000)
  })

  it('fetches immediately when there is no prior attempt', () => {
    expect(shouldFetchOnTick(OPERATIONAL_STATE.IDLE, null, 0)).toBe(true)
  })

  it('does not fetch before the interval has elapsed', () => {
    expect(shouldFetchOnTick(OPERATIONAL_STATE.CONNECTED, 1000, 1000 + REFRESH_INTERVAL_MS - 1)).toBe(false)
  })

  it('fetches once the interval has fully elapsed', () => {
    expect(shouldFetchOnTick(OPERATIONAL_STATE.CONNECTED, 1000, 1000 + REFRESH_INTERVAL_MS)).toBe(true)
  })

  it('never fetches on tick while in a stopped-polling state (401/403/404), regardless of elapsed time', () => {
    expect(shouldFetchOnTick(OPERATIONAL_STATE.SESSION_REQUIRED, 0, 10 * REFRESH_INTERVAL_MS)).toBe(false)
    expect(shouldFetchOnTick(OPERATIONAL_STATE.FORBIDDEN, 0, 10 * REFRESH_INTERVAL_MS)).toBe(false)
    expect(shouldFetchOnTick(OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED, 0, 10 * REFRESH_INTERVAL_MS)).toBe(false)
  })

  it('a STALE state keeps polling on tick', () => {
    expect(shouldFetchOnTick(OPERATIONAL_STATE.STALE, 0, REFRESH_INTERVAL_MS)).toBe(true)
  })
})

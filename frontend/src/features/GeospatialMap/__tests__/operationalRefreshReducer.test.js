import { describe, expect, it } from 'vitest'

import {
  MIN_REFRESH_INTERVAL_MS,
  OPERATIONAL_STATE,
  REFRESH_INTERVAL_MS,
  applyFetchResult,
  beginFetch,
  initialOperationalRefreshState,
  shouldPauseForHiddenTab,
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

describe('GEO-HYBRID-LIVE-SYNC-08-REFRESH-05: ~2s fallback reconciliation cycle, never faster than the floor', () => {
  it('REFRESH_INTERVAL_MS is 2000 (2s) -- the hybrid model\'s fallback cadence', () => {
    expect(REFRESH_INTERVAL_MS).toBe(2000)
  })

  it('REFRESH_INTERVAL_MS is never shorter than MIN_REFRESH_INTERVAL_MS (a hard floor against a request storm)', () => {
    expect(REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(MIN_REFRESH_INTERVAL_MS)
    expect(MIN_REFRESH_INTERVAL_MS).toBeGreaterThanOrEqual(1000)
  })

  it('shouldPoll permits the three transient/steady states to keep the reconciliation cycle scheduling', () => {
    expect(shouldPoll(OPERATIONAL_STATE.IDLE)).toBe(true)
    expect(shouldPoll(OPERATIONAL_STATE.CONNECTED)).toBe(true)
    expect(shouldPoll(OPERATIONAL_STATE.STALE)).toBe(true)
  })

  it('shouldPoll is false for exactly the three terminal 401/403/404 states -- the cycle must stop rescheduling', () => {
    expect(shouldPoll(OPERATIONAL_STATE.SESSION_REQUIRED)).toBe(false)
    expect(shouldPoll(OPERATIONAL_STATE.FORBIDDEN)).toBe(false)
    expect(shouldPoll(OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED)).toBe(false)
  })
})

describe('GEO-LIVE-UPDATE-RECOVERY-06: hidden-tab pause', () => {
  it('pauses when the document is hidden', () => {
    expect(shouldPauseForHiddenTab('hidden')).toBe(true)
  })

  it('does not pause when visible', () => {
    expect(shouldPauseForHiddenTab('visible')).toBe(false)
  })

  it('does not pause when visibility is unknown (non-browser environment)', () => {
    expect(shouldPauseForHiddenTab(undefined)).toBe(false)
  })
})

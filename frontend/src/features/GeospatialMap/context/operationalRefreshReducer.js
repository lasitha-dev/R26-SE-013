/**
 * GEO-INT-03 Section 14/15: pure, framework-free operational-context
 * refresh state machine -- same split this feature already uses for
 * every other stateful concern (`snapshotAssembly.js`'s pure reducer +
 * `state/useGeospatialSnapshot.js`'s thin hook wiring it to real
 * fetch/transport; `outbreakSelectionReducer.js` + `GeospatialContext.jsx`).
 * `useOperationalContext.js` is the only caller of the impure side (real
 * `requestAnimationFrame`/`fetch`/`AbortController`); it contains no
 * state-transition DECISION logic of its own -- every decision below is
 * made here, independently unit-testable in this repo's Node-only Vitest
 * environment without any DOM/timer/fetch.
 */

export const OPERATIONAL_STATE = {
  IDLE: 'idle',
  LOADING: 'loading',
  CONNECTED: 'connected',
  STALE: 'stale',
  SESSION_REQUIRED: 'session_required',
  FORBIDDEN: 'forbidden',
  HOST_COMPOSITION_REQUIRED: 'host_composition_required',
  OPERATIONAL_UNAVAILABLE: 'operational_unavailable',
  ERROR: 'error',
}

// Section 14: 60s controlled refresh -- never shorter than 30s.
export const REFRESH_INTERVAL_MS = 60000

export const initialOperationalRefreshState = {
  state: OPERATIONAL_STATE.IDLE,
  data: null,
  lastRefreshedAt: null,
}

/** Section 15: exactly the three "stop polling" states (401/403/404). */
const NON_POLLING_STATES = new Set([
  OPERATIONAL_STATE.SESSION_REQUIRED,
  OPERATIONAL_STATE.FORBIDDEN,
  OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED,
])

export function shouldPoll(state) {
  return !NON_POLLING_STATES.has(state)
}

/**
 * Section 14/15: whether enough real time has passed since the last
 * fetch ATTEMPT to trigger the next controlled auto-refresh, and whether
 * the current state even permits one. `now`/`lastFetchAt` are both
 * monotonic milliseconds (`performance.now()`-style), injected by the
 * caller -- never read from a global here, keeping this pure/testable.
 */
export function shouldFetchOnTick(currentState, lastFetchAt, now, intervalMs = REFRESH_INTERVAL_MS) {
  if (!shouldPoll(currentState)) return false
  if (lastFetchAt == null) return true
  return now - lastFetchAt >= intervalMs
}

/**
 * A fetch attempt has just started. Section 15: only visually "loading"
 * (wipes the display) the very FIRST attempt -- a refresh that already
 * has good data (or is already past the initial attempt) stays on its
 * current state/data until the result is known, so a controlled 60s
 * auto-refresh never flickers the UI back to a bare loading state.
 */
export function beginFetch(prev) {
  if (prev.state === OPERATIONAL_STATE.IDLE) {
    return { ...prev, state: OPERATIONAL_STATE.LOADING }
  }
  return prev
}

/**
 * Section 15: the one place a fetch OUTCOME becomes the next state.
 * `result` is `{ ok: true, data }` on success, or
 * `{ ok: false, operationalStatus }` on failure -- `operationalStatus`
 * is one of `api/operationalApi.js`'s `OPERATIONAL_FETCH_STATUS` values,
 * never a raw `Error`/stack (the caller already reduced it).
 */
export function applyFetchResult(prev, result, now) {
  if (result.ok) {
    return { state: OPERATIONAL_STATE.CONNECTED, data: result.data, lastRefreshedAt: now }
  }

  switch (result.operationalStatus) {
    case 'SESSION_REQUIRED':
      // Section 15: 401 -- stop polling, session required. A prior
      // authorized snapshot must not keep showing once the session is gone.
      return { state: OPERATIONAL_STATE.SESSION_REQUIRED, data: null, lastRefreshedAt: prev.lastRefreshedAt }

    case 'FORBIDDEN':
      // Section 15: 403 -- stop polling, veterinarian access required.
      return { state: OPERATIONAL_STATE.FORBIDDEN, data: null, lastRefreshedAt: prev.lastRefreshedAt }

    case 'HOST_COMPOSITION_REQUIRED':
      // Section 15: 404 -- stop polling (never re-poll a permanent 404
      // every interval). This is the expected current-branch state.
      return { state: OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED, data: prev.data, lastRefreshedAt: prev.lastRefreshedAt }

    case 'OPERATIONAL_UNAVAILABLE':
    case 'NETWORK_ERROR':
    default: {
      // Section 15: a transient failure keeps polling. If there was a
      // previous success, its markers stay visible, only marked STALE --
      // never wiped. With no previous success yet, this is a plain ERROR.
      const hadPreviousSuccess = prev.data != null
      return {
        state: hadPreviousSuccess ? OPERATIONAL_STATE.STALE : OPERATIONAL_STATE.ERROR,
        data: prev.data,
        lastRefreshedAt: prev.lastRefreshedAt,
      }
    }
  }
}

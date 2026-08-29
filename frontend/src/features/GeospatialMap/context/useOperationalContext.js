/**
 * GEO-INT-03: thin hook wiring `operationalRefreshReducer.js` (pure
 * decision logic, fully unit-tested) to the real `fetchOperationalContext`
 * HTTP call, a `requestAnimationFrame`-driven tick (Section 14/17 --
 * setInterval/setTimeout are structurally forbidden anywhere in this
 * feature's source, `noAutoPolling.test.js`; this mirrors
 * `OutbreakMapPage.jsx`'s existing playback-loop pattern exactly: a
 * self-rescheduling RAF tick that compares elapsed real time against a
 * threshold), and `AbortController` (Section 6/17: request aborted on
 * unmount, previous in-flight request aborted before a new one starts).
 *
 * Contains no state-transition decision of its own -- every decision is
 * delegated to the pure reducer, so it stays covered by
 * `operationalRefreshReducer.test.js` even though this hook itself, like
 * every other data hook in this feature (`useNationalOutbreaks.js`,
 * `useSelectedOutbreakFrames.js`, `useGeospatialSnapshot.js`), is not
 * directly rendered/tested in this repo's Node-only Vitest environment
 * (no DOM/jsdom).
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { normalizeOperationalContext } from '../adapters/operationalContextAdapter'
import { fetchOperationalContext, hasTokenDisappeared, readAuthToken } from '../api/operationalApi'
import { applyFetchResult, beginFetch, initialOperationalRefreshState, shouldFetchOnTick } from './operationalRefreshReducer'

export { OPERATIONAL_STATE, REFRESH_INTERVAL_MS } from './operationalRefreshReducer'

export function useOperationalContext() {
  const [refreshState, setRefreshState] = useState(initialOperationalRefreshState)

  // Mirrors the latest state into a ref so the long-lived RAF tick
  // (defined once, mount-only effect below) always reads the CURRENT
  // state without needing to re-subscribe the effect on every change.
  const refreshStateRef = useRef(refreshState)
  useEffect(() => {
    refreshStateRef.current = refreshState
  }, [refreshState])

  const abortControllerRef = useRef(null)
  const lastFetchAtRef = useRef(null)
  const inFlightRef = useRef(false)
  const rafRef = useRef(null)
  const mountedRef = useRef(true)
  const lastKnownTokenRef = useRef(null)

  const runFetch = useCallback(() => {
    // Section 16/17: abort a still-in-flight request before starting a
    // new one -- manual refresh and the auto-refresh tick both go
    // through this same path, so neither can ever create a duplicate
    // outstanding request.
    if (inFlightRef.current) {
      abortControllerRef.current?.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller
    inFlightRef.current = true
    lastFetchAtRef.current = performance.now()
    lastKnownTokenRef.current = readAuthToken()

    setRefreshState((prev) => beginFetch(prev))

    fetchOperationalContext({ signal: controller.signal })
      .then((raw) => {
        inFlightRef.current = false
        if (!mountedRef.current || controller.signal.aborted) return
        const data = normalizeOperationalContext(raw)
        setRefreshState((prev) => applyFetchResult(prev, { ok: true, data }, Date.now()))
      })
      .catch((err) => {
        inFlightRef.current = false
        if (!mountedRef.current || err?.name === 'AbortError') return
        setRefreshState((prev) => applyFetchResult(prev, { ok: false, operationalStatus: err?.operationalStatus }, Date.now()))
      })
  }, [])

  useEffect(() => {
    mountedRef.current = true
    runFetch() // Section 28 test 19: initial fetch occurs once, on mount.

    const tick = () => {
      // Section 7 "logout/token disappearance: abort SSE/fetch stream
      // immediately" -- applies to this controlled request loop too, not
      // only the SSE stream. Checked before the interval-based
      // `shouldFetchOnTick` branch so a logout is never left waiting out
      // the rest of the current 60s cycle before the session is dropped.
      if (hasTokenDisappeared(lastKnownTokenRef.current, readAuthToken())) {
        lastKnownTokenRef.current = null
        if (inFlightRef.current) {
          abortControllerRef.current?.abort()
          inFlightRef.current = false
        }
        setRefreshState((prev) => applyFetchResult(prev, { ok: false, operationalStatus: 'SESSION_REQUIRED' }, Date.now()))
      } else {
        const now = performance.now()
        if (shouldFetchOnTick(refreshStateRef.current.state, lastFetchAtRef.current, now)) {
          runFetch()
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)

    return () => {
      mountedRef.current = false
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      abortControllerRef.current?.abort()
    }
    // Intentionally mount-once: a single RAF loop for the whole hook
    // lifetime (Section 17 "only one polling timer exists"), matching
    // `MapLibreCanvas.jsx`'s mount-once map-creation effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ...refreshState, refresh: runFetch }
}

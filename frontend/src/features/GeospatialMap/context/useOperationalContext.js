/**
 * GEO-INT-03 / GEO-HYBRID-LIVE-SYNC-08: thin hook wiring
 * `operationalRefreshReducer.js` (pure decision logic, fully unit-tested)
 * to the real `fetchOperationalContext` HTTP call, a single self-
 * scheduling `setTimeout` reconciliation cycle, and `AbortController`
 * (Section 6/17: request aborted on unmount, previous in-flight request
 * aborted before a new one starts).
 *
 * GEO-HYBRID-LIVE-SYNC-08 Phase 5: this is the ONE place in the feature
 * `setTimeout` is intentionally used, as the fallback operational-
 * reconciliation clock -- `noAutoPolling.test.js` still forbids
 * `setInterval` everywhere and forbids any recurring timer at all on the
 * scientific/historical side. `runFetch` is a single self-rescheduling
 * function used for EVERY trigger (initial mount, manual refresh, an
 * SSE-triggered refresh, AND the recurring cycle itself) -- the next
 * cycle is armed only after a call's own fetch settles successfully
 * (never a fixed-rate elapsed-time check against a ticking clock), so a
 * manual/SSE-triggered refresh that aborts an in-flight cycle can never
 * silently kill the recurring schedule: whichever call's fetch actually
 * settles is the one that reschedules. A slow backend naturally can't
 * produce overlapping requests either -- there is structurally never more
 * than one fetch in flight.
 *
 * Phase 6: the cycle stops rescheduling entirely while the tab is hidden
 * (a real `visibilitychange` listener, added/removed on mount/unmount)
 * and resumes with exactly one immediate cycle when the tab becomes
 * visible again -- the listener always clears any pending timer first, in
 * either direction, so a visibility flip can never leave two timers or a
 * stale scheduled request racing a fresh one.
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

import { GEO_TIMING, markTiming } from '../adapters/loadTiming'
import { normalizeOperationalContext } from '../adapters/operationalContextAdapter'
import { fetchOperationalContext, hasTokenDisappeared, readAuthToken } from '../api/operationalApi'
import { applyFetchResult, beginFetch, initialOperationalRefreshState, shouldPauseForHiddenTab, shouldPoll } from './operationalRefreshReducer'

export { OPERATIONAL_STATE, REFRESH_INTERVAL_MS } from './operationalRefreshReducer'

function currentVisibilityState() {
  return typeof document === 'undefined' ? undefined : document.visibilityState
}

export function useOperationalContext() {
  const [refreshState, setRefreshState] = useState(initialOperationalRefreshState)

  const abortControllerRef = useRef(null)
  const inFlightRef = useRef(false)
  const timeoutRef = useRef(null)
  const mountedRef = useRef(true)
  const lastKnownTokenRef = useRef(null)

  const runFetch = useCallback(() => {
    // Section 7 "logout/token disappearance: abort SSE/fetch stream
    // immediately" -- checked before starting a new request so a logout
    // is never left waiting out the rest of a cycle before the session is
    // dropped. Terminal, non-polling state -- clears any pending cycle.
    if (hasTokenDisappeared(lastKnownTokenRef.current, readAuthToken())) {
      lastKnownTokenRef.current = null
      if (inFlightRef.current) {
        abortControllerRef.current?.abort()
        inFlightRef.current = false
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      let next
      setRefreshState((prev) => {
        next = applyFetchResult(prev, { ok: false, operationalStatus: 'SESSION_REQUIRED' }, Date.now())
        return next
      })
      return Promise.resolve(next)
    }

    // Section 16/17: abort a still-in-flight request before starting a
    // new one -- every caller (mount, manual, SSE-triggered, recurring
    // cycle) goes through this same path, so none can ever create a
    // duplicate outstanding request.
    if (inFlightRef.current) {
      abortControllerRef.current?.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller
    inFlightRef.current = true
    lastKnownTokenRef.current = readAuthToken()
    // GEO33B Section 1/2: the FIRST of these marks proves this fetch
    // starts on mount, in parallel with MapLibre construction -- it never
    // waits on the map. Later (reconciliation-cycle / manual) fetches are
    // deliberately not re-marked; the mark is about initial load.
    markTiming(GEO_TIMING.OPERATIONAL_FETCH_START)

    setRefreshState((prev) => beginFetch(prev))

    const settled = fetchOperationalContext({ signal: controller.signal })
      .then((raw) => {
        inFlightRef.current = false
        if (!mountedRef.current || controller.signal.aborted) return null
        markTiming(GEO_TIMING.OPERATIONAL_FETCH_END)
        const data = normalizeOperationalContext(raw)
        let next
        setRefreshState((prev) => {
          next = applyFetchResult(prev, { ok: true, data }, Date.now())
          return next
        })
        return next
      })
      .catch((err) => {
        inFlightRef.current = false
        if (!mountedRef.current || err?.name === 'AbortError') return null
        let next
        setRefreshState((prev) => {
          next = applyFetchResult(prev, { ok: false, operationalStatus: err?.operationalStatus }, Date.now())
          return next
        })
        return next
      })

    settled.then((next) => {
      // GEO-HYBRID-LIVE-SYNC-08 Phase 5: every settled fetch is
      // responsible for keeping the single scheduler alive. A call that
      // was aborted/superseded or resolved after unmount (`next ===
      // null`) intentionally does NOT reschedule -- whichever call
      // superseded it already started its own in-flight request and will
      // reschedule once THAT one settles.
      if (!mountedRef.current || next == null) return
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      if (!shouldPoll(next.state)) return // terminal 401/403/404 -- stop, never re-poll
      if (shouldPauseForHiddenTab(currentVisibilityState())) return // went hidden while this fetch was in flight
      timeoutRef.current = setTimeout(runFetch, REFRESH_INTERVAL_MS)
    })

    return settled
  }, [])

  useEffect(() => {
    mountedRef.current = true
    runFetch() // Section 28 test 19: initial fetch occurs once, on mount; also arms the recurring cycle once it settles.

    function onVisibilityChange() {
      // Phase 6: a visibility flip must never leave a stale scheduled
      // cycle running alongside a fresh one -- always clear any pending
      // timer first, in EITHER direction.
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      if (document.visibilityState === 'visible') {
        runFetch() // exactly one immediate safe reconciliation on resume
      }
      // becoming hidden: nothing further to do -- the loop is now fully
      // stopped (no pending timer) until the next 'visible' transition.
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibilityChange)
    }

    return () => {
      mountedRef.current = false
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      abortControllerRef.current?.abort()
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibilityChange)
      }
    }
    // Intentionally mount-once: a single reconciliation scheduler for the
    // whole hook lifetime (Section 17 "only one polling timer exists").
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ...refreshState, refresh: runFetch }
}

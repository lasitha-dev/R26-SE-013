/**
 * GEO-AREA-02 Section 32/33: fetches the real My Area context whenever
 * the authorized farm, disease, selected origin, or forecast day
 * changes -- and ONLY then. Deliberately NOT a `requestAnimationFrame`
 * polling loop like `useOperationalContext.js` -- Section 32 explicitly
 * forbids a second auto-poll for this scientific/relationship request;
 * this mirrors `useSelectedOutbreakFrames.js`'s existing "refetch on
 * dependency change only" convention instead.
 *
 * Section 33 race safety: an `AbortController` per request (cancels the
 * actual in-flight fetch on rapid re-selection or unmount) PLUS a
 * monotonic request-id ref (belt-and-suspenders -- ignores a response
 * that resolves after a newer request already started, even in the
 * unlikely case the abort itself raced the resolution).
 */
import { useEffect, useRef, useState } from 'react'

import { normalizeMyAreaContext } from '../adapters/myAreaContextAdapter'
import { MY_AREA_FETCH_STATUS, fetchMyAreaContext } from '../api/myAreaApi'

export const MY_AREA_REQUEST_STATE = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
}

/**
 * `retryToken` is a plain counter the caller can bump (mirrors
 * `OutbreakMapPage.jsx`'s existing `refreshToken` pattern) to force a
 * manual re-fetch of the exact same selection -- never auto-incremented
 * by a timer.
 */
export function useMyAreaContext({ farmId, disease, originId, day, retryToken = 0 }) {
  const [state, setState] = useState({ status: MY_AREA_REQUEST_STATE.IDLE, data: null, errorStatus: null })
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!farmId || !disease) {
      setState({ status: MY_AREA_REQUEST_STATE.IDLE, data: null, errorStatus: null })
      return undefined
    }

    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const controller = new AbortController()

    setState((prev) => ({ status: MY_AREA_REQUEST_STATE.LOADING, data: prev.data, errorStatus: null }))

    fetchMyAreaContext({ farmId, disease, originId, day }, { signal: controller.signal })
      .then((raw) => {
        if (requestIdRef.current !== requestId) return // a newer selection already superseded this response
        setState({ status: MY_AREA_REQUEST_STATE.READY, data: normalizeMyAreaContext(raw), errorStatus: null })
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return
        if (requestIdRef.current !== requestId) return
        setState({ status: MY_AREA_REQUEST_STATE.ERROR, data: null, errorStatus: err?.myAreaStatus ?? MY_AREA_FETCH_STATUS.NETWORK_ERROR })
      })

    return () => {
      controller.abort()
    }
  }, [farmId, disease, originId, day, retryToken])

  return state
}

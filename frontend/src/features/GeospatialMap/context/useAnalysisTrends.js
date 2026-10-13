/**
 * GEO-ANALYSIS-02 Section 37/38: fetches the real Analysis & Trends
 * context whenever `disease`/`originId` changes -- and ONLY then. No
 * polling (Section 38 -- this is historical/model evidence, not a live
 * feed); mirrors `useMyAreaContext.js`'s exact "refetch on dependency
 * change only" convention.
 *
 * Race safety: an `AbortController` per request PLUS a monotonic
 * request-id ref, so a slow stale LSD response can never overwrite a
 * newer FMD selection, and a slow stale origin response can never
 * overwrite the current origin selection (Section 37).
 */
import { useEffect, useRef, useState } from 'react'

import { normalizeAnalysisTrendsContext } from '../adapters/analysisTrendsAdapter'
import { ANALYSIS_TRENDS_FETCH_STATUS, fetchAnalysisTrends } from '../api/analysisTrendsApi'

export const ANALYSIS_TRENDS_REQUEST_STATE = {
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
}

/**
 * `retryToken` is a plain counter the caller can bump to force a manual
 * re-fetch of the exact same selection -- never auto-incremented by a
 * timer.
 */
export function useAnalysisTrends({ disease, originId, retryToken = 0 }) {
  const [state, setState] = useState({ status: ANALYSIS_TRENDS_REQUEST_STATE.IDLE, data: null, errorStatus: null })
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!disease) {
      setState({ status: ANALYSIS_TRENDS_REQUEST_STATE.IDLE, data: null, errorStatus: null })
      return undefined
    }

    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const controller = new AbortController()

    setState((prev) => ({ status: ANALYSIS_TRENDS_REQUEST_STATE.LOADING, data: prev.data, errorStatus: null }))

    fetchAnalysisTrends({ disease, originId }, { signal: controller.signal })
      .then((raw) => {
        if (requestIdRef.current !== requestId) return // a newer selection already superseded this response
        setState({ status: ANALYSIS_TRENDS_REQUEST_STATE.READY, data: normalizeAnalysisTrendsContext(raw), errorStatus: null })
      })
      .catch((err) => {
        if (err?.name === 'AbortError') return
        if (requestIdRef.current !== requestId) return
        setState({ status: ANALYSIS_TRENDS_REQUEST_STATE.ERROR, data: null, errorStatus: err?.analysisTrendsStatus ?? ANALYSIS_TRENDS_FETCH_STATUS.NETWORK_ERROR })
      })

    return () => {
      controller.abort()
    }
  }, [disease, originId, retryToken])

  return state
}

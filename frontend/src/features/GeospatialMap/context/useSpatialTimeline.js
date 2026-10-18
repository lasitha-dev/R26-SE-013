/**
 * Fetches ONE spatial-timeline snapshot per (disease, scope, district,
 * asOf, refreshToken) -- never per animation frame. Playback only changes the
 * selected frame index in the page; this hook is not involved. Same race
 * safety as `useMyAreaContext.js`: AbortController + monotonic request id.
 */
import { useEffect, useRef, useState } from 'react'

import { readAuthToken } from '../api/operationalApi'
import { SPATIAL_TIMELINE_FETCH_STATUS, fetchSpatialTimeline } from '../api/spatialTimelineApi'

export const SPATIAL_TIMELINE_STATE = Object.freeze({
  IDLE: 'idle',
  LOADING: 'loading',
  READY: 'ready',
  ERROR: 'error',
})

// Failures that can clear on their own (backend busy/restarting, network).
const RETRYABLE = new Set([
  SPATIAL_TIMELINE_FETCH_STATUS.NETWORK_ERROR,
  SPATIAL_TIMELINE_FETCH_STATUS.SERVICE_UNAVAILABLE,
  SPATIAL_TIMELINE_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE,
])

/** `retryKey`: the page's existing sync heartbeat (no timer of its own). A
 * retryable failure is fetched again on the next heartbeat. */
export function useSpatialTimeline({ disease, scope, district = null, asOf = null, enabled = true, refreshToken = 0, retryKey = null }) {
  const [state, setState] = useState({ status: SPATIAL_TIMELINE_STATE.IDLE, data: null, errorStatus: null })
  const [retry, setRetry] = useState(0)
  const requestIdRef = useRef(0)
  const scopeKeyRef = useRef(null)
  // A different signed-in vet is a different scope: their authorised case
  // details must never be shown from the previous session's snapshot.
  const session = readAuthToken()

  useEffect(() => {
    if (retryKey == null) return
    if (state.status === SPATIAL_TIMELINE_STATE.ERROR && RETRYABLE.has(state.errorStatus)) setRetry((n) => n + 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryKey])

  useEffect(() => {
    if (!enabled || !disease || !scope) {
      scopeKeyRef.current = null
      setState({ status: SPATIAL_TIMELINE_STATE.IDLE, data: null, errorStatus: null })
      return undefined
    }
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const controller = new AbortController()
    // Only a refresh of the SAME disease/scope/district/date keeps the previous
    // snapshot visible while loading; any scope change clears it, so another
    // disease's, district's or date's zones are never shown under new labels.
    const scopeKey = JSON.stringify([disease, scope, district, asOf, session])
    const sameScope = scopeKeyRef.current === scopeKey
    scopeKeyRef.current = scopeKey
    setState((prev) => ({ status: SPATIAL_TIMELINE_STATE.LOADING, data: sameScope ? prev.data : null, errorStatus: null }))

    fetchSpatialTimeline({ disease, scope, district, asOf }, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted || requestIdRef.current !== requestId) return
        setState({ status: SPATIAL_TIMELINE_STATE.READY, data, errorStatus: null })
      })
      .catch((err) => {
        if (controller.signal.aborted || err?.name === 'AbortError' || requestIdRef.current !== requestId) return
        setState({
          status: SPATIAL_TIMELINE_STATE.ERROR,
          data: null,
          errorStatus: err?.spatialTimelineStatus ?? SPATIAL_TIMELINE_FETCH_STATUS.NETWORK_ERROR,
        })
      })
    return () => controller.abort()
  }, [disease, scope, district, asOf, session, enabled, refreshToken, retry])

  if (!enabled || !disease || !scope) return { status: SPATIAL_TIMELINE_STATE.IDLE, data: null, errorStatus: null }
  // Hide the previous selection in the render BEFORE the new effect runs.
  if (scopeKeyRef.current !== JSON.stringify([disease, scope, district, asOf, session])) {
    return { status: SPATIAL_TIMELINE_STATE.LOADING, data: null, errorStatus: null }
  }
  return state
}

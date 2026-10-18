/**
 * Countrywide LSD/FMD case records for national surveillance
 * (`GET /api/geospatial/national-cases`, read-only, vets only).
 *
 * No timer of its own: this feature allows exactly one scheduler (the
 * operational reconciliation loop in `useOperationalContext.js`). This hook
 * re-fetches on that existing heartbeat, throttled to every
 * NATIONAL_REFRESH_MS, and immediately when a live case event arrives.
 * Records merge by their stable `record_key` (a changed status simply
 * replaces the record); the previous data stays visible while refreshing.
 */
import { useEffect, useRef, useState } from 'react'

import { GEOSPATIAL_API_PREFIX } from '../api/apiConfig'
import { readAuthToken } from '../api/operationalApi'

export const NATIONAL_REFRESH_MS = 15000

export const NATIONAL_CASES_STATE = Object.freeze({ IDLE: 'idle', LOADING: 'loading', READY: 'ready', ERROR: 'error', SESSION_REQUIRED: 'session_required' })

export async function fetchNationalCases({ signal } = {}) {
  const token = readAuthToken()
  const response = await fetch(`${GEOSPATIAL_API_PREFIX}/national-cases`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal })
  if (response.status === 401 || response.status === 403) {
    const error = new Error('Session required for national case records.')
    error.nationalStatus = NATIONAL_CASES_STATE.SESSION_REQUIRED
    throw error
  }
  if (!response.ok) throw new Error(`National case records unavailable (${response.status}).`)
  const data = await response.json()
  if (!Array.isArray(data?.records)) throw new Error('National case response is invalid: records missing.')
  return data
}

/** Refetch key for `useNationalCases`: changes on a verified clinical event
 * or on a debounced realtime data change (SSE `geospatial_data_changed`,
 * which also covers deletions, withdrawals and reclassifications). */
export function nationalCasesEventKey(clinicalEvents) {
  const eventId = clinicalEvents?.lastEvent?.event_id ?? ''
  const token = clinicalEvents?.dataChangeToken ?? 0
  return eventId || token ? `${eventId}|${token}` : null
}

export function useNationalCases({ heartbeat = null, eventKey = null } = {}) {
  const [state, setState] = useState({ status: NATIONAL_CASES_STATE.IDLE, data: null, lastSyncedAt: null })
  const lastFetchRef = useRef(0)
  const inFlightRef = useRef(null)

  function runFetch() {
    inFlightRef.current?.abort()
    const controller = new AbortController()
    inFlightRef.current = controller
    lastFetchRef.current = Date.now()
    setState((prev) => ({ ...prev, status: prev.data ? prev.status : NATIONAL_CASES_STATE.LOADING }))
    fetchNationalCases({ signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return
        setState({ status: NATIONAL_CASES_STATE.READY, data, lastSyncedAt: Date.now() })
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.name === 'AbortError') return
        // A failed refresh keeps the last good records on the map (stale but
        // real, labelled by the page with their sync time); only a session
        // problem clears them.
        const status = error?.nationalStatus ?? NATIONAL_CASES_STATE.ERROR
        setState((prev) => ({ ...prev, data: status === NATIONAL_CASES_STATE.SESSION_REQUIRED ? null : prev.data, status, error: error.message }))
      })
  }

  // First load.
  useEffect(() => {
    runFetch()
    return () => inFlightRef.current?.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Existing reconciliation heartbeat, throttled.
  useEffect(() => {
    if (heartbeat == null) return
    if (Date.now() - lastFetchRef.current >= NATIONAL_REFRESH_MS) runFetch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heartbeat])

  // A genuine live case event: refresh now.
  useEffect(() => {
    if (eventKey) runFetch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventKey])

  return { ...state, refresh: runFetch }
}

/**
 * Real ERA5 reanalysis observations at the spatial timeline's own eligible
 * sources (`GET /api/geospatial/environment`). Display only: the backend states
 * `used_in_score: false` -- these values never change the frozen C0 score.
 * Fetched once per disease / district / analysis date; no timer.
 */
import { useEffect, useRef, useState } from 'react'

import { GEOSPATIAL_API_PREFIX } from '../api/apiConfig'
import { readAuthToken } from '../api/operationalApi'

export function useEnvironmentObservations({ disease, district, asOf = null, enabled = false, refreshToken = 0 }) {
  const [state, setState] = useState({ status: 'idle', data: null })
  const currentScope = JSON.stringify([disease, district, asOf])
  // A refresh of the SAME disease/district/date (realtime data change) keeps
  // the current layer visible until the new response lands; any scope change
  // clears it so another selection's results are never shown.
  const scopeKeyRef = useRef(null)
  useEffect(() => {
    if (!enabled || !disease || !district) {
      scopeKeyRef.current = null
      setState({ status: 'idle', data: null }) // never keep another district's/date's weather
      return undefined
    }
    const controller = new AbortController()
    const params = new URLSearchParams({ disease: String(disease).toLowerCase(), scope: 'district', district })
    if (asOf) params.set('as_of', asOf)
    const token = readAuthToken()
    const scopeKey = JSON.stringify([disease, district, asOf])
    const sameScope = scopeKeyRef.current === scopeKey
    scopeKeyRef.current = scopeKey
    setState((prev) => ({ status: 'loading', data: sameScope ? prev.data : null, scopeKey }))
    fetch(`${GEOSPATIAL_API_PREFIX}/environment?${params}`, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`environment ${response.status}`))))
      .then((data) => { if (!controller.signal.aborted) setState({ status: 'ready', data, scopeKey }) })
      .catch((error) => { if (!controller.signal.aborted && error?.name !== 'AbortError') setState({ status: 'error', data: null, scopeKey }) })
    return () => controller.abort()
  }, [disease, district, asOf, enabled, refreshToken])
  if (!enabled || !disease || !district) return { status: 'idle', data: null }
  // Do not expose the previous scope for even the render before effect cleanup.
  if (state.scopeKey !== currentScope) return { status: 'loading', data: null }
  return { status: state.status, data: state.data }
}

/**
 * Checkpoint 11A: thin HTTP wrapper over the locked, read-only
 * geospatial API. Never computes a scientific value -- every response
 * is returned verbatim (JSON-parsed only).
 */

import { GEOSPATIAL_API_PREFIX } from './apiConfig'

async function getJson(path, { signal } = {}) {
  const response = await fetch(`${GEOSPATIAL_API_PREFIX}${path}`, signal ? { signal } : undefined)
  if (!response.ok) {
    let detail = null
    try {
      detail = await response.json()
    } catch {
      // response body was not JSON -- fall through with detail=null,
      // never surface a raw parse error to the caller
    }
    const status = detail?.detail?.status || `HTTP_${response.status}`
    const message = detail?.detail?.message || `request to ${path} failed with status ${response.status}`
    const error = new Error(message)
    error.status = status
    error.httpStatus = response.status
    throw error
  }
  return response.json()
}

export function fetchProtocol() {
  return getJson('/protocol')
}

/**
 * LSD-UI-03: `disease` added (backward compatible -- omitted, this
 * resolves to the backend's own default, unchanged from Checkpoint
 * 1-10B.1a behavior). The disease-neutral Page 1 architecture needs to
 * ask for a disease explicitly rather than rely on an implicit default
 * once FMD becomes selectable.
 */
export function fetchOrigins({ disease, country, signal } = {}) {
  const params = new URLSearchParams()
  if (disease) params.set('disease', disease)
  if (country) params.set('country', country)
  const query = params.toString()
  return getJson(`/origins${query ? `?${query}` : ''}`, { signal })
}

/**
 * FMD-10C1: real, OBSERVED historical T0 trigger-source geometry for one
 * origin (`api/router.py::get_origin_trigger_sources`) -- disease-neutral,
 * NOT the LSD-shaped `/analysis/{id}/sources` route (that one stays
 * gated behind `DISEASE_MODEL_READINESS_10A` and still 409s for FMD).
 * Response is a GeoJSON FeatureCollection, same coordinate-order/CRS
 * convention as every other geometry response in this file -- returned
 * verbatim, never recomputed.
 */
export function fetchOriginTriggerSources(forecastOriginId, { disease, signal } = {}) {
  const params = new URLSearchParams()
  if (disease) params.set('disease', disease)
  const query = params.toString()
  return getJson(`/origins/${encodeURIComponent(forecastOriginId)}/trigger-sources${query ? `?${query}` : ''}`, { signal })
}

export function fetchAnalysisSummary(forecastOriginId) {
  return getJson(`/analysis/${encodeURIComponent(forecastOriginId)}/summary`)
}

export function fetchAnalysisCells(forecastOriginId) {
  return getJson(`/analysis/${encodeURIComponent(forecastOriginId)}/cells`)
}

export function fetchAnalysisSources(forecastOriginId, { signal } = {}) {
  return getJson(`/analysis/${encodeURIComponent(forecastOriginId)}/sources`, { signal })
}

/**
 * FMD-10C: the FMD-only scalar risk-score route
 * (`api/router.py::get_fmd_risk_analysis`) -- deliberately its own
 * endpoint, never `disease=fmd` on `/summary`/`/cells`/`/sources` above
 * (those stay 409 for FMD; see `fmdOutbreakAdapter.js`). No `disease`
 * query param: the route is implicitly FMD-scoped. Response is returned
 * verbatim, same as every other function in this file -- the caller
 * (`useFmdOriginRisk.js`) never recomputes or reclassifies `risk_score`.
 */
export function fetchFmdRiskAnalysis(forecastOriginId) {
  return getJson(`/analysis/${encodeURIComponent(forecastOriginId)}/fmd-risk`)
}

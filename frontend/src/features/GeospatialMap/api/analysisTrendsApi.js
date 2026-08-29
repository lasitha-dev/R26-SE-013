/**
 * GEO-ANALYSIS-02 Section 4/5: thin HTTP client for the Geospatial-owned
 * Page-3 endpoint (`GET /api/geospatial/analysis-trends`,
 * GEO-ANALYSIS-01/01H). Mirrors `myAreaApi.js`'s exact conventions --
 * same real bearer-token read (`readAuthToken`, imported rather than
 * reimplemented), same thin-wrapper/never-computes-a-value discipline,
 * same structured-vs-generic-error distinction technique, adapted to
 * this endpoint's own status taxonomy.
 *
 * Section 4: NO `country` parameter exists on this function's signature
 * at all, and none is ever sent -- the backend owns Sri Lanka study
 * scope (GEO-ANALYSIS-01H). No `farm_id`/`vet_id`/`vet email`/`role`/
 * `latitude`/`longitude` either -- `disease` (required) and `origin_id`
 * (optional) are the only two request parameters this endpoint accepts.
 *
 * Section 5 -- the same critical 404/422/500 distinction `myAreaApi.js`
 * already established: this route is not globally mounted on this
 * branch yet, so a generic "no route" 404 from FastAPI itself has body
 * `{"detail": "Not Found"}` (`detail` is a bare STRING). The REAL
 * Analysis & Trends route, once mounted, instead returns a STRUCTURED
 * 404 with `{"detail": {"status": "ORIGIN_NOT_FOUND"}}` (verified
 * read-only, `api/analysis_trends_router_factory.py::
 * _HTTP_STATUS_BY_ANALYSIS_TRENDS_STATUS`). The same split applies to
 * 422 (`UNSUPPORTED_DISEASE` vs FastAPI's own native query-validation
 * error, whose `detail` is an ARRAY) and 500
 * (`ANALYSIS_INTERNAL_ERROR`, always structured from this router, but a
 * genuinely unexpected exception could still bypass it with a generic
 * body -- never assumed structured).
 */

import { readAuthToken } from './operationalApi'
import { GEOSPATIAL_API_PREFIX, readStructuredErrorStatus } from './apiConfig'

export const ANALYSIS_TRENDS_FETCH_STATUS = {
  SESSION_REQUIRED: 'SESSION_REQUIRED', // 401
  FORBIDDEN: 'FORBIDDEN', // 403
  HOST_COMPOSITION_REQUIRED: 'HOST_COMPOSITION_REQUIRED', // generic 404 -- route not mounted yet
  ORIGIN_NOT_FOUND: 'ORIGIN_NOT_FOUND', // structured 404
  UNSUPPORTED_DISEASE: 'UNSUPPORTED_DISEASE', // structured 422
  INVALID_REQUEST: 'INVALID_REQUEST', // generic/native FastAPI 422 (e.g. missing disease)
  ANALYSIS_INTERNAL_ERROR: 'ANALYSIS_INTERNAL_ERROR', // structured 500
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE', // any other non-2xx / generic 500
  NETWORK_ERROR: 'NETWORK_ERROR',
}

function taggedError(message, analysisTrendsStatus) {
  const error = new Error(message)
  error.analysisTrendsStatus = analysisTrendsStatus
  return error
}

/**
 * Section 4/37: `AbortController`-aware. `disease` is REQUIRED (never
 * omitted, never defaulted client-side). `originId` is OMITTED entirely
 * from the query string when absent/null -- never sent as an empty
 * string (Section 10's "no origin auto-selection" is enforced by the
 * caller never passing one, not by this client silently defaulting).
 */
export async function fetchAnalysisTrends({ disease, originId } = {}, { signal } = {}) {
  const token = readAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  const params = new URLSearchParams()
  params.set('disease', disease)
  if (originId) params.set('origin_id', originId)

  let response
  try {
    response = await fetch(`${GEOSPATIAL_API_PREFIX}/analysis-trends?${params.toString()}`, { headers, signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw taggedError('Could not reach the Analysis & Trends endpoint.', ANALYSIS_TRENDS_FETCH_STATUS.NETWORK_ERROR)
  }

  if (response.status === 401) {
    throw taggedError('Session required.', ANALYSIS_TRENDS_FETCH_STATUS.SESSION_REQUIRED)
  }
  if (response.status === 403) {
    throw taggedError('Veterinarian access required.', ANALYSIS_TRENDS_FETCH_STATUS.FORBIDDEN)
  }

  if (response.status === 404) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'ORIGIN_NOT_FOUND') {
      throw taggedError('Selected historical/model origin is unavailable.', ANALYSIS_TRENDS_FETCH_STATUS.ORIGIN_NOT_FOUND)
    }
    throw taggedError('Analysis & Trends is not connected yet.', ANALYSIS_TRENDS_FETCH_STATUS.HOST_COMPOSITION_REQUIRED)
  }

  if (response.status === 422) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'UNSUPPORTED_DISEASE') {
      throw taggedError('Unsupported disease selection.', ANALYSIS_TRENDS_FETCH_STATUS.UNSUPPORTED_DISEASE)
    }
    throw taggedError('Invalid Analysis & Trends request.', ANALYSIS_TRENDS_FETCH_STATUS.INVALID_REQUEST)
  }

  if (response.status === 500) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'ANALYSIS_INTERNAL_ERROR') {
      throw taggedError('Analysis temporarily unavailable.', ANALYSIS_TRENDS_FETCH_STATUS.ANALYSIS_INTERNAL_ERROR)
    }
    throw taggedError('Analysis & Trends request failed.', ANALYSIS_TRENDS_FETCH_STATUS.SERVICE_UNAVAILABLE)
  }

  if (!response.ok) {
    throw taggedError('Analysis & Trends request failed.', ANALYSIS_TRENDS_FETCH_STATUS.SERVICE_UNAVAILABLE)
  }

  return response.json()
}

/**
 * GEO-AREA-02 Section 6: thin HTTP client for the Geospatial-owned Page-2
 * endpoint (`GET /api/geospatial/my-area`, GEO-AREA-01/01H). Mirrors
 * `operationalApi.js`'s exact conventions -- same real bearer-token read
 * (`readAuthToken`, imported rather than reimplemented -- Section 6: "the
 * same REAL host token convention already fixed in GEO-INT-03H"), same
 * thin-wrapper/never-computes-a-value discipline -- with its own status
 * taxonomy, because this endpoint's 404s are NOT all the same thing
 * (Section 7).
 *
 * Section 7 -- the critical 404 distinction: this route is not globally
 * mounted on this branch yet, so a generic "no route" 404 from FastAPI
 * itself has body `{"detail": "Not Found"}` (`detail` is a bare STRING).
 * The REAL My Area route, once mounted, instead returns a STRUCTURED
 * 404 with `{"detail": {"status": "ASSIGNED_AREA_NOT_FOUND"}}` or
 * `{"detail": {"status": "ORIGIN_NOT_FOUND"}}` (verified read-only,
 * `api/my_area_router_factory.py::_HTTP_STATUS_BY_MY_AREA_STATUS`). This
 * client tells them apart by checking whether `detail` is an object with
 * a recognized `.status` -- never assumes every 404 means the same thing.
 * The same structured-vs-generic split applies to 422 (backend
 * `UNSUPPORTED_DISEASE` vs FastAPI's own native query-validation error,
 * whose `detail` is an ARRAY, not an object) and 409 (`ANALYSIS_
 * UNAVAILABLE_DISEASE_MODEL_NOT_READY` vs `OPERATIONAL_DATA_UNAVAILABLE`).
 */

import { readAuthToken } from './operationalApi'
import { GEOSPATIAL_API_PREFIX, readStructuredErrorStatus } from './apiConfig'

export const MY_AREA_FETCH_STATUS = {
  SESSION_REQUIRED: 'SESSION_REQUIRED', // 401
  FORBIDDEN: 'FORBIDDEN', // 403
  HOST_COMPOSITION_REQUIRED: 'HOST_COMPOSITION_REQUIRED', // generic 404 -- route not mounted yet
  ASSIGNED_AREA_NOT_FOUND: 'ASSIGNED_AREA_NOT_FOUND', // structured 404
  ORIGIN_NOT_FOUND: 'ORIGIN_NOT_FOUND', // structured 404
  UNSUPPORTED_DISEASE: 'UNSUPPORTED_DISEASE', // structured 422
  INVALID_REQUEST: 'INVALID_REQUEST', // generic/native FastAPI 422 (e.g. day out of range, missing param)
  ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY: 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY', // structured 409
  OPERATIONAL_DATA_UNAVAILABLE: 'OPERATIONAL_DATA_UNAVAILABLE', // structured 409 (or any other non-2xx)
  NETWORK_ERROR: 'NETWORK_ERROR',
}

function taggedError(message, myAreaStatus) {
  const error = new Error(message)
  error.myAreaStatus = myAreaStatus
  return error
}

/**
 * Section 6/33: `AbortController`-aware. No `latitude`/`longitude`
 * parameter exists on this function's signature at all -- the farm's
 * coordinate is never sent by the browser (Section 6, backend Section 6
 * reaffirmed). `disease` is REQUIRED (GEO-AREA-01H Section 11) -- never
 * omitted, never defaulted client-side either.
 */
export async function fetchMyAreaContext({ farmId, disease, originId, day }, { signal } = {}) {
  const token = readAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  const params = new URLSearchParams()
  params.set('farm_id', farmId)
  params.set('disease', disease)
  if (originId) params.set('origin_id', originId)
  if (day !== undefined && day !== null) params.set('day', String(day))

  let response
  try {
    response = await fetch(`${GEOSPATIAL_API_PREFIX}/my-area?${params.toString()}`, { headers, signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw taggedError('Could not reach the My Area endpoint.', MY_AREA_FETCH_STATUS.NETWORK_ERROR)
  }

  if (response.status === 401) {
    throw taggedError('Session required.', MY_AREA_FETCH_STATUS.SESSION_REQUIRED)
  }
  if (response.status === 403) {
    throw taggedError('Veterinarian access required.', MY_AREA_FETCH_STATUS.FORBIDDEN)
  }

  if (response.status === 404) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'ASSIGNED_AREA_NOT_FOUND') {
      throw taggedError('Selected farm is not authorized or unavailable.', MY_AREA_FETCH_STATUS.ASSIGNED_AREA_NOT_FOUND)
    }
    if (structured === 'ORIGIN_NOT_FOUND') {
      throw taggedError('Selected historical/model origin is unavailable.', MY_AREA_FETCH_STATUS.ORIGIN_NOT_FOUND)
    }
    throw taggedError('My Area is not connected yet.', MY_AREA_FETCH_STATUS.HOST_COMPOSITION_REQUIRED)
  }

  if (response.status === 422) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'UNSUPPORTED_DISEASE') {
      throw taggedError('Unsupported disease selection.', MY_AREA_FETCH_STATUS.UNSUPPORTED_DISEASE)
    }
    throw taggedError('Invalid My Area request.', MY_AREA_FETCH_STATUS.INVALID_REQUEST)
  }

  if (response.status === 409) {
    const structured = await readStructuredErrorStatus(response)
    if (structured === 'ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY') {
      throw taggedError('Scientific analysis unavailable for this disease.', MY_AREA_FETCH_STATUS.ANALYSIS_UNAVAILABLE_DISEASE_MODEL_NOT_READY)
    }
    throw taggedError('Operational context unavailable.', MY_AREA_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE)
  }

  if (!response.ok) {
    throw taggedError('My Area request failed.', MY_AREA_FETCH_STATUS.OPERATIONAL_DATA_UNAVAILABLE)
  }

  return response.json()
}

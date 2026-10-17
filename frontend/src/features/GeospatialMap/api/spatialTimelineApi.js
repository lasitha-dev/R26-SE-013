/**
 * Thin client for `GET /api/geospatial/spatial-timeline` (backend
 * `api/spatial_timeline_router_factory.py`, contract `SPATIAL_TIMELINE_1.0`,
 * documented in `backend/components/geospatial_tracking/SPATIAL_TIMELINE_API.md`).
 * Same conventions as `myAreaApi.js`: the shared bearer-token reader, the
 * shared API prefix, and structured `{ detail: { status } }` errors mapped to
 * explicit fetch statuses. It never computes a value -- the response is
 * returned exactly as the backend produced it.
 */

import { GEOSPATIAL_API_PREFIX, readStructuredErrorStatus } from './apiConfig'
import { readAuthToken } from './operationalApi'

export const SPATIAL_TIMELINE_FETCH_STATUS = Object.freeze({
  SESSION_REQUIRED: 'SESSION_REQUIRED', // 401
  FORBIDDEN: 'FORBIDDEN', // 403 (non-vet)
  DISTRICT_NOT_AUTHORISED: 'DISTRICT_NOT_AUTHORISED', // 403
  DISTRICT_NOT_FOUND: 'DISTRICT_NOT_FOUND', // 404
  NO_AUTHORISED_DISTRICT: 'NO_AUTHORISED_DISTRICT', // 409
  DISTRICT_REQUIRED: 'DISTRICT_REQUIRED', // 422
  UNSUPPORTED_DISEASE: 'UNSUPPORTED_DISEASE', // 422
  INVALID_REQUEST: 'INVALID_REQUEST', // other 422 / generic 404
  OPERATIONAL_DATA_UNAVAILABLE: 'OPERATIONAL_DATA_UNAVAILABLE', // 503
  SERVICE_UNAVAILABLE: 'SERVICE_UNAVAILABLE', // other non-2xx
  NETWORK_ERROR: 'NETWORK_ERROR',
  INVALID_RESPONSE: 'INVALID_RESPONSE', // 200 whose body is not a timeline snapshot
})

/** Structural check only (never repairs or fills): an object with a status;
 * a computed (OK) snapshot must carry its frames array, and cells / risk
 * zones, when present, must be an array / FeatureCollection. */
export function isSpatialTimelineShape(data) {
  if (!data || typeof data !== 'object' || typeof data.status !== 'string') return false
  if (data.cells !== undefined && !Array.isArray(data.cells)) return false
  if (data.risk_zones != null && !Array.isArray(data.risk_zones.features)) return false
  return data.status !== 'OK' || Array.isArray(data.frames)
}

export const SPATIAL_TIMELINE_HORIZON_DAYS = 14

const STRUCTURED_STATUSES = new Set(Object.values(SPATIAL_TIMELINE_FETCH_STATUS))

function taggedError(message, status) {
  const error = new Error(message)
  error.spatialTimelineStatus = status
  return error
}

/** `scope` is 'national' or 'district'; `district` is only sent for district
 * scope (omitted -> the backend uses the vet's own registered district).
 * `asOf` is omitted by default so the backend uses today (Asia/Colombo). */
export async function fetchSpatialTimeline({ disease, scope, district = null, asOf = null, horizonDays = SPATIAL_TIMELINE_HORIZON_DAYS } = {}, { signal } = {}) {
  const token = readAuthToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}

  const params = new URLSearchParams()
  params.set('disease', String(disease).toLowerCase())
  params.set('scope', scope)
  if (scope === 'district' && district) params.set('district', district)
  if (asOf) params.set('as_of', asOf)
  params.set('horizon_days', String(horizonDays))

  let response
  try {
    response = await fetch(`${GEOSPATIAL_API_PREFIX}/spatial-timeline?${params.toString()}`, { headers, signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw taggedError('Could not reach the spatial timeline endpoint.', SPATIAL_TIMELINE_FETCH_STATUS.NETWORK_ERROR)
  }

  if (response.ok) {
    let data
    try {
      data = await response.json()
    } catch {
      throw taggedError('Spatial timeline response could not be read.', SPATIAL_TIMELINE_FETCH_STATUS.INVALID_RESPONSE)
    }
    if (!isSpatialTimelineShape(data)) throw taggedError('Spatial timeline response is not a timeline snapshot.', SPATIAL_TIMELINE_FETCH_STATUS.INVALID_RESPONSE)
    return data
  }
  if (response.status === 401) throw taggedError('Session required.', SPATIAL_TIMELINE_FETCH_STATUS.SESSION_REQUIRED)

  const structured = await readStructuredErrorStatus(response)
  if (structured && STRUCTURED_STATUSES.has(structured)) {
    throw taggedError(`Spatial timeline unavailable: ${structured}`, structured)
  }
  if (response.status === 403) throw taggedError('Veterinarian access required.', SPATIAL_TIMELINE_FETCH_STATUS.FORBIDDEN)
  if (response.status === 404 || response.status === 422) {
    throw taggedError('Invalid spatial timeline request.', SPATIAL_TIMELINE_FETCH_STATUS.INVALID_REQUEST)
  }
  throw taggedError('Spatial timeline request failed.', SPATIAL_TIMELINE_FETCH_STATUS.SERVICE_UNAVAILABLE)
}

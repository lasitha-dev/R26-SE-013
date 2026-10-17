/**
 * My Area: where the authorised-district context stands (pure). The page
 * shows counts only when it is READY -- never a successful-looking 0 while
 * the district, its boundary or the operational context is still unknown.
 */
import { DISTRICT_GEOMETRY_STATUS } from '../context/useDistrictGeometry'
import { OPERATIONAL_STATE } from '../context/operationalRefreshReducer'

/** Where the authorised-district context stands. Counts are only shown once
 * it is READY -- never a successful-looking 0 while it is still unknown. */
export const AREA_CONTEXT_STATE = Object.freeze({
  LOADING: 'LOADING', // operational context or district boundary still loading
  FAILED: 'FAILED', // operational context request failed
  UNRESOLVED: 'UNRESOLVED', // context loaded, but no authorised district
  BOUNDARY_FAILED: 'BOUNDARY_FAILED', // district known, boundary not available
  READY: 'READY',
})

export const OPERATIONAL_FAILURE_TEXT = {
  [OPERATIONAL_STATE.SESSION_REQUIRED]: 'Sign-in required: your session is missing or expired, so your authorised district could not be loaded.',
  [OPERATIONAL_STATE.FORBIDDEN]: 'This account is not a veterinarian account, so no authorised district is available.',
  [OPERATIONAL_STATE.HOST_COMPOSITION_REQUIRED]: 'The operational context service is not connected on this server.',
  [OPERATIONAL_STATE.OPERATIONAL_UNAVAILABLE]: 'Operational data is unavailable right now, so your authorised district could not be loaded.',
  [OPERATIONAL_STATE.ERROR]: 'Could not load your authorised district (request failed).',
}

export function resolveAreaContextState({ operationalState, hasOperationalData, district, districtGeometryStatus, hasDistrictFeature }) {
  if (district) {
    if (districtGeometryStatus === DISTRICT_GEOMETRY_STATUS.ERROR || (districtGeometryStatus === DISTRICT_GEOMETRY_STATUS.READY && !hasDistrictFeature)) return AREA_CONTEXT_STATE.BOUNDARY_FAILED
    return districtGeometryStatus === DISTRICT_GEOMETRY_STATUS.READY ? AREA_CONTEXT_STATE.READY : AREA_CONTEXT_STATE.LOADING
  }
  if (hasOperationalData) return AREA_CONTEXT_STATE.UNRESOLVED
  return OPERATIONAL_FAILURE_TEXT[operationalState] ? AREA_CONTEXT_STATE.FAILED : AREA_CONTEXT_STATE.LOADING
}

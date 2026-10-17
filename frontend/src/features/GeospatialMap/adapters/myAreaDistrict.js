import { normalizeDistrictDisplayName } from './districtGeometry'

/**
 * Resolves the district My Area focuses on from the authenticated vet's
 * own operational context (`GET /operational-context`). Never a fixed
 * district and never a guess:
 *  - a vet whose profile names a district uses that district;
 *  - a national (`ALL_DISTRICTS`) account uses the selected assigned
 *    farm's district, or asks for a farm to be selected;
 *  - otherwise the page shows an explicit unresolved state.
 */
export const MY_AREA_DISTRICT_STATUS = Object.freeze({
  LOADING: 'LOADING',
  RESOLVED: 'RESOLVED',
  SELECT_FARM_FOR_NATIONAL_SCOPE: 'SELECT_FARM_FOR_NATIONAL_SCOPE',
  NO_REGISTERED_DISTRICT: 'NO_REGISTERED_DISTRICT',
  DISTRICT_DATA_UNAVAILABLE: 'DISTRICT_DATA_UNAVAILABLE',
})

export const MY_AREA_DISTRICT_SOURCE = Object.freeze({
  VET_PROFILE: 'VET_PROFILE',
  SELECTED_FARM: 'SELECTED_FARM',
})

const ALL_DISTRICTS = 'all_districts'

function unresolved(status) {
  return { status, district: null, source: null }
}

function isNationalScope(rawDistrict) {
  return typeof rawDistrict === 'string' && rawDistrict.trim().toLowerCase() === ALL_DISTRICTS
}

export function resolveMyAreaDistrict({ operationalData = null, selectedFarmId = null } = {}) {
  if (!operationalData) return unresolved(MY_AREA_DISTRICT_STATUS.LOADING)

  const rawDistrict = operationalData.vetDistrict
  if (rawDistrict && !isNationalScope(rawDistrict)) {
    const district = normalizeDistrictDisplayName(rawDistrict)
    if (district) return { status: MY_AREA_DISTRICT_STATUS.RESOLVED, district, source: MY_AREA_DISTRICT_SOURCE.VET_PROFILE }
  }

  if (isNationalScope(rawDistrict)) {
    const farms = [...(operationalData.farms ?? []), ...(operationalData.surveillanceFarms ?? [])]
    const selectedFarm = selectedFarmId ? farms.find((farm) => farm?.farmId === selectedFarmId) : null
    const district = normalizeDistrictDisplayName(selectedFarm?.locationDistrict)
    if (district) return { status: MY_AREA_DISTRICT_STATUS.RESOLVED, district, source: MY_AREA_DISTRICT_SOURCE.SELECTED_FARM }
    return unresolved(MY_AREA_DISTRICT_STATUS.SELECT_FARM_FOR_NATIONAL_SCOPE)
  }

  if (operationalData.surveillanceStatus === 'DISTRICT_DATA_UNAVAILABLE') {
    return unresolved(MY_AREA_DISTRICT_STATUS.DISTRICT_DATA_UNAVAILABLE)
  }
  return unresolved(MY_AREA_DISTRICT_STATUS.NO_REGISTERED_DISTRICT)
}

/** The real verified cases My Area may anchor on: the vet's district
 * surveillance cases plus their own assigned-farm cases (and any the
 * `/my-area` response returned), one per case id, for the selected disease. */
export function collectMyAreaCaseContexts({ operationalData = null, myAreaContexts = [], disease = null } = {}) {
  if (!disease) return []
  const byCaseId = new Map()
  const all = [
    ...(operationalData?.surveillanceContexts ?? []),
    ...(operationalData?.clinicalContexts ?? []),
    ...(Array.isArray(myAreaContexts) ? myAreaContexts : []),
  ]
  for (const context of all) {
    if (!context?.caseId || context.disease !== disease || byCaseId.has(context.caseId)) continue
    byCaseId.set(context.caseId, context)
  }
  return [...byCaseId.values()]
}

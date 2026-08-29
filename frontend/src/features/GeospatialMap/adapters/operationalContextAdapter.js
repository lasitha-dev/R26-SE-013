/**
 * GEO-INT-03 Section 25: normalizes the raw
 * `GET /api/geospatial/operational-context` response (GEO-INT-02's
 * `dataclasses.asdict(OperationalGeospatialContext)`) into the small,
 * defensive shape this feature's map/UI layer consumes. Mirrors
 * `lsdOutbreakAdapter.js`'s validation discipline: malformed records are
 * DROPPED, never repaired or guessed. An unknown disease is excluded,
 * never defaulted to LSD (Section 25's explicit rule) -- the backend
 * itself already applies this rule (`disease_normalization.py`), this is
 * defense in depth, not a second source of truth. A farm with
 * `LOCATION_REQUIRED` never produces a marker (Section 26) -- no
 * coordinate is ever invented here.
 */

const KNOWN_DISEASES = new Set(['LSD', 'FMD'])

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Section 25/26: keeps every farm record (even an invalid-location one,
 * for the honest "N farms need geolocation" count), but only a `VALID`
 * one carries usable coordinates. */
function normalizeFarm(rawFarm) {
  if (!rawFarm || typeof rawFarm.farm_id !== 'string' || !rawFarm.farm_id) return null
  const hasValidLocation =
    rawFarm.location_status === 'VALID' && isFiniteNumber(rawFarm.latitude) && isFiniteNumber(rawFarm.longitude)
  return {
    farmId: rawFarm.farm_id,
    latitude: hasValidLocation ? rawFarm.latitude : null,
    longitude: hasValidLocation ? rawFarm.longitude : null,
    locationStatus: hasValidLocation ? 'VALID' : 'LOCATION_REQUIRED',
    locationDistrict: typeof rawFarm.location_district === 'string' ? rawFarm.location_district : null,
  }
}

/** Section 25: drops a clinical-context record unless its disease is a
 * KNOWN value AND its farm resolved to a valid, mapped location AND its
 * semantic class is exactly the approved one -- never defaults an
 * unrecognized disease to LSD/FMD, never renders a marker with no real
 * coordinate. */
function normalizeClinicalContext(rawContext, farmsById) {
  if (!rawContext || typeof rawContext.case_id !== 'string' || !rawContext.case_id) return null
  if (!KNOWN_DISEASES.has(rawContext.disease)) return null
  if (rawContext.semantic_class !== 'VERIFIED_CLINICAL_CONTEXT') return null

  const farm = farmsById.get(rawContext.farm_id)
  if (!farm || farm.locationStatus !== 'VALID') return null

  return {
    caseId: rawContext.case_id,
    farmId: rawContext.farm_id,
    disease: rawContext.disease,
    semanticClass: rawContext.semantic_class,
    verificationTime: typeof rawContext.verification_time === 'string' ? rawContext.verification_time : null,
    timestampBasis: rawContext.timestamp_basis === 'VERIFICATION_TIME' ? rawContext.timestamp_basis : null,
    latitude: farm.latitude,
    longitude: farm.longitude,
    locationDistrict: farm.locationDistrict,
  }
}

/**
 * Section 25: deterministic ordering (`caseId`, stable string sort) --
 * never Mongo/host natural order, never dependent on array position.
 */
export function normalizeOperationalContext(raw) {
  const status = typeof raw?.status === 'string' ? raw.status : 'OPERATIONAL_DATA_UNAVAILABLE'
  const rawFarms = Array.isArray(raw?.farms) ? raw.farms : []
  const rawContexts = Array.isArray(raw?.clinical_contexts) ? raw.clinical_contexts : []

  const farms = rawFarms.map(normalizeFarm).filter(Boolean)
  const farmsById = new Map(farms.map((f) => [f.farmId, f]))

  const clinicalContexts = rawContexts
    .map((c) => normalizeClinicalContext(c, farmsById))
    .filter(Boolean)
    .sort((a, b) => (a.caseId < b.caseId ? -1 : a.caseId > b.caseId ? 1 : 0))

  const locationRequiredFarmCount = farms.filter((f) => f.locationStatus !== 'VALID').length

  return {
    status,
    vetRole: typeof raw?.vet?.role === 'string' ? raw.vet.role : null,
    farms,
    clinicalContexts,
    locationRequiredFarmCount,
    generatedAt: typeof raw?.generated_at === 'string' ? raw.generated_at : null,
  }
}

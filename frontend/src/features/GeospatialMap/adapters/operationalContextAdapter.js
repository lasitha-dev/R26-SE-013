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

import { normalizeDistrictDisplayName } from './districtGeometry'

const KNOWN_DISEASES = new Set(['LSD', 'FMD'])

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Section 25/26: keeps every farm record (even an invalid-location one,
 * for the honest "N farms need geolocation" count), but only a `VALID`
 * one carries usable coordinates.
 *
 * GEO29A Phase 5/6: `personally_assigned` (default `true`, matching the
 * backend's own default -- see `OperationalFarm.personally_assigned`)
 * distinguishes a farm the vet directly administers from one that only
 * qualifies through district-wide surveillance; the frontend popup uses
 * this to decide whether a richer farm label is shown. */
function normalizeFarm(rawFarm) {
  if (!rawFarm || typeof rawFarm.farm_id !== 'string' || !rawFarm.farm_id) return null
  const hasValidLocation =
    rawFarm.location_status === 'VALID' && isFiniteNumber(rawFarm.latitude) && Math.abs(rawFarm.latitude) <= 90 && isFiniteNumber(rawFarm.longitude) && Math.abs(rawFarm.longitude) <= 180
  return {
    farmId: rawFarm.farm_id,
    latitude: hasValidLocation ? rawFarm.latitude : null,
    longitude: hasValidLocation ? rawFarm.longitude : null,
    locationStatus: hasValidLocation ? 'VALID' : 'LOCATION_REQUIRED',
    // GEO-MY-AREA-FINAL-PASS: same real messy raw format as
    // `myAreaContextAdapter.js::normalizeArea` (verified from the
    // backend's own `district_matches` docstring) -- normalized here too
    // so a farm's dropdown/label/popup text never shows raw coordinates.
    locationDistrict: normalizeDistrictDisplayName(rawFarm.location_district),
    personallyAssigned: rawFarm.personally_assigned !== false,
    totalAnimals: rawFarm.personally_assigned !== false && Number.isFinite(rawFarm.total_animals) ? rawFarm.total_animals : null,
  }
}

/** Section 25: drops a clinical-context record unless its disease is a
 * KNOWN value AND its farm resolved to a valid, mapped location AND its
 * semantic class is exactly the approved one -- never defaults an
 * unrecognized disease to LSD/FMD, never renders a marker with no real
 * coordinate. */
function normalizeClinicalContext(rawContext, farmsById, includeUnmapped = false) {
  if (!rawContext || typeof rawContext.case_id !== 'string' || !rawContext.case_id) return null
  if (!KNOWN_DISEASES.has(rawContext.disease)) return null
  if (rawContext.semantic_class !== 'VERIFIED_CLINICAL_CONTEXT') return null

  const farm = farmsById.get(rawContext.farm_id)
  if (!farm || (!includeUnmapped && farm.locationStatus !== 'VALID')) return null

  return {
    caseId: rawContext.case_id,
    farmId: rawContext.farm_id,
    disease: rawContext.disease,
    semanticClass: rawContext.semantic_class,
    verificationTime: typeof rawContext.verification_time === 'string' ? rawContext.verification_time : null,
    reportedAt: typeof rawContext.case_creation_time === 'string' ? rawContext.case_creation_time : null,
    locationStatus: farm.locationStatus,
    timestampBasis: rawContext.timestamp_basis === 'VERIFICATION_TIME' ? rawContext.timestamp_basis : null,
    latitude: farm.latitude,
    longitude: farm.longitude,
    locationDistrict: farm.locationDistrict,
    personallyAssigned: farm.personallyAssigned,
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

  // GEO29A Phase 4/6: the additive registered-district surveillance
  // scope -- a real, independently-populated broader set (may include
  // the same farms as `farms` above, tagged `personallyAssigned: true`
  // there too), parsed with the exact same defensive rules as the
  // assigned-farm fields (unknown disease dropped, invalid location
  // dropped, never repaired/guessed).
  const rawSurveillanceFarms = Array.isArray(raw?.surveillance_farms) ? raw.surveillance_farms : []
  const rawSurveillanceContexts = Array.isArray(raw?.surveillance_contexts) ? raw.surveillance_contexts : []
  const surveillanceFarms = rawSurveillanceFarms.map(normalizeFarm).filter(Boolean)
  const surveillanceFarmsById = new Map(surveillanceFarms.map((f) => [f.farmId, f]))
  const surveillanceContexts = rawSurveillanceContexts
    .map((c) => normalizeClinicalContext(c, surveillanceFarmsById))
    .filter(Boolean)
    .sort((a, b) => (a.caseId < b.caseId ? -1 : a.caseId > b.caseId ? 1 : 0))

  return {
    status,
    vetRole: typeof raw?.vet?.role === 'string' ? raw.vet.role : null,
    farms,
    clinicalContexts,
    // List/count population is independent of whether the farm can be mapped.
    clinicalRecords: rawContexts.map((c) => normalizeClinicalContext(c, farmsById, true)).filter(Boolean),
    locationRequiredFarmCount,
    generatedAt: typeof raw?.generated_at === 'string' ? raw.generated_at : null,
    vetDistrict: typeof raw?.vet_district === 'string' && raw.vet_district.trim() ? raw.vet_district : null,
    surveillanceFarms,
    surveillanceContexts,
    surveillanceRecords: rawSurveillanceContexts.map((c) => normalizeClinicalContext(c, surveillanceFarmsById, true)).filter(Boolean),
    surveillanceStatus: typeof raw?.surveillance_status === 'string' ? raw.surveillance_status : null,
  }
}

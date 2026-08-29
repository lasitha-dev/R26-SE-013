/**
 * GEO-AREA-02 Section 36: normalizes the raw `GET /api/geospatial/my-area`
 * response (GEO-AREA-01/01H's `dataclasses.asdict(MyAreaContext)`) into
 * the shape this page's components consume. Mirrors
 * `operationalContextAdapter.js`'s validation discipline: malformed
 * records are DROPPED, never repaired or guessed; an unknown disease is
 * excluded, never defaulted to LSD. `distance_basis`/`anchor_basis`/`t0`
 * are preserved VERBATIM under their own names -- never renamed into a
 * shorter, more ambiguous generic field the backend deliberately removed
 * (GEO-AREA-01H's whole point).
 */

const KNOWN_DISEASES = new Set(['LSD', 'FMD'])

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function normalizeArea(rawArea) {
  if (!rawArea || typeof rawArea.farm_id !== 'string' || !rawArea.farm_id) return null
  const hasValidLocation =
    rawArea.location_status === 'VALID' && isFiniteNumber(rawArea.latitude) && isFiniteNumber(rawArea.longitude)
  return {
    farmId: rawArea.farm_id,
    latitude: hasValidLocation ? rawArea.latitude : null,
    longitude: hasValidLocation ? rawArea.longitude : null,
    locationStatus: hasValidLocation ? 'VALID' : 'LOCATION_REQUIRED',
    locationDistrict: typeof rawArea.location_district === 'string' ? rawArea.location_district : null,
    totalAnimals: typeof rawArea.total_animals === 'number' ? rawArea.total_animals : null,
  }
}

function normalizeRelevantOrigin(raw) {
  if (!raw || typeof raw.origin_id !== 'string' || !raw.origin_id) return null
  if (!KNOWN_DISEASES.has(raw.disease)) return null
  if (!isFiniteNumber(raw.distance_from_area_km)) return null
  return {
    originId: raw.origin_id,
    disease: raw.disease,
    t0: typeof raw.t0 === 'string' ? raw.t0 : null,
    distanceFromAreaKm: raw.distance_from_area_km,
    // Preserved verbatim -- Section 10/36: never collapsed into a bare
    // "distance" with the basis dropped.
    distanceBasis: typeof raw.distance_basis === 'string' ? raw.distance_basis : null,
    scientificMode: typeof raw.scientific_mode === 'string' ? raw.scientific_mode : null,
  }
}

function normalizeNearestHistoricalSource(raw) {
  if (!raw || typeof raw.source_id !== 'string' || !raw.source_id || !isFiniteNumber(raw.distance_from_area_km)) return null
  return {
    sourceId: raw.source_id,
    distanceFromAreaKm: raw.distance_from_area_km,
    availabilityQuality: typeof raw.availability_quality === 'string' ? raw.availability_quality : null,
    gpsQuality: typeof raw.gps_quality === 'string' ? raw.gps_quality : null,
  }
}

function normalizeRelativeSpatialScore(raw) {
  if (!raw) return null
  return {
    // Section 21/38: null stays null -- never coerced to 0.
    value: isFiniteNumber(raw.value) ? raw.value : null,
    label: typeof raw.label === 'string' ? raw.label : 'Relative Spatial Score',
    temporalBasis: typeof raw.temporal_basis === 'string' ? raw.temporal_basis : null,
    status: typeof raw.status === 'string' ? raw.status : null,
    scientificCellId: typeof raw.scientific_cell_id === 'string' ? raw.scientific_cell_id : null,
  }
}

function normalizeNominalReachContext(raw) {
  if (!raw) return null
  return {
    day: Number.isInteger(raw.day) ? raw.day : null,
    forecastDate: typeof raw.forecast_date === 'string' ? raw.forecast_date : null,
    basis: typeof raw.basis === 'string' ? raw.basis : null,
    nominalReachKm: isFiniteNumber(raw.nominal_reach_km) ? raw.nominal_reach_km : null,
    // Section 20/38: preserved verbatim -- always NOT_APPLICABLE under
    // the current backend contract, never recomputed here.
    relation: typeof raw.relation === 'string' ? raw.relation : 'NOT_APPLICABLE',
    anchorBasis: typeof raw.anchor_basis === 'string' ? raw.anchor_basis : null,
    disclaimer: typeof raw.disclaimer === 'string' ? raw.disclaimer : null,
  }
}

function normalizeSelectedOriginContext(raw) {
  if (!raw || typeof raw.origin_id !== 'string' || !raw.origin_id) return null
  return {
    originId: raw.origin_id,
    disease: KNOWN_DISEASES.has(raw.disease) ? raw.disease : null,
    forecastDay: Number.isInteger(raw.forecast_day) ? raw.forecast_day : null,
    forecastDate: typeof raw.forecast_date === 'string' ? raw.forecast_date : null,
    t0: typeof raw.t0 === 'string' ? raw.t0 : null,
    nearestHistoricalSource: normalizeNearestHistoricalSource(raw.nearest_historical_source),
    relativeSpatialScore: normalizeRelativeSpatialScore(raw.relative_spatial_score),
    nominalReachContext: normalizeNominalReachContext(raw.nominal_reach_context),
  }
}

function normalizeClinicalContext(raw) {
  if (!raw || typeof raw.case_id !== 'string' || !raw.case_id) return null
  if (!KNOWN_DISEASES.has(raw.disease)) return null
  if (raw.semantic_class !== 'VERIFIED_CLINICAL_CONTEXT') return null
  return {
    caseId: raw.case_id,
    farmId: typeof raw.farm_id === 'string' ? raw.farm_id : null,
    disease: raw.disease,
    semanticClass: raw.semantic_class,
    verificationTime: typeof raw.verification_time === 'string' ? raw.verification_time : null,
    timestampBasis: raw.timestamp_basis === 'VERIFICATION_TIME' ? raw.timestamp_basis : null,
  }
}

/** Section 36: deterministic ordering -- origins by distance then id
 * (mirrors the backend's own tie-break), clinical contexts by caseId. */
export function normalizeMyAreaContext(raw) {
  const status = typeof raw?.status === 'string' ? raw.status : 'OPERATIONAL_DATA_UNAVAILABLE'
  const disease = KNOWN_DISEASES.has(raw?.disease) ? raw.disease : null
  const area = normalizeArea(raw?.area)

  const relevantOrigins = (Array.isArray(raw?.relevant_origins) ? raw.relevant_origins : [])
    .map(normalizeRelevantOrigin)
    .filter(Boolean)
    .sort((a, b) => a.distanceFromAreaKm - b.distanceFromAreaKm || (a.originId < b.originId ? -1 : a.originId > b.originId ? 1 : 0))

  const selectedOriginContext = normalizeSelectedOriginContext(raw?.selected_origin_context)

  const verifiedClinicalContexts = (Array.isArray(raw?.verified_clinical_contexts) ? raw.verified_clinical_contexts : [])
    .map(normalizeClinicalContext)
    .filter(Boolean)
    .sort((a, b) => (a.caseId < b.caseId ? -1 : a.caseId > b.caseId ? 1 : 0))

  return {
    status,
    disease,
    area,
    relevantOrigins,
    selectedOriginContext,
    verifiedClinicalContexts,
    generatedAt: typeof raw?.generated_at === 'string' ? raw.generated_at : null,
  }
}
